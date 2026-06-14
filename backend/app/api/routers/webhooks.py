from fastapi import APIRouter, Request, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, Any

from app.api.deps import SessionDep
from app.models.email import EmailEvent

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("/brevo", status_code=status.HTTP_200_OK)
async def brevo_webhook(request: Request, session: SessionDep):
    """
    Receives webhook events from Brevo (opens, clicks, bounces, etc).
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Example Brevo Payload Event Name: 'opened', 'click', 'delivered'
    event_type = payload.get("event")
    email_id = payload.get("message-id") # This requires mapping Brevo's message-id to our Email record
    
    if not event_type:
        return {"status": "ignored"}

    # In a real app, you'd lookup the `email_id` in the database to link it back to a Lead and Campaign
    # For now, we will log it assuming we have a mock ID or we just store the raw payload.
    # To implement this fully, we need the `Email` table to store the `message-id` returned by Brevo.

    print(f"Received Brevo Event: {event_type} for message {email_id}")
    
    # Store the event
    # new_event = EmailEvent(
    #     email_id=...,
    #     event_type=event_type,
    #     user_agent=payload.get("user_agent"),
    #     ip_address=payload.get("ip")
    # )
    # session.add(new_event)
    # await session.commit()

    return {"status": "success"}
