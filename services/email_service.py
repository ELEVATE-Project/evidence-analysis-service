"""
Email notification service
Sends email alerts on execution completion/failure
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

from core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications"""
    
    @staticmethod
    def send_completion_email(
        recipient_email: str,
        execution_name: str,
        execution_id: str,
        status: str,
        details: Optional[dict] = None
    ) -> bool:
        """
        Send execution completion/failure email
        
        Args:
            recipient_email: Email address of recipient
            execution_name: Name of the execution
            execution_id: ID of the execution
            status: Status (completed or failed)
            details: Additional details to include
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.warning("SMTP not configured, skipping email notification")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Evidence Analysis: {execution_name} - {status.upper()}"
            msg['From'] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg['To'] = recipient_email
            
            # Create email body
            if status == 'completed':
                html_body = EmailService._create_success_email(
                    execution_name, execution_id, details
                )
            else:
                html_body = EmailService._create_failure_email(
                    execution_name, execution_id, details
                )
            
            # Attach HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                if settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False
    
    @staticmethod
    def _create_success_email(execution_name: str, execution_id: str, details: Optional[dict]) -> str:
        """Create HTML body for success email"""
        total_rows = details.get('total_rows', 'N/A') if details else 'N/A'
        processing_time = details.get('processing_time', 'N/A') if details else 'N/A'
        
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9f9f9; }}
                .footer {{ padding: 10px; text-align: center; color: #666; font-size: 12px; }}
                .metric {{ display: inline-block; margin: 10px 20px; }}
                .metric-label {{ font-weight: bold; color: #333; }}
                .metric-value {{ color: #4CAF50; font-size: 18px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✓ Execution Completed Successfully</h1>
                </div>
                <div class="content">
                    <h2>{execution_name}</h2>
                    <p><strong>Execution ID:</strong> {execution_id}</p>
                    <p><strong>Status:</strong> <span style="color: #4CAF50;">COMPLETED</span></p>
                    
                    <div style="margin: 20px 0;">
                        <div class="metric">
                            <div class="metric-label">Total Rows</div>
                            <div class="metric-value">{total_rows}</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Processing Time</div>
                            <div class="metric-value">{processing_time}</div>
                        </div>
                    </div>
                    
                    <p>Your evidence analysis execution has completed successfully. 
                    You can view the results in the portal.</p>
                </div>
                <div class="footer">
                    <p>Evidence Analysis System | Automated Notification</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    @staticmethod
    def _create_failure_email(execution_name: str, execution_id: str, details: Optional[dict]) -> str:
        """Create HTML body for failure email"""
        error_message = details.get('error_message', 'Unknown error') if details else 'Unknown error'
        
        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #f44336; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background: #f9f9f9; }}
                .footer {{ padding: 10px; text-align: center; color: #666; font-size: 12px; }}
                .error-box {{ background: #ffebee; border-left: 4px solid #f44336; padding: 15px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✗ Execution Failed</h1>
                </div>
                <div class="content">
                    <h2>{execution_name}</h2>
                    <p><strong>Execution ID:</strong> {execution_id}</p>
                    <p><strong>Status:</strong> <span style="color: #f44336;">FAILED</span></p>
                    
                    <div class="error-box">
                        <strong>Error Details:</strong><br>
                        {error_message}
                    </div>
                    
                    <p>Your evidence analysis execution has failed. 
                    Please check the error details and try again.</p>
                </div>
                <div class="footer">
                    <p>Evidence Analysis System | Automated Notification</p>
                </div>
            </div>
        </body>
        </html>
        """
