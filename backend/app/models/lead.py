from sqlalchemy import Column, String, ForeignKey, JSON, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class Lead(BaseModel):
    __tablename__ = "leads"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, index=True)
    linkedin_url = Column(String)
    company = Column(String)
    job_title = Column(String)
    
    phone_number = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    
    status = Column(String, default="new")
    score = Column(Integer, default=0)
    source = Column(String)

    # Relationships
    list_memberships = relationship("LeadListMember", back_populates="lead", cascade="all, delete-orphan")
    research_documents = relationship("ResearchDocument", back_populates="lead", cascade="all, delete-orphan")
    campaign_leads = relationship("CampaignLead", back_populates="lead", cascade="all, delete-orphan")
    ai_generations = relationship("AIGeneration", back_populates="lead", cascade="all, delete-orphan")

class LeadList(BaseModel):
    __tablename__ = "lead_lists"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)

    # Relationships
    members = relationship("LeadListMember", back_populates="lead_list", cascade="all, delete-orphan")

class LeadListMember(BaseModel):
    __tablename__ = "lead_list_members"

    lead_list_id = Column(UUID(as_uuid=True), ForeignKey("lead_lists.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)

    lead_list = relationship("LeadList", back_populates="members")
    lead = relationship("Lead", back_populates="list_memberships")

class ResearchDocument(BaseModel):
    __tablename__ = "research_documents"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True) # can be null if company-level
    
    doc_type = Column(String, nullable=False) # "linkedin", "company", "website", "news"
    content = Column(String, nullable=False)
    embedding = Column(JSON, nullable=True) # or pgvector Column if using pgvector
    
    lead = relationship("Lead", back_populates="research_documents")
