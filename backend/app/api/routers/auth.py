from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Annotated

from app.api.deps import SessionDep
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.tenant import User, Organization, Membership
from app.schemas.token import Token
from app.schemas.tenant import UserCreate, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
async def login_access_token(
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    result = await session.execute(select(User).filter(User.email == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    membership = await session.execute(select(Membership).filter(Membership.user_id == user.id))
    mem = membership.scalars().first()
    org_id = str(mem.organization_id) if mem else None
        
    access_token = create_access_token(subject=user.id)
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "organization_id": org_id
        }
    }

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    user_in: UserCreate,
    session: SessionDep,
):
    """
    Create a new user and a default organization for them.
    """
    # Check if user exists
    result = await session.execute(select(User).filter(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="User with this email already exists")
        
    # Create User
    new_user = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        first_name=user_in.first_name,
        last_name=user_in.last_name
    )
    session.add(new_user)
    await session.flush()
    
    # Create default Organization
    org_name = f"{user_in.first_name or user_in.email}'s Organization"
    new_org = Organization(name=org_name)
    session.add(new_org)
    await session.flush()
    
    # Link them as owner
    membership = Membership(
        user_id=new_user.id,
        organization_id=new_org.id,
        role="owner"
    )
    session.add(membership)
    
    await session.commit()
    await session.refresh(new_user)
    return new_user
