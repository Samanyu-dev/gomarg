import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, BackgroundTasks
from app.api.deps import SessionDep
from app.models.email import Email, EmailEvent
from sqlalchemy.future import select

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)

@router.post("/brevo")
async def brevo_webhook(request: Request, session: SessionDep, background_tasks: BackgroundTasks):
    """
    Receives webhook events from Brevo (opened, clicked, bounced, etc).
    """
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}
    
    event_type = payload.get("event")
    message_id = payload.get("message-id") or payload.get("messageId")
    provider_event_id = str(payload.get("id", ""))
    
    if not message_id or not event_type:
        return {"status": "ignored", "reason": "Missing required fields"}
        
    logger.info(f"Received Brevo Webhook: {event_type} for message {message_id}")

    # Find the email by provider_message_id
    result = await session.execute(
        select(Email).filter(Email.provider_message_id == message_id)
    )
    email = result.scalars().first()
    
    if not email:
        logger.warning(f"Webhook received for unknown message_id: {message_id}")
        return {"status": "not_found"}

    # Update email status if applicable
    if event_type == "bounced" or event_type == "hard_bounce":
        email.status = "bounced"
    elif event_type == "delivered" and email.status == "sent":
        email.status = "delivered"
        
    # Create the event record
    event = EmailEvent(
        email_id=email.id,
        event_type=event_type,
        provider_event_id=provider_event_id
    )
    session.add(event)
    await session.commit()
    
    # We will trigger the classification engine here in a later step
    
    return {"status": "success"}

