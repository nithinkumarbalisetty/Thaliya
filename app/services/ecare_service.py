from typing import Dict, Any
import uuid
from datetime import datetime, timedelta
from app.services.base_service import BaseHealthcareService
from app.services.rag_service import get_rag_service
from app.core.database import db
from app.chatbot.core.intent_classifier import AIIntentClassifier
import re
import jwt
import os
from app.services.otp_service import SecureOTPManager

class ECareService(BaseHealthcareService):
    """
    Stateless E-Care service for chat widget integration.
    """

    def __init__(self):
        super().__init__("ecare") 
        self.rag_service = None
        self.intent_classifier = None
        self.otp_manager = SecureOTPManager()

    async def _get_intent_classifier(self):
        """Get or initialize the AI intent classifier"""
        if self.intent_classifier is None:
            self.intent_classifier = AIIntentClassifier()
            await self.intent_classifier._ensure_initialized()
        return self.intent_classifier

    async def _classify_intent_ai(self, user_query: str) -> str:
        """
        AI-powered intent classification using Azure OpenAI
        """
        try:
            classifier = await self._get_intent_classifier()
            result = await classifier.classify_intent(user_query)
            return result.get("intent", "general")
        except Exception as e:
            # Fallback to simple classification if AI fails
            print(f"AI intent classification failed: {e}")
            return self._classify_intent_simple(user_query)

    def _classify_intent_simple(self, user_query: str) -> str:
        """
        Simple keyword-based intent classification (fallback)
        """
        user_query_lower = user_query.lower()
        
        if any(word in user_query_lower for word in ['appointment', 'book', 'schedule', 'visit']):
            return "appointment"
        elif any(word in user_query_lower for word in ['ticket', 'issue', 'problem', 'help', 'refill', 'prescription']):
            return "ticket"
        elif any(word in user_query_lower for word in ['hours', 'location', 'address', 'services', 'doctors', 'insurance']):
            return "rag_info"
        else:
            return "general"

    def health_check(self) -> Dict[str, Any]:
        """
        Implementation of abstract method from BaseHealthcareService
        """
        return {
            "status": "healthy",
            "service": "ecare",
            "timestamp": datetime.utcnow().isoformat()
        }

    async def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implementation of abstract method from BaseHealthcareService
        """
        request_type = request_data.get("request_type")
        
        if request_type == "chatbot":
            return await self.process_chat(request_data)
        elif request_type == "guest_chat":
            return await self.process_guest_chat(
                user_query=request_data.get("user_query"),
                session_token=request_data.get("session_token")
            )
        else:
            return {
                "success": False,
                "error": f"Unknown request type: {request_type}",
                "timestamp": datetime.utcnow().isoformat()
            }

    async def process_guest_chat(self, user_query: str, session_token: str) -> Dict[str, Any]:
        # 1. Validate session token first
        session_valid = await self._validate_guest_session(session_token)
        if not session_valid:
            return {
                "success": False,
                "error": "Invalid or expired session token",
                "error_code": "INVALID_SESSION",
                "message": "Please create a new session by calling /chatbot/guest/session",
                "session_token": None
            }

        # 2. Update last activity for the session
        await self._update_session_activity(session_token)

        # 3. Get current session state and auth data
        session_data = await self._get_session_state(session_token)
        print(  f"Session data for token {session_token}: {session_data}"   )
        current_state = session_data.get("session_state", "general")
        print(f"Current session state: {current_state}")

        # 4. Handle different conversation states
        if current_state == "awaiting_auth_details":
            print("Here in awaiting_auth_details state")
            return await self._handle_auth_step_1(user_query, session_token)
        elif current_state == "awaiting_dob_email":
            return await self._handle_auth_step_2(user_query, session_token, session_data)
        elif current_state == "awaiting_otp":
            return await self._handle_otp_verification(user_query, session_token, session_data)
        elif current_state == "authenticated":
            return await self._handle_authenticated_flow(user_query, session_token, session_data)
        else:
            # Regular chat flow - check for auth-required intents
            return await self._handle_regular_chat(user_query, session_token)

    async def _handle_regular_chat(self, user_query: str, session_token: str) -> Dict[str, Any]:
        """Handle regular chat and trigger auth if needed"""
        intent = await self._classify_intent_ai(user_query)
        
        if intent == "rag_info":
            # No auth needed - serve immediately
            if self.rag_service is None:
                self.rag_service = await get_rag_service()
            rag_result = await self.rag_service.retrieve_relevant_context(query=user_query, max_context_length=2000)
            bot_response = rag_result.get("answer", "Sorry, I couldn't find relevant information.")
            
            await self._store_chat_history(session_token, user_query, bot_response, "general", intent)
            
            return {
                "success": True,
                "intent": "rag_response",
                "output": bot_response,
                "session_token": session_token
            }
        
        elif intent in ["appointment", "ticket"]:
            # Auth required - store original intent and start auth flow
            await self._store_auth_temp_data(session_token, intent, user_query)
            
            bot_response = (
                f"I understand you want to {intent.replace('_', ' ')}. "
                "To proceed, I'll need to verify your identity first. "
                "Please provide your first name and last name."
            )
            
            await self._update_session_status(session_token, "awaiting_auth_details")
            await self._store_chat_history(session_token, user_query, bot_response, "awaiting_auth_details", intent)
            
            return {
                "success": True,
                "intent": "awaiting_auth",
                "output": bot_response,
                "session_token": session_token,
                "requires_auth": True,
                "original_intent": intent
            }
        
        else:
            # General chat
            bot_response = "I'm here to help! Please let me know your question."
            await self._store_chat_history(session_token, user_query, bot_response, "general", intent)
            
            return {
                "success": True,
                "intent": "general",
                "output": bot_response,
                "session_token": session_token
            }

    async def _handle_auth_step_1(self, user_query: str, session_token: str) -> Dict[str, Any]:
        """Handle first name and last name collection"""
        names = self._parse_names(user_query)
        
        if not names:
            bot_response = "Please provide your first name and last name (e.g., 'John Smith')"
            await self._store_chat_history(session_token, user_query, bot_response, "awaiting_auth_details", "auth_validation", is_sensitive=True)
            
            return {
                "success": True,
                "intent": "awaiting_auth",
                "output": bot_response,
                "session_token": session_token,
                "validation_error": True
            }
        
        # Store names and move to next step
        await self._update_auth_temp_data(session_token, {
            "first_name": names["first_name"],
            "last_name": names["last_name"]
        })
        
        await self._update_session_status(session_token, "awaiting_dob_email")
        
        bot_response = f"Thanks {names['first_name']}! Now please provide your date of birth (MM/DD/YYYY) and email address."
        await self._store_chat_history(session_token, "[Name provided]", bot_response, "awaiting_dob_email", "auth_step1", is_sensitive=True)
        
        return {
            "success": True,
            "intent": "awaiting_dob_email",
            "output": bot_response,
            "session_token": session_token,
            "collected_data": {"first_name": names["first_name"], "last_name": names["last_name"]}
        }

    async def _handle_auth_step_2(self, user_query: str, session_token: str, session_data: dict) -> Dict[str, Any]:
        """Handle DOB and email collection"""
        auth_data = self._parse_dob_email(user_query)
        
        if not auth_data:
            bot_response = "Please provide your date of birth (MM/DD/YYYY) and email address (e.g., '01/15/1990 john@email.com')"
            await self._store_chat_history(session_token, user_query, bot_response, "awaiting_dob_email", "auth_validation", is_sensitive=True)
            
            return {
                "success": True,
                "intent": "awaiting_dob_email",
                "output": bot_response,
                "session_token": session_token,
                "validation_error": True
            }
        
        # Verify user exists in database
        user_verification = await self._verify_user_credentials(
            session_data["first_name"],
            session_data["last_name"], 
            auth_data["dob"],
            auth_data["email"]
        )
        
        if not user_verification["valid"]:
            bot_response = "Sorry, we couldn't verify your information. Please check your details and try again."
            await self._store_chat_history(session_token, "[DOB/Email provided]", bot_response, "awaiting_dob_email", "auth_failed", is_sensitive=True)
            
            return {
                "success": True,
                "intent": "auth_failed",
                "output": bot_response,
                "session_token": session_token,
                "auth_failed": True
            }
        
        # Generate and send OTP
        otp_code = self._generate_otp()
        print(otp_code)
        # Update auth temp data with complete info
        await self._update_auth_temp_data(session_token, {
            "dob": auth_data["dob"],
            "email": auth_data["email"],
            "user_id": user_verification["user_id"],
            "otp_code": otp_code,
            "otp_expires": datetime.utcnow() + timedelta(minutes=5)
        })
        
        await self._update_session_status(session_token, "awaiting_otp")
        
        # TODO: Send actual OTP via email
        print(f"DEBUG: OTP for {auth_data['email']}: {otp_code}")
        
        bot_response = f"Verification details confirmed! We've sent a 6-digit code to {auth_data['email']}. Please enter the code to complete authentication."
        await self._store_chat_history(session_token, "[DOB/Email provided]", bot_response, "awaiting_otp", "auth_step2", is_sensitive=True)
        
        return {
            "success": True,
            "intent": "awaiting_otp",
            "output": bot_response,
            "session_token": session_token
        }

    async def _handle_otp_verification(self, user_query: str, session_token: str, session_data: dict) -> Dict[str, Any]:
        """Handle OTP verification and resume original task"""
        otp_input = user_query.strip()
        
        # Verify OTP
        if not self._verify_otp(otp_input, session_data.get("otp_code"), session_data.get("otp_expires")):
            bot_response = "Invalid or expired code. Please enter the 6-digit code sent to your email."
            await self._store_chat_history(session_token, "[OTP provided]", bot_response, "awaiting_otp", "otp_invalid", is_sensitive=True)
            
            return {
                "success": True,
                "intent": "awaiting_otp",
                "output": bot_response,
                "session_token": session_token,
                "otp_invalid": True
            }
        
        # Create authenticated user session
        await self._create_authenticated_session(session_token, session_data["user_id"])
        
        # Clean up auth temp data
        await self._cleanup_auth_temp_data(session_token)
        
        # Generate JWT token (don't store it)
        jwt_token = self._generate_jwt_token({
            "user_id": session_data["user_id"],
            "session_id": session_token,
            "authenticated_at": datetime.utcnow().isoformat()
        })
        
        # Resume original task
        original_intent = session_data.get("original_intent")
        original_query = session_data.get("original_query")
        
        if original_intent:
            return await self._resume_original_task(session_token, session_data, original_intent, original_query, jwt_token)
        else:
            bot_response = "Authentication successful! How can I help you today?"
            await self._store_chat_history(session_token, "[OTP verified]", bot_response, "authenticated", "auth_success", is_sensitive=True)
            
            return {
                "success": True,
                "intent": "authenticated",
                "output": bot_response,
                "session_token": session_token,
                "jwt_token": jwt_token,
                "authenticated": True,
                "user_id": session_data["user_id"]
            }

    async def _resume_original_task(self, session_token: str, session_data: dict, original_intent: str, original_query: str, jwt_token: str) -> Dict[str, Any]:
        """Resume the original task after successful authentication"""
        user_id = session_data["user_id"]
        
        if original_intent == "appointment":
            bot_response = (
                f"Great! Now I can help you book an appointment. "
                f"Based on your earlier request: '{original_query}'. "
                f"What type of appointment would you like to schedule?"
            )
            
            await self._update_session_status(session_token, "booking_appointment")
            await self._store_chat_history(session_token, "Authentication completed", bot_response, "booking_appointment", "appointment")
            
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
            ticket_type = self._extract_ticket_type(original_query)
            
            bot_response = (
                f"Perfect! I can now help you with your {ticket_type} request. "
                f"Based on your earlier message: '{original_query}'. "
                f"Please provide more details about your issue."
            )
            
            await self._update_session_status(session_token, "creating_ticket")
            await self._store_chat_history(session_token, "Authentication completed", bot_response, "creating_ticket", "ticket")
            
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
            await self._store_chat_history(session_token, "Authentication completed", bot_response, "authenticated", "general")
            
            return {
                "success": True,
                "intent": "authenticated",
                "output": bot_response,
                "session_token": session_token,
                "jwt_token": jwt_token,
                "authenticated": True,
                "user_id": user_id
            }

    async def _handle_authenticated_flow(self, user_query: str, session_token: str, session_data: dict) -> Dict[str, Any]:
        """Handle chat for already authenticated users"""
        # Get user info from authenticated_user_sessions
        auth_session = await self._get_authenticated_session(session_token)
        
        if not auth_session:
            # Session expired, restart auth
            await self._update_session_status(session_token, "active")
            return await self._handle_regular_chat(user_query, session_token)
        
        user_id = auth_session["user_id"]
        intent = await self._classify_intent_ai(user_query)
        
        # Now handle as authenticated user (similar to your process_chat method)
        if intent == "rag_info":
            if self.rag_service is None:
                self.rag_service = await get_rag_service()
            rag_result = await self.rag_service.retrieve_relevant_context(query=user_query, max_context_length=2000)
            bot_response = rag_result.get("answer", "Sorry, I couldn't find relevant information.")
            
            await self._store_chat_history(session_token, user_query, bot_response, "authenticated", intent)
            
            return {
                "success": True,
                "intent": "rag_response",
                "output": bot_response,
                "session_token": session_token,
                "user_id": user_id,
                "authenticated": True
            }
        
        elif intent == "appointment":
            booking_id = str(uuid.uuid4())
            bot_response = f"Your appointment has been booked successfully! Booking ID: {booking_id[:8]}"
            
            await self._store_chat_history(session_token, user_query, bot_response, "authenticated", intent)
            
            return {
                "success": True,
                "intent": "booking",
                "booking_id": booking_id,
                "output": bot_response,
                "session_token": session_token,
                "user_id": user_id,
                "authenticated": True
            }
        
        elif intent == "ticket":
            ticket_id = str(uuid.uuid4())
            bot_response = f"Your support ticket has been created successfully! Ticket ID: {ticket_id[:8]}"
            
            await self._store_chat_history(session_token, user_query, bot_response, "authenticated", intent)
            
            return {
                "success": True,
                "intent": "ticket",
                "ticket_id": ticket_id,
                "output": bot_response,
                "session_token": session_token,
                "user_id": user_id,
                "authenticated": True
            }
        
        else:
            bot_response = "I'm here to help! You can book appointments, create tickets, or ask any questions."
            await self._store_chat_history(session_token, user_query, bot_response, "authenticated", intent)
            
            return {
                "success": True,
                "intent": "general",
                "output": bot_response,
                "session_token": session_token,
                "user_id": user_id,
                "authenticated": True
            }

    # Helper methods for database operations
    async def _get_session_state(self, session_token: str) -> dict:
        """Get session state and auth temp data"""
        try:
            # 1. ALWAYS get the current state from guest_sessions first (source of truth)
            session_result = await db.fetch(
                "SELECT status FROM guest_sessions WHERE session_id = $1",
                session_token
            )
            
            if not session_result:
                return {"session_state": "general"}
            
            current_status = session_result[0]["status"]
            
            # 2. If we're in an auth flow, get the auth temp data as well
            if current_status in ["awaiting_auth_details", "awaiting_dob_email", "awaiting_otp"]:
                auth_result = await db.fetch(
                    """
                    SELECT original_intent, original_query, first_name, last_name, 
                           dob, email, user_id, otp_code, otp_expires
                    FROM guest_auth_temp 
                    WHERE session_id = $1
                    """,
                    session_token
                )
                
                if auth_result:
                    # Combine auth data WITH session state
                    auth_data = dict(auth_result[0])
                    auth_data["session_state"] = current_status  # Add the state!
                    return auth_data
            
            # 3. For non-auth states, just return the state
            return {"session_state": current_status}
            
        except Exception as e:
            print(f"Error getting session state: {e}")
            return {"session_state": "general"}

    async def _store_auth_temp_data(self, session_token: str, intent: str, user_query: str):
        """Store original intent and query in guest_auth_temp"""
        try:
            # First check if record exists
            existing = await db.fetch(
                "SELECT session_id FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            
            if existing:
                # Update existing record
                await db.execute(
                    """
                    UPDATE guest_auth_temp 
                    SET original_intent = $2, original_query = $3, expires_at = CURRENT_TIMESTAMP + INTERVAL '30 minutes'
                    WHERE session_id = $1
                    """,
                    session_token, intent, user_query
                )
            else:
                # Insert new record
                await db.execute(
                    """
                    INSERT INTO guest_auth_temp (session_id, original_intent, original_query)
                    VALUES ($1, $2, $3)
                    """,
                    session_token, intent, user_query
                )
        except Exception as e:
            print(f"Error storing auth temp data: {e}")

    async def _update_auth_temp_data(self, session_token: str, data: dict):
        """Update auth temp data with new information"""
        try:
            # Build dynamic update query based on provided data
            set_clauses = []
            values = [session_token]
            param_num = 2
            
            for key, value in data.items():
                set_clauses.append(f"{key} = ${param_num}")
                values.append(value)
                param_num += 1
            
            if set_clauses:
                query = f"""
                    UPDATE guest_auth_temp 
                    SET {', '.join(set_clauses)}
                    WHERE session_id = $1
                """
                res = await db.execute(query, *values)
                print(query,set_clauses)
        except Exception as e:
            print(f"Error updating auth temp data: {e}")

    async def _update_session_status(self, session_token: str, status: str):
        """Update guest session status"""
        try:
            await db.execute(
                """
                UPDATE guest_sessions 
                SET status = $2, last_activity = CURRENT_TIMESTAMP
                WHERE session_id = $1
                """,
                session_token, status
            )
            print('Updating session status to:', status)
        except Exception as e:
            print(f"Error updating session status: {e}")

    async def _create_authenticated_session(self, session_token: str, user_id: int):
        """Create authenticated user session"""
        try:
            await db.execute(
                """
                INSERT INTO authenticated_user_sessions (session_id, user_id, authenticated_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (session_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    authenticated_at = EXCLUDED.authenticated_at,
                    last_activity = CURRENT_TIMESTAMP
                """,
                session_token, user_id, datetime.utcnow()
            )
            
            # Update guest session status
            await self._update_session_status(session_token, "authenticated")
            
        except Exception as e:
            print(f"Error creating authenticated session: {e}")

    async def _get_authenticated_session(self, session_token: str) -> dict:
        """Get authenticated session info"""
        try:
            result = await db.fetch(
                """
                SELECT user_id, authenticated_at, last_activity
                FROM authenticated_user_sessions 
                WHERE session_id = $1
                """,
                session_token
            )
            
            return dict(result[0]) if result else None
            
        except Exception as e:
            print(f"Error getting authenticated session: {e}")
            return None

    async def _cleanup_auth_temp_data(self, session_token: str):
        """Clean up temporary auth data after successful authentication"""
        try:
            await db.execute(
                "DELETE FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
        except Exception as e:
            print(f"Error cleaning up auth temp data: {e}")

    async def _store_chat_history(self, session_token: str, user_query: str, bot_response: str, 
                                 session_state: str, intent: str, is_sensitive: bool = False):
        """Store chat with sensitivity flag"""
        try:
            await db.execute(
                """
                INSERT INTO guest_chat_history 
                (session_id, user_query, bot_response, session_state, intent, is_sensitive, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                session_token, user_query, bot_response, session_state, intent, is_sensitive, datetime.utcnow()
            )
        except Exception as e:
            print(f"Error storing chat history: {e}")

    # Validation and parsing methods
    def _parse_names(self, user_input: str) -> dict:
        """Parse first and last name from user input"""
        # Simple parsing - you can enhance this
        words = user_input.strip().split()
        if len(words) >= 2:
            return {
                "first_name": words[0].capitalize(),
                "last_name": " ".join(words[1:]).capitalize()
            }
        return None

    def _parse_dob_email(self, user_input: str) -> dict:
        """Parse date of birth and email from user input"""
        # Look for date pattern (MM/DD/YYYY or MM-DD-YYYY)
        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})'
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        
        date_match = re.search(date_pattern, user_input)
        email_match = re.search(email_pattern, user_input)
        
        if date_match and email_match:
            date_str = date_match.group(1)
            
            # Convert date string to proper date object
            try:
                # Handle both MM/DD/YYYY and MM-DD-YYYY formats
                date_str = date_str.replace('-', '/')
                dob_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                
                return {
                    "dob": dob_date,  # Now it's a proper date object
                    "email": email_match.group(1)
                }
            except ValueError as e:
                print(f"Error parsing date {date_str}: {e}")
                return None
        
        return None

    async def _verify_user_credentials(self, first_name: str, last_name: str, dob: str, email: str) -> dict:
        """Verify user exists in the database"""
        try:
            # TODO: Implement actual user verification against your users table
            # For now, return a mock verification
            return {
                "valid": True,
                "user_id": 12345  # Mock user ID
            }
        except Exception as e:
            print(f"Error verifying user credentials: {e}")
            return {"valid": False}

    def _generate_otp(self) -> str:
        """Generate 6-digit OTP"""
        import random
        return str(random.randint(100000, 999999))

    def _verify_otp(self, user_otp: str, stored_otp: str, expires_at: datetime) -> bool:
        """Verify OTP code and expiration"""
        if not user_otp or not stored_otp:
            return False
        
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        if datetime.utcnow() > expires_at:
            return False
        
        return user_otp.strip() == stored_otp

    def _generate_jwt_token(self, payload: dict) -> str:
        """Generate JWT token"""
        try:
            secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key")
            
            # Add expiration if not present
            if "exp" not in payload:
                payload["exp"] = datetime.utcnow() + timedelta(hours=24)
            
            return jwt.encode(payload, secret_key, algorithm="HS256")
        except Exception as e:
            print(f"Error generating JWT: {e}")
            return None

    def _extract_ticket_type(self, original_query: str) -> str:
        """Extract the type of ticket from the original query"""
        query_lower = original_query.lower()
        
        if any(word in query_lower for word in ['prescription', 'refill', 'medication']):
            return "prescription_refill"
        elif any(word in query_lower for word in ['billing', 'bill', 'payment', 'insurance']):
            return "billing"
        elif any(word in query_lower for word in ['result', 'lab', 'test']):
            return "lab_results"
        elif any(word in query_lower for word in ['referral', 'specialist']):
            return "referral"
        else:
            return "general_support"

    # Keep your existing methods
    async def process_chat(self, chatbot_data: dict) -> Dict[str, Any]:
        # Your existing authenticated flow
        user_query = chatbot_data.get("message")
        session_token = chatbot_data.get("session_id")
        user_id = chatbot_data.get("user_id")

        intent = await self._classify_intent_ai(user_query)

        if intent == "rag_info":
            if self.rag_service is None:
                self.rag_service = await get_rag_service()
            rag_result = await self.rag_service.retrieve_relevant_context(query=user_query, max_context_length=2000)
            bot_response = rag_result.get("answer", "Sorry, I couldn't find relevant information.")
            response_json = {
                "success": True,
                "intent": "rag_response",
                "message": bot_response,
                "session_id": session_token,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        elif intent == "appointment":
            booking_id = str(uuid.uuid4())
            bot_response = f"Your appointment has been booked. Booking ID: {booking_id[:8]}"
            response_json = {
                "success": True,
                "intent": "booking",
                "booking_id": booking_id,
                "message": bot_response,
                "session_id": session_token,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        elif intent == "ticket":
            ticket_id = str(uuid.uuid4())
            bot_response = f"Your ticket has been created. Ticket ID: {ticket_id[:8]}"
            response_json = {
                "success": True,
                "intent": "ticket",
                "ticket_id": ticket_id,
                "message": bot_response,
                "session_id": session_token,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            bot_response = "I'm here to help! Please let me know your question."
            response_json = {
                "success": True,
                "intent": "general",
                "message": bot_response,
                "session_id": session_token,
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            }

        return response_json

    async def _validate_guest_session(self, session_token: str) -> bool:
        """Validate if the guest session token is valid and not expired"""
        try:
            result = await db.fetch(
                """
                SELECT COUNT(*) as count FROM guest_sessions 
                WHERE session_id = $1 
                AND status IN ('active', 'awaiting_auth_details', 'awaiting_dob_email', 'awaiting_otp', 'authenticated')
                AND expires_at > CURRENT_TIMESTAMP
                """,
                session_token
            )
            count = result[0]['count'] if result else 0
            return count > 0
        except Exception as e:
            print(f"Session validation error: {e}")
            return False

    async def _update_session_activity(self, session_token: str):
        """Update the last activity timestamp for the session"""
        try:
            await db.execute(
                """
                UPDATE guest_sessions 
                SET last_activity = CURRENT_TIMESTAMP 
                WHERE session_id = $1
                """,
                session_token
            )
        except Exception as e:
            print(f"Failed to update session activity: {e}")
