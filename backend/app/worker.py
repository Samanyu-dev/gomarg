import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.session import AsyncSessionLocal
from app.models.campaign import Campaign, CampaignLead
from app.models.lead import Lead
from app.models.email import Email
from app.services.email_generation import AIEmailGenerator
from app.services.email_sender import EmailSenderService

logger = logging.getLogger(__name__)

async def autonomous_agent_loop():
    """
    The main autonomous agent loop. It wakes up periodically, finds active campaigns,
    and automatically processes leads (generates & sends emails, manages sequences).
    """
    logger.info("🤖 Autonomous Agent Loop Started...")
    while True:
        try:
            await process_active_campaigns()
        except Exception as e:
            logger.error(f"Agent Loop Error: {e}")
        
        # Wake up every 10 seconds to check for work
        await asyncio.sleep(10)

async def process_active_campaigns():
    async with AsyncSessionLocal() as session:
        # Find all active campaigns
        result = await session.execute(
            select(Campaign).filter(Campaign.status == 'active')
        )
        active_campaigns = result.scalars().all()
        
        for campaign in active_campaigns:
            await process_campaign(session, campaign)

async def process_campaign(session: AsyncSession, campaign: Campaign):
    # We want to process leads that are enrolled or contacted (for follow-up)
    result = await session.execute(
        select(CampaignLead)
        .filter(CampaignLead.campaign_id == campaign.id)
        .filter(CampaignLead.status.in_(['enrolled', 'contacted']))
    )
    campaign_leads = result.scalars().all()
    
    generator = AIEmailGenerator(session)
    sender = EmailSenderService(session)

    for cl in campaign_leads:
        lead_result = await session.execute(select(Lead).filter(Lead.id == cl.lead_id))
        lead = lead_result.scalars().first()
        if not lead:
            continue

        # If Hot lead, we skip sequences. (Assuming immediate escalation handles them elsewhere)
        if lead.lead_score == 'hot':
            if cl.status != 'completed':
                cl.status = 'completed'
                await session.commit()
            continue

        # Check if we need to draft a new email
        email_check = await session.execute(
            select(Email).filter(Email.lead_id == cl.lead_id).order_by(Email.created_at.desc())
        )
        emails = email_check.scalars().all()
        latest_email = emails[0] if emails else None
        
        # Determine if we should generate something new
        should_generate = False
        is_followup = False
        sequence_step_target = lead.sequence_step
        
        if cl.status == 'enrolled' and lead.sequence_step == 0 and not latest_email:
            should_generate = True
            is_followup = False
            sequence_step_target = 1
            
        elif cl.status == 'contacted' and lead.next_contact_at and datetime.now(timezone.utc) >= lead.next_contact_at:
            should_generate = True
            is_followup = True
            sequence_step_target = lead.sequence_step + 1
            
        # Draft the email
        if should_generate:
            logger.info(f"🤖 Agent Drafting Email for Lead {cl.lead_id} (Step {sequence_step_target})...")
            try:
                if not is_followup:
                    await generator.generate_email(
                        lead_id=cl.lead_id, 
                        org_id=campaign.organization_id,
                        campaign_goal=f"Outreach for {campaign.name}"
                    )
                else:
                    prior_context = "\n".join([f"Subject: {e.subject}\nBody: {e.body}" for e in emails])
                    await generator.generate_followup_email(
                        lead_id=cl.lead_id,
                        org_id=campaign.organization_id,
                        sequence_step=sequence_step_target,
                        prior_emails_context=prior_context
                    )
                
                # Fetch newly created email
                new_email_res = await session.execute(
                    select(Email).filter(Email.lead_id == cl.lead_id).order_by(Email.created_at.desc())
                )
                latest_email = new_email_res.scalars().first()
            except Exception as e:
                logger.error(f"Failed to generate for lead {cl.lead_id}: {e}")
                continue
                
        # Send the draft email
        if latest_email and latest_email.status == 'draft':
            logger.info(f"🤖 Agent Sending Email for Lead {cl.lead_id} (Step {sequence_step_target})...")
            success = await sender.send_email(latest_email.id)
            
            if success:
                cl.status = 'contacted'
                lead.sequence_step = sequence_step_target
                
                if sequence_step_target == 1:
                    lead.next_contact_at = datetime.now(timezone.utc) + timedelta(days=3)
                elif sequence_step_target == 2:
                    lead.next_contact_at = datetime.now(timezone.utc) + timedelta(days=4) # Day 7 total
                else:
                    lead.next_contact_at = None
                    cl.status = 'completed'
                    
                await session.commit()
