"""
Temporary Storage Manager
Handles temporary authentication data storage and retrieval
"""

import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import text


class TempStorageManager:
    """Manages temporary authentication data storage"""
    
    def __init__(self):
        self.temp_record_expiry_minutes = 30
    
    def create_temp_record(
        self,
        contact_method: str,
        user_id: int,
        step: str,
        db,
        additional_data: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Create temporary authentication record
        """
        print(f"[DEBUG] Creating temp record for user {user_id}, step: {step}")
        
        try:
            # Generate unique record ID
            record_id = str(uuid.uuid4())
            
            # Calculate expiry time
            expiry_time = datetime.utcnow() + timedelta(minutes=self.temp_record_expiry_minutes)
            
            # Clean up any existing records for this contact method
            self._cleanup_existing_records(contact_method, db)
            
            # Prepare additional data
            extra_data = additional_data or {}
            
            # Insert new record
            insert_query = text("""
                INSERT INTO guest_auth_temp (
                    record_id, contact_method, user_id, auth_step,
                    expiry_time, additional_data, created_at
                ) VALUES (
                    :record_id, :contact_method, :user_id, :auth_step,
                    :expiry_time, :additional_data, :created_at
                )
            """)
            
            db.execute(insert_query, {
                "record_id": record_id,
                "contact_method": contact_method,
                "user_id": user_id,
                "auth_step": step,
                "expiry_time": expiry_time,
                "additional_data": str(extra_data),  # Store as string
                "created_at": datetime.utcnow()
            })
            db.commit()
            
            print(f"[DEBUG] Created temp record with ID: {record_id}")
            return record_id
            
        except Exception as e:
            print(f"[ERROR] Failed to create temp record: {e}")
            db.rollback()
            return None
    
    def get_temp_record(self, record_id: str, db) -> Optional[Dict[str, Any]]:
        """
        Retrieve temporary authentication record
        """
        print(f"[DEBUG] Retrieving temp record: {record_id}")
        
        try:
            query = text("""
                SELECT contact_method, user_id, auth_step, 
                       expiry_time, additional_data, created_at
                FROM guest_auth_temp 
                WHERE record_id = :record_id
            """)
            
            result = db.execute(query, {"record_id": record_id}).first()
            
            if not result:
                print(f"[DEBUG] No temp record found for ID: {record_id}")
                return None
            
            contact_method, user_id, auth_step, expiry_time, additional_data, created_at = result
            
            # Check if record is expired
            if datetime.utcnow() > expiry_time:
                print(f"[DEBUG] Temp record expired for ID: {record_id}")
                self.cleanup_temp_record(record_id, db)
                return None
            
            print(f"[DEBUG] Retrieved temp record - Contact: {contact_method}, User: {user_id}")
            
            return {
                "record_id": record_id,
                "contact_method": contact_method,
                "user_id": user_id,
                "auth_step": auth_step,
                "expiry_time": expiry_time,
                "additional_data": additional_data,
                "created_at": created_at
            }
            
        except Exception as e:
            print(f"[ERROR] Failed to retrieve temp record: {e}")
            return None
    
    def update_temp_record(
        self,
        record_id: str,
        step: str,
        db,
        additional_data: Dict[str, Any] = None
    ) -> bool:
        """
        Update temporary authentication record
        """
        try:
            extra_data = additional_data or {}
            
            update_query = text("""
                UPDATE guest_auth_temp 
                SET auth_step = :auth_step,
                    additional_data = :additional_data
                WHERE record_id = :record_id
            """)
            
            result = db.execute(update_query, {
                "record_id": record_id,
                "auth_step": step,
                "additional_data": str(extra_data)
            })
            
            db.commit()
            
            if result.rowcount > 0:
                print(f"[DEBUG] Updated temp record: {record_id}")
                return True
            else:
                print(f"[DEBUG] No temp record found to update: {record_id}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to update temp record: {e}")
            db.rollback()
            return False
    
    def cleanup_temp_record(self, record_id: str, db):
        """
        Clean up temporary authentication record
        """
        try:
            delete_query = text("""
                DELETE FROM guest_auth_temp 
                WHERE record_id = :record_id
            """)
            
            db.execute(delete_query, {"record_id": record_id})
            db.commit()
            
            print(f"[DEBUG] Cleaned up temp record: {record_id}")
            
        except Exception as e:
            print(f"[ERROR] Failed to cleanup temp record: {e}")
            db.rollback()
    
    def cleanup_expired_records(self, db):
        """
        Clean up all expired temporary records
        """
        try:
            delete_query = text("""
                DELETE FROM guest_auth_temp 
                WHERE expiry_time < :current_time
            """)
            
            result = db.execute(delete_query, {"current_time": datetime.utcnow()})
            db.commit()
            
            if result.rowcount > 0:
                print(f"[DEBUG] Cleaned up {result.rowcount} expired temp records")
            
        except Exception as e:
            print(f"[ERROR] Failed to cleanup expired records: {e}")
            db.rollback()
    
    def _cleanup_existing_records(self, contact_method: str, db):
        """
        Clean up existing records for contact method
        """
        try:
            delete_query = text("""
                DELETE FROM guest_auth_temp 
                WHERE contact_method = :contact_method
            """)
            
            db.execute(delete_query, {"contact_method": contact_method})
            db.commit()
            
            print(f"[DEBUG] Cleaned up existing temp records for {contact_method}")
            
        except Exception as e:
            print(f"[ERROR] Failed to cleanup existing temp records: {e}")
            db.rollback()

    async def update_auth_temp_with_dob(self, session_token: str, parsed_data: Dict[str, Any]) -> None:
        """Update auth temp record with DOB and contact info"""
        try:
            from app.core.database import db
            
            print(f"DEBUG: Updating auth temp with DOB for session: {session_token}")
            print(f"DEBUG: Parsed data: {parsed_data}")
            
            # Reset fields that might be stale from previous attempts
            update_result = await db.execute(
                """
                UPDATE guest_auth_temp 
                SET dob = $2, email = $3, phone = $4, user_id = NULL, 
                    preferred_otp_channel = NULL, otp_attempts = 0, last_otp_sent = NULL
                WHERE session_id = $1
                """,
                session_token, 
                parsed_data["dob"],
                parsed_data.get("email"),
                parsed_data.get("phone_number")
            )
            print(f"DEBUG: Update result: {update_result}")
            
        except Exception as e:
            print(f"ERROR: Error updating auth temp with DOB: {e}")
            import traceback
            traceback.print_exc()

    async def update_auth_temp_with_user_id(self, session_token: str, user_id: int, contact_method: str) -> None:
        """Update auth temp record with verified user ID"""
        try:
            from app.core.database import db
            
            print(f"DEBUG: Updating auth temp with user_id for session: {session_token}")
            print(f"DEBUG: user_id: {user_id}, contact_method: {contact_method}")
            
            channel = "email" if "@" in contact_method else "sms"
            
            update_result = await db.execute(
                """
                UPDATE guest_auth_temp 
                SET user_id = $2, preferred_otp_channel = $3, last_otp_sent = CURRENT_TIMESTAMP
                WHERE session_id = $1
                """,
                session_token, user_id, channel
            )
            print(f"DEBUG: Update result: {update_result}")
            
        except Exception as e:
            print(f"ERROR: Error updating auth temp with user_id: {e}")
            import traceback
            traceback.print_exc()

    async def create_auth_temp_record(self, session_token: str, names: Dict[str, str]) -> None:
        """Create initial record in guest_auth_temp table - matches original auth_handler method"""
        try:
            from app.core.database import db
            
            print(f"DEBUG: About to create auth temp record for session: {session_token}")
            print(f"DEBUG: Names: {names}")
            
            # First, delete any existing record to ensure clean start
            delete_result = await db.execute(
                "DELETE FROM guest_auth_temp WHERE session_id = $1",
                session_token
            )
            print(f"DEBUG: Deleted {delete_result} existing records")
            
            # Insert fresh auth temp record
            insert_result = await db.execute(
                """
                INSERT INTO guest_auth_temp (
                    session_id, first_name, last_name, created_at, expires_at
                ) VALUES ($1, $2, $3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '1 hour')
                """,
                session_token, names["first_name"], names["last_name"]
            )
            print(f"DEBUG: Insert result: {insert_result}")
            
            print(f"DEBUG: Successfully created auth temp record for {names['first_name']} {names['last_name']}")
            
        except Exception as e:
            print(f"ERROR: Failed to create auth temp record: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def get_auth_temp_data(self, session_token: str) -> Dict[str, Any]:
        """Get auth temp data from the guest_auth_temp table - matches original auth_handler method"""
        try:
            from app.core.database import db
            
            print(f"DEBUG: Getting auth temp data for session: {session_token}")
            
            result = await db.fetch(
                """
                SELECT session_id, original_intent, original_query, first_name, last_name, 
                       dob, email, phone, user_id, preferred_otp_channel, otp_attempts,
                       created_at, expires_at
                FROM guest_auth_temp 
                WHERE session_id = $1 AND expires_at > CURRENT_TIMESTAMP
                """,
                session_token
            )
            
            print(f"DEBUG: Query result: {result}")
            
            if result:
                auth_data = dict(result[0])
                # Map phone back to phone_number for consistency
                if auth_data.get("phone"):
                    auth_data["phone_number"] = auth_data["phone"]
                print(f"DEBUG: Retrieved auth data: {auth_data}")
                return auth_data
            else:
                print(f"DEBUG: No auth temp data found for session {session_token}")
                return None
            
        except Exception as e:
            print(f"ERROR: Error getting auth temp data: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def update_auth_temp_with_contact_info(self, session_token: str, contact_method: str, is_new_user: bool, user_id: int) -> bool:
        """
        Update auth temp data with contact information and user status
        """
        try:
            from app.core.database import db
            
            # Extract email and phone from contact_method
            email = contact_method if "@" in contact_method else None
            phone = contact_method if "@" not in contact_method else None
            
            # Update the record with contact information and user status
            update_result = await db.execute(
                """
                UPDATE auth_temp 
                SET email = $1, phone = $2, is_new_user = $3, user_id = $4
                WHERE session_token = $5
                """,
                email, phone, is_new_user, user_id, session_token
            )
            
            if update_result:
                print(f"[DEBUG] Updated auth temp with contact info for session: {session_token}")
                return True
            else:
                print(f"[WARNING] No auth temp record found to update for session: {session_token}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Failed to update auth temp with contact info: {e}")
            import traceback
            traceback.print_exc()
            return False
