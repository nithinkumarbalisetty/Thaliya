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
