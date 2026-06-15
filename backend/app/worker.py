import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import AsyncSessionLocal
from app.models.campaign import Campaign, CampaignLead
from app.models.email import Email
from app.services.email_generation import AIEmailGenerator
from app.services.email_sender import EmailSenderService

logger = logging.getLogger(__name__)

async def autonomous_agent_loop():
    """
    The main autonomous agent loop. It wakes up periodically, finds active campaigns,
    and automatically processes leads (generates & sends emails).
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
    # Find leads in this campaign that haven't been emailed yet
    # A lead needs generation if they don't have an email in this campaign
    result = await session.execute(
        select(CampaignLead)
        .outerjoin(Email, (Email.lead_id == CampaignLead.lead_id) & (Email.campaign_step_id == campaign.id)) # using campaign_step_id hack for now since email lacks campaign_id
        .filter(CampaignLead.campaign_id == campaign.id)
        .filter(CampaignLead.status == 'enrolled')
    )
    
    # Actually, simpler: find CampaignLeads where status == 'enrolled'
    campaign_leads = result.scalars().all()
    
    generator = AIEmailGenerator(session)
    sender = EmailSenderService(session)

    for cl in campaign_leads:
        # Check if email exists
        email_check = await session.execute(
            select(Email).filter(Email.lead_id == cl.lead_id)
        )
        email = email_check.scalars().first()
        
        if not email:
            logger.info(f"🤖 Agent Drafting Email for Lead {cl.lead_id}...")
            # Generate the email
            try:
                email_data = await generator.generate_email(
                    lead_id=cl.lead_id, 
                    org_id=campaign.organization_id,
                    campaign_goal=f"Outreach for {campaign.name}"
                )
                
                # Fetch the newly created email
                new_email_res = await session.execute(
                    select(Email).filter(Email.lead_id == cl.lead_id).order_by(Email.created_at.desc())
                )
                email = new_email_res.scalars().first()
            except Exception as e:
                logger.error(f"Failed to generate for lead {cl.lead_id}: {e}")
                continue
                
        if email and email.status == 'draft':
            logger.info(f"🤖 Agent Sending Email for Lead {cl.lead_id}...")
            # Send the email
            success = await sender.send_email(email.id)
            if success:
                cl.status = 'contacted'
                await session.commit()
