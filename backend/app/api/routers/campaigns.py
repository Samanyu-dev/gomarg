from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.api.deps import SessionDep, CurrentOrgIdDep
from app.models.campaign import Campaign, CampaignStep
from app.schemas.campaign import (
    CampaignCreate, CampaignUpdate, CampaignResponse,
    CampaignStepCreate, CampaignStepUpdate, CampaignStepResponse
)
from uuid import UUID

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(campaign_in: CampaignCreate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    new_campaign = Campaign(
        organization_id=UUID(current_org_id),
        name=campaign_in.name,
        status=campaign_in.status,
        settings=campaign_in.settings
    )
    session.add(new_campaign)
    await session.flush() # flush to get campaign id
    
    # Add steps if provided
    for step_in in campaign_in.steps:
        new_step = CampaignStep(
            campaign_id=new_campaign.id,
            order_index=step_in.order_index,
            step_type=step_in.step_type,
            config=step_in.config
        )
        session.add(new_step)

    await session.commit()
    # Reload with steps
    result = await session.execute(
        select(Campaign).options(selectinload(Campaign.steps)).filter(Campaign.id == new_campaign.id)
    )
    return result.scalars().first()

@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(session: SessionDep, current_org_id: CurrentOrgIdDep, skip: int = 0, limit: int = 100):
    result = await session.execute(
        select(Campaign)
        .options(selectinload(Campaign.steps))
        .filter(Campaign.organization_id == UUID(current_org_id))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()

@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Campaign)
        .options(selectinload(Campaign.steps))
        .filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    campaign = result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: UUID, campaign_in: CampaignUpdate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Campaign)
        .options(selectinload(Campaign.steps))
        .filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    campaign = result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    update_data = campaign_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)
        
    await session.commit()
    await session.refresh(campaign)
    return campaign

@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Campaign).filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    campaign = result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    await session.delete(campaign)
    await session.commit()

# Nested Routes for Steps
@router.post("/{campaign_id}/steps", response_model=CampaignStepResponse, status_code=status.HTTP_201_CREATED)
async def add_campaign_step(campaign_id: UUID, step_in: CampaignStepCreate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    # Verify campaign exists & belongs to org
    result = await session.execute(
        select(Campaign).filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    new_step = CampaignStep(
        campaign_id=campaign_id,
        **step_in.model_dump()
    )
    session.add(new_step)
    await session.commit()
    await session.refresh(new_step)
    return new_step
