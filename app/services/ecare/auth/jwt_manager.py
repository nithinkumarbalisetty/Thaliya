"""
JWT Token Manager
Handles JWT token generation and validation for authentication
"""

import os
import jwt
from typing import Dict, Any
from datetime import datetime, timedelta


class JWTManager:
    """Manages JWT token operations for authentication"""
    
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    
    def generate_jwt_token(self, payload: Dict[str, Any]) -> str:
        """Generate JWT token"""
        try:
            # Add expiration if not present
            if "exp" not in payload:
                payload["exp"] = datetime.utcnow() + timedelta(hours=24)
            
            return jwt.encode(payload, self.secret_key, algorithm="HS256")
        except Exception as e:
            print(f"Error generating JWT: {e}")
            return None
    
    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            return jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            print("JWT token has expired")
            return None
        except jwt.InvalidTokenError:
            print("Invalid JWT token")
            return None
        except Exception as e:
            print(f"Error verifying JWT: {e}")
            return None
    
    def create_user_token(self, user_id: int, session_id: str) -> str:
        """Create JWT token for authenticated user"""
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "authenticated_at": datetime.utcnow().isoformat()
        }
        return self.generate_jwt_token(payload)
