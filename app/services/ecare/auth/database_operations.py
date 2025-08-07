"""
Database Operations Handler
Manages database operations for authentication
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta


class DatabaseOperationsHandler:
    """Handles database operations for authentication"""
    
    def __init__(self, auth_handler):
        self.auth_handler = auth_handler
    
    async def get_user_by_credentials(self, first_name: str, last_name: str, dob: str, 
                                    email: str = None, phone: str = None) -> Optional[Dict[str, Any]]:
        """Get user by authentication credentials"""
        from app.core.database import db
        
        try:
            # Build dynamic query based on provided contact method
            # Phone is primary identifier for healthcare
            if phone:
                query = """
                    SELECT user_id, first_name, last_name, dob, email, phone
                    FROM users 
                    WHERE LOWER(first_name) = LOWER($1) 
                    AND LOWER(last_name) = LOWER($2) 
                    AND dob = $3 
                    AND phone = $4
                """
                params = [first_name, last_name, dob, phone]
            elif email:
                query = """
                    SELECT user_id, first_name, last_name, dob, email, phone
                    FROM users 
                    WHERE LOWER(first_name) = LOWER($1) 
                    AND LOWER(last_name) = LOWER($2) 
                    AND dob = $3 
                    AND LOWER(email) = LOWER($4)
                """
                params = [first_name, last_name, dob, email]
            else:
                return None
            
            result = await db.fetch(query, *params)
            
            if result:
                user_record = result[0]
                return dict(user_record)
            
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to get user by credentials: {e}")
            return None
    
    async def create_new_user(self, first_name: str, last_name: str, dob: str, 
                            email: str = None, phone: str = None) -> Optional[Dict[str, Any]]:
        """Create a new user record"""
        from app.core.database import db
        
        try:
            query = """
                INSERT INTO users (first_name, last_name, dob, email, phone)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING user_id, first_name, last_name, dob, email, phone
            """
            
            params = [first_name, last_name, dob, email, phone]
            
            result = await db.fetch(query, *params)
            
            if result:
                user_record = result[0]
                user_data = dict(user_record)
                print(f"DEBUG: Created new user with ID {user_data['user_id']}")
                return user_data
            
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to create user: {e}")
            return None
    
    async def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        from app.core.database import db
        
        try:
            result = await db.fetch(
                "SELECT user_id, first_name, last_name, dob, email, phone FROM users WHERE user_id = $1",
                user_id
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to get user by ID: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        from app.core.database import db
        
        try:
            result = await db.fetch(
                "SELECT user_id, first_name, last_name, dob, email, phone FROM users WHERE LOWER(email) = LOWER($1)",
                email
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to get user by email: {e}")
            return None
    
    async def get_user_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Get user by phone"""
        from app.core.database import db
        
        try:
            result = await db.fetch(
                "SELECT user_id, first_name, last_name, dob, email, phone FROM users WHERE phone = $1",
                phone
            )
            
            if result:
                return dict(result[0])
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to get user by phone: {e}")
            return None
    
    async def find_existing_user(self, first_name: str, last_name: str, dob: str, 
                               email: str = None, phone: str = None) -> Dict[str, Any]:
        """
        Find existing user by credentials without creating new user
        Returns standardized response for Option A flow
        """
        user_data = await self.get_user_by_credentials(first_name, last_name, dob, email, phone)
        
        if user_data:
            return {
                "exists": True,
                "user_id": user_data["user_id"],
                "user_data": user_data
            }
        else:
            return {
                "exists": False,
                "user_id": None,
                "user_data": None
            }
    
    async def update_user_contact_info(self, user_id: int, email: str = None, phone: str = None) -> bool:
        """Update user contact information"""
        from app.core.database import db
        
        try:
            updates = []
            params = []
            param_count = 1
            
            if email:
                updates.append(f"email = ${param_count}")
                params.append(email)
                param_count += 1
            
            if phone:
                updates.append(f"phone = ${param_count}")
                params.append(phone)
                param_count += 1
            
            if not updates:
                return False
            
            updates.append(f"updated_at = ${param_count}")
            params.append(datetime.utcnow())
            param_count += 1
            
            params.append(user_id)
            
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ${param_count}"
            
            await db.execute(query, *params)
            print(f"DEBUG: Updated contact info for user {user_id}")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to update user contact info: {e}")
            return False
    
    async def check_contact_method_exists(self, email: str = None, phone: str = None) -> Dict[str, Any]:
        """Check if contact method already exists for another user"""
        from app.core.database import db
        
        try:
            if email:
                result = await db.fetch(
                    "SELECT id, first_name, last_name FROM users WHERE LOWER(email) = LOWER($1)",
                    email
                )
                if result:
                    return {
                        "exists": True,
                        "method": "email",
                        "user_id": result[0]["id"],
                        "user_name": f"{result[0]['first_name']} {result[0]['last_name']}"
                    }

            if phone:
                result = await db.fetch(
                    "SELECT id, first_name, last_name FROM users WHERE phone = $1",
                    phone
                )
                if result:
                    return {
                        "exists": True,
                        "method": "phone",
                        "user_id": result[0]["id"],
                        "user_name": f"{result[0]['first_name']} {result[0]['last_name']}"
                    }
            
            return {"exists": False}
            
        except Exception as e:
            print(f"ERROR: Failed to check contact method existence: {e}")
            return {"exists": False, "error": str(e)}
    
    async def get_user_sessions(self, user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get user sessions"""
        from app.core.database import db
        
        try:
            if active_only:
                query = """
                    SELECT session_id, user_id, created_at, last_activity, status, user_agent, ip_address
                    FROM user_sessions 
                    WHERE user_id = $1 AND status = 'active'
                    ORDER BY last_activity DESC
                """
            else:
                query = """
                    SELECT session_id, user_id, created_at, last_activity, status, user_agent, ip_address
                    FROM user_sessions 
                    WHERE user_id = $1
                    ORDER BY last_activity DESC
                """
            
            result = await db.fetch(query, user_id)
            
            if result:
                return [dict(row) for row in result]
            return []
            
        except Exception as e:
            print(f"ERROR: Failed to get user sessions: {e}")
            return []
    
    async def create_user_session(self, session_id: str, user_id: int, user_agent: str = None, 
                                ip_address: str = None) -> bool:
        """Create user session record"""
        from app.core.database import db
        
        try:
            now = datetime.utcnow()
            await db.execute("""
                INSERT INTO user_sessions (session_id, user_id, created_at, last_activity, status, user_agent, ip_address)
                VALUES ($1, $2, $3, $4, 'active', $5, $6)
            """, session_id, user_id, now, now, user_agent, ip_address)
            
            print(f"DEBUG: Created session {session_id} for user {user_id}")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to create user session: {e}")
            return False
    
    async def update_session_activity(self, session_id: str) -> bool:
        """Update session last activity timestamp"""
        from app.core.database import db
        
        try:
            await db.execute(
                "UPDATE user_sessions SET last_activity = $1 WHERE session_id = $2",
                datetime.utcnow(), session_id
            )
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to update session activity: {e}")
            return False
    
    async def invalidate_user_session(self, session_id: str) -> bool:
        """Invalidate a user session"""
        from app.core.database import db
        
        try:
            await db.execute(
                "UPDATE user_sessions SET status = 'expired' WHERE session_id = $1",
                session_id
            )
            print(f"DEBUG: Invalidated session {session_id}")
            return True
            
        except Exception as e:
            print(f"ERROR: Failed to invalidate session: {e}")
            return False
    
    async def cleanup_expired_sessions(self, expire_hours: int = 24) -> int:
        """Cleanup expired sessions"""
        from app.core.database import db
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=expire_hours)
            
            result = await db.execute(
                "UPDATE user_sessions SET status = 'expired' WHERE last_activity < $1 AND status = 'active'",
                cutoff_time
            )
            
            print(f"DEBUG: Cleaned up expired sessions")
            return result if isinstance(result, int) else 0
            
        except Exception as e:
            print(f"ERROR: Failed to cleanup sessions: {e}")
            return 0
    
    async def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics"""
        from app.core.database import db
        
        try:
            # Get session count
            session_result = await db.fetch(
                "SELECT COUNT(*) as session_count FROM user_sessions WHERE user_id = $1",
                user_id
            )
            
            # Get OTP request count (last 30 days)
            cutoff = datetime.utcnow() - timedelta(days=30)
            otp_result = await db.fetch(
                "SELECT COUNT(*) as otp_count FROM otp_requests WHERE user_id = $1 AND created_at > $2",
                user_id, cutoff
            )
            
            return {
                "user_id": user_id,
                "total_sessions": session_result[0]["session_count"] if session_result else 0,
                "otp_requests_last_30_days": otp_result[0]["otp_count"] if otp_result else 0
            }
            
        except Exception as e:
            print(f"ERROR: Failed to get user statistics: {e}")
            return {"error": str(e)}
