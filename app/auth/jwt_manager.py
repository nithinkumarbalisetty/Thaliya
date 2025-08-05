"""
JWT Token Manager for Authentication
Handles JWT token generation and validation
"""

import jwt
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class JWTManager:
    """
    Manages JWT tokens for authentication
    """
    
    def __init__(self):
        # In production, load this from environment variables
        self.secret_key = secrets.token_hex(32)  # Generate random secret for dev
        self.algorithm = "HS256"
        self.token_expiry_hours = 24  # 24 hours
        self.refresh_token_expiry_days = 30  # 30 days
    
    def configure(self, secret_key: str, algorithm: str = "HS256"):
        """
        Configure JWT manager with custom settings
        
        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT algorithm to use
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        logger.info("JWT manager configured")
    
    def generate_access_token(self, user_data: Dict[str, Any]) -> str:
        """
        Generate access token for authenticated user
        
        Args:
            user_data: User information to include in token
            
        Returns:
            JWT access token string
        """
        try:
            payload = {
                "user_id": user_data.get("user_id"),
                "session_id": user_data.get("session_id"),
                "email": user_data.get("email"),
                "phone": user_data.get("phone"),
                "auth_method": "otp",
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(hours=self.token_expiry_hours),
                "type": "access"
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.info(f"Generated access token for user: {user_data.get('user_id')}")
            return token
            
        except Exception as e:
            logger.error(f"Error generating access token: {str(e)}")
            raise
    
    def generate_refresh_token(self, user_data: Dict[str, Any]) -> str:
        """
        Generate refresh token for token renewal
        
        Args:
            user_data: User information to include in token
            
        Returns:
            JWT refresh token string
        """
        try:
            payload = {
                "user_id": user_data.get("user_id"),
                "session_id": user_data.get("session_id"),
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expiry_days),
                "type": "refresh"
            }
            
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.info(f"Generated refresh token for user: {user_data.get('user_id')}")
            return token
            
        except Exception as e:
            logger.error(f"Error generating refresh token: {str(e)}")
            raise
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload or None if invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error verifying token: {str(e)}")
            return None
    
    def is_token_expired(self, token: str) -> bool:
        """
        Check if token is expired
        
        Args:
            token: JWT token string
            
        Returns:
            True if expired, False otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                exp_datetime = datetime.fromtimestamp(exp_timestamp)
                return datetime.utcnow() > exp_datetime
            return True
            
        except jwt.ExpiredSignatureError:
            return True
        except Exception:
            return True
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """
        Generate new access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token or None if refresh token invalid
        """
        try:
            payload = self.verify_token(refresh_token)
            if not payload or payload.get("type") != "refresh":
                logger.warning("Invalid refresh token")
                return None
            
            # Generate new access token with same user data
            user_data = {
                "user_id": payload.get("user_id"),
                "session_id": payload.get("session_id"),
                "email": payload.get("email"),
                "phone": payload.get("phone")
            }
            
            return self.generate_access_token(user_data)
            
        except Exception as e:
            logger.error(f"Error refreshing access token: {str(e)}")
            return None
    
    def extract_user_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Extract user information from valid token
        
        Args:
            token: JWT token string
            
        Returns:
            User data dictionary or None if invalid
        """
        payload = self.verify_token(token)
        if not payload:
            return None
        
        return {
            "user_id": payload.get("user_id"),
            "session_id": payload.get("session_id"),
            "email": payload.get("email"),
            "phone": payload.get("phone"),
            "auth_method": payload.get("auth_method"),
            "token_type": payload.get("type")
        }

# Global JWT manager instance
jwt_manager = JWTManager()
