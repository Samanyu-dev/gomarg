from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class Email(BaseModel):
    __tablename__ = "emails"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    campaign_step_id = Column(UUID(as_uuid=True), ForeignKey("campaign_steps.id", ondelete="SET NULL"), nullable=True)
    
    subject = Column(String, nullable=False)
    body = Column(String, nullable=False)
    status = Column(String, default="draft") # draft, scheduled, sent, failed
    sent_at = Column(DateTime(timezone=True), nullable=True)
    provider_message_id = Column(String, nullable=True)

    events = relationship("EmailEvent", back_populates="email", cascade="all, delete-orphan")

class EmailEvent(BaseModel):
    __tablename__ = "email_events"

    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String, nullable=False) # open, click, reply, bounce, spam
    provider_event_id = Column(String, nullable=True)
    
    email = relationship("Email", back_populates="events")
