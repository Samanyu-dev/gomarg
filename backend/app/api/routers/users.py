from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.future import select
from app.api.deps import SessionDep, CurrentOrgIdDep
from app.models.tenant import User, Membership
from app.schemas.tenant import UserCreate, UserUpdate, UserResponse
from uuid import UUID

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_in: UserCreate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    # Hash password in a real app
    new_user = User(
        email=user_in.email,
        password_hash=user_in.password, # MUST HASH
        first_name=user_in.first_name,
        last_name=user_in.last_name
    )
    session.add(new_user)
    await session.flush() # Get user ID
    
    # Create membership
    membership = Membership(
        user_id=new_user.id,
        organization_id=UUID(current_org_id),
        role="member"
    )
    session.add(membership)
    await session.commit()
    await session.refresh(new_user)
    return new_user

@router.get("/", response_model=List[UserResponse])
async def list_users(session: SessionDep, current_org_id: CurrentOrgIdDep, skip: int = 0, limit: int = 100):
    result = await session.execute(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(Membership.organization_id == UUID(current_org_id))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .filter(User.id == user_id, Membership.organization_id == UUID(current_org_id))
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in organization")
    return user
