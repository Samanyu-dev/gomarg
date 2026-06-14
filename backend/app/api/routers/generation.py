from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from uuid import UUID
from app.api.deps import SessionDep, CurrentOrgIdDep
from app.services.email_generation import AIEmailGenerator

router = APIRouter(prefix="/generate", tags=["AI Generation"])

class EmailGenerationRequest(BaseModel):
    campaign_goal: str = "Book a meeting for our AI outreach tool"

class EmailGenerationResponse(BaseModel):
    subject: str
    intro_sentence: str
    full_body: str

@router.post("/email/{lead_id}", response_model=EmailGenerationResponse, status_code=status.HTTP_200_OK)
async def generate_email_for_lead(
    lead_id: UUID,
    request: EmailGenerationRequest,
    session: SessionDep,
    current_org_id: CurrentOrgIdDep
):
    """
    Triggers the AI Email Generation pipeline for a specific lead.
    """
    generator = AIEmailGenerator(session)
    try:
        email_data = await generator.generate_email(
            lead_id=lead_id, 
            org_id=UUID(current_org_id),
            campaign_goal=request.campaign_goal
        )
        return EmailGenerationResponse(**email_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email generation failed: {str(e)}")
