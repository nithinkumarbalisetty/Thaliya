"""
Authentication schemas for OTP functionality
"""

from pydantic import BaseModel, Field, EmailStr, field_validator
from pydantic_core import ValidationError
from typing import Optional, Literal
from datetime import datetime
import re

class OTPRequestSchema(BaseModel):
    """Schema for OTP generation request"""
    identifier: str = Field(..., description="Email address or phone number")
    channel: Literal["email", "sms"] = Field(..., description="Delivery channel")
    session_id: str = Field(..., description="Session identifier")
    
    @field_validator('identifier')
    @classmethod
    def validate_identifier(cls, v, info):
        """Validate email or phone format based on channel"""
        # Get channel from the context
        channel = info.data.get('channel') if info.data else None
        
        if channel == 'email':
            # Basic email validation (Pydantic EmailStr is more strict)
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError('Invalid email format')
        
        elif channel == 'sms':
            # Phone number validation
            phone_pattern = r'^[\+]?[1-9][\d\s\-\(\)]{8,15}$'
            clean_phone = re.sub(r'[^\d+]', '', v)
            if not re.match(phone_pattern, clean_phone):
                raise ValueError('Invalid phone number format')
        
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "identifier": "user@example.com",
                "channel": "email",
                "session_id": "guest_123456"
            }
        }
    }

class OTPVerificationSchema(BaseModel):
    """Schema for OTP verification request"""
    otp_code: str = Field(..., description="6-digit OTP code", min_length=6, max_length=6)
    otp_id: str = Field(..., description="OTP identifier")
    session_id: str = Field(..., description="Session identifier")
    
    @field_validator('otp_code')
    @classmethod
    def validate_otp_code(cls, v):
        """Validate OTP format"""
        # Remove spaces and dashes
        cleaned = v.strip().replace(' ', '').replace('-', '')
        
        # Must be exactly 6 digits
        if not re.match(r'^\d{6}$', cleaned):
            raise ValueError('OTP must be exactly 6 digits')
        
        return cleaned
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "otp_code": "123456",
                "otp_id": "otp_abc12345",
                "session_id": "guest_123456"
            }
        }
    }

class OTPResponseSchema(BaseModel):
    """Schema for OTP generation response"""
    success: bool = Field(..., description="Request success status")
    message: str = Field(..., description="Response message")
    otp_id: Optional[str] = Field(None, description="OTP identifier (if successful)")
    channel: Optional[str] = Field(None, description="Delivery channel used")
    expires_in_minutes: Optional[int] = Field(None, description="OTP expiration time")
    rate_limit_info: Optional[dict] = Field(None, description="Rate limit information")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "message": "OTP sent successfully",
                "otp_id": "otp_abc12345",
                "channel": "email",
                "expires_in_minutes": 5,
                "rate_limit_info": {
                    "requests_remaining": 4,
                    "window_minutes": 60
                }
            }
        }
    }

class OTPVerificationResponseSchema(BaseModel):
    """Schema for OTP verification response"""
    success: bool = Field(..., description="Verification success status")
    message: str = Field(..., description="Verification message")
    verified: bool = Field(..., description="Whether OTP was verified")
    attempts_remaining: Optional[int] = Field(None, description="Remaining verification attempts")
    next_step: Optional[str] = Field(None, description="Next step in authentication flow")
    auth_token: Optional[str] = Field(None, description="Authentication token (if verification successful)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "message": "OTP verified successfully",
                "verified": True,
                "next_step": "complete_registration",
                "auth_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            }
        }
    }

class UserContactUpdateSchema(BaseModel):
    """Schema for updating user contact information"""
    email: Optional[EmailStr] = Field(None, description="User email address")
    phone: Optional[str] = Field(None, description="User phone number")
    preferred_otp_channel: Optional[Literal["email", "sms"]] = Field(None, description="Preferred OTP delivery method")
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate phone number format"""
        if v is not None:
            phone_pattern = r'^[\+]?[1-9][\d\s\-\(\)]{8,15}$'
            clean_phone = re.sub(r'[^\d+]', '', v)
            if not re.match(phone_pattern, clean_phone):
                raise ValueError('Invalid phone number format')
        return v
    
    @field_validator('preferred_otp_channel')
    @classmethod
    def validate_otp_channel_with_contact(cls, v, info):
        """Ensure preferred channel has corresponding contact info"""
        values = info.data if info.data else {}
        if v == 'email' and not values.get('email'):
            raise ValueError('Email required when email is preferred OTP channel')
        if v == 'sms' and not values.get('phone'):
            raise ValueError('Phone required when SMS is preferred OTP channel')
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "phone": "+1234567890",
                "preferred_otp_channel": "email"
            }
        }
    }

class AuthStatusSchema(BaseModel):
    """Schema for authentication status response"""
    authenticated: bool = Field(..., description="User authentication status")
    session_id: str = Field(..., description="Session identifier")
    user_id: Optional[str] = Field(None, description="User identifier (if authenticated)")
    email: Optional[str] = Field(None, description="User email (if authenticated)")
    phone: Optional[str] = Field(None, description="User phone (if authenticated)")
    preferred_otp_channel: Optional[str] = Field(None, description="User's preferred OTP channel")
    auth_method: Optional[str] = Field(None, description="Authentication method used")
    expires_at: Optional[datetime] = Field(None, description="Session expiration time")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "authenticated": True,
                "session_id": "auth_123456",
                "user_id": "user_789",
                "email": "user@example.com",
                "phone": "+1234567890",
                "preferred_otp_channel": "email",
                "auth_method": "otp_email",
                "expires_at": "2024-01-01T12:00:00Z"
            }
        }
    }

class RateLimitResponseSchema(BaseModel):
    """Schema for rate limit response"""
    allowed: bool = Field(..., description="Whether request is allowed")
    reason: str = Field(..., description="Rate limit status reason")
    requests_remaining: Optional[int] = Field(None, description="Remaining requests in current window")
    wait_minutes: Optional[int] = Field(None, description="Minutes to wait if blocked")
    window_minutes: Optional[int] = Field(None, description="Rate limit window duration")
    message: Optional[str] = Field(None, description="Human-readable message")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "allowed": False,
                "reason": "rate_limit_exceeded",
                "wait_minutes": 30,
                "window_minutes": 60,
                "message": "Too many OTP requests. Please try again in 30 minutes."
            }
        }
    }
