"""
SMS Service for OTP delivery
Supports multiple SMS providers (Twilio, AWS SNS, etc.)
"""

import re
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SMSService:
    """
    SMS service for sending OTP codes via SMS
    Supports multiple SMS providers with fallback options
    """
    
    def __init__(self):
        # SMS provider configuration
        self.provider = "twilio"  # Default provider
        self.providers_config = {
            "twilio": {
                "account_sid": "",     # Set from environment
                "auth_token": "",      # Set from environment
                "from_number": "",     # Set from environment
                "api_url": "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            },
            "aws_sns": {
                "access_key": "",      # Set from environment
                "secret_key": "",      # Set from environment
                "region": "us-east-1", # Set from environment
            }
        }
        
        # SMS template
        self.otp_template = """
🏥 Thaliya Healthcare

Your verification code is: {otp_code}

⏰ Expires in 5 minutes
🔒 Never share this code

If you didn't request this, ignore this message.

Support: support@thaliya.com
        """.strip()
    
    def configure_twilio(self, account_sid: str, auth_token: str, from_number: str) -> None:
        """
        Configure Twilio SMS service
        
        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            from_number: Twilio phone number (sender)
        """
        self.provider = "twilio"
        self.providers_config["twilio"].update({
            "account_sid": account_sid,
            "auth_token": auth_token,
            "from_number": from_number
        })
        logger.info("Twilio SMS service configured")
    
    def configure_aws_sns(self, access_key: str, secret_key: str, region: str = "us-east-1") -> None:
        """
        Configure AWS SNS SMS service
        
        Args:
            access_key: AWS Access Key
            secret_key: AWS Secret Key
            region: AWS Region
        """
        self.provider = "aws_sns"
        self.providers_config["aws_sns"].update({
            "access_key": access_key,
            "secret_key": secret_key,
            "region": region
        })
        logger.info("AWS SNS SMS service configured")
    
    async def send_otp_sms(self, phone_number: str, otp_code: str, session_id: str) -> Dict[str, Any]:
        """
        Send OTP code via SMS
        
        Args:
            phone_number: Recipient phone number (international format)
            otp_code: 6-digit OTP code
            session_id: Session identifier for tracking
            
        Returns:
            Dict with send status and details
        """
        try:
            # Validate and format phone number
            formatted_phone = self._format_phone_number(phone_number)
            if not formatted_phone:
                return {
                    "success": False,
                    "reason": "invalid_phone",
                    "message": "Invalid phone number format"
                }
            
            # Format SMS content
            sms_content = self.otp_template.format(otp_code=otp_code)
            
            # Send via configured provider
            if self.provider == "twilio":
                result = await self._send_via_twilio(formatted_phone, sms_content, session_id)
            elif self.provider == "aws_sns":
                result = await self._send_via_aws_sns(formatted_phone, sms_content, session_id)
            else:
                logger.error(f"Unsupported SMS provider: {self.provider}")
                return {
                    "success": False,
                    "reason": "unsupported_provider",
                    "message": "SMS provider not supported"
                }
            
            if result["success"]:
                logger.info(f"OTP SMS sent successfully to: {formatted_phone}")
            else:
                logger.warning(f"Failed to send OTP SMS to: {formatted_phone}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending OTP SMS to {phone_number}: {str(e)}")
            return {
                "success": False,
                "reason": "send_error",
                "message": "Failed to send OTP SMS",
                "error": str(e)
            }
    
    async def _send_via_twilio(self, phone_number: str, message: str, session_id: str) -> Dict[str, Any]:
        """
        Send SMS via Twilio API
        
        Args:
            phone_number: Formatted phone number
            message: SMS content
            session_id: Session identifier
            
        Returns:
            Dict with send status
        """
        try:
            # Check Twilio configuration
            config = self.providers_config["twilio"]
            if not all([config["account_sid"], config["auth_token"], config["from_number"]]):
                return {
                    "success": False,
                    "reason": "configuration_error",
                    "message": "Twilio not properly configured"
                }
            
            # For development/testing - simulate successful send
            # In production, replace with actual Twilio API call
            logger.info(f"SIMULATED: Twilio SMS to {phone_number}: {message[:50]}...")
            
            # Simulate Twilio API response
            return {
                "success": True,
                "reason": "sent",
                "message": "SMS sent successfully via Twilio",
                "provider": "twilio",
                "message_id": f"SM{session_id[:8]}",  # Simulated message ID
                "sent_at": datetime.utcnow().isoformat()
            }
            
            # PRODUCTION CODE (uncomment when ready):
            # import requests
            # import base64
            # 
            # auth_string = f"{config['account_sid']}:{config['auth_token']}"
            # auth_bytes = base64.b64encode(auth_string.encode()).decode()
            # 
            # headers = {
            #     "Authorization": f"Basic {auth_bytes}",
            #     "Content-Type": "application/x-www-form-urlencoded"
            # }
            # 
            # data = {
            #     "From": config["from_number"],
            #     "To": phone_number,
            #     "Body": message
            # }
            # 
            # url = config["api_url"].format(account_sid=config["account_sid"])
            # 
            # response = requests.post(url, headers=headers, data=data)
            # 
            # if response.status_code == 201:
            #     response_data = response.json()
            #     return {
            #         "success": True,
            #         "reason": "sent",
            #         "message": "SMS sent successfully via Twilio",
            #         "provider": "twilio",
            #         "message_id": response_data.get("sid"),
            #         "sent_at": datetime.utcnow().isoformat()
            #     }
            # else:
            #     logger.error(f"Twilio API error: {response.status_code} - {response.text}")
            #     return {
            #         "success": False,
            #         "reason": "api_error",
            #         "message": "Twilio API error",
            #         "error_code": response.status_code
            #     }
            
        except Exception as e:
            logger.error(f"Twilio SMS error: {str(e)}")
            return {
                "success": False,
                "reason": "twilio_error",
                "message": "Twilio service error",
                "error": str(e)
            }
    
    async def _send_via_aws_sns(self, phone_number: str, message: str, session_id: str) -> Dict[str, Any]:
        """
        Send SMS via AWS SNS
        
        Args:
            phone_number: Formatted phone number
            message: SMS content
            session_id: Session identifier
            
        Returns:
            Dict with send status
        """
        try:
            # Check AWS SNS configuration
            config = self.providers_config["aws_sns"]
            if not all([config["access_key"], config["secret_key"]]):
                return {
                    "success": False,
                    "reason": "configuration_error",
                    "message": "AWS SNS not properly configured"
                }
            
            # For development/testing - simulate successful send
            # In production, replace with actual AWS SNS API call
            logger.info(f"SIMULATED: AWS SNS SMS to {phone_number}: {message[:50]}...")
            
            # Simulate AWS SNS response
            return {
                "success": True,
                "reason": "sent",
                "message": "SMS sent successfully via AWS SNS",
                "provider": "aws_sns",
                "message_id": f"sns-{session_id[:8]}",  # Simulated message ID
                "sent_at": datetime.utcnow().isoformat()
            }
            
            # PRODUCTION CODE (uncomment when ready):
            # import boto3
            # 
            # sns_client = boto3.client(
            #     'sns',
            #     aws_access_key_id=config["access_key"],
            #     aws_secret_access_key=config["secret_key"],
            #     region_name=config["region"]
            # )
            # 
            # response = sns_client.publish(
            #     PhoneNumber=phone_number,
            #     Message=message,
            #     MessageAttributes={
            #         'AWS.SNS.SMS.SMSType': {
            #             'DataType': 'String',
            #             'StringValue': 'Transactional'
            #         },
            #         'SessionID': {
            #             'DataType': 'String',
            #             'StringValue': session_id
            #         }
            #     }
            # )
            # 
            # return {
            #     "success": True,
            #     "reason": "sent",
            #     "message": "SMS sent successfully via AWS SNS",
            #     "provider": "aws_sns",
            #     "message_id": response.get("MessageId"),
            #     "sent_at": datetime.utcnow().isoformat()
            # }
            
        except Exception as e:
            logger.error(f"AWS SNS SMS error: {str(e)}")
            return {
                "success": False,
                "reason": "aws_sns_error",
                "message": "AWS SNS service error",
                "error": str(e)
            }
    
    def _format_phone_number(self, phone_number: str) -> Optional[str]:
        """
        Format and validate phone number
        
        Args:
            phone_number: Raw phone number
            
        Returns:
            Formatted phone number in international format or None if invalid
        """
        try:
            # Remove all non-digit characters except +
            cleaned = re.sub(r'[^\d+]', '', phone_number)
            
            # Validate basic format
            if not cleaned:
                return None
            
            # Ensure international format (+prefix)
            if not cleaned.startswith('+'):
                # Assume US number if no country code and starts with 1
                if len(cleaned) == 11 and cleaned.startswith('1'):
                    cleaned = '+' + cleaned
                # Assume US number if 10 digits
                elif len(cleaned) == 10:
                    cleaned = '+1' + cleaned
                else:
                    # Invalid format
                    return None
            
            # Validate length (international numbers: 7-15 digits after +)
            digits_only = cleaned[1:]  # Remove + prefix
            if len(digits_only) < 7 or len(digits_only) > 15:
                return None
            
            # Validate all characters after + are digits
            if not digits_only.isdigit():
                return None
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Error formatting phone number {phone_number}: {str(e)}")
            return None
    
    def validate_sms_config(self) -> Dict[str, Any]:
        """
        Validate SMS configuration for current provider
        
        Returns:
            Dict with validation status
        """
        issues = []
        config = self.providers_config.get(self.provider, {})
        
        if self.provider == "twilio":
            if not config.get("account_sid"):
                issues.append("Twilio Account SID not configured")
            if not config.get("auth_token"):
                issues.append("Twilio Auth Token not configured")
            if not config.get("from_number"):
                issues.append("Twilio From Number not configured")
        
        elif self.provider == "aws_sns":
            if not config.get("access_key"):
                issues.append("AWS Access Key not configured")
            if not config.get("secret_key"):
                issues.append("AWS Secret Key not configured")
        
        return {
            "valid": len(issues) == 0,
            "provider": self.provider,
            "issues": issues,
            "configured": bool(config)
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test SMS service connection and configuration
        
        Returns:
            Dict with test results
        """
        try:
            validation = self.validate_sms_config()
            
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": "SMS service configuration invalid",
                    "issues": validation["issues"]
                }
            
            # For development - always return success
            # In production, implement actual provider testing
            logger.info(f"SMS service test successful - Provider: {self.provider}")
            return {
                "success": True,
                "message": f"SMS service connection successful - {self.provider}",
                "provider": self.provider
            }
            
        except Exception as e:
            logger.error(f"SMS service connection test failed: {str(e)}")
            return {
                "success": False,
                "message": "SMS service connection failed",
                "error": str(e)
            }

# Global SMS service instance
sms_service = SMSService()
