"""
Main E-Care service - orchestrates all healthcare chat operations
This is the main entry point that delegates to specialized handlers
"""

from typing import Dict, Any
from datetime import datetime
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
        """Clean state routing to appropriate handlers"""
        
        # Authentication flow states
        if state == "awaiting_auth_details":
            return await self.auth_handler.handle_auth_step_1(user_query, session_token)
        elif state == "awaiting_dob_email":
            return await self.auth_handler.handle_auth_step_2(user_query, session_token, session_data)
        elif state == "awaiting_otp":
            return await self.auth_handler.handle_otp_verification(user_query, session_token, session_data)
        
        # Authenticated chat flow
        elif state == "authenticated":
            return await self.chat_handler.handle_authenticated_flow(user_query, session_token, session_data)
        
        # Regular/general chat flow (default)
        else:
            return await self.chat_handler.handle_regular_chat(user_query, session_token)
