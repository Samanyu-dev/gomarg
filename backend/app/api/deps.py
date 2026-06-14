from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
import jwt

from app.db.session import get_db
from app.core.config import settings
from app.core.security import ALGORITHM
from app.schemas.token import TokenPayload
from app.models.tenant import User, Membership

SessionDep = Annotated[AsyncSession, Depends(get_db)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    session: SessionDep,
    token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)
        if token_data.sub is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    result = await session.execute(select(User).filter(User.id == UUID(token_data.sub)))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
        
    return user

CurrentUserDep = Annotated[User, Depends(get_current_user)]

async def get_current_organization_id(
    session: SessionDep,
    current_user: CurrentUserDep,
    x_organization_id: Annotated[str | None, Header()] = None
) -> str:
    """
    Validates that the user is a member of the requested organization.
    """
    if not x_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-ID header missing"
        )
        
    # Verify membership
    result = await session.execute(
        select(Membership).filter(
            Membership.user_id == current_user.id,
            Membership.organization_id == UUID(x_organization_id)
        )
    )
    membership = result.scalars().first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization"
        )
        
    return x_organization_id

CurrentOrgIdDep = Annotated[str, Depends(get_current_organization_id)]
