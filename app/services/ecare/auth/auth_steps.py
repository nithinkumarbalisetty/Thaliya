"""
Authentication Steps Handler
Manages the multi-step authentication workflow
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class AuthStepsHandler:
    """Handles multi-step authentication workflow"""
    
    def __init__(self, auth_handler):
        self.auth_handler = auth_handler
    
    async def handle_step_1(self, user_query: str, session_token: str) -> Dict[str, Any]:
        """Handle first name and last name collection using guest_auth_temp table"""
        print(f"🚨 DEBUG: handle_auth_step_1 called with query='{user_query}', session='{session_token}'")
        
        # Test database connection first
        try:
            from app.core.database import db
            test_result = await db.fetch("SELECT COUNT(*) as count FROM guest_auth_temp")
            print(f"DEBUG: Current records in guest_auth_temp: {test_result[0]['count'] if test_result else 'QUERY FAILED'}")
        except Exception as e:
            print(f"ERROR: Database connection issue: {e}")
        
        names = self.auth_handler.parsers.parse_names(user_query)
        
        if not names:
            bot_response = "Please provide your first name and last name (e.g., 'John Smith')"
            await self.auth_handler.session_manager.store_chat_history(
                session_token, user_query, bot_response, "awaiting_auth_details", "auth_validation", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "awaiting_auth_details",
                "output": bot_response,
                "session_token": session_token,
                "validation_error": True
            }
        
        # Store names in guest_auth_temp table
        await self.auth_handler.temp_storage.create_auth_temp_record(session_token, names)
        
        await self.auth_handler.session_manager.update_session_status(session_token, "awaiting_dob_email")
        
        bot_response = f"Thanks {names['first_name']}! Now please provide your date of birth (MM/DD/YYYY) and phone number for verification."
        await self.auth_handler.session_manager.store_chat_history(
            session_token, "[Name provided]", bot_response, "awaiting_dob_email", "auth_step1", is_sensitive=True
        )
        
        return {
            "success": True,
            "intent": "awaiting_dob_email",
            "output": bot_response,
            "session_token": session_token,
            "collected_data": {"first_name": names["first_name"], "last_name": names["last_name"]}
        }

    async def handle_step_2(self, user_query: str, session_token: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle DOB and phone collection - Phone is required for healthcare"""
        
        # Get auth temp data from the guest_auth_temp table
        auth_temp_data = await self.auth_handler.temp_storage.get_auth_temp_data(session_token)
        
        if not auth_temp_data or not auth_temp_data.get("first_name") or not auth_temp_data.get("last_name"):
            # Fallback: restart auth process
            bot_response = "It looks like we need to start from the beginning. Please provide your first name and last name (e.g., 'John Smith')"
            
            # Reset to step 1
            await self.auth_handler.session_manager.update_session_status(session_token, "awaiting_auth_details")
            await self.auth_handler.session_manager.store_chat_history(
                session_token, user_query, bot_response, "awaiting_auth_details", "auth_reset", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "awaiting_auth_details",
                "output": bot_response,
                "session_token": session_token,
                "reset_to_step1": True
            }
        
        auth_data = self.auth_handler.parsers.parse_dob_phone(user_query)
        
        print(f"DEBUG: Parsed auth data from user input: {auth_data}")
        print(f"DEBUG: Existing auth temp data: first_name={auth_temp_data.get('first_name')}, last_name={auth_temp_data.get('last_name')}")
        
        if not auth_data or not auth_data.get("phone_number"):
            bot_response = f"Hi {auth_temp_data['first_name']}, please provide your date of birth (MM/DD/YYYY) and phone number (e.g., '01/15/1990 (555) 123-4567'). Phone number is required for appointment reminders and emergency contact."
            await self.auth_handler.session_manager.store_chat_history(
                session_token, user_query, bot_response, "awaiting_dob_email", "auth_validation", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "awaiting_dob_email",
                "output": bot_response,
                "session_token": session_token,
                "validation_error": True
            }
        
        # Update auth temp record with DOB and contact info from CURRENT user input
        await self.auth_handler.temp_storage.update_auth_temp_with_dob(session_token, auth_data)
        
        # Phone is required, email is optional in this phase
        phone_number = auth_data.get("phone_number")
        email = auth_data.get("email")  # Optional
        
        print(f"DEBUG: Checking if user exists with: first_name={auth_temp_data['first_name']}, last_name={auth_temp_data['last_name']}, dob={auth_data['dob']}, phone={phone_number}, email={email}")
        
        # Option A: Check if user exists without creating - use phone as primary identifier
        existing_user_check = await self.auth_handler.db_ops.find_existing_user(
            auth_temp_data["first_name"],
            auth_temp_data["last_name"], 
            auth_data["dob"],  # Use PARSED DOB from current input
            email=email,  # Optional email
            phone=phone_number  # Required phone
        )
        
        print(f"DEBUG: Existing user check result: {existing_user_check}")
        
        # Determine user_id for OTP generation (if user exists)
        user_id = existing_user_check.get("user_id") if existing_user_check.get("exists") else None
        is_new_user = not existing_user_check.get("exists", False)
        
        print(f"DEBUG: About to generate OTP for user_id={user_id}, phone={phone_number}, is_new_user={is_new_user}")
        
        otp_result = await self.auth_handler.otp_ops.generate_and_store_otp_distributed(
            session_token, 
            user_id,  # None for new users, existing user_id for returning users
            phone_number  # Always use phone for OTP in healthcare
        )
        
        print(f"DEBUG: OTP generation result: {otp_result}")
        
        if not otp_result["success"]:
            return await self._handle_otp_generation_error(session_token, otp_result)
        
        print(f"DEBUG: OTP for {phone_number}: {otp_result['otp_code']}")
        
        # Store contact method and user existence info in auth temp (NOT user_id yet)
        await self.auth_handler.temp_storage.update_auth_temp_with_contact_info(
            session_token, phone_number, is_new_user, user_id
        )
        
        await self.auth_handler.session_manager.update_session_status(session_token, "awaiting_otp")
        
        # Send OTP via external service (distributed) - always to phone
        await self.auth_handler.otp_ops.send_otp_via_service(phone_number, otp_result["otp_code"], session_token)
        
        # Customize message based on whether user exists or is new
        
        if is_new_user:
            bot_response = (
                f"Great! We'll create your profile after verification. A 6-digit verification code has been sent to {phone_number}.\n"
                f"⚠️ Important: You have only 1 attempt to enter the correct code.\n"
                f"Please enter the code carefully to complete your registration and authentication."
            )
        else:
            bot_response = (
                f"Welcome back! We've sent a 6-digit verification code to {phone_number}.\n"
                f"⚠️ Important: You have only 1 attempt to enter the correct code.\n"
                f"Please enter the code carefully to complete authentication."
            )
        
        await self.auth_handler.session_manager.store_chat_history(
            session_token, "[DOB/Phone provided]", bot_response, "awaiting_otp", "auth_step2", is_sensitive=True
        )
        
        return {
            "success": True,
            "intent": "awaiting_otp",
            "output": bot_response,
            "session_token": session_token,
            "user_will_be_created": is_new_user,
            "pending_user_id": user_id  # None for new users, existing ID for returning users
        }

    async def handle_otp_verification(self, user_query: str, session_token: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle OTP verification with single attempt and recovery options"""
        # Get auth temp data from guest_auth_temp table
        auth_temp_data = await self.auth_handler.temp_storage.get_auth_temp_data(session_token)
        
        # Check if we have the required session data - we need at least basic auth info
        # Note: user_id can be None for new users in Option A flow
        if not auth_temp_data or not auth_temp_data.get("first_name") or not auth_temp_data.get("last_name"):
            # Missing required data, restart authentication
            return await self._handle_auth_restart(session_token)
        
        otp_input = user_query.strip().lower()
        
        # Check if user wants to request new OTP or restart
        if otp_input in ['new otp', 'resend', 'resend otp', 'new code', 'resend code']:
            return await self._handle_otp_resend_request(session_token, auth_temp_data)
        
        if otp_input in ['restart', 'start over', 'begin again']:
            return await self._handle_auth_restart(session_token)
        
        # Continue with normal OTP verification
        otp_input = user_query.strip()
        
        # Verify OTP from database (stateless - works across all machines)
        otp_verification = await self.auth_handler.otp_ops.verify_otp_from_database(session_token, otp_input)
        
        if not otp_verification["valid"]:
            return await self._handle_invalid_otp(session_token, auth_temp_data)
        
        # Mark OTP as used in database
        await self.auth_handler.otp_ops.mark_otp_as_verified(otp_verification["otp_id"])
        
        # Option A: Create user now if this is a new user (user_id is None)
        user_id = auth_temp_data.get("user_id")
        user_created = False
        
        if user_id is None:
            # This is a new user - create them now after OTP verification
            user_data = await self.auth_handler.db_ops.create_new_user(
                first_name=auth_temp_data.get("first_name"),
                last_name=auth_temp_data.get("last_name"),
                dob=auth_temp_data.get("dob"),
                email=auth_temp_data.get("email"),
                phone=auth_temp_data.get("phone_number")
            )
            
            if user_data:
                user_id = user_data["user_id"]
                user_created = True
                print(f"[DEBUG] Created new user after OTP verification: {user_id}")
            else:
                # User creation failed - this is a critical error
                bot_response = (
                    "❌ Authentication verification succeeded, but we encountered an error creating your account. "
                    "Please try again or contact support if this persists."
                )
                await self.auth_handler.session_manager.store_chat_history(
                    session_token, "[OTP verified but user creation failed]", bot_response, "auth_error", "auth_step_error", is_sensitive=True
                )
                return {
                    "success": False,
                    "intent": "auth_error",
                    "output": bot_response,
                    "session_token": session_token,
                    "error": "user_creation_failed"
                }
        
        # Create authenticated user session
        await self.auth_handler.session_manager.create_authenticated_session(session_token, user_id)
        
        # Clean up auth temp data
        await self.auth_handler.session_manager.cleanup_auth_temp_data(session_token)
        
        # Resume original task
        original_intent = auth_temp_data.get("original_intent")
        original_query = auth_temp_data.get("original_query")
        
        if original_intent:
            return await self._resume_original_task(session_token, auth_temp_data, original_intent, original_query, user_id)
        else:
            # Customize success message based on whether user was just created
            if user_created:
                bot_response = "Verification Success! How can I help you today?"
            else:
                bot_response = "Verification Success! How can I help you today?"
                
            await self.auth_handler.session_manager.store_chat_history(
                session_token, "[OTP verified]", bot_response, "authenticated", "auth_success", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "authenticated",
                "output": bot_response,
                "session_token": session_token,
                "authenticated": True,
                "user_id": user_id,
                "user_created": user_created
            }

    async def _handle_otp_generation_error(self, session_token: str, otp_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle OTP generation errors"""
        if otp_result.get("error") == "Rate limit exceeded":
            retry_minutes = otp_result.get("retry_after", 3600) // 60
            bot_response = (
                f"🚫 You've reached the maximum number of verification attempts for this session. "
                f"For security, please wait {retry_minutes} minutes before trying again.\n\n"
                f"This helps protect your profile from unauthorized access attempts.\n\n"
                f"Alternative options:\n"
                f"• Wait {retry_minutes} minutes and try again\n"
                f"• Contact support for immediate assistance"
            )
            await self.auth_handler.session_manager.store_chat_history(
                session_token, "[DOB/Phone provided]", bot_response, "awaiting_dob_email", "rate_limited", is_sensitive=True
            )
            return {
                "success": False,
                "error": "Rate limit exceeded",
                "output": bot_response,
                "session_token": session_token,
                "rate_limited": True,
                "retry_after": otp_result.get("retry_after", 3600)
            }
        else:
            # Generic OTP error
            bot_response = "Sorry, there was an error sending the verification code. Please try again later."
            await self.auth_handler.session_manager.store_chat_history(
                session_token, "[DOB/Phone provided]", bot_response, "awaiting_dob_email", "otp_error", is_sensitive=True
            )
            return {
                "success": False,
                "error": "OTP generation failed",
                "output": bot_response,
                "session_token": session_token
            }

    async def _handle_invalid_otp(self, session_token: str, auth_temp_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle invalid OTP entry"""
        contact_method = auth_temp_data.get("email") or auth_temp_data.get("phone") or "your contact method"
        
        # Since we only allow 1 attempt, any wrong OTP means it's expired
        bot_response = (
            f"❌ Invalid verification code. The code has been expired for security.\n\n"
            f"Your options:\n"
            f"• Type 'new otp' to get a fresh verification code\n"
            f"• Type 'restart' to begin authentication again\n"
            f"• Contact support if you need assistance"
        )
        
        await self.auth_handler.session_manager.store_chat_history(
            session_token, "[OTP provided]", bot_response, "awaiting_otp", "otp_invalid", is_sensitive=True
        )
        
        return {
            "success": True,
            "intent": "awaiting_otp", 
            "output": bot_response,
            "session_token": session_token,
            "otp_invalid": True,
            "attempts_remaining": 0,
            "options": ["new_otp", "restart"]
        }

    async def _handle_otp_resend_request(self, session_token: str, auth_temp_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request for new OTP"""
        try:
            # Check if we have the necessary data
            if not auth_temp_data.get("user_id"):
                return await self._handle_auth_restart(session_token)
            
            contact_method = auth_temp_data.get("email") or auth_temp_data.get("phone")
            if not contact_method:
                return await self._handle_auth_restart(session_token)
            
            user_id = auth_temp_data["user_id"]
            
            # Check rate limiting for new OTP (contact-based)
            identifier_type = "email" if "@" in contact_method else "phone"
            rate_limit_check = await self.auth_handler.rate_limiting.check_otp_rate_limit(contact_method, identifier_type)
            
            if not rate_limit_check["allowed"]:
                retry_minutes = rate_limit_check.get("retry_after", 3600) // 60
                bot_response = (
                    f"🚫 Too many verification requests. Please wait {retry_minutes} minutes before requesting a new code.\n\n"
                    f"Your options:\n"
                    f"• Wait and try again later\n"
                    f"• Type 'restart' to begin authentication with different contact info\n"
                    f"• Contact support for assistance"
                )
                
                await self.auth_handler.session_manager.store_chat_history(
                    session_token, "new otp", bot_response, "awaiting_otp", "rate_limited", is_sensitive=True
                )
                
                return {
                    "success": True,
                    "intent": "awaiting_otp",
                    "output": bot_response,
                    "session_token": session_token,
                    "rate_limited": True,
                    "retry_after": rate_limit_check.get("retry_after", 3600)
                }
            
            # Generate new OTP
            otp_result = await self.auth_handler.otp_ops.generate_and_store_otp_distributed(
                session_token, user_id, contact_method
            )
            
            if not otp_result["success"]:
                bot_response = (
                    "❌ Sorry, there was an error generating a new verification code. "
                    "Please type 'restart' to begin again or contact support."
                )
                return {
                    "success": False,
                    "error": "OTP generation failed",
                    "output": bot_response,
                    "session_token": session_token
                }
            
            # Send new OTP
            await self.auth_handler.otp_ops.send_otp_via_service(contact_method, otp_result["otp_code"], session_token)
            print(f"DEBUG: New OTP for {contact_method}: {otp_result['otp_code']}")
            
            # Determine channel type for user message
            channel_type = "email" if "@" in contact_method else "phone"
            
            bot_response = (
                f"✅ New verification code sent to {contact_method}!\n"
                f"Please enter the 6-digit code to complete authentication.\n\n"
                f"⚠️ Note: You have only 1 attempt to enter the correct code.\n\n"
                f"Options:\n"
                f"• Enter the 6-digit code from your {channel_type}\n"
                f"• Type 'restart' if you want to use different contact info"
            )
            
            await self.auth_handler.session_manager.store_chat_history(
                session_token, "new otp", bot_response, "awaiting_otp", "otp_resent", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "awaiting_otp",
                "output": bot_response,
                "session_token": session_token,
                "otp_resent": True
            }
            
        except Exception as e:
            print(f"Error handling OTP resend: {e}")
            return await self._handle_auth_restart(session_token)

    async def _handle_auth_restart(self, session_token: str) -> Dict[str, Any]:
        """Handle authentication restart request"""
        try:
            # Clear any existing auth data from guest_auth_temp
            from app.core.database import db
            
            # Get any existing auth data to reset rate limits
            auth_temp_data = await self.auth_handler.temp_storage.get_auth_temp_data(session_token)
            
            await db.execute(
                "DELETE FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            
            # Expire any pending OTPs for this session
            await db.execute(
                "UPDATE otp_requests SET status = 'expired' WHERE session_id = $1 AND status = 'pending'",
                session_token
            )
            
            # In development mode, reset rate limits to allow testing
            import os
            if os.getenv("DEVELOPMENT_MODE", "false").lower() == "true" and auth_temp_data:
                # Reset contact method rate limits if they exist
                if auth_temp_data.get("email"):
                    await self.auth_handler.rate_limiting.reset_rate_limit(auth_temp_data["email"], "email")
                if auth_temp_data.get("phone"):
                    await self.auth_handler.rate_limiting.reset_rate_limit(auth_temp_data["phone"], "phone")
            
            # Clear session manager auth temp data as well
            await self.auth_handler.session_manager.cleanup_auth_temp_data(session_token)
            
            # Reset session to beginning of auth process
            await self.auth_handler.session_manager.update_session_status(session_token, "awaiting_auth_details")
            
            bot_response = (
                "🔄 Let's start over with the authentication process.\n"
                "Please provide your first name and last name (e.g., 'John Smith')"
            )
            
            await self.auth_handler.session_manager.store_chat_history(
                session_token, "restart", bot_response, "awaiting_auth_details", "auth_restart", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "awaiting_auth_details",
                "output": bot_response,
                "session_token": session_token,
                "restarted": True
            }
            
        except Exception as e:
            print(f"Error restarting auth: {e}")
            # Fallback to general state
            await self.auth_handler.session_manager.update_session_status(session_token, "general")
            
            return {
                "success": True,
                "intent": "general",
                "output": "Let's start fresh. How can I help you today?",
                "session_token": session_token,
                "restarted": True
            }

    async def _resume_original_task(self, session_token: str, session_data: Dict[str, Any], 
                                  original_intent: str, original_query: str, user_id: int) -> Dict[str, Any]:
        """Resume the original task after successful authentication"""
        
        if original_intent == "appointment":
            bot_response = (
                f"Great! Now I can help you book an appointment. "
                f"Based on your earlier request: '{original_query}'. "
                f"What type of appointment would you like to schedule?"
            )
            
            await self.auth_handler.session_manager.update_session_status(session_token, "booking_appointment")
            await self.auth_handler.session_manager.store_chat_history(
                session_token, "Authentication completed", bot_response, "booking_appointment", "appointment"
            )
            
            return {
                "success": True,
                "intent": "booking_appointment",
                "output": bot_response,
                "session_token": session_token,
                "authenticated": True,
                "user_id": user_id,
                "original_intent": original_intent
            }
        
        elif original_intent == "ticket":
            ticket_type = self.auth_handler.parsers.extract_ticket_type(original_query)
            
            bot_response = (
                f"Perfect! I can now help you with your {ticket_type} request. "
                f"Based on your earlier message: '{original_query}'. "
                f"Please provide more details about your issue."
            )
            
            await self.auth_handler.session_manager.update_session_status(session_token, "creating_ticket")
            await self.auth_handler.session_manager.store_chat_history(
                session_token, "Authentication completed", bot_response, "creating_ticket", "ticket"
            )
            
            return {
                "success": True,
                "intent": "creating_ticket",
                "output": bot_response,
                "session_token": session_token,
                "authenticated": True,
                "user_id": user_id,
                "original_intent": original_intent,
                "ticket_type": ticket_type
            }
        
        else:
            bot_response = "Authentication successful! How can I help you today?"
            await self.auth_handler.session_manager.store_chat_history(
                session_token, "Authentication completed", bot_response, "authenticated", "general"
            )
            
            return {
                "success": True,
                "intent": "authenticated",
                "output": bot_response,
                "session_token": session_token,
                "authenticated": True,
                "user_id": user_id
            }
