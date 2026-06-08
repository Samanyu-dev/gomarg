from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any
from uuid import UUID
from app.api.deps import SessionDep, CurrentOrgIdDep
from app.services.research import AIResearchService

router = APIRouter(prefix="/research", tags=["AI Research Engine"])

class ResearchResponse(BaseModel):
    pain_points: List[str]
    signals: List[str]
    summary: str

@router.post("/{lead_id}/generate", response_model=ResearchResponse, status_code=status.HTTP_200_OK)
async def generate_research_for_lead(lead_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    """
    Triggers the AI Research Pipeline for a specific lead.
    """
    service = AIResearchService(session)
    try:
        insights = await service.generate_insights(lead_id=lead_id, org_id=UUID(current_org_id))
        return ResearchResponse(**insights)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Research generation failed: {str(e)}")
