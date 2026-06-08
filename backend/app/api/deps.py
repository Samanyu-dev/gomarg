from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db

SessionDep = Annotated[AsyncSession, Depends(get_db)]

async def get_current_organization_id(x_organization_id: Annotated[str | None, Header()] = None) -> str:
    """
    Mock dependency for multi-tenancy isolation.
    In a real scenario, this would extract the org ID from the JWT token and verify user membership.
    """
    if not x_organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-ID header missing"
        )
    return x_organization_id

CurrentOrgIdDep = Annotated[str, Depends(get_current_organization_id)]
