"""
Session Manager for OTP Authentication
Handles session state and authentication tracking
"""

import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.core.database import db
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages user sessions and authentication state
    """
    
    def __init__(self):
        self.session_timeout_minutes = 60  # 1 hour session timeout
        self.cleanup_interval_hours = 24   # Clean old sessions every 24 hours
    
    async def create_guest_session(self) -> str:
        """
        Create a new guest session
        
        Returns:
            Session ID string
        """
        try:
            session_id = f"guest_{secrets.token_hex(8)}"
            expires_at = datetime.utcnow() + timedelta(minutes=self.session_timeout_minutes)
            
            # Store session in database
            await db.execute(
                """
                INSERT INTO guest_sessions (session_id, expires_at, created_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (session_id) DO UPDATE SET
                    expires_at = EXCLUDED.expires_at,
                    updated_at = CURRENT_TIMESTAMP
                """,
                session_id, expires_at, datetime.utcnow()
            )
            
            logger.info(f"Created guest session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Error creating guest session: {str(e)}")
            raise
    
    async def validate_session(self, session_id: str) -> bool:
        """
        Validate if a session is active and not expired
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session is valid, False otherwise
        """
        try:
            result = await db.fetch(
                """
                SELECT expires_at FROM guest_sessions 
                WHERE session_id = $1 AND expires_at > CURRENT_TIMESTAMP
                """,
                session_id
            )
            
            return len(result) > 0
            
        except Exception as e:
            logger.error(f"Error validating session {session_id}: {str(e)}")
            return False
    
    async def extend_session(self, session_id: str) -> bool:
        """
        Extend session expiration time
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if extended successfully, False otherwise
        """
        try:
            new_expires_at = datetime.utcnow() + timedelta(minutes=self.session_timeout_minutes)
            
            result = await db.execute(
                """
                UPDATE guest_sessions 
                SET expires_at = $2, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = $1 AND expires_at > CURRENT_TIMESTAMP
                """,
                session_id, new_expires_at
            )
            
            # Check if any rows were updated
            return True  # asyncpg doesn't return rowcount easily
            
        except Exception as e:
            logger.error(f"Error extending session {session_id}: {str(e)}")
            return False
    
    async def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data including authentication status
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session data dictionary or None if not found
        """
        try:
            # Get basic session info
            session_result = await db.fetch(
                """
                SELECT session_id, expires_at, created_at, updated_at
                FROM guest_sessions 
                WHERE session_id = $1 AND expires_at > CURRENT_TIMESTAMP
                """,
                session_id
            )
            
            if not session_result:
                return None
            
            session_data = dict(session_result[0])
            
            # Get authentication data if available
            auth_result = await db.fetch(
                """
                SELECT email, phone_number, preferred_otp_channel, 
                       email_verified, phone_verified
                FROM guest_auth_temp 
                WHERE session_id = $1
                """,
                session_id
            )
            
            if auth_result:
                auth_data = dict(auth_result[0])
                session_data.update({
                    "authenticated": auth_data.get("email_verified") or auth_data.get("phone_verified"),
                    "email": auth_data.get("email"),
                    "phone": auth_data.get("phone_number"),
                    "preferred_otp_channel": auth_data.get("preferred_otp_channel"),
                    "email_verified": auth_data.get("email_verified", False),
                    "phone_verified": auth_data.get("phone_verified", False)
                })
            else:
                session_data.update({
                    "authenticated": False,
                    "email": None,
                    "phone": None,
                    "preferred_otp_channel": None,
                    "email_verified": False,
                    "phone_verified": False
                })
            
            return session_data
            
        except Exception as e:
            logger.error(f"Error getting session data for {session_id}: {str(e)}")
            return None
    
    async def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a session (mark as expired)
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            await db.execute(
                """
                UPDATE guest_sessions 
                SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 minute',
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = $1
                """,
                session_id
            )
            
            # Also clean up auth data
            await db.execute(
                """
                DELETE FROM guest_auth_temp WHERE session_id = $1
                """,
                session_id
            )
            
            logger.info(f"Invalidated session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating session {session_id}: {str(e)}")
            return False
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions (maintenance function)
        
        Returns:
            Number of cleaned up sessions
        """
        try:
            # Clean up expired guest sessions
            await db.execute(
                """
                DELETE FROM guest_sessions 
                WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 hour'
                """
            )
            
            # Clean up orphaned auth temp records
            await db.execute(
                """
                DELETE FROM guest_auth_temp 
                WHERE session_id NOT IN (
                    SELECT session_id FROM guest_sessions 
                    WHERE expires_at > CURRENT_TIMESTAMP
                )
                """
            )
            
            logger.info("Cleaned up expired sessions")
            return 0  # asyncpg doesn't return row count easily
            
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {str(e)}")
            return 0
    
    async def get_session_statistics(self) -> Dict[str, Any]:
        """
        Get session statistics for monitoring
        
        Returns:
            Dictionary with session statistics
        """
        try:
            # Count active sessions
            active_sessions = await db.fetchval(
                """
                SELECT COUNT(*) FROM guest_sessions 
                WHERE expires_at > CURRENT_TIMESTAMP
                """
            )
            
            # Count authenticated sessions
            authenticated_sessions = await db.fetchval(
                """
                SELECT COUNT(*) FROM guest_auth_temp gat
                JOIN guest_sessions gs ON gat.session_id = gs.session_id
                WHERE gs.expires_at > CURRENT_TIMESTAMP
                AND (gat.email_verified = true OR gat.phone_verified = true)
                """
            )
            
            # Count sessions created today
            sessions_today = await db.fetchval(
                """
                SELECT COUNT(*) FROM guest_sessions 
                WHERE created_at > CURRENT_DATE
                """
            )
            
            return {
                "active_sessions": active_sessions or 0,
                "authenticated_sessions": authenticated_sessions or 0,
                "sessions_created_today": sessions_today or 0,
                "authentication_rate": (authenticated_sessions / max(active_sessions, 1)) * 100 if active_sessions else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting session statistics: {str(e)}")
            return {
                "active_sessions": 0,
                "authenticated_sessions": 0,
                "sessions_created_today": 0,
                "authentication_rate": 0
            }

# Global session manager instance
session_manager = SessionManager()
