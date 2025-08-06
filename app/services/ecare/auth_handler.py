"""
Authentication flow handler for E-Care service
Manages the multi-step authentication process using modular components
"""

import os
import jwt
from typing import Dict, Any
from datetime import datetime, timedelta
from app.services.otp_service import OTPService
from .session_manager import ECareSessionManager
from .user_manager import ECareUserManager
from .parsers import ECareDataParsers

# Import modular authentication components
from .auth import (
    AuthUtils,
    RateLimiter,
    TempStorageManager,
    JWTManager
)


class ECareAuthHandler:
    """Handles all authentication-related flows using modular components"""

    def __init__(self):
        # Core service components
        self.session_manager = ECareSessionManager()
        self.user_manager = ECareUserManager()
        self.parsers = ECareDataParsers()
        self.otp_service = OTPService()
        
        # Modular authentication components
        self.auth_utils = AuthUtils()
        self.rate_limiter = RateLimiter()
        self.temp_storage = TempStorageManager()
        self.jwt_manager = JWTManager()
        
        print("🔧 ECareAuthHandler initialized with modular components")

    async def handle_auth_step_1(self, user_query: str, session_token: str) -> Dict[str, Any]:
        """Handle first name and last name collection using guest_auth_temp table"""
        print(f"🚨 DEBUG: handle_auth_step_1 called with query='{user_query}', session='{session_token}'")
        
        # Test database connection first
        try:
            from app.core.database import db
            test_result = await db.fetch("SELECT COUNT(*) as count FROM guest_auth_temp")
            print(f"DEBUG: Current records in guest_auth_temp: {test_result[0]['count'] if test_result else 'QUERY FAILED'}")
        except Exception as e:
            print(f"ERROR: Database connection issue: {e}")
        
        names = self.parsers.parse_names(user_query)
        
        if not names:
            bot_response = "Please provide your first name and last name (e.g., 'John Smith')"
            await self.session_manager.store_chat_history(
                session_token, user_query, bot_response, "awaiting_auth_details", "auth_validation", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "awaiting_auth_details",
                "output": bot_response,
                "session_token": session_token,
                "validation_error": True
            }
        
        # Store names in guest_auth_temp table (your excellent table!)
        await self._create_auth_temp_record(session_token, names)
        
        await self.session_manager.update_session_status(session_token, "awaiting_dob_email")
        
        bot_response = f"Thanks {names['first_name']}! Now please provide your date of birth (MM/DD/YYYY) and either your email address or phone number."
        await self.session_manager.store_chat_history(
            session_token, "[Name provided]", bot_response, "awaiting_dob_email", "auth_step1", is_sensitive=True
        )
        
        return {
            "success": True,
            "intent": "awaiting_dob_email",
            "output": bot_response,
            "session_token": session_token,
            "collected_data": {"first_name": names["first_name"], "last_name": names["last_name"]}
        }

    async def handle_auth_step_2(self, user_query: str, session_token: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle DOB and email collection - using guest_auth_temp table properly"""
        
        # Get auth temp data from the guest_auth_temp table
        auth_temp_data = await self._get_auth_temp_data(session_token)
        
        if not auth_temp_data or not auth_temp_data.get("first_name") or not auth_temp_data.get("last_name"):
            # Fallback: restart auth process
            bot_response = "It looks like we need to start from the beginning. Please provide your first name and last name (e.g., 'John Smith')"
            
            # Reset to step 1
            await self.session_manager.update_session_status(session_token, "awaiting_auth_details")
            await self.session_manager.store_chat_history(
                session_token, user_query, bot_response, "awaiting_auth_details", "auth_reset", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "awaiting_auth_details",
                "output": bot_response,
                "session_token": session_token,
                "reset_to_step1": True
            }
        
        auth_data = self.parsers.parse_dob_email(user_query)
        
        print(f"DEBUG: Parsed auth data from user input: {auth_data}")
        print(f"DEBUG: Existing auth temp data: first_name={auth_temp_data.get('first_name')}, last_name={auth_temp_data.get('last_name')}")
        
        if not auth_data:
            bot_response = f"Hi {auth_temp_data['first_name']}, please provide your date of birth (MM/DD/YYYY) and either your email address or phone number (e.g., '01/15/1990 john@email.com' or '01/15/1990 555-123-4567')"
            await self.session_manager.store_chat_history(
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
        await self._update_auth_temp_with_dob(session_token, auth_data)
        
        # Verify user exists in database using PARSED data from current user input
        print(f"DEBUG: Verifying user with: first_name={auth_temp_data['first_name']}, last_name={auth_temp_data['last_name']}, dob={auth_data['dob']}, email={auth_data.get('email')}, phone={auth_data.get('phone_number')}")
        
        user_verification = await self.user_manager.verify_user_credentials(
            auth_temp_data["first_name"],
            auth_temp_data["last_name"], 
            auth_data["dob"],  # Use PARSED DOB from current input
            auth_data.get("email"),  # Use PARSED email from current input
            auth_data.get("phone_number")  # Use PARSED phone from current input
        )
        
        print(f"DEBUG: User verification result: {user_verification}")
        
        if not user_verification["valid"]:
            error_msg = user_verification.get("error", "Could not verify your information")
            bot_response = f"Sorry, we couldn't verify your information: {error_msg}. Please check your details and try again."
            await self.session_manager.store_chat_history(
                session_token, "[DOB/Email provided]", bot_response, "awaiting_dob_email", "auth_failed", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "auth_failed",
                "output": bot_response,
                "session_token": session_token,
                "auth_failed": True
            }
        
        # Generate and store OTP in database (stateless approach)
        contact_method = auth_data.get("email") or auth_data.get("phone_number")
        
        print(f"DEBUG: About to generate OTP for user_id={user_verification['user_id']}, contact_method={contact_method}")
        
        otp_result = await self._generate_and_store_otp_distributed(
            session_token, 
            user_verification["user_id"], 
            contact_method
        )
        
        print(f"DEBUG: OTP generation result: {otp_result}")
        
        if not otp_result["success"]:
            # Handle specific error types
            if otp_result.get("error") == "Rate limit exceeded":
                retry_minutes = otp_result.get("retry_after", 3600) // 60
                bot_response = (
                    f"🚫 You've reached the maximum number of verification attempts for this session. "
                    f"For security, please wait {retry_minutes} minutes before trying again.\n\n"
                    f"This helps protect your account from unauthorized access attempts.\n\n"
                    f"Alternative options:\n"
                    f"• Wait {retry_minutes} minutes and try again\n"
                    f"• Contact support for immediate assistance"
                )
                await self.session_manager.store_chat_history(
                    session_token, "[DOB/Email provided]", bot_response, "awaiting_dob_email", "rate_limited", is_sensitive=True
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
                await self.session_manager.store_chat_history(
                    session_token, "[DOB/Email provided]", bot_response, "awaiting_dob_email", "otp_error", is_sensitive=True
                )
                return {
                    "success": False,
                    "error": "OTP generation failed",
                    "output": bot_response,
                    "session_token": session_token
                }
        
        print(f"DEBUG: OTP for {contact_method}: {otp_result['otp_code']}")
        
        # Update auth temp record with user_id and OTP info
        await self._update_auth_temp_with_user_id(session_token, user_verification["user_id"], contact_method)
        
        await self.session_manager.update_session_status(session_token, "awaiting_otp")
        
        # Send OTP via external service (distributed)
        await self._send_otp_via_service(contact_method, otp_result["otp_code"], session_token)
        
        # TODO: Send actual OTP via email or SMS
        contact_method_display = auth_data.get("email", auth_data.get("phone_number", "your contact"))
        
        # Customize message based on whether user was newly created or existing
        if user_verification.get("newly_created"):
            bot_response = (
                f"Great! I've created your account and sent a 6-digit verification code to {contact_method_display}.\n"
                f"⚠️ Important: You have only 1 attempt to enter the correct code.\n"
                f"Please enter the code carefully to complete your registration and authentication."
            )
        else:
            bot_response = (
                f"Verification details confirmed! We've sent a 6-digit code to {contact_method_display}.\n"
                f"⚠️ Important: You have only 1 attempt to enter the correct code.\n"
                f"Please enter the code carefully to complete authentication."
            )
        
        await self.session_manager.store_chat_history(
            session_token, "[DOB/Email provided]", bot_response, "awaiting_otp", "auth_step2", is_sensitive=True
        )
        
        return {
            "success": True,
            "intent": "awaiting_otp",
            "output": bot_response,
            "session_token": session_token,
            "user_created": user_verification.get("newly_created", False),
            "user_id": user_verification["user_id"]
        }

    async def handle_otp_verification(self, user_query: str, session_token: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle OTP verification with single attempt and recovery options"""
        # Get auth temp data from guest_auth_temp table
        auth_temp_data = await self._get_auth_temp_data(session_token)
        
        # Check if we have the required session data
        if not auth_temp_data or not auth_temp_data.get("user_id"):
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
        otp_verification = await self._verify_otp_from_database(session_token, otp_input)
        
        if not otp_verification["valid"]:
            contact_method = auth_temp_data.get("email") or auth_temp_data.get("phone") or "your contact method"
            
            # Since we only allow 1 attempt, any wrong OTP means it's expired
            bot_response = (
                f"❌ Invalid verification code. The code has been expired for security.\n\n"
                f"Your options:\n"
                f"• Type 'new otp' to get a fresh verification code\n"
                f"• Type 'restart' to begin authentication again\n"
                f"• Contact support if you need assistance"
            )
            
            await self.session_manager.store_chat_history(
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
        
        # Mark OTP as used in database
        await self._mark_otp_as_verified(otp_verification["otp_id"])
        
        # Create authenticated user session
        await self.session_manager.create_authenticated_session(session_token, auth_temp_data["user_id"])
        
        # Clean up auth temp data
        await self.session_manager.cleanup_auth_temp_data(session_token)
        
        # Generate JWT token (don't store it)
        jwt_token = self._generate_jwt_token({
            "user_id": auth_temp_data["user_id"],
            "session_id": session_token,
            "authenticated_at": datetime.utcnow().isoformat()
        })
        
        # Resume original task
        original_intent = auth_temp_data.get("original_intent")
        original_query = auth_temp_data.get("original_query")
        
        if original_intent:
            return await self._resume_original_task(session_token, auth_temp_data, original_intent, original_query, jwt_token)
        else:
            bot_response = "✅ Authentication successful! How can I help you today?"
            await self.session_manager.store_chat_history(
                session_token, "[OTP verified]", bot_response, "authenticated", "auth_success", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": "authenticated",
                "output": bot_response,
                "session_token": session_token,
                "jwt_token": jwt_token,
                "authenticated": True,
                "user_id": auth_temp_data["user_id"]
            }

    async def _resume_original_task(self, session_token: str, session_data: Dict[str, Any], 
                                  original_intent: str, original_query: str, jwt_token: str) -> Dict[str, Any]:
        """Resume the original task after successful authentication"""
        user_id = session_data["user_id"]
        
        if original_intent == "appointment":
            bot_response = (
                f"Great! Now I can help you book an appointment. "
                f"Based on your earlier request: '{original_query}'. "
                f"What type of appointment would you like to schedule?"
            )
            
            await self.session_manager.update_session_status(session_token, "booking_appointment")
            await self.session_manager.store_chat_history(
                session_token, "Authentication completed", bot_response, "booking_appointment", "appointment"
            )
            
            return {
                "success": True,
                "intent": "booking_appointment",
                "output": bot_response,
                "session_token": session_token,
                "jwt_token": jwt_token,
                "authenticated": True,
                "user_id": user_id,
                "original_intent": original_intent
            }
        
        elif original_intent == "ticket":
            ticket_type = self.parsers.extract_ticket_type(original_query)
            
            bot_response = (
                f"Perfect! I can now help you with your {ticket_type} request. "
                f"Based on your earlier message: '{original_query}'. "
                f"Please provide more details about your issue."
            )
            
            await self.session_manager.update_session_status(session_token, "creating_ticket")
            await self.session_manager.store_chat_history(
                session_token, "Authentication completed", bot_response, "creating_ticket", "ticket"
            )
            
            return {
                "success": True,
                "intent": "creating_ticket",
                "output": bot_response,
                "session_token": session_token,
                "jwt_token": jwt_token,
                "authenticated": True,
                "user_id": user_id,
                "original_intent": original_intent,
                "ticket_type": ticket_type
            }
        
        else:
            bot_response = "Authentication successful! How can I help you today?"
            await self.session_manager.store_chat_history(
                session_token, "Authentication completed", bot_response, "authenticated", "general"
            )
            
            return {
                "success": True,
                "intent": "authenticated",
                "output": bot_response,
                "session_token": session_token,
                "jwt_token": jwt_token,
                "authenticated": True,
                "user_id": user_id
            }

    async def _generate_and_store_otp_distributed(self, session_token: str, user_id: int, contact_method: str) -> Dict[str, Any]:
        """Generate and store OTP in your otp_requests table for distributed access"""
        try:
            # Check rate limiting first using otp_rate_limits table (contact-based)
            identifier = contact_method  # Use email/phone for rate limiting
            identifier_type = "email" if "@" in contact_method else "phone"
            
            rate_limit_check = await self._check_otp_rate_limit(identifier, identifier_type)
            if not rate_limit_check["allowed"]:
                return {
                    "success": False, 
                    "error": "Rate limit exceeded",
                    "retry_after": rate_limit_check.get("retry_after", 60)
                }
            
            # Generate secure OTP
            otp_code = self._generate_secure_otp()
            salt = self._generate_salt()  # Generate salt FIRST
            otp_hash = self._hash_otp(otp_code, salt)  # Use the salt for hashing
            expires_at = datetime.utcnow() + timedelta(minutes=5)
            
            print(f"DEBUG OTP Generation:")
            print(f"  - Generated OTP: {otp_code}")
            print(f"  - Generated salt: {salt}")
            print(f"  - Generated hash: {otp_hash}")
            
            # Store OTP in otp_requests table
            from app.core.database import db
            
            # First, invalidate any existing pending OTPs for this session
            await db.execute(
                "UPDATE otp_requests SET status = 'expired' WHERE session_id = $1 AND status = 'pending'",
                session_token
            )
            
            # Generate shorter OTP ID that fits in varchar(50)
            import secrets
            short_otp_id = f"otp_{secrets.token_hex(8)}"  # Much shorter: otp_1234567890abcdef
            
            result = await db.fetch(
                """
                INSERT INTO otp_requests (
                    otp_id, session_id, identifier, channel, otp_hash, salt, expires_at, attempts_left, status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 1, 'pending', CURRENT_TIMESTAMP)
                RETURNING id
                """,
                short_otp_id,
                session_token,
                identifier,
                identifier_type,
                otp_hash,
                salt,
                expires_at
            )
            
            # Update rate limiting table (contact-based)
            await self._update_otp_rate_limit(identifier, identifier_type)
            
            return {
                "success": True,
                "otp_code": otp_code,  # Return for sending (don't store in session)
                "otp_id": result[0]["id"],
                "expires_at": expires_at
            }
            
        except Exception as e:
            print(f"Error storing OTP in database: {e}")
            return {"success": False, "error": str(e)}

    async def _verify_otp_from_database(self, session_token: str, user_otp: str) -> Dict[str, Any]:
        """Verify OTP from your otp_requests table - stateless across machines"""
        try:
            from app.core.database import db
            
            # Get active OTP for this session
            result = await db.fetch(
                """
                SELECT id, otp_hash, salt, expires_at, attempts_left, identifier, channel
                FROM otp_requests 
                WHERE session_id = $1 AND status = 'pending'
                ORDER BY created_at DESC 
                LIMIT 1
                """,
                session_token
            )
            
            if not result:
                return {
                    "valid": False, 
                    "message": "No active verification code found. Please request a new one.",
                    "attempts_remaining": 0,
                    "can_request_new": True
                }
            
            otp_record = result[0]
            
            # Check if already used (should not happen with 1 attempt, but safety check)
            if otp_record["attempts_left"] <= 0:
                await self._mark_otp_as_expired(otp_record["id"])
                return {
                    "valid": False, 
                    "message": "Verification code already used.",
                    "attempts_remaining": 0,
                    "can_request_new": True
                }
            
            # Check expiration
            if datetime.utcnow() > otp_record["expires_at"]:
                await self._mark_otp_as_expired(otp_record["id"])
                return {
                    "valid": False, 
                    "message": "Verification code has expired.",
                    "attempts_remaining": 0,
                    "can_request_new": True
                }
            
            # Verify OTP using hash
            print(f"DEBUG OTP Verification:")
            print(f"  - User input: '{user_otp}'")
            print(f"  - Stored hash: {otp_record['otp_hash']}")
            print(f"  - Salt: {otp_record['salt']}")
            
            # Compute hash for comparison
            computed_hash = self._hash_otp(user_otp, otp_record["salt"])
            print(f"  - Computed hash: {computed_hash}")
            print(f"  - Hashes match: {computed_hash == otp_record['otp_hash']}")
            
            if not self._verify_otp_hash(user_otp, otp_record["otp_hash"], otp_record["salt"]):
                # Wrong OTP - immediately expire it (single attempt rule)
                await self._mark_otp_as_expired(otp_record["id"])
                return {
                    "valid": False,
                    "message": "Invalid verification code. Code expired for security.",
                    "attempts_remaining": 0,
                    "can_request_new": True
                }
            
            # OTP is valid
            return {
                "valid": True,
                "otp_id": otp_record["id"],
                "identifier": otp_record["identifier"],
                "channel": otp_record["channel"]
            }
                
        except Exception as e:
            print(f"Error verifying OTP from database: {e}")
            return {
                "valid": False, 
                "message": "Verification failed due to system error.",
                "attempts_remaining": 0,
                "can_request_new": True
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
            rate_limit_check = await self._check_otp_rate_limit(contact_method, identifier_type)
            
            if not rate_limit_check["allowed"]:
                retry_minutes = rate_limit_check.get("retry_after", 3600) // 60
                bot_response = (
                    f"🚫 Too many verification requests. Please wait {retry_minutes} minutes before requesting a new code.\n\n"
                    f"Your options:\n"
                    f"• Wait and try again later\n"
                    f"• Type 'restart' to begin authentication with different contact info\n"
                    f"• Contact support for assistance"
                )
                
                await self.session_manager.store_chat_history(
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
            otp_result = await self._generate_and_store_otp_distributed(
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
            await self._send_otp_via_service(contact_method, otp_result["otp_code"], session_token)
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
            
            await self.session_manager.store_chat_history(
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
            auth_temp_data = await self._get_auth_temp_data(session_token)
            
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
                    await self.reset_otp_rate_limit(auth_temp_data["email"], "email")
                if auth_temp_data.get("phone"):
                    await self.reset_otp_rate_limit(auth_temp_data["phone"], "phone")
            
            # Clear session manager auth temp data as well
            await self.session_manager.cleanup_auth_temp_data(session_token)
            
            # Reset session to beginning of auth process
            await self.session_manager.update_session_status(session_token, "awaiting_auth_details")
            
            bot_response = (
                "🔄 Let's start over with the authentication process.\n"
                "Please provide your first name and last name (e.g., 'John Smith')"
            )
            
            await self.session_manager.store_chat_history(
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
            await self.session_manager.update_session_status(session_token, "general")
            
            return {
                "success": True,
                "intent": "general",
                "output": "Let's start fresh. How can I help you today?",
                "session_token": session_token,
                "restarted": True
            }

    async def _create_auth_temp_record(self, session_token: str, names: Dict[str, str]) -> None:
        """Create initial record in guest_auth_temp table"""
        try:
            from app.core.database import db
            
            print(f"DEBUG: About to create auth temp record for session: {session_token}")
            print(f"DEBUG: Names: {names}")
            
            # First, delete any existing record to ensure clean start
            delete_result = await db.execute(
                "DELETE FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            print(f"DEBUG: Deleted {delete_result} existing records")
            
            # Insert fresh auth temp record
            insert_result = await db.execute(
                """
                INSERT INTO guest_auth_temp (
                    session_id, first_name, last_name, created_at, expires_at
                ) VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '1 hour')
                """,
                session_token, names["first_name"], names["last_name"]
            )
            print(f"DEBUG: Insert result: {insert_result}")
            
            # Verify the record was created
            verify_result = await db.fetch(
                "SELECT * FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            print(f"DEBUG: Verification query result: {verify_result}")
            
            print(f"DEBUG: Successfully created auth temp record for {names['first_name']} {names['last_name']}")
            
        except Exception as e:
            print(f"ERROR: Failed to create auth temp record: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _get_auth_temp_data(self, session_token: str) -> Dict[str, Any]:
        """Get auth temp data from the guest_auth_temp table"""
        try:
            from app.core.database import db
            
            print(f"DEBUG: Getting auth temp data for session: {session_token}")
            
            result = await db.fetch(
                """
                SELECT session_id, original_intent, original_query, first_name, last_name, 
                       dob, email, phone, user_id, preferred_otp_channel, otp_attempts,
                       created_at, expires_at
                FROM guest_auth_temp 
                WHERE session_id = $1 AND expires_at > CURRENT_TIMESTAMP
                """,
                session_token
            )
            
            print(f"DEBUG: Query result: {result}")
            
            if result:
                auth_data = dict(result[0])
                # Map phone back to phone_number for consistency
                if auth_data.get("phone"):
                    auth_data["phone_number"] = auth_data["phone"]
                print(f"DEBUG: Retrieved auth data: {auth_data}")
                return auth_data
            else:
                print(f"DEBUG: No auth temp data found for session {session_token}")
                return None
            
        except Exception as e:
            print(f"ERROR: Error getting auth temp data: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _update_auth_temp_with_dob(self, session_token: str, parsed_data: Dict[str, Any]) -> None:
        """Update auth temp record with DOB and contact info"""
        try:
            from app.core.database import db
            
            print(f"DEBUG: Updating auth temp with DOB for session: {session_token}")
            print(f"DEBUG: Parsed data: {parsed_data}")
            
            # Reset fields that might be stale from previous attempts
            update_result = await db.execute(
                """
                UPDATE guest_auth_temp 
                SET dob = $2, email = $3, phone = $4, user_id = NULL, 
                    preferred_otp_channel = NULL, otp_attempts = 0, last_otp_sent = NULL
                WHERE session_id = $1
                """,
                session_token, 
                parsed_data["dob"],
                parsed_data.get("email"),
                parsed_data.get("phone_number")
            )
            print(f"DEBUG: Update result: {update_result}")
            
            # Verify the update
            verify_result = await db.fetch(
                "SELECT * FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            print(f"DEBUG: After update verification: {verify_result}")
            
            print(f"DEBUG: Updated auth temp with fresh DOB and contact info, reset user_id")
            
        except Exception as e:
            print(f"ERROR: Error updating auth temp with DOB: {e}")
            import traceback
            traceback.print_exc()

    async def _update_auth_temp_with_user_id(self, session_token: str, user_id: int, contact_method: str) -> None:
        """Update auth temp record with verified user ID"""
        try:
            from app.core.database import db
            
            print(f"DEBUG: Updating auth temp with user_id for session: {session_token}")
            print(f"DEBUG: user_id: {user_id}, contact_method: {contact_method}")
            
            channel = "email" if "@" in contact_method else "sms"
            
            update_result = await db.execute(
                """
                UPDATE guest_auth_temp 
                SET user_id = $2, preferred_otp_channel = $3, last_otp_sent = CURRENT_TIMESTAMP
                WHERE session_id = $1
                """,
                session_token, user_id, channel
            )
            print(f"DEBUG: Update result: {update_result}")
            
            # Verify the update
            verify_result = await db.fetch(
                "SELECT * FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            print(f"DEBUG: After user_id update verification: {verify_result}")
            
            print(f"DEBUG: Updated auth temp with user_id {user_id}")
            
        except Exception as e:
            print(f"ERROR: Error updating auth temp with user_id: {e}")
            import traceback
            traceback.print_exc()

    async def _check_otp_rate_limit(self, identifier: str, identifier_type: str) -> Dict[str, Any]:
        """Check rate limiting - using original implementation for now"""
        try:
            from app.core.database import db
            
            # For development: Allow bypassing rate limit for testing
            import os
            if os.getenv("DEVELOPMENT_MODE", "false").lower() == "true":
                print(f"DEBUG: Development mode - bypassing rate limit for {identifier_type}:{identifier}")
                return {"allowed": True}
            
            result = await db.fetch(
                """
                SELECT request_count, last_request, blocked_until
                FROM otp_rate_limits 
                WHERE identifier = $1 AND identifier_type = $2
                """,
                identifier, identifier_type
            )
            
            if not result:
                return {"allowed": True}
            
            rate_data = result[0]
            now = datetime.utcnow()
            
            # Check if currently blocked
            if rate_data["blocked_until"] and now < rate_data["blocked_until"]:
                retry_after = int((rate_data["blocked_until"] - now).total_seconds())
                
                # For development: More lenient rate limiting
                if os.getenv("DEVELOPMENT_MODE", "false").lower() == "true" and retry_after < 1800:  # 30 minutes
                    print(f"DEBUG: Development mode - reducing rate limit timeout for {identifier_type}:{identifier}")
                    return {"allowed": True}
                
                return {
                    "allowed": False,
                    "reason": "temporarily_blocked",
                    "retry_after": retry_after
                }
            
            # Check request count in last hour
            if rate_data["last_request"] and (now - rate_data["last_request"]).total_seconds() < 3600:
                max_requests = int(os.getenv("OTP_MAX_REQUESTS_PER_HOUR", "5"))  # Standard limit per contact method
                
                if rate_data["request_count"] >= max_requests:
                    # Block duration for contact methods
                    block_duration = timedelta(hours=1)  # Standard 1 hour block
                        
                    # Development mode gets shorter blocks
                    if os.getenv("DEVELOPMENT_MODE", "false").lower() == "true":
                        block_duration = timedelta(minutes=5)  # Only 5 minutes in dev mode
                        
                    block_until = now + block_duration
                    await db.execute(
                        """
                        UPDATE otp_rate_limits 
                        SET blocked_until = $3, updated_at = CURRENT_TIMESTAMP
                        WHERE identifier = $1 AND identifier_type = $2
                        """,
                        identifier, identifier_type, block_until
                    )
                    return {
                        "allowed": False,
                        "reason": "rate_limit_exceeded",
                        "retry_after": int(block_duration.total_seconds())
                    }
            
            return {"allowed": True}
            
        except Exception as e:
            print(f"Error checking rate limit: {e}")
            return {"allowed": True}  # Allow on error to not block users

    async def _update_otp_rate_limit(self, identifier: str, identifier_type: str):
        """Update rate limiting counters - using original implementation for now"""
        try:
            from app.core.database import db
            
            await db.execute(
                """
                INSERT INTO otp_rate_limits (identifier, identifier_type, request_count, last_request, created_at, updated_at)
                VALUES ($1, $2, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (identifier, identifier_type) DO UPDATE SET
                    request_count = CASE 
                        WHEN otp_rate_limits.last_request < CURRENT_TIMESTAMP - INTERVAL '1 hour' 
                        THEN 1 
                        ELSE otp_rate_limits.request_count + 1 
                    END,
                    last_request = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                identifier, identifier_type
            )
        except Exception as e:
            print(f"Error updating rate limit: {e}")

    async def reset_otp_rate_limit(self, identifier: str, identifier_type: str = None) -> bool:
        """Reset rate limit for specific identifier - FOR DEVELOPMENT/TESTING ONLY"""
        try:
            from app.core.database import db
            
            if identifier_type:
                # Reset specific identifier
                await db.execute(
                    "DELETE FROM otp_rate_limits WHERE identifier = $1 AND identifier_type = $2",
                    identifier, identifier_type
                )
                print(f"DEBUG: Reset rate limit for {identifier} ({identifier_type})")
            else:
                # Auto-detect type and reset
                if "@" in identifier:
                    await db.execute(
                        "DELETE FROM otp_rate_limits WHERE identifier = $1 AND identifier_type = 'email'",
                        identifier
                    )
                    print(f"DEBUG: Reset rate limit for email {identifier}")
                else:
                    await db.execute(
                        "DELETE FROM otp_rate_limits WHERE identifier = $1 AND identifier_type = 'phone'",
                        identifier
                    )
                    print(f"DEBUG: Reset rate limit for phone {identifier}")
            
            return True
            
        except Exception as e:
            print(f"Error resetting rate limit: {e}")
            return False

    async def _send_otp_via_service(self, contact_method: str, otp_code: str, session_token: str = None):
        """Send OTP via external service (email/SMS)"""
        try:
            if "@" in contact_method:
                # Send email OTP using OTPService
                channel = "email"
            else:
                # Send SMS OTP using OTPService
                channel = "sms"
            
            # Use the OTPService's internal delivery method
            result = await self.otp_service._deliver_otp(contact_method, channel, otp_code, session_token or "auth_session")
            
            if result.get("success"):
                print(f"DEBUG: OTP sent successfully via {channel} to {contact_method}")
                if result.get("dev_otp"):
                    print(f"DEBUG: DEV MODE - OTP Code: {result['dev_otp']}")
            else:
                print(f"DEBUG: Failed to send OTP via {channel}: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"Error sending OTP via service: {e}")

    def _generate_secure_otp(self) -> str:
        """Generate cryptographically secure 6-digit OTP using modular auth utils"""
        return self.auth_utils.generate_secure_otp()

    def _generate_salt(self) -> str:
        """Generate random salt for OTP hashing using modular auth utils"""
        return self.auth_utils.generate_salt()

    def _hash_otp(self, otp_code: str, salt: str = None) -> str:
        """Hash OTP with salt using modular auth utils"""
        if not salt:
            salt = self._generate_salt()
        return self.auth_utils.hash_otp(otp_code, salt)

    def _verify_otp_hash(self, user_otp: str, stored_hash: str, salt: str) -> bool:
        """Verify OTP against stored hash using modular auth utils"""
        return self.auth_utils.verify_otp_hash(user_otp, stored_hash, salt)

    async def _mark_otp_as_verified(self, otp_id: int):
        """Mark OTP as verified in database"""
        try:
            from app.core.database import db
            await db.execute(
                """
                UPDATE otp_requests 
                SET status = 'verified', verified_at = CURRENT_TIMESTAMP 
                WHERE id = $1
                """,
                otp_id
            )
        except Exception as e:
            print(f"Error marking OTP as verified: {e}")

    async def _mark_otp_as_expired(self, otp_id: int):
        """Mark OTP as expired"""
        try:
            from app.core.database import db
            await db.execute(
                "UPDATE otp_requests SET status = 'expired' WHERE id = $1",
                otp_id
            )
        except Exception as e:
            print(f"Error marking OTP as expired: {e}")

    async def _mark_otp_as_blocked(self, otp_id: int):
        """Mark OTP as blocked due to too many attempts"""
        try:
            from app.core.database import db
            await db.execute(
                "UPDATE otp_requests SET status = 'blocked' WHERE id = $1",
                otp_id
            )
        except Exception as e:
            print(f"Error marking OTP as blocked: {e}")

    async def _decrement_otp_attempts(self, otp_id: int):
        """Decrement remaining OTP attempts"""
        try:
            from app.core.database import db
            await db.execute(
                """
                UPDATE otp_requests 
                SET attempts_left = attempts_left - 1, last_attempt = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                otp_id
            )
        except Exception as e:
            print(f"Error decrementing OTP attempts: {e}")

    def _generate_otp(self) -> str:
        """Legacy method - use _generate_secure_otp instead"""
        return self._generate_secure_otp()

    def _verify_otp(self, user_otp: str, stored_otp: str, expires_at: datetime) -> bool:
        """Legacy method - use _verify_otp_from_database instead"""
        if not user_otp or not stored_otp:
            return False
        
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        if datetime.utcnow() > expires_at:
            return False
        
        return user_otp.strip() == stored_otp

    def _generate_jwt_token(self, payload: Dict[str, Any]) -> str:
        """Generate JWT token using modular JWT manager"""
        return self.jwt_manager.generate_jwt_token(payload)
