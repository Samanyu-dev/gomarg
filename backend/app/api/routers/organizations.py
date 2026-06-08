from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from app.api.deps import SessionDep, CurrentOrgIdDep
from app.models.tenant import Organization
from app.schemas.tenant import OrganizationCreate, OrganizationUpdate, OrganizationResponse
from uuid import UUID

router = APIRouter(prefix="/organizations", tags=["Organizations"])

@router.post("/", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(org_in: OrganizationCreate, session: SessionDep):
    new_org = Organization(**org_in.model_dump())
    session.add(new_org)
    try:
        await session.commit()
        await session.refresh(new_org)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Organization with this domain already exists.")
    return new_org

@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(org_id: UUID, session: SessionDep):
    result = await session.execute(select(Organization).filter(Organization.id == org_id))
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org

@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(org_id: UUID, org_in: OrganizationUpdate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    if str(org_id) != current_org_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this organization")
    
    result = await session.execute(select(Organization).filter(Organization.id == org_id))
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    update_data = org_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)
        
    await session.commit()
    await session.refresh(org)
    return org

@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(org_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    if str(org_id) != current_org_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this organization")
        
    result = await session.execute(select(Organization).filter(Organization.id == org_id))
    org = result.scalars().first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    await session.delete(org)
    await session.commit()
