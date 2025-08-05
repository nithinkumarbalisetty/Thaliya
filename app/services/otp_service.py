"""
OTP Service Integration Module
Provides high-level OTP functionality for the application
"""

from typing import Dict, Any, Optional, Tuple
import logging
from datetime import datetime

from app.auth.otp_manager import SecureOTPManager, OTPChannel
from app.auth.email_service import email_service
from app.auth.sms_service import sms_service
from app.core.database import db

logger = logging.getLogger(__name__)

class OTPService:
    """
    High-level OTP service that orchestrates OTP generation, delivery, and verification
    """
    
    def __init__(self):
        self.otp_manager = SecureOTPManager()
        self.email_service = email_service
        self.sms_service = sms_service
    
    async def request_otp(self, identifier: str, channel: OTPChannel, session_id: str) -> Dict[str, Any]:
        """
        Complete OTP request workflow: generation, storage, and delivery
        
        Args:
            identifier: Email address or phone number
            channel: "email" or "sms"
            session_id: Session identifier
            
        Returns:
            Dict with request status and details
        """
        try:
            logger.info(f"Processing OTP request for {channel}: {identifier}")
            
            # Step 1: Check rate limiting
            rate_limit_result = await self.otp_manager.check_rate_limit(identifier, channel)
            
            if not rate_limit_result["allowed"]:
                logger.warning(f"Rate limit exceeded for {identifier}")
                return {
                    "success": False,
                    "reason": "rate_limited",
                    "message": rate_limit_result.get("message", "Rate limit exceeded"),
                    "wait_minutes": rate_limit_result.get("wait_minutes"),
                    "rate_limit_info": rate_limit_result
                }
            
            # Step 2: Generate secure OTP
            otp_data = self.otp_manager.generate_secure_otp(identifier, channel, session_id)
            
            # Step 3: Store OTP in database
            stored = await self.otp_manager.store_otp_request(otp_data)
            
            if not stored:
                logger.error(f"Failed to store OTP for {identifier}")
                return {
                    "success": False,
                    "reason": "storage_error",
                    "message": "Failed to process OTP request"
                }
            
            # Step 4: Deliver OTP via chosen channel
            delivery_result = await self._deliver_otp(
                identifier=identifier,
                channel=channel,
                otp_code=otp_data["otp_code"],
                session_id=session_id
            )
            
            # Step 5: Return response based on delivery status
            if delivery_result["success"]:
                logger.info(f"OTP delivered successfully to {identifier}")
                return {
                    "success": True,
                    "reason": "sent",
                    "message": f"OTP sent to your {channel}",
                    "otp_id": otp_data["otp_id"],
                    "channel": channel,
                    "expires_in_minutes": self.otp_manager.otp_validity_minutes,
                    "delivery_info": delivery_result,
                    "rate_limit_info": {
                        "requests_remaining": rate_limit_result.get("requests_remaining"),
                        "window_minutes": self.otp_manager.rate_limit_window_minutes
                    }
                }
            else:
                logger.error(f"Failed to deliver OTP to {identifier}: {delivery_result}")
                return {
                    "success": False,
                    "reason": "delivery_error",
                    "message": f"Failed to send OTP via {channel}",
                    "otp_id": otp_data["otp_id"],  # Still provide OTP ID for potential retry
                    "delivery_error": delivery_result
                }
                
        except Exception as e:
            logger.error(f"Error in OTP request workflow: {str(e)}")
            return {
                "success": False,
                "reason": "internal_error",
                "message": "Internal error processing OTP request",
                "error": str(e)
            }
    
    async def verify_otp(self, otp_code: str, otp_id: str, session_id: str) -> Dict[str, Any]:
        """
        Complete OTP verification workflow
        
        Args:
            otp_code: User-provided OTP code
            otp_id: OTP identifier
            session_id: Session identifier
            
        Returns:
            Dict with verification status and next steps
        """
        try:
            logger.info(f"Processing OTP verification for: {otp_id}")
            
            # Step 1: Get stored OTP data
            stored_data = await self.otp_manager.get_otp_request(otp_id)
            
            if not stored_data:
                logger.warning(f"OTP not found: {otp_id}")
                return {
                    "success": False,
                    "verified": False,
                    "reason": "not_found",
                    "message": "OTP not found or has expired"
                }
            
            # Step 2: Validate session
            if stored_data["session_id"] != session_id:
                logger.warning(f"Session mismatch for OTP: {otp_id}")
                return {
                    "success": False,
                    "verified": False,
                    "reason": "session_mismatch",
                    "message": "Invalid session"
                }
            
            # Step 3: Verify OTP code
            verification_result = self.otp_manager.verify_otp(otp_code, stored_data)
            
            if verification_result["valid"]:
                # Step 4a: Successful verification
                await self.otp_manager.mark_otp_verified(otp_id)
                
                # Update user verification status if applicable
                await self._update_user_verification_status(stored_data)
                
                logger.info(f"OTP verified successfully: {otp_id}")
                
                return {
                    "success": True,
                    "verified": True,
                    "reason": "verified",
                    "message": "OTP verified successfully",
                    "identifier": stored_data["identifier"],
                    "channel": stored_data["channel"],
                    "verified_at": datetime.utcnow().isoformat(),
                    "next_step": "authenticated"
                }
            else:
                # Step 4b: Failed verification
                attempts_remaining = verification_result.get("attempts_remaining")
                
                if attempts_remaining is not None:
                    await self.otp_manager.update_otp_attempts(otp_id, attempts_remaining)
                
                logger.warning(f"OTP verification failed: {otp_id} - {verification_result['reason']}")
                
                return {
                    "success": False,
                    "verified": False,
                    "reason": verification_result["reason"],
                    "message": verification_result["message"],
                    "attempts_remaining": attempts_remaining,
                    "otp_id": otp_id
                }
                
        except Exception as e:
            logger.error(f"Error in OTP verification workflow: {str(e)}")
            return {
                "success": False,
                "verified": False,
                "reason": "internal_error",
                "message": "Internal error during verification",
                "error": str(e)
            }
    
    async def resend_otp(self, otp_id: str, session_id: str) -> Dict[str, Any]:
        """
        Resend OTP using the same identifier and channel
        
        Args:
            otp_id: Original OTP identifier
            session_id: Session identifier
            
        Returns:
            Dict with resend status
        """
        try:
            logger.info(f"Processing OTP resend for: {otp_id}")
            
            # Get original OTP data
            stored_data = await self.otp_manager.get_otp_request(otp_id)
            
            if not stored_data:
                return {
                    "success": False,
                    "reason": "not_found",
                    "message": "Original OTP not found"
                }
            
            # Validate session
            if stored_data["session_id"] != session_id:
                return {
                    "success": False,
                    "reason": "session_mismatch",
                    "message": "Invalid session"
                }
            
            # Create new OTP request with same identifier and channel
            return await self.request_otp(
                identifier=stored_data["identifier"],
                channel=stored_data["channel"],
                session_id=session_id
            )
            
        except Exception as e:
            logger.error(f"Error in OTP resend workflow: {str(e)}")
            return {
                "success": False,
                "reason": "internal_error",
                "message": "Internal error during resend",
                "error": str(e)
            }
    
    async def get_otp_status(self, otp_id: str, session_id: str) -> Dict[str, Any]:
        """
        Get current status of an OTP request
        
        Args:
            otp_id: OTP identifier
            session_id: Session identifier
            
        Returns:
            Dict with OTP status
        """
        try:
            stored_data = await self.otp_manager.get_otp_request(otp_id)
            
            if not stored_data:
                return {
                    "found": False,
                    "reason": "not_found",
                    "message": "OTP not found"
                }
            
            if stored_data["session_id"] != session_id:
                return {
                    "found": False,
                    "reason": "session_mismatch",
                    "message": "Invalid session"
                }
            
            # Check if expired
            expires_at = stored_data["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            
            is_expired = datetime.utcnow() > expires_at
            
            return {
                "found": True,
                "otp_id": otp_id,
                "channel": stored_data["channel"],
                "identifier": stored_data["identifier"],
                "status": stored_data["status"],
                "attempts_left": stored_data["attempts_left"],
                "expires_at": expires_at.isoformat(),
                "is_expired": is_expired,
                "created_at": stored_data["created_at"].isoformat() if stored_data.get("created_at") else None
            }
            
        except Exception as e:
            logger.error(f"Error getting OTP status: {str(e)}")
            return {
                "found": False,
                "reason": "internal_error",
                "message": "Error retrieving OTP status",
                "error": str(e)
            }
    
    async def _deliver_otp(self, identifier: str, channel: OTPChannel, otp_code: str, session_id: str) -> Dict[str, Any]:
        """
        Internal method to deliver OTP via the specified channel
        
        Args:
            identifier: Email or phone number
            channel: "email" or "sms"
            otp_code: OTP code to send
            session_id: Session identifier
            
        Returns:
            Dict with delivery status
        """
        try:
            if channel == "email":
                # Check if email service is configured
                email_config_check = self.email_service.validate_email_config()
                
                if email_config_check["valid"]:
                    return await self.email_service.send_otp_email(identifier, otp_code, session_id)
                else:
                    # Development mode - log OTP instead of sending
                    logger.info(f"DEV MODE - Email OTP for {identifier}: {otp_code}")
                    return {
                        "success": True,
                        "reason": "dev_mode",
                        "message": "OTP logged (email service not configured)",
                        "dev_otp": otp_code
                    }
            
            elif channel == "sms":
                # Check if SMS service is configured
                sms_config_check = self.sms_service.validate_sms_config()
                
                if sms_config_check["valid"]:
                    return await self.sms_service.send_otp_sms(identifier, otp_code, session_id)
                else:
                    # Development mode - log OTP instead of sending
                    logger.info(f"DEV MODE - SMS OTP for {identifier}: {otp_code}")
                    return {
                        "success": True,
                        "reason": "dev_mode",
                        "message": "OTP logged (SMS service not configured)",
                        "dev_otp": otp_code
                    }
            
            else:
                return {
                    "success": False,
                    "reason": "invalid_channel",
                    "message": f"Unsupported channel: {channel}"
                }
                
        except Exception as e:
            logger.error(f"Error delivering OTP via {channel}: {str(e)}")
            return {
                "success": False,
                "reason": "delivery_error",
                "message": f"Failed to deliver OTP via {channel}",
                "error": str(e)
            }
    
    async def _update_user_verification_status(self, otp_data: Dict[str, Any]) -> None:
        """
        Update user verification status after successful OTP verification
        
        Args:
            otp_data: Verified OTP data
        """
        try:
            identifier = otp_data["identifier"]
            channel = otp_data["channel"]
            
            # Update user verification status in database
            if channel == "email":
                await db.execute(
                    """
                    INSERT INTO users (user_id, email, email_verified, updated_at)
                    VALUES ($1, $2, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (email) 
                    DO UPDATE SET 
                        email_verified = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    f"user_{identifier.replace('@', '_').replace('.', '_')}", identifier
                )
            elif channel == "sms":
                await db.execute(
                    """
                    INSERT INTO users (user_id, phone, phone_verified, updated_at)
                    VALUES ($1, $2, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (phone) 
                    DO UPDATE SET 
                        phone_verified = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    f"user_{identifier.replace('+', '').replace('-', '')}", identifier
                )
            
            logger.info(f"Updated user verification status for {channel}: {identifier}")
            
        except Exception as e:
            logger.error(f"Error updating user verification status: {str(e)}")
            # Don't raise exception - verification was successful, this is just a bonus update

# Global OTP service instance
otp_service = OTPService()
