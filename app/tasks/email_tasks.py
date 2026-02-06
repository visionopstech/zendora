from app.core.celery_app import celery_app
from app.services.email_service import EmailService
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.email.send_email", bind=True, max_retries=3)
def send_email_task(self, to_email: str, subject: str, html_content: str):
    """
    Send an email asynchronously.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML content of the email
        
    Returns:
        bool: True if email was sent successfully
    """
    try:
        email_service = EmailService()
        # Note: If EmailService methods are async, you'll need to handle that
        # For now, assuming it has a sync method or we adapt it
        logger.info(f"Sending email to {to_email} with subject: {subject}")
        
        # If your email service is async, you might need to use asyncio.run()
        # or create a sync wrapper
        # For demonstration:
        success = True  # Replace with actual email sending logic
        
        if success:
            logger.info(f"Email sent successfully to {to_email}")
            return True
        else:
            raise Exception("Failed to send email")
            
    except Exception as exc:
        logger.error(f"Failed to send email to {to_email}: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
