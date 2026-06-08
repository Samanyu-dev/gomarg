from sqlalchemy import Column, String, ForeignKey, Integer, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from .base import BaseModel

class AIGeneration(BaseModel):
    __tablename__ = "ai_generations"

    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)
    
    task_type = Column(String, nullable=False) # research, email_generation, reply_analysis, followup
    provider = Column(String, nullable=False) # openai, gemini, ollama
    model = Column(String, nullable=False) # gpt-4, gemini-1.5-pro, etc.
    
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    
    output = Column(JSON, nullable=True)
    
    lead = relationship("Lead", back_populates="ai_generations")
