import logging
import httpx
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.email import Email
from app.models.lead import Lead
from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailSenderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.api_key = settings.BREVO_API_KEY
        self.api_url = "https://api.brevo.com/v3/smtp/email"

    async def send_email(self, email_id: UUID) -> bool:
        """
        Connects to Brevo API and sends the email.
        """
        result = await self.session.execute(
            select(Email)
            .filter(Email.id == email_id)
        )
        email_record = result.scalars().first()
        
        if not email_record:
            logger.error(f"Email {email_id} not found.")
            return False

        if email_record.status == 'sent':
            logger.info(f"Email {email_id} already sent.")
            return True

        # Fetch Lead to get email address
        lead_result = await self.session.execute(
            select(Lead).filter(Lead.id == email_record.lead_id)
        )
        lead = lead_result.scalars().first()

        if not lead or not lead.email:
            logger.error(f"Lead not found or has no email for Email ID {email_id}")
            email_record.status = 'failed'
            await self.session.commit()
            return False

        if not self.api_key:
            logger.warning("BREVO_API_KEY not set. Operating in MOCK mode.")
            email_record.status = 'sent'
            email_record.sent_at = datetime.now(timezone.utc)
            email_record.provider_message_id = f"mock_smtp_{email_id}"
            await self.session.commit()
            return True

        is_html = "<" in email_record.body and ">" in email_record.body
        
        payload = {
            "sender": {"email": settings.BREVO_SENDER_EMAIL, "name": "GoMarg AI"},
            "to": [{"email": lead.email, "name": f"{lead.first_name or ''} {lead.last_name or ''}".strip()}],
            "subject": email_record.subject,
            "replyTo": {"email": settings.BREVO_SENDER_EMAIL}
        }
        
        if is_html:
            payload["htmlContent"] = email_record.body
        else:
            payload["textContent"] = email_record.body

        
        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                message_id = data.get("messageId")
                
                logger.info(f"\\n{'='*40}\\n[BREVO SMTP] Dispatched Email\\nID: {email_id}\\nMessage ID: {message_id}\\nTo: {lead.email}\\n{'='*40}\\n")

                email_record.status = 'sent'
                email_record.sent_at = datetime.now(timezone.utc)
                email_record.provider_message_id = message_id
                
                await self.session.commit()
                return True
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Brevo API error: {e.response.text}")
            email_record.retry_count = (email_record.retry_count or 0) + 1
            if email_record.retry_count >= 3:
                email_record.status = 'failed'
            await self.session.commit()
            return False
        except Exception as e:
            logger.error(f"Failed to send email {email_id}: {e}")
            email_record.retry_count = (email_record.retry_count or 0) + 1
            if email_record.retry_count >= 3:
                email_record.status = 'failed'
            await self.session.commit()
            return False
