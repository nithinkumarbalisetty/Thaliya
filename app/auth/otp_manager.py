"""
Secure OTP Manager with Email and SMS Support
Implements industry-standard OTP generation and verification
"""

import secrets
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Literal
from app.core.database import db
import logging

logger = logging.getLogger(__name__)

OTPChannel = Literal["email", "sms"]

class SecureOTPManager:
    """
    Secure OTP Manager supporting both email and SMS channels
    """
    
    def __init__(self):
        self.max_attempts = 3
        self.otp_validity_minutes = 5
        self.rate_limit_window_minutes = 60  # 1 hour window
        self.max_requests_per_window = 5  # Max 5 OTP requests per hour
        self.block_duration_minutes = 30  # Block for 30 minutes after rate limit exceeded
    
    def generate_secure_otp(self, identifier: str, channel: OTPChannel, session_id: str) -> Dict[str, Any]:
        """
        Generate cryptographically secure OTP for email or SMS
        
        Args:
            identifier: Email address or phone number
            channel: "email" or "sms"
            session_id: Session identifier
            
        Returns:
            Dict containing OTP data (only otp_code should be sent, rest stored)
        """
        try:
            # Validate identifier format
            if not self._validate_identifier(identifier, channel):
                raise ValueError(f"Invalid {channel} format: {identifier}")
            
            # Generate secure 6-digit OTP
            otp_code = str(secrets.randbelow(900000) + 100000)  # 100000-999999
            
            # Create unique salt for this OTP
            salt = secrets.token_hex(16)
            
            # Hash the OTP for storage (never store plain OTP)
            otp_hash = hashlib.sha256(f"{otp_code}{salt}".encode()).hexdigest()
            
            # Generate expiration time
            expires_at = datetime.utcnow() + timedelta(minutes=self.otp_validity_minutes)
            
            # Create unique OTP ID for tracking
            otp_id = secrets.token_hex(8)
            
            # Format identifier for consistent storage
            formatted_identifier = self._format_identifier(identifier, channel)
            
            otp_data = {
                "otp_code": otp_code,  # Only return this, don't store it
                "otp_hash": otp_hash,  # Store this in database
                "salt": salt,          # Store this in database
                "otp_id": otp_id,      # Store this in database
                "session_id": session_id,
                "identifier": formatted_identifier,
                "channel": channel,
                "expires_at": expires_at,
                "attempts_left": self.max_attempts,
                "created_at": datetime.utcnow(),
                "status": "pending"
            }
            
            logger.info(f"Generated OTP for {channel}: {formatted_identifier}")
            return otp_data
            
        except Exception as e:
            logger.error(f"Error generating OTP: {str(e)}")
            raise
    
    
    def verify_otp(self, user_otp: str, stored_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify OTP with comprehensive security checks
        
        Args:
            user_otp: OTP code provided by user
            stored_data: Stored OTP data from database
            
        Returns:
            Dict with verification result and details
        """
        try:
            # Input validation
            if not user_otp or not isinstance(user_otp, str):
                return {
                    "valid": False,
                    "reason": "invalid_input",
                    "message": "Please provide a valid OTP code."
                }
            
            # Clean user input
            user_otp = user_otp.strip().replace(" ", "").replace("-", "")
            
            # Check OTP format (6 digits)
            if not re.match(r'^\d{6}$', user_otp):
                return {
                    "valid": False,
                    "reason": "invalid_format",
                    "message": "OTP must be 6 digits."
                }
            
            # Check if OTP is expired
            expires_at = stored_data.get("expires_at")
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            
            if datetime.utcnow() > expires_at:
                return {
                    "valid": False,
                    "reason": "expired",
                    "message": "OTP has expired. Please request a new one."
                }
            
            # Check if attempts are exhausted
            attempts_left = stored_data.get("attempts_left", 0)
            if attempts_left <= 0:
                return {
                    "valid": False,
                    "reason": "max_attempts",
                    "message": "Maximum verification attempts exceeded. Please request a new OTP."
                }
            
            # Hash the provided OTP with stored salt
            salt = stored_data.get("salt", "")
            provided_hash = hashlib.sha256(f"{user_otp}{salt}".encode()).hexdigest()
            stored_hash = stored_data.get("otp_hash", "")
            
            # Compare hashes using timing-safe comparison
            if secrets.compare_digest(provided_hash, stored_hash):
                logger.info(f"OTP verified successfully for {stored_data.get('channel')}: {stored_data.get('identifier')}")
                return {
                    "valid": True,
                    "reason": "success",
                    "message": "OTP verified successfully"
                }
            else:
                remaining_attempts = attempts_left - 1
                logger.warning(f"Invalid OTP attempt for {stored_data.get('channel')}: {stored_data.get('identifier')}, {remaining_attempts} attempts remaining")
                return {
                    "valid": False,
                    "reason": "invalid",
                    "message": f"Invalid OTP. {remaining_attempts} attempts remaining.",
                    "attempts_remaining": remaining_attempts
                }
                
        except Exception as e:
            logger.error(f"Error verifying OTP: {str(e)}")
            return {
                "valid": False,
                "reason": "error",
                "message": "Unable to verify OTP. Please try again."
            }
    
    async def check_rate_limit(self, identifier: str, channel: OTPChannel) -> Dict[str, Any]:
        """
        Check if identifier has exceeded OTP request rate limit
        
        Args:
            identifier: Email address or phone number
            channel: "email" or "sms"
            
        Returns:
            Dict with rate limit status
        """
        try:
            formatted_identifier = self._format_identifier(identifier, channel)
            
            # Check current rate limit status
            result = await db.fetch(
                """
                SELECT request_count, last_request, blocked_until, created_at
                FROM otp_rate_limits 
                WHERE identifier = $1 AND identifier_type = $2
                AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                formatted_identifier, channel
            )
            
            if not result:
                return {"allowed": True, "reason": "no_history"}
            
            rate_data = dict(result[0])
            
            # Check if currently blocked
            blocked_until = rate_data.get("blocked_until")
            if blocked_until and datetime.utcnow() < blocked_until:
                wait_minutes = int((blocked_until - datetime.utcnow()).total_seconds() / 60) + 1
                return {
                    "allowed": False, 
                    "reason": "blocked",
                    "wait_minutes": wait_minutes,
                    "message": f"Too many OTP requests. Please try again in {wait_minutes} minutes."
                }
            
            # Check request count in the current window
            request_count = rate_data.get("request_count", 0)
            if request_count >= self.max_requests_per_window:
                # Block the identifier
                blocked_until = datetime.utcnow() + timedelta(minutes=self.block_duration_minutes)
                await self._update_rate_limit_block(formatted_identifier, channel, blocked_until)
                
                return {
                    "allowed": False,
                    "reason": "rate_limit_exceeded", 
                    "wait_minutes": self.block_duration_minutes,
                    "message": f"Too many OTP requests. Please try again in {self.block_duration_minutes} minutes."
                }
            
            return {
                "allowed": True, 
                "reason": "within_limit",
                "requests_used": request_count,
                "requests_remaining": self.max_requests_per_window - request_count
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            # Fail open for availability, but log the error
            return {"allowed": True, "reason": "error_check_failed"}
    
    async def store_otp_request(self, otp_data: Dict[str, Any]) -> bool:
        """
        Store OTP request in database with rate limiting
        
        Args:
            otp_data: OTP data from generate_secure_otp
            
        Returns:
            Success status
        """
        try:
            # Store OTP request
            await db.execute(
                """
                INSERT INTO otp_requests 
                (otp_id, session_id, identifier, channel, otp_hash, salt, 
                 expires_at, attempts_left, status, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                otp_data["otp_id"], otp_data["session_id"], otp_data["identifier"],
                otp_data["channel"], otp_data["otp_hash"], otp_data["salt"],
                otp_data["expires_at"], otp_data["attempts_left"], otp_data["status"],
                otp_data["created_at"]
            )
            
            # Update rate limiting
            await db.execute(
                """
                INSERT INTO otp_rate_limits (identifier, identifier_type, request_count, last_request)
                VALUES ($1, $2, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (identifier, identifier_type) 
                DO UPDATE SET
                    request_count = CASE 
                        WHEN otp_rate_limits.created_at < CURRENT_TIMESTAMP - INTERVAL '1 hour' 
                        THEN 1 
                        ELSE otp_rate_limits.request_count + 1 
                    END,
                    last_request = CURRENT_TIMESTAMP,
                    created_at = CASE 
                        WHEN otp_rate_limits.created_at < CURRENT_TIMESTAMP - INTERVAL '1 hour' 
                        THEN CURRENT_TIMESTAMP 
                        ELSE otp_rate_limits.created_at 
                    END
                """,
                otp_data["identifier"], otp_data["channel"]
            )
            
            logger.info(f"OTP request stored for {otp_data['channel']}: {otp_data['identifier']}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing OTP request: {str(e)}")
            return False
    
    async def get_otp_request(self, otp_id: str) -> Optional[Dict[str, Any]]:
        """
        Get OTP request data by OTP ID
        
        Args:
            otp_id: Unique OTP identifier
            
        Returns:
            OTP data or None if not found
        """
        try:
            result = await db.fetch(
                """
                SELECT otp_id, session_id, identifier, channel, otp_hash, salt, 
                       expires_at, attempts_left, status, created_at
                FROM otp_requests 
                WHERE otp_id = $1 AND status IN ('pending', 'partially_used')
                """,
                otp_id
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            logger.error(f"Error getting OTP request: {str(e)}")
            return None
    
    async def update_otp_attempts(self, otp_id: str, attempts_left: int) -> bool:
        """
        Update OTP attempt count
        
        Args:
            otp_id: Unique OTP identifier
            attempts_left: Remaining attempts
            
        Returns:
            Success status
        """
        try:
            status = "blocked" if attempts_left <= 0 else "partially_used"
            await db.execute(
                """
                UPDATE otp_requests 
                SET attempts_left = $2, status = $3, last_attempt = CURRENT_TIMESTAMP
                WHERE otp_id = $1
                """,
                otp_id, attempts_left, status
            )
            
            logger.info(f"Updated OTP attempts for {otp_id}: {attempts_left} remaining")
            return True
            
        except Exception as e:
            logger.error(f"Error updating OTP attempts: {str(e)}")
            return False
    
    async def mark_otp_verified(self, otp_id: str) -> bool:
        """
        Mark OTP as successfully verified
        
        Args:
            otp_id: Unique OTP identifier
            
        Returns:
            Success status
        """
        try:
            await db.execute(
                """
                UPDATE otp_requests 
                SET status = 'verified', verified_at = CURRENT_TIMESTAMP
                WHERE otp_id = $1
                """,
                otp_id
            )
            
            logger.info(f"OTP marked as verified: {otp_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error marking OTP verified: {str(e)}")
            return False
    
    async def cleanup_expired_otps(self) -> int:
        """
        Clean up expired OTP requests (maintenance function)
        
        Returns:
            Number of cleaned up records
        """
        try:
            result = await db.execute(
                """
                DELETE FROM otp_requests 
                WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 hour'
                AND status != 'verified'
                """
            )
            
            # Also clean up old rate limit records
            await db.execute(
                """
                DELETE FROM otp_rate_limits 
                WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '24 hours'
                AND blocked_until IS NULL
                """
            )
            
            logger.info(f"Cleaned up expired OTP records")
            return 0  # asyncpg doesn't return row count for DELETE
            
        except Exception as e:
            logger.error(f"Error cleaning up expired OTPs: {str(e)}")
            return 0
    
    def _validate_identifier(self, identifier: str, channel: OTPChannel) -> bool:
        """Validate email or phone number format"""
        if channel == "email":
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(email_pattern, identifier))
        elif channel == "sms":
            # Accept various phone formats: +1234567890, 1234567890, (123) 456-7890, etc.
            phone_pattern = r'^[\+]?[1-9][\d\s\-\(\)]{8,15}$'
            return bool(re.match(phone_pattern, identifier.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")))
        return False
    
    def _format_identifier(self, identifier: str, channel: OTPChannel) -> str:
        """Format identifier for consistent storage"""
        if channel == "email":
            return identifier.lower().strip()
        elif channel == "sms":
            # Remove all non-digit characters except +
            phone = re.sub(r'[^\d+]', '', identifier)
            # Ensure + prefix for international format
            if not phone.startswith('+'):
                # Assume US number if no country code
                phone = '+1' + phone
            return phone
        return identifier
    
    async def _update_rate_limit_block(self, identifier: str, channel: OTPChannel, blocked_until: datetime) -> bool:
        """Update rate limit record with block information"""
        try:
            await db.execute(
                """
                UPDATE otp_rate_limits 
                SET blocked_until = $3 
                WHERE identifier = $1 AND identifier_type = $2
                """,
                identifier, channel, blocked_until
            )
            return True
        except Exception as e:
            logger.error(f"Error updating rate limit block: {str(e)}")
            return False