"""
OTP Authentication Router
Provides endpoints for OTP generation and verification
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from typing import Dict, Any

from app.schemas.auth_schemas import (
    OTPRequestSchema, OTPVerificationSchema, OTPResponseSchema, 
    OTPVerificationResponseSchema, RateLimitResponseSchema
)
from app.auth.otp_manager import SecureOTPManager
from app.auth.email_service import email_service
from app.auth.sms_service import sms_service
from app.core.database import db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/otp", tags=["OTP Authentication"])

# Initialize OTP manager
otp_manager = SecureOTPManager()

@router.post("/request", response_model=OTPResponseSchema)
async def request_otp(request: OTPRequestSchema):
    """
    Generate and send OTP via email or SMS
    
    This endpoint generates a secure OTP and sends it via the specified channel.
    Rate limiting is enforced to prevent abuse.
    """
    try:
        # Check rate limiting first
        rate_limit_check = await otp_manager.check_rate_limit(
            request.identifier, request.channel
        )
        
        if not rate_limit_check["allowed"]:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "message": rate_limit_check.get("message", "Rate limit exceeded"),
                    "rate_limit_info": {
                        "wait_minutes": rate_limit_check.get("wait_minutes"),
                        "reason": rate_limit_check.get("reason")
                    }
                }
            )
        
        # Generate OTP
        otp_data = otp_manager.generate_secure_otp(
            request.identifier, request.channel, request.session_id
        )
        
        # Store OTP request in database
        stored = await otp_manager.store_otp_request(otp_data)
        if not stored:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store OTP request"
            )
        
        # Send OTP via selected channel
        delivery_result = None
        if request.channel == "email":
            delivery_result = await email_service.send_otp_email(
                request.identifier, otp_data["otp_code"], request.session_id
            )
        elif request.channel == "sms":
            delivery_result = await sms_service.send_otp_sms(
                request.identifier, otp_data["otp_code"], request.session_id
            )
        
        # Check delivery result
        if not delivery_result or not delivery_result.get("success"):
            # Log the actual OTP for development (remove in production)
            logger.warning(f"OTP delivery failed, but OTP generated: {otp_data['otp_code']} for {request.identifier}")
            
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "message": f"Failed to send OTP via {request.channel}",
                    "otp_id": otp_data["otp_id"],  # Still provide OTP ID for retry
                    "channel": request.channel
                }
            )
        
        # Success response (never include actual OTP code)
        logger.info(f"OTP sent successfully via {request.channel} to {request.identifier}")
        
        return OTPResponseSchema(
            success=True,
            message=f"OTP sent successfully via {request.channel}",
            otp_id=otp_data["otp_id"],
            channel=request.channel,
            expires_in_minutes=otp_manager.otp_validity_minutes,
            rate_limit_info={
                "requests_remaining": rate_limit_check.get("requests_remaining"),
                "window_minutes": otp_manager.rate_limit_window_minutes
            }
        )
        
    except ValueError as e:
        logger.error(f"Validation error in OTP request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in OTP request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/verify", response_model=OTPVerificationResponseSchema)
async def verify_otp(request: OTPVerificationSchema):
    """
    Verify OTP code
    
    This endpoint verifies the provided OTP code against the stored hash.
    Failed attempts are tracked and rate limited.
    """
    try:
        # Get stored OTP data
        stored_otp = await otp_manager.get_otp_request(request.otp_id)
        if not stored_otp:
            logger.warning(f"OTP verification attempted with invalid/expired OTP ID: {request.otp_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP"
            )
        
        # Verify session matches
        if stored_otp["session_id"] != request.session_id:
            logger.warning(f"OTP verification session mismatch: {request.session_id} vs {stored_otp['session_id']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session mismatch"
            )
        
        # Perform OTP verification
        verification_result = otp_manager.verify_otp(request.otp_code, stored_otp)
        
        if verification_result["valid"]:
            # Mark OTP as verified
            await otp_manager.mark_otp_verified(request.otp_id)
            
            # Update authentication state for this session
            await _update_session_auth_status(
                request.session_id, 
                stored_otp["identifier"], 
                stored_otp["channel"]
            )
            
            logger.info(f"OTP verified successfully for {stored_otp['channel']}: {stored_otp['identifier']}")
            
            return OTPVerificationResponseSchema(
                success=True,
                message="OTP verified successfully",
                verified=True,
                next_step="authenticated",
                auth_token=None  # Could generate JWT token here if needed
            )
        
        else:
            # Update attempt count
            remaining_attempts = verification_result.get("attempts_remaining", 0)
            await otp_manager.update_otp_attempts(request.otp_id, remaining_attempts)
            
            logger.warning(f"Invalid OTP attempt for {stored_otp['identifier']}: {remaining_attempts} attempts remaining")
            
            return OTPVerificationResponseSchema(
                success=False,
                message=verification_result["message"],
                verified=False,
                attempts_remaining=remaining_attempts
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in OTP verification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/rate-limit/{identifier}")
async def check_rate_limit(identifier: str, channel: str):
    """
    Check rate limit status for an identifier
    
    This endpoint allows checking the current rate limit status
    without triggering a new OTP request.
    """
    try:
        if channel not in ["email", "sms"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Channel must be 'email' or 'sms'"
            )
        
        rate_limit_status = await otp_manager.check_rate_limit(identifier, channel)
        
        return RateLimitResponseSchema(
            allowed=rate_limit_status["allowed"],
            reason=rate_limit_status["reason"],
            requests_remaining=rate_limit_status.get("requests_remaining"),
            wait_minutes=rate_limit_status.get("wait_minutes"),
            window_minutes=otp_manager.rate_limit_window_minutes,
            message=rate_limit_status.get("message")
        )
        
    except Exception as e:
        logger.error(f"Error checking rate limit: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/resend")
async def resend_otp(request: OTPRequestSchema):
    """
    Resend OTP using the same logic as request
    
    This is essentially the same as the request endpoint but with
    potentially different rate limiting for resends.
    """
    # For now, use the same logic as request_otp
    return await request_otp(request)

@router.delete("/cancel/{otp_id}")
async def cancel_otp(otp_id: str, session_id: str):
    """
    Cancel an active OTP request
    
    This endpoint allows canceling an OTP request before it expires,
    useful for cleanup or if user changes their mind.
    """
    try:
        # Get stored OTP data
        stored_otp = await otp_manager.get_otp_request(otp_id)
        if not stored_otp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="OTP not found"
            )
        
        # Verify session matches
        if stored_otp["session_id"] != session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session mismatch"
            )
        
        # Mark OTP as cancelled
        await db.execute(
            "UPDATE otp_requests SET status = 'cancelled' WHERE otp_id = $1",
            otp_id
        )
        
        logger.info(f"OTP cancelled: {otp_id}")
        
        return {
            "success": True,
            "message": "OTP cancelled successfully",
            "otp_id": otp_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/status/{session_id}")
async def get_auth_status(session_id: str):
    """
    Get current authentication status for a session
    
    This endpoint returns whether the session is authenticated
    via OTP and what contact information is verified.
    """
    try:
        # Check if session has completed OTP authentication
        result = await db.fetch(
            """
            SELECT ga.email, ga.phone_number, ga.preferred_otp_channel, 
                   ga.email_verified, ga.phone_verified, ga.created_at
            FROM guest_auth_temp ga
            WHERE ga.session_id = $1 
            AND (ga.email_verified = true OR ga.phone_verified = true)
            ORDER BY ga.created_at DESC
            LIMIT 1
            """,
            session_id
        )
        
        if result:
            auth_data = dict(result[0])
            return {
                "authenticated": True,
                "session_id": session_id,
                "email": auth_data.get("email"),
                "phone": auth_data.get("phone_number"),
                "preferred_otp_channel": auth_data.get("preferred_otp_channel"),
                "email_verified": auth_data.get("email_verified", False),
                "phone_verified": auth_data.get("phone_verified", False),
                "auth_method": "otp",
                "authenticated_at": auth_data.get("created_at")
            }
        else:
            return {
                "authenticated": False,
                "session_id": session_id,
                "message": "Session not authenticated via OTP"
            }
            
    except Exception as e:
        logger.error(f"Error getting auth status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

async def _update_session_auth_status(session_id: str, identifier: str, channel: str):
    """
    Update session authentication status after successful OTP verification
    
    Args:
        session_id: Session identifier
        identifier: Verified email or phone
        channel: Verification channel (email/sms)
    """
    try:
        if channel == "email":
            # Update or insert guest authentication record
            await db.execute(
                """
                INSERT INTO guest_auth_temp (session_id, email, email_verified, preferred_otp_channel)
                VALUES ($1, $2, true, 'email')
                ON CONFLICT (session_id) DO UPDATE SET
                    email = EXCLUDED.email,
                    email_verified = true,
                    preferred_otp_channel = EXCLUDED.preferred_otp_channel,
                    updated_at = CURRENT_TIMESTAMP
                """,
                session_id, identifier
            )
        elif channel == "sms":
            # Update or insert guest authentication record
            await db.execute(
                """
                INSERT INTO guest_auth_temp (session_id, phone_number, phone_verified, preferred_otp_channel)
                VALUES ($1, $2, true, 'sms')
                ON CONFLICT (session_id) DO UPDATE SET
                    phone_number = EXCLUDED.phone_number,
                    phone_verified = true,
                    preferred_otp_channel = EXCLUDED.preferred_otp_channel,
                    updated_at = CURRENT_TIMESTAMP
                """,
                session_id, identifier
            )
        
        logger.info(f"Updated session auth status for {session_id}: {channel} verified")
        
    except Exception as e:
        logger.error(f"Error updating session auth status: {str(e)}")
        raise
