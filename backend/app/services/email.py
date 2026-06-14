import httpx
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

class EmailService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.api_key = settings.BREVO_API_KEY
        self.sender_email = settings.BREVO_SENDER_EMAIL
        self.base_url = "https://api.brevo.com/v3/smtp/email"

    async def send_email(self, to_email: str, subject: str, html_content: str, metadata: Dict[str, Any] = None) -> bool:
        """
        Sends an email using Brevo API.
        """
        if not self.api_key:
            print("WARNING: Brevo API key not configured. Mocking email send.")
            return True

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json"
        }

        payload = {
            "sender": {"email": self.sender_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_content
        }

        if metadata:
            payload["tags"] = [f"{k}:{v}" for k, v in metadata.items() if isinstance(v, str)]

        async with httpx.AsyncClient() as client:
            response = await client.post(self.base_url, headers=headers, json=payload)
            if response.status_code in [200, 201, 202]:
                return True
            else:
                print(f"Failed to send email: {response.text}")
                return False
