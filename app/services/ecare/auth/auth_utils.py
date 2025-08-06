"""
Authentication Utilities
Provides common utility functions for authentication operations
"""

import hashlib
import secrets
from typing import Dict, Any


class AuthUtils:
    """Utility functions for authentication operations"""
    
    @staticmethod
    def generate_secure_otp() -> str:
        """Generate cryptographically secure 6-digit OTP"""
        return f"{secrets.randbelow(900000) + 100000:06d}"
    
    @staticmethod
    def generate_salt() -> str:
        """Generate random salt for OTP hashing - optimized for varchar(50)"""
        return secrets.token_hex(8)  # 16 characters, fits in varchar(50)
    
    @staticmethod
    def hash_otp(otp_code: str, salt: str = None) -> str:
        """Hash OTP with salt for secure storage - optimized for varchar(256)"""
        if not salt:
            salt = AuthUtils.generate_salt()
        # Use SHA-256 which produces 64-character hex string (fits in varchar(256))
        return hashlib.sha256((otp_code + salt).encode()).hexdigest()
    
    @staticmethod
    def verify_otp_hash(user_otp: str, stored_hash: str, salt: str) -> bool:
        """Verify OTP against stored hash"""
        computed_hash = AuthUtils.hash_otp(user_otp, salt)
        return computed_hash == stored_hash
    
    @staticmethod
    def generate_short_otp_id() -> str:
        """Generate shorter OTP ID that fits in varchar(50)"""
        return f"otp_{secrets.token_hex(8)}"  # Much shorter: otp_1234567890abcdef
    
    @staticmethod
    def is_email(contact_method: str) -> bool:
        """Check if contact method is email"""
        return "@" in contact_method
    
    @staticmethod
    def get_identifier_type(contact_method: str) -> str:
        """Get identifier type (email/phone) from contact method"""
        return "email" if AuthUtils.is_email(contact_method) else "phone"
    
    @staticmethod
    def get_channel_type(contact_method: str) -> str:
        """Get channel type for display purposes"""
        return "email" if AuthUtils.is_email(contact_method) else "sms"
