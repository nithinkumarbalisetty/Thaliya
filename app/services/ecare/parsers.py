"""
Data parsing utilities for E-Care service
Handles parsing of user input for names, dates, emails, and phone numbers
"""

import re
from datetime import datetime
from typing import Dict, Optional, Any


class ECareDataParsers:
    """Handles parsing of user input data"""

    def parse_names(self, user_input: str) -> Optional[Dict[str, str]]:
        """Parse first and last name from user input"""
        # Simple parsing - you can enhance this
        words = user_input.strip().split()
        if len(words) >= 2:
            return {
                "first_name": words[0].capitalize(),
                "last_name": " ".join(words[1:]).capitalize()
            }
        return None

    def parse_dob_email(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Parse date of birth, email, and optional phone number from user input"""
        # Look for date pattern (MM/DD/YYYY or MM-DD-YYYY)
        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})'
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        # Phone pattern: supports various formats like (123) 456-7890, 123-456-7890, 1234567890
        phone_pattern = r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})'
        
        date_match = re.search(date_pattern, user_input)
        email_match = re.search(email_pattern, user_input)
        phone_match = re.search(phone_pattern, user_input)
        
        if date_match and (email_match or phone_match):
            date_str = date_match.group(1)
            
            # Convert date string to proper date object
            try:
                # Handle both MM/DD/YYYY and MM-DD-YYYY formats
                date_str = date_str.replace('-', '/')
                dob_date = datetime.strptime(date_str, '%m/%d/%Y').date()
                
                result = {
                    "dob": dob_date,  # Now it's a proper date object
                }
                
                if email_match:
                    result["email"] = email_match.group(1)
                    
                if phone_match:
                    # Clean up phone number (remove non-digits)
                    phone = re.sub(r'[^\d]', '', phone_match.group(1))
                    result["phone_number"] = phone
                
                return result
                
            except ValueError as e:
                print(f"Error parsing date {date_str}: {e}")
                return None
        
        return None

    def extract_ticket_type(self, original_query: str) -> str:
        """Extract the type of ticket from the original query"""
        query_lower = original_query.lower()
        
        ticket_types = {
            "prescription_refill": ['prescription', 'refill', 'medication'],
            "billing": ['billing', 'bill', 'payment', 'insurance'],
            "lab_results": ['result', 'lab', 'test'],
            "referral": ['referral', 'specialist']
        }
        
        for ticket_type, keywords in ticket_types.items():
            if any(word in query_lower for word in keywords):
                return ticket_type
        
        return "general_support"

    def extract_appointment_type(self, user_query: str) -> str:
        """Extract appointment type from user query"""
        query_lower = user_query.lower()
        
        appointment_types = {
            "cardiology": ['cardio', 'heart', 'chest pain'],
            "dental": ['dental', 'tooth', 'teeth'],
            "ophthalmology": ['eye', 'vision', 'glasses'],
            "dermatology": ['skin', 'rash', 'dermat'],
            "general_checkup": ['check', 'physical', 'routine']
        }
        
        for appointment_type, keywords in appointment_types.items():
            if any(word in query_lower for word in keywords):
                return appointment_type
        
        return "general"

    def determine_ticket_priority(self, user_query: str) -> str:
        """Determine ticket priority based on keywords"""
        query_lower = user_query.lower()
        
        if any(word in query_lower for word in ['urgent', 'emergency', 'pain', 'bleeding']):
            return "high"
        elif any(word in query_lower for word in ['soon', 'important', 'medication']):
            return "medium"
        else:
            return "low"
