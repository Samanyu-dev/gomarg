from sqlalchemy import Column, String, ForeignKey, JSON, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class Campaign(BaseModel):
    __tablename__ = "campaigns"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, default="draft") # draft, active, paused, completed
    settings = Column(JSON, default={})

    # Relationships
    steps = relationship("CampaignStep", back_populates="campaign", cascade="all, delete-orphan", order_by="CampaignStep.order_index")
    campaign_leads = relationship("CampaignLead", back_populates="campaign", cascade="all, delete-orphan")

class CampaignStep(BaseModel):
    __tablename__ = "campaign_steps"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    order_index = Column(Integer, nullable=False)
    step_type = Column(String, nullable=False) # "email", "wait", "ai_task"
    config = Column(JSON, default={}) # Email template, wait duration, etc.

    campaign = relationship("Campaign", back_populates="steps")

class CampaignLead(BaseModel):
    __tablename__ = "campaign_leads"

    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, default="enrolled") # enrolled, active, completed, exited, bounced
    current_step_id = Column(UUID(as_uuid=True), ForeignKey("campaign_steps.id", ondelete="SET NULL"), nullable=True)

    campaign = relationship("Campaign", back_populates="campaign_leads")
    lead = relationship("Lead", back_populates="campaign_leads")
