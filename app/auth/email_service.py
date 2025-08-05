"""
Email Service for OTP delivery
Supports multiple email providers with fallback options
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailService:
    """
    Email service for sending OTP codes via email
    Supports SMTP configuration and HTML email templates
    """
    
    def __init__(self):
        # Email configuration (should be loaded from environment)
        self.smtp_server = "smtp.gmail.com"  # Default to Gmail
        self.smtp_port = 587
        self.smtp_username = ""  # Set from environment
        self.smtp_password = ""  # Set from environment (app password)
        self.from_email = ""     # Set from environment
        self.from_name = "Thaliya Healthcare"
        
        # Email template
        self.otp_template = {
            "subject": "Your Thaliya Healthcare Verification Code",
            "html_body": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OTP Verification - Thaliya Healthcare</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .container {
            background-color: #ffffff;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .logo {
            font-size: 28px;
            font-weight: bold;
            color: #007bff;
            margin-bottom: 10px;
        }
        .otp-code {
            background-color: #007bff;
            color: white;
            font-size: 32px;
            font-weight: bold;
            letter-spacing: 8px;
            text-align: center;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            box-shadow: 0 2px 5px rgba(0,123,255,0.3);
        }
        .message {
            font-size: 16px;
            margin: 20px 0;
            text-align: center;
        }
        .warning {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            font-size: 14px;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #666;
        }
        .help-link {
            color: #007bff;
            text-decoration: none;
        }
        .help-link:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🏥 Thaliya Healthcare</div>
            <p>Secure Healthcare Services</p>
        </div>
        
        <div class="message">
            <h2>Email Verification Required</h2>
            <p>Please use the following verification code to complete your authentication:</p>
        </div>
        
        <div class="otp-code">
            {otp_code}
        </div>
        
        <div class="message">
            <p><strong>This code will expire in 5 minutes.</strong></p>
            <p>Enter this code in the Thaliya Healthcare application to verify your email address.</p>
        </div>
        
        <div class="warning">
            <strong>Security Notice:</strong>
            <ul style="margin: 10px 0; padding-left: 20px;">
                <li>Never share this code with anyone</li>
                <li>Thaliya Healthcare will never ask for this code via phone or email</li>
                <li>If you didn't request this code, please ignore this email</li>
            </ul>
        </div>
        
        <div class="footer">
            <p>This email was sent to: <strong>{email_address}</strong></p>
            <p>Sent on: {timestamp}</p>
            <br>
            <p>Need help? Contact our support team at <a href="mailto:support@thaliya.com" class="help-link">support@thaliya.com</a></p>
            <p>&copy; 2024 Thaliya Healthcare. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
            """,
            "text_body": """
Thaliya Healthcare - Email Verification

Your verification code is: {otp_code}

This code will expire in 5 minutes.
Please enter this code in the Thaliya Healthcare application to verify your email.

Security Notice:
- Never share this code with anyone
- Thaliya Healthcare will never ask for this code via phone or email
- If you didn't request this code, please ignore this email

This email was sent to: {email_address}
Sent on: {timestamp}

Need help? Contact support@thaliya.com
© 2024 Thaliya Healthcare. All rights reserved.
            """
        }
    
    def configure(self, smtp_config: Dict[str, str]) -> None:
        """
        Configure email service with SMTP settings
        
        Args:
            smtp_config: Dictionary with SMTP configuration
        """
        self.smtp_server = smtp_config.get("smtp_server", self.smtp_server)
        self.smtp_port = int(smtp_config.get("smtp_port", self.smtp_port))
        self.smtp_username = smtp_config.get("smtp_username", "")
        self.smtp_password = smtp_config.get("smtp_password", "")
        self.from_email = smtp_config.get("from_email", "")
        self.from_name = smtp_config.get("from_name", self.from_name)
        
        logger.info(f"Email service configured with SMTP server: {self.smtp_server}:{self.smtp_port}")
    
    async def send_otp_email(self, email_address: str, otp_code: str, session_id: str) -> Dict[str, Any]:
        """
        Send OTP code via email
        
        Args:
            email_address: Recipient email address
            otp_code: 6-digit OTP code
            session_id: Session identifier for tracking
            
        Returns:
            Dict with send status and details
        """
        try:
            # Validate email configuration
            if not all([self.smtp_username, self.smtp_password, self.from_email]):
                logger.error("Email service not properly configured")
                return {
                    "success": False,
                    "reason": "configuration_error",
                    "message": "Email service not configured"
                }
            
            # Create email message
            message = MIMEMultipart("alternative")
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = email_address
            message["Subject"] = self.otp_template["subject"]
            
            # Add custom headers for tracking
            message["X-Session-ID"] = session_id
            message["X-Priority"] = "1"  # High priority
            
            # Format email content
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            
            # Plain text version
            text_content = self.otp_template["text_body"].format(
                otp_code=otp_code,
                email_address=email_address,
                timestamp=timestamp
            )
            
            # HTML version
            html_content = self.otp_template["html_body"].format(
                otp_code=otp_code,
                email_address=email_address,
                timestamp=timestamp
            )
            
            # Attach both versions
            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")
            
            message.attach(text_part)
            message.attach(html_part)
            
            # Send email
            await self._send_email(message, email_address)
            
            logger.info(f"OTP email sent successfully to: {email_address}")
            return {
                "success": True,
                "reason": "sent",
                "message": "OTP email sent successfully",
                "sent_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error sending OTP email to {email_address}: {str(e)}")
            return {
                "success": False,
                "reason": "send_error",
                "message": "Failed to send OTP email",
                "error": str(e)
            }
    
    async def _send_email(self, message: MIMEMultipart, recipient: str) -> None:
        """
        Internal method to send email via SMTP
        
        Args:
            message: Formatted email message
            recipient: Recipient email address
        """
        try:
            # Create secure SSL context
            context = ssl.create_default_context()
            
            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                # Enable security
                server.starttls(context=context)
                
                # Login to server
                server.login(self.smtp_username, self.smtp_password)
                
                # Send email
                server.send_message(message, to_addrs=[recipient])
                
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {str(e)}")
            raise Exception("Email authentication failed")
        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"Recipient email refused: {str(e)}")
            raise Exception("Invalid recipient email address")
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {str(e)}")
            raise Exception("Email delivery failed")
        except Exception as e:
            logger.error(f"Unexpected error sending email: {str(e)}")
            raise
    
    def validate_email_config(self) -> Dict[str, Any]:
        """
        Validate email configuration
        
        Returns:
            Dict with validation status
        """
        issues = []
        
        if not self.smtp_username:
            issues.append("SMTP username not configured")
        if not self.smtp_password:
            issues.append("SMTP password not configured")
        if not self.from_email:
            issues.append("From email address not configured")
        if not self.smtp_server:
            issues.append("SMTP server not configured")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "configured_server": f"{self.smtp_server}:{self.smtp_port}",
            "from_email": self.from_email
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test SMTP connection and authentication
        
        Returns:
            Dict with test results
        """
        try:
            context = ssl.create_default_context()
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                
            logger.info("Email service connection test successful")
            return {
                "success": True,
                "message": "Email service connection successful",
                "server": f"{self.smtp_server}:{self.smtp_port}"
            }
            
        except Exception as e:
            logger.error(f"Email service connection test failed: {str(e)}")
            return {
                "success": False,
                "message": "Email service connection failed",
                "error": str(e)
            }

# Global email service instance
email_service = EmailService()
