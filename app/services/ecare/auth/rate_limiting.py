"""
Rate Limiting Handler
Manages rate limiting for authentication operations
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta


class RateLimitingHandler:
    """Handles rate limiting for authentication operations"""
    
    def __init__(self, auth_handler):
        self.auth_handler = auth_handler
    
    async def check_otp_rate_limit(self, contact_method: str, identifier_type: str) -> Dict[str, Any]:
        """Check if OTP request is within rate limits (contact method based)"""
        from app.core.database import db
        
        try:
            # Rate limiting rules (contact method based - prevents abuse across all users)
            limit_window = timedelta(hours=1)  # 1 hour window
            max_requests = 5  # Maximum 5 OTP requests per contact method per hour
            
            # Check requests in the last hour for this contact method
            since_time = datetime.utcnow() - limit_window
            
            result = await db.fetch("""
                SELECT COUNT(*) as request_count
                FROM otp_rate_limits 
                WHERE identifier = $1 AND created_at > $2
            """, contact_method, since_time)
            
            current_count = result[0]["request_count"] if result else 0
            
            print(f"DEBUG: Rate limit check for {contact_method}: {current_count}/{max_requests} requests in last hour")
            
            if current_count >= max_requests:
                # Find the oldest request to calculate retry time
                oldest_result = await db.fetch("""
                    SELECT created_at 
                    FROM otp_rate_limits 
                    WHERE identifier = $1 AND created_at > $2
                    ORDER BY created_at ASC 
                    LIMIT 1
                """, contact_method, since_time)
                
                if oldest_result:
                    oldest_request = oldest_result[0]["created_at"]
                    retry_after = int((oldest_request + limit_window - datetime.utcnow()).total_seconds())
                    retry_after = max(retry_after, 60)  # Minimum 1 minute
                else:
                    retry_after = 3600  # Default 1 hour
                
                return {
                    "allowed": False,
                    "retry_after": retry_after,
                    "current_count": current_count,
                    "max_requests": max_requests,
                    "reason": f"Rate limit exceeded for {contact_method}"
                }
            
            return {
                "allowed": True,
                "current_count": current_count,
                "max_requests": max_requests,
                "remaining": max_requests - current_count
            }
            
        except Exception as e:
            print(f"ERROR: Rate limit check failed: {e}")
            # Allow request on error to avoid blocking legitimate users
            return {"allowed": True, "error": str(e)}

    async def record_otp_request(self, contact_method: str, identifier_type: str) -> None:
        """Record an OTP request for rate limiting"""
        from app.core.database import db
        
        try:
            await db.execute("""
                INSERT INTO otp_rate_limits (identifier, identifier_type, created_at)
                VALUES ($1, $2, $3)
            """, contact_method, identifier_type, datetime.utcnow())
            
            print(f"DEBUG: Recorded OTP request for rate limiting: {contact_method}")
            
        except Exception as e:
            print(f"ERROR: Failed to record OTP request: {e}")

    async def reset_rate_limit(self, contact_method: str, identifier_type: str) -> None:
        """Reset rate limit for a contact method (development/admin use)"""
        from app.core.database import db
        
        try:
            result = await db.execute(
                "DELETE FROM otp_rate_limits WHERE identifier = $1",
                contact_method
            )
            
            print(f"DEBUG: Reset rate limit for {contact_method}")
            
        except Exception as e:
            print(f"ERROR: Failed to reset rate limit: {e}")

    async def cleanup_old_rate_limit_records(self) -> None:
        """Cleanup old rate limit records (maintenance task)"""
        from app.core.database import db
        
        try:
            # Delete records older than 24 hours
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            result = await db.execute(
                "DELETE FROM otp_rate_limits WHERE created_at < $1",
                cutoff_time
            )
            
            print(f"DEBUG: Cleaned up old rate limit records")
            
        except Exception as e:
            print(f"ERROR: Rate limit cleanup failed: {e}")

    async def get_rate_limit_status(self, contact_method: str) -> Dict[str, Any]:
        """Get current rate limit status for a contact method"""
        from app.core.database import db
        
        try:
            # Check requests in the last hour
            since_time = datetime.utcnow() - timedelta(hours=1)
            max_requests = 5
            
            result = await db.fetch("""
                SELECT COUNT(*) as request_count, MIN(created_at) as oldest_request
                FROM otp_rate_limits 
                WHERE identifier = $1 AND created_at > $2
            """, contact_method, since_time)
            
            if result:
                data = result[0]
                current_count = data["request_count"]
                oldest_request = data["oldest_request"]
                
                remaining = max(0, max_requests - current_count)
                
                if current_count >= max_requests and oldest_request:
                    reset_time = oldest_request + timedelta(hours=1)
                    reset_in = max(0, int((reset_time - datetime.utcnow()).total_seconds()))
                else:
                    reset_in = 0
                
                return {
                    "contact_method": contact_method,
                    "current_count": current_count,
                    "max_requests": max_requests,
                    "remaining": remaining,
                    "reset_in_seconds": reset_in,
                    "is_blocked": current_count >= max_requests
                }
            
            return {
                "contact_method": contact_method,
                "current_count": 0,
                "max_requests": max_requests,
                "remaining": max_requests,
                "reset_in_seconds": 0,
                "is_blocked": False
            }
            
        except Exception as e:
            print(f"ERROR: Failed to get rate limit status: {e}")
            return {"error": str(e)}

    async def check_session_rate_limit(self, session_token: str) -> Dict[str, Any]:
        """Check rate limits for session-based operations"""
        # This can be used for other session-based rate limiting
        # For now, we primarily use contact-method-based rate limiting
        return {"allowed": True}

    async def get_all_blocked_contacts(self) -> list:
        """Get all currently blocked contact methods"""
        from app.core.database import db
        
        try:
            since_time = datetime.utcnow() - timedelta(hours=1)
            max_requests = 5
            
            result = await db.fetch("""
                SELECT contact_method, COUNT(*) as request_count, MIN(created_at) as oldest_request
                FROM otp_rate_limits 
                WHERE created_at > $1
                GROUP BY contact_method
                HAVING COUNT(*) >= $2
            """, since_time, max_requests)
            
            blocked_contacts = []
            for row in result:
                reset_time = row["oldest_request"] + timedelta(hours=1)
                reset_in = max(0, int((reset_time - datetime.utcnow()).total_seconds()))
                
                blocked_contacts.append({
                    "contact_method": row["contact_method"],
                    "request_count": row["request_count"],
                    "reset_in_seconds": reset_in
                })
            
            return blocked_contacts
            
        except Exception as e:
            print(f"ERROR: Failed to get blocked contacts: {e}")
            return []
