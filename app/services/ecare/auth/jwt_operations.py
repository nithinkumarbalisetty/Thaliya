"""
JWT Operations Handler
Manages JWT token creation, validation, and related operations
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import jwt
import os


class JWTOperationsHandler:
    """Handles JWT token operations"""
    
    def __init__(self, auth_handler):
        self.auth_handler = auth_handler
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60 * 24  # 24 hours
        self.refresh_token_expire_days = 30  # 30 days
    
    def generate_token(self, payload: Dict[str, Any], token_type: str = "access") -> str:
        """Generate JWT token with expiration"""
        try:
            # Add standard claims
            now = datetime.utcnow()
            
            if token_type == "access":
                expire_delta = timedelta(minutes=self.access_token_expire_minutes)
            elif token_type == "refresh":
                expire_delta = timedelta(days=self.refresh_token_expire_days)
            else:
                expire_delta = timedelta(minutes=self.access_token_expire_minutes)
            
            token_payload = {
                **payload,
                "iat": now,  # Issued at
                "exp": now + expire_delta,  # Expiration
                "type": token_type,
                "iss": "thaliya-auth"  # Issuer
            }
            
            token = jwt.encode(token_payload, self.secret_key, algorithm=self.algorithm)
            
            print(f"DEBUG: Generated {token_type} JWT token for user {payload.get('user_id')}")
            return token
            
        except Exception as e:
            print(f"ERROR: JWT token generation failed: {e}")
            raise Exception(f"Token generation failed: {str(e)}")
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if token is expired
            exp_timestamp = payload.get("exp")
            if exp_timestamp and datetime.utcnow().timestamp() > exp_timestamp:
                return {
                    "valid": False,
                    "error": "Token expired",
                    "expired": True
                }
            
            return {
                "valid": True,
                "payload": payload,
                "user_id": payload.get("user_id"),
                "session_id": payload.get("session_id"),
                "token_type": payload.get("type", "access")
            }
            
        except jwt.ExpiredSignatureError:
            return {
                "valid": False,
                "error": "Token expired",
                "expired": True
            }
        except jwt.InvalidTokenError as e:
            return {
                "valid": False,
                "error": f"Invalid token: {str(e)}",
                "invalid": True
            }
        except Exception as e:
            print(f"ERROR: JWT verification failed: {e}")
            return {
                "valid": False,
                "error": f"Token verification failed: {str(e)}"
            }
    
    def create_user_token_pair(self, user_id: int, session_id: str, additional_data: Dict[str, Any] = None) -> Dict[str, str]:
        """Create both access and refresh tokens for a user"""
        try:
            base_payload = {
                "user_id": user_id,
                "session_id": session_id,
                "authenticated_at": datetime.utcnow().isoformat()
            }
            
            if additional_data:
                base_payload.update(additional_data)
            
            access_token = self.generate_token(base_payload, "access")
            refresh_token = self.generate_token(base_payload, "refresh")
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": self.access_token_expire_minutes * 60  # in seconds
            }
            
        except Exception as e:
            print(f"ERROR: Token pair creation failed: {e}")
            raise Exception(f"Token pair creation failed: {str(e)}")
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Generate new access token using refresh token"""
        try:
            # Verify refresh token
            verification = self.verify_token(refresh_token)
            
            if not verification["valid"]:
                return {
                    "success": False,
                    "error": verification["error"]
                }
            
            payload = verification["payload"]
            
            # Check if it's actually a refresh token
            if payload.get("type") != "refresh":
                return {
                    "success": False,
                    "error": "Invalid token type for refresh"
                }
            
            # Generate new access token with same user data
            new_access_token = self.generate_token({
                "user_id": payload["user_id"],
                "session_id": payload["session_id"],
                "authenticated_at": payload.get("authenticated_at")
            }, "access")
            
            return {
                "success": True,
                "access_token": new_access_token,
                "token_type": "Bearer",
                "expires_in": self.access_token_expire_minutes * 60
            }
            
        except Exception as e:
            print(f"ERROR: Token refresh failed: {e}")
            return {
                "success": False,
                "error": f"Token refresh failed: {str(e)}"
            }
    
    def extract_user_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Extract user information from token"""
        try:
            verification = self.verify_token(token)
            
            if not verification["valid"]:
                return None
            
            payload = verification["payload"]
            return {
                "user_id": payload.get("user_id"),
                "session_id": payload.get("session_id"),
                "authenticated_at": payload.get("authenticated_at"),
                "token_type": payload.get("type")
            }
            
        except Exception as e:
            print(f"ERROR: User extraction from token failed: {e}")
            return None
    
    def is_token_valid(self, token: str) -> bool:
        """Simple check if token is valid"""
        try:
            verification = self.verify_token(token)
            return verification["valid"]
        except:
            return False
    
    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """Get token expiration datetime"""
        try:
            verification = self.verify_token(token)
            
            if not verification["valid"]:
                return None
            
            exp_timestamp = verification["payload"].get("exp")
            if exp_timestamp:
                return datetime.utcfromtimestamp(exp_timestamp)
            
            return None
            
        except Exception as e:
            print(f"ERROR: Token expiry extraction failed: {e}")
            return None
    
    def create_temporary_token(self, data: Dict[str, Any], expire_minutes: int = 15) -> str:
        """Create a temporary token for specific operations (like password reset)"""
        try:
            payload = {
                **data,
                "type": "temporary",
                "purpose": data.get("purpose", "general")
            }
            
            # Override expiration for temporary tokens
            now = datetime.utcnow()
            token_payload = {
                **payload,
                "iat": now,
                "exp": now + timedelta(minutes=expire_minutes),
                "iss": "thaliya-auth"
            }
            
            token = jwt.encode(token_payload, self.secret_key, algorithm=self.algorithm)
            print(f"DEBUG: Generated temporary token for {data.get('purpose', 'general')}")
            return token
            
        except Exception as e:
            print(f"ERROR: Temporary token creation failed: {e}")
            raise Exception(f"Temporary token creation failed: {str(e)}")
    
    def blacklist_token(self, token: str) -> bool:
        """Add token to blacklist (implement with Redis or database in production)"""
        try:
            # TODO: Implement token blacklisting with Redis or database
            # For now, we'll just log the blacklisting
            verification = self.verify_token(token)
            if verification["valid"]:
                user_id = verification["payload"].get("user_id")
                print(f"DEBUG: Token blacklisted for user {user_id}")
                return True
            return False
        except Exception as e:
            print(f"ERROR: Token blacklisting failed: {e}")
            return False
    
    def validate_bearer_token(self, authorization_header: str) -> Dict[str, Any]:
        """Validate Bearer token from Authorization header"""
        try:
            if not authorization_header:
                return {
                    "valid": False,
                    "error": "Missing authorization header"
                }
            
            if not authorization_header.startswith("Bearer "):
                return {
                    "valid": False,
                    "error": "Invalid authorization format"
                }
            
            token = authorization_header.replace("Bearer ", "")
            return self.verify_token(token)
            
        except Exception as e:
            print(f"ERROR: Bearer token validation failed: {e}")
            return {
                "valid": False,
                "error": f"Bearer token validation failed: {str(e)}"
            }
