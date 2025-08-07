"""
Core Authentication Handler - Main orchestrator
Coordinates between different authentication modules
"""

import os
from typing import Dict, Any
from datetime import datetime, timedelta
from app.services.otp_service import OTPService
from ..session_manager import ECareSessionManager
from ..user_manager import ECareUserManager
from ..parsers import ECareDataParsers

# Import auth modules
from .auth_steps import AuthStepsHandler
from .otp_operations import OTPOperationsHandler
from .rate_limiting import RateLimitingHandler
from .temp_storage import TempStorageManager
from .database_operations import DatabaseOperationsHandler

# Import existing modular components
from .auth_utils import AuthUtils
from .rate_limiter import RateLimiter


class ECareAuthHandler:
    """
    Main authentication handler - coordinates between modules
    """

    def __init__(self):
        # Core service components
        self.session_manager = ECareSessionManager()
        self.user_manager = ECareUserManager()
        self.parsers = ECareDataParsers()
        self.otp_service = OTPService()
        
        # Initialize existing modular components
        self.auth_utils = AuthUtils()
        self.rate_limiter = RateLimiter()
        
        # Authentication modules
        self.auth_steps = AuthStepsHandler(self)
        self.otp_ops = OTPOperationsHandler(self)
        self.rate_limiting = RateLimitingHandler(self)
        self.temp_storage = TempStorageManager()
        self.db_ops = DatabaseOperationsHandler(self)
        
        print("🔧 ECareAuthHandler initialized with modular components")

    # Main authentication entry points - delegate to modules
    async def handle_auth_step_1(self, user_query: str, session_token: str) -> Dict[str, Any]:
        """Handle first name and last name collection"""
        return await self.auth_steps.handle_step_1(user_query, session_token)

    async def handle_auth_step_2(self, user_query: str, session_token: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle DOB and email collection"""
        return await self.auth_steps.handle_step_2(user_query, session_token, session_data)

    async def handle_otp_verification(self, user_query: str, session_token: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle OTP verification"""
        return await self.auth_steps.handle_otp_verification(user_query, session_token, session_data)
    
    # Additional methods for compatibility
    async def reset_otp_rate_limit(self, identifier: str, identifier_type: str = None) -> bool:
        """Reset rate limit for specific identifier"""
        return await self.rate_limiting.reset_rate_limit(identifier, identifier_type)
    
    async def _send_otp_via_service(self, contact_method: str, otp_code: str, session_token: str = None):
        """Send OTP via service"""
        return await self.otp_ops.send_otp_via_service(contact_method, otp_code, session_token)

    # Utility methods for backward compatibility
    async def reset_otp_rate_limit(self, identifier: str, identifier_type: str = None) -> bool:
        """Reset rate limit for specific identifier"""
        return await self.rate_limiter.reset_rate_limit(identifier, identifier_type)

    def _generate_secure_otp(self) -> str:
        """Generate secure OTP"""
        return self.auth_utils.generate_secure_otp()

    def _generate_salt(self) -> str:
        """Generate salt"""
        return self.auth_utils.generate_salt()

    def _hash_otp(self, otp_code: str, salt: str = None) -> str:
        """Hash OTP"""
        return self.auth_utils.hash_otp(otp_code, salt)

    def _verify_otp_hash(self, user_otp: str, stored_hash: str, salt: str) -> bool:
        """Verify OTP hash"""
        return self.auth_utils.verify_otp_hash(user_otp, stored_hash, salt)
