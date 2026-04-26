"""
Email notification service for execution completion/failure updates.
"""
from __future__ import annotations

import html
import logging
import smtplib
import time
from datetime import datetime
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy.orm import Session

from core.config import settings
from models.execution import Execution
from models.user import User

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"completed", "failed"}


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class EmailService:
    """Service for sending execution status email notifications."""

    @staticmethod
    def notify_execution_status(db: Session, execution: Execution) -> bool:
        """
        Send terminal status email (completed/failed) and update notification flags.
        This method is idempotent using execution.notification_sent.
        """
        # Check if notifications are enabled
        if not settings.IS_NOTIFICATION_ENABLED:
            logger.info(
                "email_notification_skipped ts=%s reason=notifications_disabled execution_id=%s",
                _utc_now_iso(),
                execution.id,
            )
            return False
        
        normalized_status = (execution.status or "").strip().lower()
        if normalized_status not in TERMINAL_STATUSES:
            return False

        if bool(execution.notification_sent):
            return True

        recipient_email = EmailService._resolve_recipient_email(db, execution)
        if not recipient_email:
            logger.warning(
                "email_notification_skipped ts=%s reason=no_recipient execution_id=%s status=%s created_by=%s",
                _utc_now_iso(),
                execution.id,
                normalized_status,
                execution.created_by,
            )
            return False

        if not EmailService._is_smtp_configured():
            logger.warning(
                "email_notification_skipped ts=%s reason=smtp_not_configured execution_id=%s recipient=%s status=%s",
                _utc_now_iso(),
                execution.id,
                recipient_email,
                normalized_status,
            )
            return False

        subject = EmailService._build_subject(execution)
        html_body = EmailService._build_html_body(execution, normalized_status)
        success = EmailService._send_html_email_with_retry(
            recipient_email=recipient_email,
            subject=subject,
            html_body=html_body,
            status=normalized_status,
            execution_id=str(execution.id),
        )

        if success:
            execution.notification_sent = True
            execution.notification_sent_at = datetime.utcnow()
            db.commit()
            db.refresh(execution)

        return success

    @staticmethod
    def _resolve_recipient_email(db: Session, execution: Execution) -> str:
        created_by = (execution.created_by or "").strip()
        if not created_by:
            return ""

        user = db.query(User).filter(User.id == created_by).first()
        if user and isinstance(user.email, str):
            return user.email.strip()

        # Backward-compatible fallback when created_by itself stores an email-like value.
        if "@" in created_by:
            return created_by

        return ""

    @staticmethod
    def _is_smtp_configured() -> bool:
        host = (settings.SMTP_HOST or "").strip()
        from_email = (settings.SMTP_FROM_EMAIL or "").strip()
        return bool(host and from_email)

    @staticmethod
    def _resolve_smtp_auth() -> tuple[Optional[str], Optional[str]]:
        """
        Auth precedence:
        1) SMTP_API_KEY (SendGrid style; defaults username to "apikey")
        2) SMTP_USER + SMTP_PASSWORD
        """
        smtp_api_key = (settings.SMTP_API_KEY or "").strip()
        smtp_user = (settings.SMTP_USER or "").strip()
        smtp_password = (settings.SMTP_PASSWORD or "").strip()

        if smtp_api_key:
            return (smtp_user or "apikey"), smtp_api_key

        if smtp_user and smtp_password:
            return smtp_user, smtp_password

        return None, None

    @staticmethod
    def _send_html_email_with_retry(
        *,
        recipient_email: str,
        subject: str,
        html_body: str,
        status: str,
        execution_id: str,
    ) -> bool:
        max_attempts = max(1, min(3, int(settings.SMTP_MAX_RETRIES or 3)))
        base_backoff_seconds = max(1, int(settings.SMTP_RETRY_BACKOFF_SECONDS or 1))
        timeout_seconds = max(5, int(settings.SMTP_TIMEOUT_SECONDS or 30))

        smtp_user, smtp_secret = EmailService._resolve_smtp_auth()
        from_email = (settings.SMTP_FROM_EMAIL or "").strip()
        from_name = (settings.SMTP_FROM_NAME or "Evidence Analysis System").strip()

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "email_notification_attempt ts=%s recipient=%s status=%s execution_id=%s attempt=%s",
                    _utc_now_iso(),
                    recipient_email,
                    status,
                    execution_id,
                    attempt,
                )

                message = MIMEMultipart("alternative")
                message["Subject"] = subject
                message["From"] = f"{from_name} <{from_email}>"
                message["To"] = recipient_email
                message.attach(MIMEText(html_body, "html", "utf-8"))

                with smtplib.SMTP(
                    host=settings.SMTP_HOST,
                    port=int(settings.SMTP_PORT),
                    timeout=timeout_seconds,
                ) as smtp_server:
                    if settings.SMTP_USE_TLS:
                        smtp_server.starttls()
                    if smtp_user and smtp_secret:
                        smtp_server.login(smtp_user, smtp_secret)
                    smtp_server.send_message(message)

                logger.info(
                    "email_notification_sent ts=%s recipient=%s status=%s execution_id=%s attempt=%s",
                    _utc_now_iso(),
                    recipient_email,
                    status,
                    execution_id,
                    attempt,
                )
                return True
            except (smtplib.SMTPException, OSError, TimeoutError) as exc:
                if attempt >= max_attempts:
                    logger.error(
                        "email_notification_failed ts=%s recipient=%s status=%s execution_id=%s attempts=%s error=%s",
                        _utc_now_iso(),
                        recipient_email,
                        status,
                        execution_id,
                        attempt,
                        exc,
                    )
                    return False

                delay_seconds = base_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "email_notification_retry ts=%s recipient=%s status=%s execution_id=%s attempt=%s delay_seconds=%s error=%s",
                    _utc_now_iso(),
                    recipient_email,
                    status,
                    execution_id,
                    attempt,
                    delay_seconds,
                    exc,
                )
                time.sleep(delay_seconds)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "email_notification_failed_unexpected ts=%s recipient=%s status=%s execution_id=%s error=%s",
                    _utc_now_iso(),
                    recipient_email,
                    status,
                    execution_id,
                    exc,
                )
                return False

        return False

    @staticmethod
    def _build_subject(execution: Execution) -> str:
        execution_name = (execution.name or "Analysis").strip()
        status_label = (execution.status or "updated").strip().lower()
        if status_label == "completed":
            return f"✓ Your Analysis is Ready: {execution_name}"
        elif status_label == "failed":
            return f"⚠ Action Required: {execution_name} Analysis Failed"
        return f"Evidence Analysis Update: {execution_name}"

    @staticmethod
    def _build_html_body(execution: Execution, normalized_status: str) -> str:
        if normalized_status == "completed":
            return EmailService._create_success_email(execution)
        return EmailService._create_failure_email(execution)

    @staticmethod
    def _portal_base_url() -> str:
        base_url = (settings.PORTAL_BASE_URL or "").strip() or "http://localhost:5173"
        return base_url.rstrip("/")

    @staticmethod
    def _execution_link(execution: Execution) -> str:
        return f"{EmailService._portal_base_url()}/executions/{execution.id}"

    @staticmethod
    def _report_link(execution: Execution) -> str:
        return f"{EmailService._portal_base_url()}/reports/{execution.id}"

    @staticmethod
    def _processing_seconds(execution: Execution) -> Optional[float]:
        if execution.processing_started_at and execution.processing_completed_at:
            delta_seconds = (
                execution.processing_completed_at - execution.processing_started_at
            ).total_seconds()
            if delta_seconds >= 0:
                return float(delta_seconds)

        if execution.average_processing_time is not None and execution.processed_rows:
            return float(execution.average_processing_time) * int(execution.processed_rows or 0)

        return None

    @staticmethod
    def _format_processing_time(seconds: Optional[float]) -> str:
        if seconds is None:
            return "N/A"

        total_seconds = max(0, int(round(seconds)))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        if minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    @staticmethod
    def _format_cost(value: Optional[Decimal]) -> str:
        if value is None:
            return "N/A"
        return f"${float(value):.4f}"

    @staticmethod
    def _create_success_email(execution: Execution) -> str:
        execution_name = html.escape((execution.name or "Your Analysis").strip())
        processing_time = html.escape(
            EmailService._format_processing_time(EmailService._processing_seconds(execution))
        )
        cost_display = html.escape(
            EmailService._format_cost(execution.actual_cost or execution.estimated_cost)
        )
        processed_rows = html.escape(str(execution.processed_rows or 0))
        total_rows = html.escape(str(execution.total_rows or execution.processed_rows or 0))
        report_link = html.escape(EmailService._report_link(execution))

        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background: #f9fafb; }}
                .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #fff; padding: 32px 24px; border-radius: 12px 12px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
                .content {{ background: #ffffff; padding: 32px 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
                .status-badge {{ display: inline-block; padding: 6px 16px; border-radius: 20px; background: #d1fae5; color: #065f46; font-weight: 600; font-size: 14px; margin-bottom: 20px; }}
                .message {{ font-size: 16px; color: #374151; margin-bottom: 24px; line-height: 1.7; }}
                .details {{ width: 100%; border-collapse: collapse; margin: 24px 0; background: #f9fafb; border-radius: 8px; overflow: hidden; }}
                .details tr {{ border-bottom: 1px solid #e5e7eb; }}
                .details tr:last-child {{ border-bottom: none; }}
                .details td {{ padding: 14px 16px; font-size: 14px; }}
                .details td:first-child {{ color: #6b7280; font-weight: 500; width: 42%; }}
                .details td:last-child {{ color: #111827; font-weight: 600; }}
                .cta-button {{ display: inline-block; margin: 24px 0 16px 0; padding: 14px 28px; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: #ffffff !important; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(37, 99, 235, 0.3); transition: all 0.2s; }}
                .cta-button:hover {{ box-shadow: 0 6px 8px rgba(37, 99, 235, 0.4); transform: translateY(-1px); }}
                .footer {{ margin-top: 24px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; text-align: center; }}
                .help-text {{ font-size: 13px; color: #6b7280; margin-top: 16px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✓ Analysis Completed</h1>
                </div>
                <div class="content">
                    <h2 style="margin: 0 0 12px 0; font-size: 20px; color: #111827;">{execution_name}</h2>
                    <span class="status-badge">COMPLETED</span>
                    <p class="message">
                        Great news! Your analysis has been successfully completed and the results are ready for review. 
                        Click the button below to view your comprehensive analysis report.
                    </p>
                    <table class="details">
                        <tr><td>Processing Time</td><td>{processing_time}</td></tr>
                        <tr><td>Processing Cost</td><td>{cost_display}</td></tr>
                        <tr><td>Processed Rows</td><td>{processed_rows}</td></tr>
                        <tr><td>Total Rows</td><td>{total_rows}</td></tr>
                    </table>
                    <div style="text-align: center;">
                        <a class="cta-button" href="{report_link}" target="_blank" rel="noopener noreferrer">View Report</a>
                    </div>
                    <p class="help-text">
                        💡 Need help interpreting the results? Contact your program coordinator for assistance.
                    </p>
                    <div class="footer">
                        This is an automated notification from Evidence Analysis System.<br/>
                        Please do not reply to this email.
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    @staticmethod
    def _create_failure_email(execution: Execution) -> str:
        execution_name = html.escape((execution.name or "Your Analysis").strip())
        processing_time = html.escape(
            EmailService._format_processing_time(EmailService._processing_seconds(execution))
        )
        cost_display = html.escape(
            EmailService._format_cost(execution.actual_cost or execution.estimated_cost)
        )
        failure_reason = html.escape((execution.failure_reason or "An unexpected error occurred during processing").strip())
        retry_count = int(execution.retry_count or 0)
        max_retries = int(settings.CELERY_MAX_RETRIES or 3)
        execution_link = html.escape(EmailService._execution_link(execution))

        return f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; background: #f9fafb; }}
                .header {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); color: #fff; padding: 32px 24px; border-radius: 12px 12px 0 0; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; font-weight: 600; }}
                .content {{ background: #ffffff; padding: 32px 24px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 12px 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
                .status-badge {{ display: inline-block; padding: 6px 16px; border-radius: 20px; background: #fee2e2; color: #991b1b; font-weight: 600; font-size: 14px; margin-bottom: 20px; }}
                .message {{ font-size: 16px; color: #374151; margin-bottom: 24px; line-height: 1.7; }}
                .details {{ width: 100%; border-collapse: collapse; margin: 24px 0; background: #f9fafb; border-radius: 8px; overflow: hidden; }}
                .details tr {{ border-bottom: 1px solid #e5e7eb; }}
                .details tr:last-child {{ border-bottom: none; }}
                .details td {{ padding: 14px 16px; font-size: 14px; }}
                .details td:first-child {{ color: #6b7280; font-weight: 500; width: 42%; }}
                .details td:last-child {{ color: #111827; font-weight: 600; }}
                .error-box {{ margin: 20px 0; background: #fef2f2; border-left: 4px solid #ef4444; border-radius: 8px; padding: 16px; }}
                .error-box strong {{ color: #991b1b; font-size: 15px; }}
                .error-box p {{ color: #7f1d1d; margin: 8px 0 0 0; font-size: 14px; }}
                .action-box {{ margin: 20px 0; background: #eff6ff; border-left: 4px solid #3b82f6; border-radius: 8px; padding: 16px; }}
                .action-box strong {{ color: #1e40af; font-size: 15px; display: block; margin-bottom: 10px; }}
                .action-box ul {{ margin: 0; padding-left: 20px; color: #1e3a8a; }}
                .action-box li {{ margin: 6px 0; font-size: 14px; }}
                .cta-button {{ display: inline-block; margin: 24px 0 16px 0; padding: 14px 28px; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: #ffffff !important; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px; box-shadow: 0 4px 6px rgba(37, 99, 235, 0.3); transition: all 0.2s; }}
                .cta-button:hover {{ box-shadow: 0 6px 8px rgba(37, 99, 235, 0.4); transform: translateY(-1px); }}
                .footer {{ margin-top: 24px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; text-align: center; }}
                .help-text {{ font-size: 13px; color: #6b7280; margin-top: 16px; padding: 12px; background: #f3f4f6; border-radius: 6px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠ Analysis Failed</h1>
                </div>
                <div class="content">
                    <h2 style="margin: 0 0 12px 0; font-size: 20px; color: #111827;">{execution_name}</h2>
                    <span class="status-badge">FAILED</span>
                    <p class="message">
                        We encountered an issue while processing your analysis. The system attempted {retry_count} of {max_retries} retries, 
                        but was unable to complete the task. Please review the error details below and take appropriate action.
                    </p>
                    <table class="details">
                        <tr><td>Processing Time</td><td>{processing_time}</td></tr>
                        <tr><td>Processing Cost</td><td>{cost_display}</td></tr>
                        <tr><td>Retry Attempts</td><td>{retry_count} of {max_retries}</td></tr>
                    </table>
                    <div class="error-box">
                        <strong>⚠ Error Details</strong>
                        <p>{failure_reason}</p>
                    </div>
                    <div class="action-box">
                        <strong>📋 What You Can Do</strong>
                        <ul>
                            <li>Check your input files for formatting or data issues</li>
                            <li>Verify that all required criteria are properly configured</li>
                            <li>Review the analysis details for more diagnostic information</li>
                            <li>Contact support if the issue persists</li>
                        </ul>
                    </div>
                    <div style="text-align: center;">
                        <a class="cta-button" href="{execution_link}" target="_blank" rel="noopener noreferrer">View Analysis Details</a>
                    </div>
                    <p class="help-text">
                        <strong>Need Help?</strong> Contact your program coordinator or technical support team for assistance with this analysis.
                    </p>
                    <div class="footer">
                        This is an automated notification from Evidence Analysis System.<br/>
                        Please do not reply to this email.
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
