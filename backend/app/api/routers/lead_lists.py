from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.future import select
from app.api.deps import SessionDep, CurrentOrgIdDep
from app.models.lead import LeadList
from app.schemas.lead import LeadListCreate, LeadListUpdate, LeadListResponse
from uuid import UUID

router = APIRouter(prefix="/lead-lists", tags=["Lead Lists"])

@router.post("/", response_model=LeadListResponse, status_code=status.HTTP_201_CREATED)
async def create_lead_list(list_in: LeadListCreate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    new_list = LeadList(
        organization_id=UUID(current_org_id),
        **list_in.model_dump()
    )
    session.add(new_list)
    await session.commit()
    await session.refresh(new_list)
    return new_list

@router.get("/", response_model=List[LeadListResponse])
async def list_lead_lists(session: SessionDep, current_org_id: CurrentOrgIdDep, skip: int = 0, limit: int = 100):
    result = await session.execute(
        select(LeadList).filter(LeadList.organization_id == UUID(current_org_id)).offset(skip).limit(limit)
    )
    return result.scalars().all()

@router.get("/{list_id}", response_model=LeadListResponse)
async def get_lead_list(list_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(LeadList).filter(LeadList.id == list_id, LeadList.organization_id == UUID(current_org_id))
    )
    llist = result.scalars().first()
    if not llist:
        raise HTTPException(status_code=404, detail="Lead list not found")
    return llist

@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead_list(list_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(LeadList).filter(LeadList.id == list_id, LeadList.organization_id == UUID(current_org_id))
    )
    llist = result.scalars().first()
    if not llist:
        raise HTTPException(status_code=404, detail="Lead list not found")
        
    await session.delete(llist)
    await session.commit()
