"""
Rate Limiter
Handles rate limiting for OTP requests and authentication attempts
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import text
from .auth_utils import AuthUtils


class RateLimiter:
    """Manages rate limiting for authentication operations"""
    
    def __init__(self):
        self.auth_utils = AuthUtils()
        # Rate limiting configuration
        self.otp_limit_per_hour = int(os.getenv("OTP_LIMIT_PER_HOUR", "5"))
        self.otp_limit_per_day = int(os.getenv("OTP_LIMIT_PER_DAY", "20"))
        self.development_mode = os.getenv("ENVIRONMENT", "development") == "development"
        self.development_bypass_contacts = [
            "test@test.com",
            "+1234567890",
            "dev@example.com"
        ]
    
    def can_send_otp(self, contact_method: str, db=None) -> bool:
        """
        Check if OTP can be sent to contact method based on rate limits
        """
        print(f"[DEBUG] Checking rate limit for contact method: {contact_method}")
        
        # Development bypass
        if self.development_mode and contact_method in self.development_bypass_contacts:
            print(f"[DEBUG] Development bypass for {contact_method}")
            return True
        
        if not db:
            print("[WARNING] No database session provided for rate limiting")
            return True
        
        try:
            # Check hourly limit
            hourly_limit_exceeded = self._check_hourly_limit(contact_method, db)
            if hourly_limit_exceeded:
                print(f"[DEBUG] Hourly limit exceeded for {contact_method}")
                return False
            
            # Check daily limit
            daily_limit_exceeded = self._check_daily_limit(contact_method, db)
            if daily_limit_exceeded:
                print(f"[DEBUG] Daily limit exceeded for {contact_method}")
                return False
            
            print(f"[DEBUG] Rate limit check passed for {contact_method}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Rate limit check failed: {e}")
            # Allow request if rate limiting check fails
            return True
    
    def record_otp_request(self, contact_method: str, db=None):
        """Record OTP request for rate limiting"""
        if not db:
            print("[WARNING] No database session provided for rate limit recording")
            return
        
        try:
            # Clean up old records first
            self._cleanup_old_records(db)
            
            # Record new request
            insert_query = text("""
                INSERT INTO otp_rate_limits (
                    contact_method, request_time, created_at
                ) VALUES (
                    :contact_method, :request_time, :created_at
                )
            """)
            
            now = datetime.utcnow()
            db.execute(insert_query, {
                "contact_method": contact_method,
                "request_time": now,
                "created_at": now
            })
            db.commit()
            
            print(f"[DEBUG] Recorded OTP request for {contact_method}")
            
        except Exception as e:
            print(f"[ERROR] Failed to record OTP request: {e}")
            db.rollback()
    
    def get_rate_limit_info(self, contact_method: str, db) -> Dict[str, Any]:
        """Get rate limiting information for contact method"""
        try:
            # Get hourly count
            hourly_count = self._get_hourly_count(contact_method, db)
            daily_count = self._get_daily_count(contact_method, db)
            
            # Calculate remaining attempts
            hourly_remaining = max(0, self.otp_limit_per_hour - hourly_count)
            daily_remaining = max(0, self.otp_limit_per_day - daily_count)
            
            # Calculate reset times
            now = datetime.utcnow()
            hourly_reset = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            daily_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            
            return {
                "hourly_count": hourly_count,
                "daily_count": daily_count,
                "hourly_limit": self.otp_limit_per_hour,
                "daily_limit": self.otp_limit_per_day,
                "hourly_remaining": hourly_remaining,
                "daily_remaining": daily_remaining,
                "hourly_reset": hourly_reset.isoformat(),
                "daily_reset": daily_reset.isoformat()
            }
            
        except Exception as e:
            print(f"[ERROR] Failed to get rate limit info: {e}")
            return {}
    
    def _check_hourly_limit(self, contact_method: str, db) -> bool:
        """Check if hourly limit is exceeded"""
        try:
            count = self._get_hourly_count(contact_method, db)
            return count >= self.otp_limit_per_hour
        except Exception as e:
            print(f"[ERROR] Hourly limit check failed: {e}")
            return False
    
    def _check_daily_limit(self, contact_method: str, db) -> bool:
        """Check if daily limit is exceeded"""
        try:
            count = self._get_daily_count(contact_method, db)
            return count >= self.otp_limit_per_day
        except Exception as e:
            print(f"[ERROR] Daily limit check failed: {e}")
            return False
    
    def _get_hourly_count(self, contact_method: str, db) -> int:
        """Get OTP request count in the last hour"""
        try:
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            
            query = text("""
                SELECT COUNT(*) 
                FROM otp_rate_limits 
                WHERE contact_method = :contact_method 
                AND request_time >= :one_hour_ago
            """)
            
            result = db.execute(query, {
                "contact_method": contact_method,
                "one_hour_ago": one_hour_ago
            }).scalar()
            
            return result or 0
            
        except Exception as e:
            print(f"[ERROR] Failed to get hourly count: {e}")
            return 0
    
    def _get_daily_count(self, contact_method: str, db) -> int:
        """Get OTP request count in the last 24 hours"""
        try:
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            
            query = text("""
                SELECT COUNT(*) 
                FROM otp_rate_limits 
                WHERE contact_method = :contact_method 
                AND request_time >= :twenty_four_hours_ago
            """)
            
            result = db.execute(query, {
                "contact_method": contact_method,
                "twenty_four_hours_ago": twenty_four_hours_ago
            }).scalar()
            
            return result or 0
            
        except Exception as e:
            print(f"[ERROR] Failed to get daily count: {e}")
            return 0
    
    def _cleanup_old_records(self, db):
        """Clean up old rate limiting records"""
        try:
            # Clean up records older than 24 hours
            twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
            
            delete_query = text("""
                DELETE FROM otp_rate_limits 
                WHERE request_time < :twenty_four_hours_ago
            """)
            
            db.execute(delete_query, {"twenty_four_hours_ago": twenty_four_hours_ago})
            db.commit()
            
        except Exception as e:
            print(f"[ERROR] Failed to cleanup old rate limit records: {e}")
            db.rollback()
