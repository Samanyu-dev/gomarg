from pydantic import BaseModel, ConfigDict
from typing import Optional, Any, List
from uuid import UUID
from datetime import datetime

# Campaign Step Schemas
class CampaignStepBase(BaseModel):
    order_index: int
    step_type: str # e.g., 'email', 'wait', 'ai_task'
    config: Optional[dict[str, Any]] = {}

class CampaignStepCreate(CampaignStepBase):
    pass

class CampaignStepUpdate(BaseModel):
    order_index: Optional[int] = None
    step_type: Optional[str] = None
    config: Optional[dict[str, Any]] = None

class CampaignStepResponse(CampaignStepBase):
    id: UUID
    campaign_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# Campaign Schemas
class CampaignBase(BaseModel):
    name: str
    status: Optional[str] = "draft"
    settings: Optional[dict[str, Any]] = {}

class CampaignCreate(CampaignBase):
    steps: Optional[List[CampaignStepCreate]] = []

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[dict[str, Any]] = None

class CampaignResponse(CampaignBase):
    id: UUID
    organization_id: UUID
    steps: List[CampaignStepResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CampaignLeadCreate(BaseModel):
    lead_ids: List[UUID]

class CampaignLeadResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    lead_id: UUID
    status: str
    current_step_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
