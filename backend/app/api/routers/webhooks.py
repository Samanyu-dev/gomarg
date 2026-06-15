import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, BackgroundTasks
from app.api.deps import SessionDep
from app.models.email import Email, EmailEvent
from app.models.lead import Lead
from app.services.email_generation import AIEmailGenerator
from sqlalchemy.future import select
from sqlalchemy import func

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
    
    # --- LEAD CLASSIFICATION ENGINE ---
    # We count events for ALL emails sent to this lead
    lead_events_result = await session.execute(
        select(EmailEvent.event_type, func.count(EmailEvent.id))
        .join(Email, Email.id == EmailEvent.email_id)
        .filter(Email.lead_id == email.lead_id)
        .group_by(EmailEvent.event_type)
    )
    
    event_counts = dict(lead_events_result.all())
    opens = event_counts.get("opened", 0)
    clicks = event_counts.get("clicked", 0)
    
    lead_result = await session.execute(select(Lead).filter(Lead.id == email.lead_id))
    lead = lead_result.scalars().first()
    
    if lead:
        new_score = "cold"
        if clicks >= 1 or opens >= 3:
            new_score = "hot"
        elif opens == 2:
            new_score = "warm"
        elif opens == 1:
            new_score = "low"
            
        if lead.lead_score != new_score:
            logger.info(f"Lead {lead.id} classified as {new_score.upper()}")
            lead.lead_score = new_score
            # If hot, we could log an escalation action here
            if new_score == "hot":
                logger.info(f"🔥 HOT LEAD ALERT: {lead.email} has {opens} opens and {clicks} clicks!")
                
            await session.commit()
            
    return {"status": "success"}

@router.post("/inbound")
async def inbound_reply_webhook(request: Request, session: SessionDep):
    """
    Receives inbound parsed replies from Brevo.
    Extracts the body, calls Gemini for NLP sentiment, and stores the event.
    """
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}
        
    items = payload.get("items", [])
    if not items:
        return {"status": "ignored"}
        
    item = items[0]
    message_id = item.get("In-Reply-To", "").strip('<>')
    if not message_id:
        return {"status": "no_in_reply_to"}
        
    text_content = item.get("RawHtmlBody") or item.get("RawTextBody") or ""
    
    # Find the original email
    result = await session.execute(
        select(Email).filter(Email.provider_message_id == message_id)
    )
    email = result.scalars().first()
    
    if not email:
        logger.warning(f"Inbound reply received for unknown message_id: {message_id}")
        return {"status": "not_found"}
        
    # Analyze Sentiment
    try:
        generator = AIEmailGenerator(session)
        analysis = await generator.analyze_reply(text_content[:2000]) # cap length
    except Exception as e:
        logger.error(f"NLP Analysis failed: {e}")
        analysis = {"sentiment": "neutral", "intent_summary": "Analysis failed"}
        
    event = EmailEvent(
        email_id=email.id,
        event_type="reply",
        provider_event_id=item.get("MessageId", ""),
        metadata_payload=analysis
    )
    session.add(event)
    
    # Mark email as replied and lead score as hot if positive
    email.status = "replied"
    
    lead_result = await session.execute(select(Lead).filter(Lead.id == email.lead_id))
    lead = lead_result.scalars().first()
    if lead and analysis.get("sentiment") == "positive":
        lead.lead_score = "hot"
        logger.info(f"🔥 POSITIVE REPLY ALERT: {lead.email} replied positively. Score set to HOT.")
        
    await session.commit()
    return {"status": "success", "sentiment": analysis.get("sentiment")}


