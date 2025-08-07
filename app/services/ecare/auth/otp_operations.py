"""
OTP Operations Handler
Manages OTP generation, verification, and related operations
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import secrets
import string
import hashlib
import httpx
import asyncio


class OTPOperationsHandler:
    """Handles all OTP-related operations"""
    
    def __init__(self, auth_handler):
        self.auth_handler = auth_handler
    
    async def generate_and_store_otp_distributed(self, session_token: str, user_id: int, contact_method: str) -> Dict[str, Any]:
        """Generate OTP and store it in database for stateless distributed system"""
        from app.core.database import db
        
        try:
            # Check rate limiting first (contact method based)
            identifier_type = "email" if "@" in contact_method else "phone"
            channel_type = "email" if "@" in contact_method else "sms"  # Database expects 'sms' for phone numbers
            rate_limit_check = await self.auth_handler.rate_limiting.check_otp_rate_limit(contact_method, identifier_type)
            
            if not rate_limit_check["allowed"]:
                return {
                    "success": False,
                    "error": "Rate limit exceeded",
                    "message": f"Too many OTP requests. Try again in {rate_limit_check.get('retry_after', 3600) // 60} minutes",
                    "retry_after": rate_limit_check.get("retry_after", 3600)
                }
            
            # Expire any existing pending OTPs for this session
            await db.execute(
                "UPDATE otp_requests SET status = 'expired' WHERE session_id = $1 AND status = 'pending'",
                session_token
            )
            
            # Generate secure 6-digit OTP
            otp_code = self.auth_handler.auth_utils.generate_secure_otp()
            
            # Hash the OTP for storage security
            salt = self.auth_handler.auth_utils.generate_salt()
            hashed_otp = self.auth_handler.auth_utils.hash_otp(otp_code, salt)
            
            # Store OTP in database with expiration (10 minutes)
            expiry_time = datetime.utcnow() + timedelta(minutes=10)
            
            # Generate shorter OTP ID that fits in varchar(50)
            import secrets
            short_otp_id = f"otp_{secrets.token_hex(8)}"  # Much shorter: otp_1234567890abcdef
            
            await db.execute("""
                INSERT INTO otp_requests (otp_id, session_id, identifier, channel, otp_hash, salt, 
                                        expires_at, attempts_left, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, 1, 'pending', $8)
            """, short_otp_id, session_token, contact_method, channel_type, hashed_otp, salt, 
            expiry_time, datetime.utcnow())
            
            print(f"DEBUG: OTP stored for session {session_token}, user {user_id}, contact {contact_method}")
            
            # Record the rate limit (contact method based)
            await self.auth_handler.rate_limiting.record_otp_request(contact_method, identifier_type)
            
            return {
                "success": True,
                "otp_code": otp_code,  # Return plaintext OTP for sending
                "expires_at": expiry_time.isoformat(),
                "contact_method": contact_method
            }
            
        except Exception as e:
            print(f"ERROR: Failed to generate OTP: {e}")
            return {
                "success": False,
                "error": "Generation failed",
                "message": f"Failed to generate OTP: {str(e)}"
            }

    async def verify_otp_from_database(self, session_token: str, otp_input: str) -> Dict[str, Any]:
        """Verify OTP against database record (stateless)"""
        from app.core.database import db
        
        try:
            # Get the pending OTP record for this session
            result = await db.fetch("""
                SELECT id, otp_hash, salt, identifier, expires_at, attempts_left
                FROM otp_requests 
                WHERE session_id = $1 AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
            """, session_token)
            
            if not result:
                return {
                    "valid": False,
                    "error": "No pending OTP found",
                    "expired": True
                }
            
            otp_record = result[0]
            
            # Check if OTP is expired
            if datetime.utcnow() > otp_record["expires_at"]:
                # Mark as expired
                await db.execute(
                    "UPDATE otp_requests SET status = 'expired' WHERE id = $1",
                    otp_record["id"]
                )
                return {
                    "valid": False,
                    "error": "OTP expired",
                    "expired": True
                }
            
            # Check if already used maximum attempts (we allow only 1 attempt)
            if otp_record["attempts_left"] <= 0:
                # Mark as expired due to too many attempts
                await db.execute(
                    "UPDATE otp_requests SET status = 'expired' WHERE id = $1",
                    otp_record["id"]
                )
                return {
                    "valid": False,
                    "error": "Maximum attempts exceeded",
                    "expired": True
                }
            
            # Decrement attempt count
            await db.execute(
                "UPDATE otp_requests SET attempts_left = attempts_left - 1 WHERE id = $1",
                otp_record["id"]
            )
            
            # Verify the OTP hash
            is_valid = self.auth_handler.auth_utils.verify_otp_hash(
                otp_input, otp_record["otp_hash"], otp_record["salt"]
            )
            
            if is_valid:
                return {
                    "valid": True,
                    "otp_id": otp_record["id"],
                    "contact_method": otp_record["identifier"]
                }
            else:
                # Wrong OTP - mark as expired since we only allow 1 attempt
                await db.execute(
                    "UPDATE otp_requests SET status = 'expired' WHERE id = $1",
                    otp_record["id"]
                )
                return {
                    "valid": False,
                    "error": "Invalid OTP",
                    "wrong_code": True
                }
            
        except Exception as e:
            print(f"ERROR: OTP verification failed: {e}")
            return {
                "valid": False,
                "error": f"Verification failed: {str(e)}"
            }

    async def mark_otp_as_verified(self, otp_id: int) -> None:
        """Mark OTP as successfully verified"""
        from app.core.database import db
        
        try:
            await db.execute(
                "UPDATE otp_requests SET status = 'verified', verified_at = $1 WHERE id = $2",
                datetime.utcnow(), otp_id
            )
            print(f"DEBUG: OTP {otp_id} marked as verified")
        except Exception as e:
            print(f"ERROR: Failed to mark OTP as verified: {e}")

    async def send_otp_via_service(self, contact_method: str, otp_code: str, session_token: str) -> bool:
        """Send OTP via external service (email or SMS)"""
        try:
            if "@" in contact_method:
                # Send via email
                success = await self._send_email_otp(contact_method, otp_code, session_token)
            else:
                # Send via SMS
                success = await self._send_sms_otp(contact_method, otp_code, session_token)
            
            print(f"DEBUG: OTP sending {'succeeded' if success else 'failed'} for {contact_method}")
            return success
            
        except Exception as e:
            print(f"ERROR: Failed to send OTP to {contact_method}: {e}")
            return False

    async def _send_email_otp(self, email: str, otp_code: str, session_token: str) -> bool:
        """Send OTP via email service"""
        try:
            # For now, we'll simulate email sending
            # In production, integrate with actual email service (SendGrid, SES, etc.)
            
            print(f"📧 EMAIL OTP: Sending {otp_code} to {email} (session: {session_token})")
            
            # Simulate API call delay
            await asyncio.sleep(0.5)
            
            # TODO: Replace with actual email service integration
            # Example with httpx:
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(
            #         "https://api.sendgrid.com/v3/mail/send",
            #         headers={"Authorization": f"Bearer {API_KEY}"},
            #         json={
            #             "personalizations": [{"to": [{"email": email}]}],
            #             "from": {"email": "noreply@thaliya.com"},
            #             "subject": "Your Verification Code",
            #             "content": [{"type": "text/plain", "value": f"Your verification code is: {otp_code}"}]
            #         }
            #     )
            #     return response.status_code == 202
            
            return True  # Simulate success for development
            
        except Exception as e:
            print(f"ERROR: Email sending failed: {e}")
            return False

    async def _send_sms_otp(self, phone: str, otp_code: str, session_token: str) -> bool:
        """Send OTP via SMS service"""
        try:
            # For now, we'll simulate SMS sending
            # In production, integrate with actual SMS service (Twilio, AWS SNS, etc.)
            
            print(f"📱 SMS OTP: Sending {otp_code} to {phone} (session: {session_token})")
            
            # Simulate API call delay
            await asyncio.sleep(0.5)
            
            # TODO: Replace with actual SMS service integration
            # Example with httpx:
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(
            #         "https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json",
            #         auth=(ACCOUNT_SID, AUTH_TOKEN),
            #         data={
            #             "To": phone,
            #             "From": "+1234567890",  # Your Twilio number
            #             "Body": f"Your verification code is: {otp_code}"
            #         }
            #     )
            #     return response.status_code == 201
            
            return True  # Simulate success for development
            
        except Exception as e:
            print(f"ERROR: SMS sending failed: {e}")
            return False

    async def cleanup_expired_otps(self) -> None:
        """Cleanup expired OTP records (maintenance task)"""
        from app.core.database import db
        
        try:
            # Delete OTP records older than 24 hours
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            result = await db.execute(
                "DELETE FROM otp_requests WHERE created_at < $1",
                cutoff_time
            )
            
            print(f"DEBUG: Cleaned up expired OTP records")
            
        except Exception as e:
            print(f"ERROR: OTP cleanup failed: {e}")

    async def get_otp_statistics(self, contact_method: str) -> Dict[str, Any]:
        """Get OTP statistics for a contact method"""
        from app.core.database import db
        
        try:
            # Get statistics for the last 24 hours
            last_24h = datetime.utcnow() - timedelta(hours=24)
            
            result = await db.fetch("""
                SELECT 
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN status = 'verified' THEN 1 END) as verified_count,
                    COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired_count,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_count
                FROM otp_requests 
                WHERE contact_method = $1 AND created_at > $2
            """, contact_method, last_24h)
            
            if result:
                stats = dict(result[0])
                stats["success_rate"] = (
                    stats["verified_count"] / stats["total_requests"] * 100 
                    if stats["total_requests"] > 0 else 0
                )
                return stats
            
            return {
                "total_requests": 0,
                "verified_count": 0,
                "expired_count": 0,
                "pending_count": 0,
                "success_rate": 0
            }
            
        except Exception as e:
            print(f"ERROR: Failed to get OTP statistics: {e}")
            return {}
