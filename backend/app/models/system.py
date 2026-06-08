from sqlalchemy import Column, String, ForeignKey, JSON, Integer, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class Webhook(BaseModel):
    __tablename__ = "webhooks"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    events = Column(JSON, nullable=False) # list of event names e.g. ["lead.created", "email.replied"]
    secret = Column(String, nullable=False)
    is_active = Column(Column(Integer, default=1))

class WebhookDelivery(BaseModel):
    __tablename__ = "webhook_deliveries"

    webhook_id = Column(UUID(as_uuid=True), ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status_code = Column(Integer, nullable=True)
    success = Column(Integer, default=0)

class UsageEvent(BaseModel):
    __tablename__ = "usage_events"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False) # email_sent, lead_enriched, tokens_used
    quantity = Column(Integer, default=1)
    metadata_json = Column(JSON, default={})

class Meeting(BaseModel):
    __tablename__ = "meetings"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    
    calendar_event_id = Column(String, nullable=True)
    meeting_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, default="scheduled") # scheduled, canceled, completed
    
    lead = relationship("Lead")
