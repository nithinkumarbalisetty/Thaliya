"""
Session management for E-Care service
Handles guest sessions, authentication sessions, and session state management
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.core.database import db


class ECareSessionManager:
    """Handles all session-related operations for E-Care service"""

    async def validate_guest_session(self, session_token: str) -> bool:
        """Validate if the guest session token is valid and not expired"""
        try:
            result = await db.fetch(
                """
                SELECT COUNT(*) as count FROM guest_sessions 
                WHERE session_id = $1 
                AND status IN ('active', 'awaiting_auth_details', 'awaiting_dob_email', 'awaiting_otp', 'authenticated')
                AND expires_at > CURRENT_TIMESTAMP
                """,
                session_token
            )
            count = result[0]['count'] if result else 0
            return count > 0
        except Exception as e:
            print(f"Session validation error: {e}")
            return False

    async def update_session_activity(self, session_token: str):
        """Update the last activity timestamp for the session"""
        try:
            await db.execute(
                """
                UPDATE guest_sessions 
                SET last_activity = CURRENT_TIMESTAMP 
                WHERE session_id = $1
                """,
                session_token
            )
        except Exception as e:
            print(f"Failed to update session activity: {e}")

    async def get_session_state(self, session_token: str) -> Dict[str, Any]:
        """Get session state and auth temp data"""
        try:
            # 1. ALWAYS get the current state from guest_sessions first (source of truth)
            session_result = await db.fetch(
                "SELECT status FROM guest_sessions WHERE session_id = $1",
                session_token
            )
            
            if not session_result:
                return {"session_state": "general"}
            
            current_status = session_result[0]["status"]
            
            # 2. If we're in an auth flow, get the auth temp data as well
            if current_status in ["awaiting_auth_details", "awaiting_dob_email", "awaiting_otp"]:
                auth_result = await db.fetch(
                    """
                    SELECT original_intent, original_query, first_name, last_name, 
                           dob, email, phone, user_id, otp_code, otp_expires
                    FROM guest_auth_temp 
                    WHERE session_id = $1
                    """,
                    session_token
                )
                
                print(f"DEBUG: Auth temp data query result for {session_token}: {auth_result}")
                
                if auth_result:
                    # Combine auth data WITH session state
                    auth_data = dict(auth_result[0])
                    auth_data["session_state"] = current_status  # Add the state!
                    
                    # Map database 'phone' column back to 'phone_number' for application consistency
                    if "phone" in auth_data and auth_data["phone"] is not None:
                        auth_data["phone_number"] = auth_data["phone"]
                    
                    print(f"DEBUG: Returning auth data: {auth_data}")
                    return auth_data
                else:
                    print(f"DEBUG: No auth temp data found for session {session_token} in state {current_status}")
                    # If we're in an auth state but have no auth data, something went wrong
                    # Return the state so the auth handler can reset properly
                    return {"session_state": current_status}
            
            # 3. For non-auth states, just return the state
            return {"session_state": current_status}
            
        except Exception as e:
            print(f"Error getting session state: {e}")
            return {"session_state": "general"}

    async def update_session_status(self, session_token: str, status: str):
        """Update guest session status"""
        try:
            await db.execute(
                """
                UPDATE guest_sessions 
                SET status = $2, last_activity = CURRENT_TIMESTAMP
                WHERE session_id = $1
                """,
                session_token, status
            )
            print('Updating session status to:', status)
        except Exception as e:
            print(f"Error updating session status: {e}")

    async def store_auth_temp_data(self, session_token: str, intent: str, user_query: str):
        """Store original intent and query in guest_auth_temp table"""
        try:
            # First check if record exists
            existing = await db.fetch(
                "SELECT session_id FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            
            if existing:
                # Update existing record
                await db.execute(
                    """
                    UPDATE guest_auth_temp 
                    SET original_intent = $2, original_query = $3, expires_at = CURRENT_TIMESTAMP + INTERVAL '1 hour'
                    WHERE session_id = $1
                    """,
                    session_token, intent, user_query
                )
            else:
                # Insert new record - this is for when auth is triggered from general chat
                await db.execute(
                    """
                    INSERT INTO guest_auth_temp (session_id, original_intent, original_query, expires_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP + INTERVAL '1 hour')
                    """,
                    session_token, intent, user_query
                )
                
            print(f"DEBUG: Stored auth temp data - intent: '{intent}' for session {session_token}")
                
        except Exception as e:
            print(f"Error storing auth temp data: {e}")

    async def update_auth_temp_data(self, session_token: str, data: Dict[str, Any]):
        """Update auth temp data with new information - UPSERT operation"""
        try:
            # First, check if record exists
            existing = await db.fetch(
                "SELECT session_id FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            
            if existing:
                # Build dynamic update query based on provided data
                set_clauses = []
                values = [session_token]
                param_num = 2
                
                for key, value in data.items():
                    # Map phone_number to phone column
                    if key == "phone_number":
                        set_clauses.append(f"phone = ${param_num}")
                    else:
                        set_clauses.append(f"{key} = ${param_num}")
                    values.append(value)
                    param_num += 1
                
                if set_clauses:
                    query = f"""
                        UPDATE guest_auth_temp 
                        SET {', '.join(set_clauses)}, expires_at = CURRENT_TIMESTAMP + INTERVAL '30 minutes'
                        WHERE session_id = $1
                    """
                    await db.execute(query, *values)
                    print(f"DEBUG: Updated auth temp data for {session_token} with {data}")
            else:
                # Create new record with the provided data
                columns = ["session_id"]
                placeholders = ["$1"]
                values = [session_token]
                param_num = 2
                
                for key, value in data.items():
                    # Map phone_number to phone column
                    if key == "phone_number":
                        columns.append("phone")
                    else:
                        columns.append(key)
                    placeholders.append(f"${param_num}")
                    values.append(value)
                    param_num += 1
                
                query = f"""
                    INSERT INTO guest_auth_temp ({', '.join(columns)}) 
                    VALUES ({', '.join(placeholders)})
                """
                await db.execute(query, *values)
                print(f"DEBUG: Created auth temp data for {session_token} with {data}")
                
        except Exception as e:
            print(f"Error updating auth temp data: {e}")
            # As fallback, try a direct insert
            try:
                await db.execute(
                    """
                    INSERT INTO guest_auth_temp (session_id, first_name, last_name) 
                    VALUES ($1, $2, $3)
                    ON CONFLICT (session_id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        expires_at = CURRENT_TIMESTAMP + INTERVAL '30 minutes'
                    """,
                    session_token, data.get("first_name"), data.get("last_name")
                )
                print(f"DEBUG: Fallback upsert successful for {session_token}")
            except Exception as e2:
                print(f"Error in fallback upsert: {e2}")

    async def create_authenticated_session(self, session_token: str, user_id: int):
        """Create authenticated user session"""
        try:
            await db.execute(
                """
                INSERT INTO authenticated_user_sessions (session_id, user_id, authenticated_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (session_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    authenticated_at = EXCLUDED.authenticated_at,
                    last_activity = CURRENT_TIMESTAMP
                """,
                session_token, user_id, datetime.utcnow()
            )
            
            # Update guest session status
            await self.update_session_status(session_token, "authenticated")
            
        except Exception as e:
            print(f"Error creating authenticated session: {e}")

    async def get_authenticated_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """Get authenticated session info"""
        try:
            result = await db.fetch(
                """
                SELECT user_id, authenticated_at, last_activity
                FROM authenticated_user_sessions 
                WHERE session_id = $1
                """,
                session_token
            )
            
            return dict(result[0]) if result else None
            
        except Exception as e:
            print(f"Error getting authenticated session: {e}")
            return None

    async def cleanup_auth_temp_data(self, session_token: str):
        """Clean up temporary auth data after successful authentication"""
        try:
            result = await db.execute(
                "DELETE FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            print(f"DEBUG: Cleaned up auth temp data for session {session_token}")
        except Exception as e:
            print(f"Error cleaning up auth temp data: {e}")

    async def store_chat_history(self, session_token: str, user_query: str, bot_response: str, 
                               session_state: str, intent: str, is_sensitive: bool = False):
        """Store chat with sensitivity flag"""
        try:
            await db.execute(
                """
                INSERT INTO guest_chat_history 
                (session_id, user_query, bot_response, session_state, intent, is_sensitive, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                session_token, user_query, bot_response, session_state, intent, is_sensitive, datetime.utcnow()
            )
        except Exception as e:
            print(f"Error storing chat history: {e}")
