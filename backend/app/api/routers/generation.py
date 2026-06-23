from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from app.api.deps import SessionDep, CurrentOrgIdDep
from app.services.email_generation import AIEmailGenerator

router = APIRouter(prefix="/generate", tags=["AI Generation"])

class EmailGenerationRequest(BaseModel):
    """
    Per-lead email customization. Every field has a sensible default
    so existing callers that just send { campaign_goal: "..." } still work.
    """
    campaign_goal: str = "Book a meeting for our AI outreach tool"
    tone: str = Field(
        default="professional",
        description="Email tone: casual, professional, bold, friendly"
    )
    writing_style: str = Field(
        default="concise",
        description="Writing style: concise, storytelling, data-driven"
    )
    cta_type: str = Field(
        default="reply_question",
        description="CTA type: book_meeting, reply_question, visit_link"
    )
    sender_name: Optional[str] = Field(
        default=None,
        description="Name to sign off with (e.g. 'Samanyu')"
    )
    sender_company: Optional[str] = Field(
        default=None,
        description="Company name for context (e.g. 'GoMarg')"
    )
    custom_instructions: Optional[str] = Field(
        default=None,
        description="Any additional instructions for the AI"
    )

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
    Triggers the AI Email Generation pipeline for a specific lead
    with full customization controls (tone, style, CTA, etc.)
    """
    generator = AIEmailGenerator(session)
    try:
        email_data = await generator.generate_email(
            lead_id=lead_id, 
            org_id=UUID(current_org_id),
            campaign_goal=request.campaign_goal,
            tone=request.tone,
            writing_style=request.writing_style,
            cta_type=request.cta_type,
            sender_name=request.sender_name,
            sender_company=request.sender_company,
            custom_instructions=request.custom_instructions,
        )
        return EmailGenerationResponse(**email_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email generation failed: {str(e)}")
