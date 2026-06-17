from typing import List
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from app.api.deps import SessionDep, CurrentOrgIdDep
from app.models.campaign import Campaign, CampaignStep, CampaignLead
from app.models.lead import Lead
from app.models.email import Email, EmailEvent
from app.schemas.campaign import (
    CampaignCreate, CampaignUpdate, CampaignResponse,
    CampaignStepCreate, CampaignStepUpdate, CampaignStepResponse
)
from uuid import UUID

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(campaign_in: CampaignCreate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    new_campaign = Campaign(
        organization_id=UUID(current_org_id),
        name=campaign_in.name,
        status=campaign_in.status,
        settings=campaign_in.settings
    )
    session.add(new_campaign)
    await session.flush() # flush to get campaign id
    
    # Add steps if provided
    for step_in in campaign_in.steps:
        new_step = CampaignStep(
            campaign_id=new_campaign.id,
            order_index=step_in.order_index,
            step_type=step_in.step_type,
            config=step_in.config
        )
        session.add(new_step)

    await session.commit()
    # Reload with steps
    result = await session.execute(
        select(Campaign).options(selectinload(Campaign.steps)).filter(Campaign.id == new_campaign.id)
    )
    return result.scalars().first()

@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(session: SessionDep, current_org_id: CurrentOrgIdDep, skip: int = 0, limit: int = 100):
    result = await session.execute(
        select(Campaign)
        .options(selectinload(Campaign.steps))
        .filter(Campaign.organization_id == UUID(current_org_id))
        .offset(skip).limit(limit)
    )
    return result.scalars().all()

@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Campaign)
        .options(selectinload(Campaign.steps))
        .filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    campaign = result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: UUID, campaign_in: CampaignUpdate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Campaign)
        .options(selectinload(Campaign.steps))
        .filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    campaign = result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    update_data = campaign_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)
        
    await session.commit()
    await session.refresh(campaign)
    return campaign

@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Campaign).filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    campaign = result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    await session.delete(campaign)
    await session.commit()



