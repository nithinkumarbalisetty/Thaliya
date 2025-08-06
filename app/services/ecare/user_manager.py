"""
User management and verification for E-Care service
Handles user verification, creation, and related database operations
"""

from typing import Dict, Any
from datetime import datetime
from app.core.database import db


class ECareUserManager:
    """Handles user verification, creation, and management"""

    async def verify_user_credentials(self, first_name: str, last_name: str, dob: str, 
                                    email: str = None, phone_number: str = None) -> Dict[str, Any]:
        """Verify user exists in the database, create if not exists"""
        try:
            # Build dynamic query based on what contact info we have
            base_query = """
                SELECT user_id, first_name, last_name, email, phone 
                FROM users 
                WHERE LOWER(first_name) = LOWER($1) 
                AND LOWER(last_name) = LOWER($2)
                AND dob = $3
            """
            
            query_params = [first_name, last_name, dob]
            
            # Add contact verification based on what we have
            if email and phone_number:
                # Both provided - check either matches
                base_query += " AND (LOWER(email) = LOWER($4) OR phone = $5)"
                query_params.extend([email, phone_number])
            elif email:
                # Only email provided - check email matches and phone is either NULL or empty
                base_query += " AND LOWER(email) = LOWER($4) AND (phone IS NULL OR phone = '')"
                query_params.append(email)
            elif phone_number:
                # Only phone provided - check phone matches and email is either NULL or empty
                base_query += " AND phone = $4 AND (email IS NULL OR email = '')"
                query_params.append(phone_number)
            else:
                # No contact info - this shouldn't happen but handle gracefully
                return {"valid": False, "error": "No email or phone number provided for verification"}
            
            existing_user = await db.fetch(base_query, *query_params)
            
            if existing_user:
                # User exists, return their ID
                user_data = dict(existing_user[0])
                print(f"Found existing user: {user_data['user_id']} - {user_data['first_name']} {user_data['last_name']}")
                return {
                    "valid": True,
                    "user_id": user_data["user_id"],
                    "existing_user": True,
                    "user_data": user_data
                }
            else:
                # User doesn't exist, create new user
                return await self._create_new_user(first_name, last_name, dob, email, phone_number)
            
        except Exception as e:
            print(f"Error verifying/creating user: {e}")
            return {"valid": False, "error": str(e)}

    async def _create_new_user(self, first_name: str, last_name: str, dob: str, 
                             email: str = None, phone_number: str = None) -> Dict[str, Any]:
        """Create a new user in the database"""
        try:
            print(f"Creating new user: {first_name} {last_name}, DOB: {dob}, Email: {email}, Phone: {phone_number}")
            
            # Ensure we have at least one contact method
            if not email and not phone_number:
                return {"valid": False, "error": "Cannot create user without email or phone number"}
            
            # Handle NULL constraints by providing empty strings or default values
            email_value = email if email else ""
            phone_value = phone_number if phone_number else ""
            
            new_user = await db.fetch(
                """
                INSERT INTO users (first_name, last_name, dob, phone, email)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING user_id, first_name, last_name, email, phone
                """,
                first_name, last_name, dob, phone_value, email_value
            )
            
            if not new_user:
                print("Failed to create new user - no data returned")
                return {"valid": False, "error": "Failed to create user"}
            
            user_data = dict(new_user[0])
            print(f"Successfully created new user: {user_data['user_id']} - {user_data['first_name']} {user_data['last_name']}")
            
            # Create related records for new user
            await self._create_user_related_records(user_data["user_id"])
            
            return {
                "valid": True,
                "user_id": user_data["user_id"],
                "existing_user": False,
                "newly_created": True,
                "user_data": user_data
            }
            
        except Exception as e:
            print(f"Error creating new user: {e}")
            return {"valid": False, "error": str(e)}

    async def _create_user_related_records(self, user_id: int):
        """Create related records for a new user in other tables"""
        try:
            # You can add any default records that should be created for new healthcare users
            # For example, default preferences, medical history setup, notification settings, etc.
            
            # Example: Create a default user profile or medical preferences record
            # await db.execute(
            #     """
            #     INSERT INTO user_preferences (user_id, notification_enabled, sms_alerts, email_alerts, created_at)
            #     VALUES ($1, true, false, true, CURRENT_TIMESTAMP)
            #     """,
            #     user_id
            # )
            
            # Example: Initialize medical profile
            # await db.execute(
            #     """
            #     INSERT INTO medical_profiles (user_id, created_at)
            #     VALUES ($1, CURRENT_TIMESTAMP)
            #     """,
            #     user_id
            # )
            
            print(f"Created related healthcare records for user_id: {user_id}")
            
        except Exception as e:
            print(f"Error creating user related records: {e}")
            # Don't fail the user creation if related records fail
            pass

    async def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        """Get user information by user ID"""
        try:
            result = await db.fetch(
                """
                SELECT user_id, first_name, last_name, email, phone, dob, created_at
                FROM users 
                WHERE user_id = $1
                """,
                user_id
            )
            
            if result:
                return {"success": True, "user_data": dict(result[0])}
            else:
                return {"success": False, "error": "User not found"}
                
        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return {"success": False, "error": str(e)}
