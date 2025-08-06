"""
Authentication Steps Manager
Handles the multi-step authentication process
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from .auth_utils import AuthUtils


class AuthStepsManager:
    """Manages multi-step authentication workflow"""
    
    def __init__(self):
        self.auth_utils = AuthUtils()
    
    async def handle_auth_step_1(
        self,
        contact_method: str,
        db,
        session_manager,
        rate_limiter,
        otp_manager,
        temp_storage
    ) -> Dict[str, Any]:
        """
        Handle authentication step 1 - Contact method validation and OTP generation
        """
        print(f"[DEBUG] Auth Step 1 - Contact method: {contact_method}")
        
        try:
            # Check rate limiting
            if not await rate_limiter.can_send_otp(contact_method, db):
                return {
                    "status": "error",
                    "message": "Too many requests. Please try again later.",
                    "code": 429
                }
            
            # Determine identifier type
            identifier_type = self.auth_utils.determine_identifier_type(contact_method)
            print(f"[DEBUG] Identifier type: {identifier_type}")
            
            # Check if user exists and validate contact method
            user = await self._find_user_by_contact(db, contact_method, identifier_type)
            if not user:
                return {
                    "status": "error",
                    "message": f"User not found with {identifier_type}: {contact_method}",
                    "code": 404
                }
            
            print(f"[DEBUG] User found: ID {user['id']}")
            
            # Create temporary authentication record
            temp_record_id = await temp_storage.create_temp_record(
                contact_method=contact_method,
                user_id=user['id'],
                step="auth_step_1",
                db=db
            )
            
            if not temp_record_id:
                return {
                    "status": "error",
                    "message": "Failed to initialize authentication process",
                    "code": 500
                }
            
            # Generate and send OTP
            otp_result = await otp_manager.generate_and_store_otp(
                contact_method=contact_method,
                user_id=user['id'],
                db=db
            )
            
            if not otp_result["success"]:
                return {
                    "status": "error",
                    "message": otp_result.get("message", "Failed to send OTP"),
                    "code": 500
                }
            
            # Update rate limiting
            await rate_limiter.record_otp_request(contact_method, db)
            
            return {
                "status": "success",
                "message": f"OTP sent to {contact_method}",
                "data": {
                    "temp_record_id": temp_record_id,
                    "contact_method": contact_method,
                    "identifier_type": identifier_type,
                    "next_step": "auth_step_2"
                }
            }
            
        except Exception as e:
            print(f"[ERROR] Auth Step 1 failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Authentication step 1 failed: {str(e)}",
                "code": 500
            }
    
    async def handle_auth_step_2(
        self,
        temp_record_id: str,
        otp: str,
        db,
        temp_storage,
        otp_manager,
        jwt_manager,
        session_manager
    ) -> Dict[str, Any]:
        """
        Handle authentication step 2 - OTP verification and session creation
        """
        print(f"[DEBUG] Auth Step 2 - Temp record ID: {temp_record_id}")
        
        try:
            # Retrieve temporary record
            temp_data = await temp_storage.get_temp_record(temp_record_id, db)
            if not temp_data:
                return {
                    "status": "error",
                    "message": "Invalid or expired authentication session",
                    "code": 400
                }
            
            contact_method = temp_data["contact_method"]
            user_id = temp_data["user_id"]
            
            print(f"[DEBUG] Retrieved temp data - Contact: {contact_method}, User ID: {user_id}")
            
            # Verify OTP
            otp_verification = await otp_manager.verify_otp(
                contact_method=contact_method,
                otp=otp,
                db=db
            )
            
            if not otp_verification["success"]:
                return {
                    "status": "error",
                    "message": otp_verification.get("message", "Invalid OTP"),
                    "code": 400
                }
            
            # Get user details
            user = await self._get_user_by_id(db, user_id)
            if not user:
                return {
                    "status": "error",
                    "message": "User not found",
                    "code": 404
                }
            
            # Create session
            session_id = session_manager.create_session(user_id)
            
            # Generate JWT token
            jwt_token = jwt_manager.create_user_token(user_id, session_id)
            
            # Clean up temporary records
            await temp_storage.cleanup_temp_record(temp_record_id, db)
            await otp_manager.cleanup_otp_record(contact_method, db)
            
            print(f"[DEBUG] Authentication successful for user {user_id}")
            
            return {
                "status": "success",
                "message": "Authentication successful",
                "data": {
                    "token": jwt_token,
                    "session_id": session_id,
                    "user": user
                }
            }
            
        except Exception as e:
            print(f"[ERROR] Auth Step 2 failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Authentication step 2 failed: {str(e)}",
                "code": 500
            }
    
    async def _find_user_by_contact(self, db, contact_method: str, identifier_type: str) -> Optional[Dict[str, Any]]:
        """Find user by contact method"""
        try:
            if identifier_type == "email":
                result = await db.fetch("SELECT * FROM users WHERE email = $1", contact_method)
            elif identifier_type == "phone":
                result = await db.fetch("SELECT * FROM users WHERE phone = $1", contact_method)
            else:
                return None
            
            if result:
                # Convert asyncpg record to dict
                user_record = result[0]
                return dict(user_record)
            return None
        except Exception as e:
            print(f"[ERROR] Error finding user: {e}")
            return None
    
    async def _get_user_by_id(self, db, user_id: int) -> Dict[str, Any]:
        """Get user by ID"""
        try:
            result = await db.fetch("SELECT * FROM users WHERE id = $1", user_id)
            if result:
                user_record = result[0]
                return dict(user_record)
            return None
        except Exception as e:
            print(f"[ERROR] Error getting user by ID: {e}")
            return None
