"""
OTP Manager
Handles OTP generation, storage, and verification
"""

import secrets
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.services.otp_service import OTPService
from .auth_utils import AuthUtils


class OTPManager:
    """Manages OTP operations for authentication"""
    
    def __init__(self):
        self.auth_utils = AuthUtils()
        self.otp_service = OTPService()
        self.otp_expiry_minutes = 10
    
    async def generate_and_store_otp(
        self,
        contact_method: str,
        user_id: int,
        db
    ) -> Dict[str, Any]:
        """
        Generate and store OTP in database with distributed approach
        """
        print(f"[DEBUG] Generating OTP for contact method: {contact_method}")
        
        try:
            # Generate OTP and salt
            otp = self.auth_utils.generate_secure_otp()
            salt = self.auth_utils.generate_salt()
            
            print(f"[DEBUG] Generated OTP: {otp}, Salt: {salt}")
            
            # Hash OTP with salt
            hashed_otp = self.auth_utils.hash_otp(otp, salt)
            
            print(f"[DEBUG] Hashed OTP: {hashed_otp}")
            
            # Calculate expiry time
            expiry_time = datetime.utcnow() + timedelta(minutes=self.otp_expiry_minutes)
            
            # Clean up any existing OTP for this contact method
            await self._cleanup_existing_otp(contact_method, db)
            
            # Insert new OTP record
            await db.execute(
                """
                INSERT INTO otp_requests (
                    contact_method, hashed_otp, salt, 
                    expiry_time, attempts, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                contact_method, hashed_otp, salt,
                expiry_time, 0, datetime.utcnow()
            )
            
            print(f"[DEBUG] OTP stored in database for {contact_method}")
            
            # Send OTP via appropriate service
            send_result = self._send_otp(contact_method, otp)
            
            if not send_result:
                # If sending fails, clean up the stored OTP
                await self._cleanup_existing_otp(contact_method, db)
                return {
                    "success": False,
                    "message": "Failed to send OTP"
                }
            
            return {
                "success": True,
                "message": "OTP generated and sent successfully"
            }
            
        except Exception as e:
            print(f"[ERROR] Failed to generate and store OTP: {e}")
            return {
                "success": False,
                "message": f"Failed to generate OTP: {str(e)}"
            }
    
    async def verify_otp(
        self,
        contact_method: str,
        otp: str,
        db
    ) -> Dict[str, Any]:
        """
        Verify OTP from database
        """
        print(f"[DEBUG] Verifying OTP for contact method: {contact_method}")
        
        try:
            # Get OTP record
            result = await db.fetch(
                """
                SELECT hashed_otp, salt, expiry_time, attempts
                FROM otp_requests 
                WHERE contact_method = $1
                """,
                contact_method
            )
            
            if not result:
                print(f"[DEBUG] No OTP record found for {contact_method}")
                return {
                    "success": False,
                    "message": "No OTP found for this contact method"
                }
            
            hashed_otp, salt, expiry_time, attempts = result[0]
            
            print(f"[DEBUG] Found OTP record - Hash: {hashed_otp}, Salt: {salt}, Expiry: {expiry_time}, Attempts: {attempts}")
            
            # Check if OTP is expired
            if datetime.utcnow() > expiry_time:
                print(f"[DEBUG] OTP expired for {contact_method}")
                await self._cleanup_existing_otp(contact_method, db)
                return {
                    "success": False,
                    "message": "OTP has expired"
                }
            
            # Check attempts (single attempt policy)
            if attempts >= 1:
                print(f"[DEBUG] OTP attempt limit exceeded for {contact_method}")
                await self._cleanup_existing_otp(contact_method, db)
                return {
                    "success": False,
                    "message": "OTP attempt limit exceeded"
                }
            
            # Verify OTP
            is_valid = self.auth_utils.verify_otp_hash(otp, hashed_otp, salt)
            
            # Update attempts count
            await db.execute(
                """
                UPDATE otp_requests 
                SET attempts = attempts + 1
                WHERE contact_method = $1
                """,
                contact_method
            )
            
            print(f"[DEBUG] OTP verification result: {is_valid}")
            
            if is_valid:
                print(f"[DEBUG] OTP verification successful for {contact_method}")
                return {
                    "success": True,
                    "message": "OTP verified successfully"
                }
            else:
                print(f"[DEBUG] OTP verification failed for {contact_method}")
                # Clean up after failed verification (single attempt policy)
                await self._cleanup_existing_otp(contact_method, db)
                return {
                    "success": False,
                    "message": "Invalid OTP"
                }
                
        except Exception as e:
            print(f"[ERROR] OTP verification failed: {e}")
            return {
                "success": False,
                "message": f"OTP verification error: {str(e)}"
            }
    
    async def cleanup_otp_record(self, contact_method: str, db):
        """Clean up OTP record after successful authentication"""
        try:
            await self._cleanup_existing_otp(contact_method, db)
            print(f"[DEBUG] Cleaned up OTP record for {contact_method}")
        except Exception as e:
            print(f"[ERROR] Failed to cleanup OTP record: {e}")
    
    async def _cleanup_existing_otp(self, contact_method: str, db):
        """Remove existing OTP record for contact method"""
        try:
            await db.execute(
                """
                DELETE FROM otp_requests 
                WHERE contact_method = $1
                """,
                contact_method
            )
            print(f"[DEBUG] Cleaned up existing OTP for {contact_method}")
        except Exception as e:
            print(f"[ERROR] Failed to cleanup existing OTP: {e}")
    
    def _send_otp(self, contact_method: str, otp: str) -> bool:
        """Send OTP via appropriate service"""
        try:
            identifier_type = self.auth_utils.determine_identifier_type(contact_method)
            
            if identifier_type == "email":
                return self.otp_service.send_email_otp(contact_method, otp)
            elif identifier_type == "phone":
                return self.otp_service.send_sms_otp(contact_method, otp)
            else:
                print(f"[ERROR] Unknown identifier type: {identifier_type}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to send OTP: {e}")
            return False