@router.get("/{campaign_id}/stats")
async def get_campaign_stats(campaign_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    # Verify campaign exists
    result = await session.execute(
        select(Campaign).filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # Get all leads in campaign
    leads_res = await session.execute(
        select(Lead.lead_score, func.count(Lead.id))
        .join(CampaignLead, CampaignLead.lead_id == Lead.id)
        .filter(CampaignLead.campaign_id == campaign_id)
        .group_by(Lead.lead_score)
    )
    lead_score_breakdown = {score: count for score, count in leads_res.all()}
    
    # Get total sent
    sent_res = await session.execute(
        select(func.count(Email.id))
        .join(CampaignLead, CampaignLead.lead_id == Email.lead_id)
        .filter(CampaignLead.campaign_id == campaign_id)
    )
    total_sent = sent_res.scalar() or 0
    
    # Get engagement counts
    events_res = await session.execute(
        select(EmailEvent.event_type, func.count(EmailEvent.id))
        .join(Email, Email.id == EmailEvent.email_id)
        .join(CampaignLead, CampaignLead.lead_id == Email.lead_id)
        .filter(CampaignLead.campaign_id == campaign_id)
        .group_by(EmailEvent.event_type)
    )
    events_breakdown = {event: count for event, count in events_res.all()}
    
    total_opens = events_breakdown.get("opened", 0)
    total_clicks = events_breakdown.get("clicked", 0)
    total_replies = events_breakdown.get("reply", 0)
    total_bounces = events_breakdown.get("bounced", 0) + events_breakdown.get("hard_bounce", 0)
    
    return {
        "total_sent": total_sent,
        "total_opens": total_opens,
        "total_clicks": total_clicks,
        "total_replies": total_replies,
        "total_bounces": total_bounces,
        "open_rate": round(total_opens / total_sent * 100, 1) if total_sent > 0 else 0,
        "ctr": round(total_clicks / total_sent * 100, 1) if total_sent > 0 else 0,
        "reply_rate": round(total_replies / total_sent * 100, 1) if total_sent > 0 else 0,
        "bounce_rate": round(total_bounces / total_sent * 100, 1) if total_sent > 0 else 0,
        "lead_score_breakdown": lead_score_breakdown
    }

# Nested Routes for Steps
@router.post("/{campaign_id}/steps", response_model=CampaignStepResponse, status_code=status.HTTP_201_CREATED)
async def add_campaign_step(campaign_id: UUID, step_in: CampaignStepCreate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    # Verify campaign exists & belongs to org
    result = await session.execute(
        select(Campaign).filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    new_step = CampaignStep(
        campaign_id=campaign_id,
        **step_in.model_dump()
    )
    session.add(new_step)
    await session.commit()
    await session.refresh(new_step)
    return new_step

@router.delete("/{campaign_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign_step(campaign_id: UUID, step_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    # Verify campaign exists & belongs to org
    result = await session.execute(
        select(Campaign).filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    step_res = await session.execute(
        select(CampaignStep).filter(CampaignStep.id == step_id, CampaignStep.campaign_id == campaign_id)
    )
    step = step_res.scalars().first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
        
    await session.delete(step)
    await session.commit()


from app.schemas.campaign import CampaignLeadCreate

@router.post("/{campaign_id}/leads", status_code=status.HTTP_200_OK)
async def assign_leads_to_campaign(campaign_id: UUID, req: CampaignLeadCreate, session: SessionDep, current_org_id: CurrentOrgIdDep):
    result = await session.execute(
        select(Campaign).filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    for lead_id in req.lead_ids:
        # Check if already enrolled
        existing = await session.execute(
            select(CampaignLead).filter(CampaignLead.campaign_id == campaign_id, CampaignLead.lead_id == lead_id)
        )
        if not existing.scalars().first():
            cl = CampaignLead(campaign_id=campaign_id, lead_id=lead_id)
            session.add(cl)
    await session.commit()
    return {"message": f"Successfully enrolled {len(req.lead_ids)} leads."}

@router.get("/{campaign_id}/leads")
async def get_campaign_leads(campaign_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    # Verify campaign exists
    result = await session.execute(
        select(Campaign).filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    # Get leads with their emails
    leads_result = await session.execute(
        select(Lead, Email)
        .join(CampaignLead, CampaignLead.lead_id == Lead.id)
        .outerjoin(Email, Email.lead_id == Lead.id)
        .filter(CampaignLead.campaign_id == campaign_id)
    )
    
    rows = leads_result.all()
    
    # Format the response
    response = []
    # Deduplicate leads just in case
    seen_leads = set()
    for lead, email in rows:
        if lead.id in seen_leads:
            continue
        seen_leads.add(lead.id)
        lead_dict = {
            "id": lead.id,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "email": lead.email,
            "job_title": lead.job_title,
            "company": lead.company,
            "lead_score": getattr(lead, 'lead_score', 'cold'),
            "draft_email": None
        }
        if email:
            lead_dict["draft_email"] = {
                "id": str(email.id),
                "subject": email.subject,
                "body": email.body,
                "status": email.status
            }
        response.append(lead_dict)
        
    return response

@router.post("/{campaign_id}/emails/{email_id}/approve", status_code=status.HTTP_200_OK)
async def approve_campaign_email(campaign_id: UUID, email_id: UUID, session: SessionDep, current_org_id: CurrentOrgIdDep):
    """
    Approves an AI generated draft email. The background worker will pick this up
    and send it on the next tick.
    """
    # Verify campaign exists
    result = await session.execute(
        select(Campaign).filter(Campaign.id == campaign_id, Campaign.organization_id == UUID(current_org_id))
    )
    if not result.scalars().first():
        raise HTTPException(status_code=404, detail="Campaign not found")
        
    email_res = await session.execute(
        select(Email).filter(Email.id == email_id, Email.status == "draft")
    )
    email = email_res.scalars().first()
    if not email:
        raise HTTPException(status_code=404, detail="Draft email not found")
        
    email.status = "approved"
    await session.commit()
    return {"message": "Email approved. Agent will send it shortly."}
