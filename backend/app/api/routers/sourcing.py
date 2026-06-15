from fastapi import APIRouter, HTTPException, status
from uuid import UUID

from app.api.deps import SessionDep, CurrentOrgIdDep
from app.services.sourcing import ApolloService
from app.schemas.sourcing import ApolloSearchRequest, ApolloSearchResponse

router = APIRouter(prefix="/sourcing", tags=["Lead Sourcing"])

@router.post("/apollo", response_model=ApolloSearchResponse, status_code=status.HTTP_200_OK)
async def search_and_import_apollo_leads(
    request: ApolloSearchRequest,
    session: SessionDep,
    current_org_id: CurrentOrgIdDep
):
    """
    Search Apollo for new leads matching the given criteria, enrich their emails,
    and save them directly into the current organization's lead database.
    """
    service = ApolloService(session)
    params = request.model_dump(exclude_none=True)
    
    try:
        imported_count = await service.search_and_import_leads(params=params, org_id=UUID(current_org_id))
        return ApolloSearchResponse(
            success=True,
            message=f"Successfully sourced and imported {imported_count} new leads.",
            leads_imported=imported_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sourcing pipeline failed: {str(e)}")
