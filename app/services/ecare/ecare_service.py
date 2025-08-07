"""
Main E-Care service - orchestrates all healthcare chat operations
This is the main entry point that delegates to specialized handlers
"""

from typing import Dict, Any, Optional
from datetime import datetime
import re
from app.services.base_service import BaseHealthcareService
from .session_manager import ECareSessionManager
from .auth.core_handler import ECareAuthHandler  # Use modular auth system
from .chat_handler import ECareChatHandler


class ECareService(BaseHealthcareService):
    """
    Main E-Care service orchestrating all healthcare chat operations
    Delegates to specialized handlers for better separation of concerns
    """

    def __init__(self):
        super().__init__("ecare")
        self.session_manager = ECareSessionManager()
        self.auth_handler = ECareAuthHandler()
        self.chat_handler = ECareChatHandler()

    def health_check(self) -> Dict[str, Any]:
        """Implementation of abstract method from BaseHealthcareService"""
        return {
            "status": "healthy",
            "service": "ecare",
            "timestamp": datetime.utcnow().isoformat()
        }

    async def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Implementation of abstract method from BaseHealthcareService"""
        request_type = request_data.get("request_type")
        
        if request_type == "guest_chat":
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
        """
        Main chat processing entry point - delegates to appropriate handlers
        """
        # 1. Validate session token first
        session_valid = await self.session_manager.validate_guest_session(session_token)
        if not session_valid:
            return {
                "success": False,
                "error": "Invalid or expired session token",
                "error_code": "INVALID_SESSION",
                "message": "Please create a new session by calling /chatbot/guest/session",
                "session_token": None
            }

        # 2. Update last activity for the session
        await self.session_manager.update_session_activity(session_token)

        # 3. Get current session state and auth data
        session_data = await self.session_manager.get_session_state(session_token)
        print(f"Session data for token {session_token}: {session_data}")
        current_state = session_data.get("session_state", "general")
        print(f"Current session state: {current_state}")

        # 4. Route to appropriate handler based on state
        return await self._route_by_state(current_state, user_query, session_token, session_data)

    async def _route_by_state(self, state: str, user_query: str, session_token: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Smart routing with hybrid context switching for better UX"""
        
        # First, check if user wants to resume paused authentication
        if user_query.lower().strip() in ['continue', 'continue auth', 'resume', 'resume auth']:
            resumption_result = await self._handle_auth_resumption(user_query, session_token)
            if resumption_result:
                return resumption_result
        
        # Authentication flow states with context switching
        if state == "awaiting_auth_details":
            # Check for general questions during name collection
            if self._is_general_question(user_query):
                await self._save_auth_progress(session_token, state)
                
                # Answer the general question
                general_response = await self.chat_handler.handle_regular_chat(user_query, session_token)
                
                # Add resumption instructions
                general_response["output"] += (
                    f"\n\n💡 **Note:** You were in the middle of authentication. "
                    f"Would you like to:\n"
                    f"• Type 'continue' to resume providing your name\n"
                    f"• Type 'restart' to start authentication over\n"
                    f"• Continue with general questions"
                )
                
                general_response["auth_resumable"] = True
                general_response["auth_state_saved"] = state
                
                return general_response
            else:
                return await self.auth_handler.handle_auth_step_1(user_query, session_token)
        
        elif state == "awaiting_dob_email":
            # Check for general questions during DOB/phone collection
            if self._is_general_question(user_query):
                await self._save_auth_progress(session_token, state)
                
                # Answer the general question
                general_response = await self.chat_handler.handle_regular_chat(user_query, session_token)
                
                # Get user's first name for personalized message
                auth_data = session_data
                first_name = auth_data.get("first_name", "")
                
                # Add resumption instructions
                general_response["output"] += (
                    f"\n\n💡 **Note:** Hi {first_name}, you were providing your date of birth and phone number. "
                    f"Would you like to:\n"
                    f"• Type 'continue' to resume where you left off\n"
                    f"• Type 'restart' to start authentication over\n"
                    f"• Continue with general questions"
                )
                
                general_response["auth_resumable"] = True
                general_response["auth_state_saved"] = state
                
                return general_response
            else:
                return await self.auth_handler.handle_auth_step_2(user_query, session_token, session_data)
        
        elif state == "awaiting_otp":
            # OTP verification stays strict for security - no context switching
            return await self.auth_handler.handle_otp_verification(user_query, session_token, session_data)
        
        # Authenticated chat flow
        elif state == "authenticated":
            return await self.chat_handler.handle_authenticated_flow(user_query, session_token, session_data)
        
        # Regular/general chat flow (default)
        else:
            return await self.chat_handler.handle_regular_chat(user_query, session_token)

    def _is_general_question(self, query: str) -> bool:
        """Detect if user is asking a general question vs providing auth details"""
        import re
        
        query_lower = query.lower().strip()
        
        # Common general question patterns for healthcare
        general_patterns = [
            r'\b(hours?|timings?|schedule|open|close|closed)\b',
            r'\b(location|address|directions|where.*located)\b', 
            r'\b(appointment|booking|book|schedule.*appointment)\b',
            r'\b(cancel|stop|help|exit|quit)\b',
            r'\b(what|when|where|how|why)\b.*\?',
            r'\b(services|treatment|doctor|clinic|hospital)\b',
            r'\b(cost|price|insurance|payment|billing)\b',
            r'\b(emergency|urgent|help)\b',
            r'\b(symptoms|medicine|medication|prescription)\b',
            r'\b(lab.*results?|test.*results?)\b',
            r'^\s*(hi|hello|hey|good\s+(morning|afternoon|evening))\s*$',
            r'^\s*(thank\s*you|thanks|bye|goodbye)\s*$',
        ]
        
        # Check if query matches any general patterns
        for pattern in general_patterns:
            if re.search(pattern, query_lower):
                return True
        
        # Check for question words at start
        question_starters = ['what', 'when', 'where', 'how', 'why', 'can', 'do', 'does', 'is', 'are', 'will']
        first_word = query_lower.split()[0] if query_lower.split() else ""
        if first_word in question_starters:
            return True
            
        return False

    async def _save_auth_progress(self, session_token: str, current_state: str) -> None:
        """Save current authentication progress for later resumption"""
        try:
            # Store progress in dedicated columns for better data integrity
            progress_data = {
                "auth_paused_state": current_state,
                "auth_paused_at": datetime.now()  # Use datetime object, not string
            }
            
            # Use the existing auth temp storage
            await self.session_manager.update_auth_temp_data(session_token, progress_data)
            
            print(f"DEBUG: Saved auth progress for session {session_token} at state {current_state}")
            
        except Exception as e:
            print(f"ERROR: Failed to save auth progress: {e}")

    async def _handle_auth_resumption(self, user_query: str, session_token: str) -> Optional[Dict[str, Any]]:
        """Handle resumption of paused authentication"""
        try:
            # Get session state to check for saved progress
            session_data = await self.session_manager.get_session_state(session_token)
            
            # Check if there's a paused authentication state
            paused_state = session_data.get("auth_paused_state")
            
            if not paused_state:
                return None
            
            # Clear the saved progress
            await self.session_manager.update_auth_temp_data(session_token, {
                "auth_paused_state": None,
                "auth_paused_at": None
            })
            
            # Update session state back to auth flow
            await self.session_manager.update_session_status(session_token, paused_state)
            
            bot_response = f"✅ Resuming authentication where we left off. "
            
            if paused_state == "awaiting_auth_details":
                bot_response += "Please provide your first name and last name (e.g., 'John Smith')"
            elif paused_state == "awaiting_dob_email":
                first_name = session_data.get("first_name", "")
                bot_response += f"Hi {first_name}, please provide your date of birth (MM/DD/YYYY) and phone number for verification."
            
            await self.session_manager.store_chat_history(
                session_token, "continue", bot_response, paused_state, "auth_resumed", is_sensitive=True
            )
            
            return {
                "success": True,
                "intent": paused_state,
                "output": bot_response,
                "session_token": session_token,
                "auth_resumed": True
            }
            
        except Exception as e:
            print(f"ERROR: Failed to handle auth resumption: {e}")
            return None
