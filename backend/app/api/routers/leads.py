from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.future import select
from app.api.deps import SessionDep, CurrentOrgIdDep
from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadUpdate, LeadResponse
from uuid import UUID

router = APIRouter(prefix="/leads", tags=["Leads"])

@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(lead_in: LeadCreate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    new_lead = Lead(
        organization_id=UUID(current_org_id),
        **lead_in.model_dump()
    )
    session.add(new_lead)
    await session.commit()
    await session.refresh(new_lead)
    return new_lead

@router.get("/", response_model=List[LeadResponse])
async def list_leads(session: SessionDep, current_org_id: CurrentOrgIdDep, skip: int = 0, limit: int = 100):
    result = await session.execute(
        select(Lead).filter(Lead.organization_id == UUID(current_org_id)).offset(skip).limit(limit)
    )
    return result.scalars().all()

@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Lead).filter(Lead.id == lead_id, Lead.organization_id == UUID(current_org_id))
    )
    lead = result.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead

@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(lead_id: UUID, lead_in: LeadUpdate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Lead).filter(Lead.id == lead_id, Lead.organization_id == UUID(current_org_id))
    )
    lead = result.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    update_data = lead_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)
        
    await session.commit()
    await session.refresh(lead)
    return lead

@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(lead_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Lead).filter(Lead.id == lead_id, Lead.organization_id == UUID(current_org_id))
    )
    lead = result.scalars().first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    await session.delete(lead)
    await session.commit()
