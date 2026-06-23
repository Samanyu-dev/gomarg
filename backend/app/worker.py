"""
GoMarg Autonomous Agent — worker.py

This is NOT a simple poller. It is a decision-making agent that:
  1. Reads the CampaignStep sequence for each campaign (the "playbook")
  2. Advances each lead through the playbook step-by-step
  3. Handles wait steps (respects timing, doesn't just fire immediately)
  4. Scores leads based on engagement and re-routes hot leads
  5. Generates contextually different emails per step (cold / follow-up / final)
  6. Processes inbound reply events and decides next action
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.campaign import Campaign, CampaignLead, CampaignStep
from app.models.email import Email, EmailEvent
from app.models.lead import Lead
from app.services.email_generation import AIEmailGenerator
from app.services.email_sender import EmailSenderService
from app.services.sourcing import ApolloService

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# AGENT CONSTANTS
# ─────────────────────────────────────────────
AGENT_TICK_SECONDS = 15          # How often the agent wakes up
HOT_LEAD_OPEN_THRESHOLD = 3      # Opens needed to classify as hot
WARM_LEAD_OPEN_THRESHOLD = 2     # Opens needed to classify as warm


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────
async def autonomous_agent_loop():
    """
    The agent's heartbeat. Wakes up every AGENT_TICK_SECONDS and runs the
    full decision cycle. Each cycle is fully independent — no shared state
    between ticks, so crashes are self-healing.
    """
    logger.info("🤖 GoMarg Agent Online — decision engine active")
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await agent_tick(session)
        except Exception as e:
            logger.error(f"❌ Agent tick failed: {e}", exc_info=True)
        await asyncio.sleep(AGENT_TICK_SECONDS)


# ─────────────────────────────────────────────
# TICK: one full decision cycle
# ─────────────────────────────────────────────
async def agent_tick(session: AsyncSession):
    """
    One complete agent cycle:
      1. Re-score leads based on engagement events
      2. Find active campaigns
      3. For each campaign, advance every enrolled lead through its step playbook
    """
    await rescore_all_leads(session)
    await sourcing_tick(session)
    await advance_all_campaigns(session)


# ─────────────────────────────────────────────
# STEP 1: RE-SCORE LEADS
# ─────────────────────────────────────────────
async def rescore_all_leads(session: AsyncSession):
    """
    Look at real engagement data (EmailEvent rows) and update each lead's
    lead_score field. This is the agent's "perception" of the world.

    Scoring logic (from the proposal):
      0 opens  → cold
      1 open   → low
      2 opens  → warm
      3+ opens or any click → hot
      positive reply → hot (handled separately via inbound webhook)
    """
    # Fetch all leads that have had email activity
    result = await session.execute(
        select(Lead)
        .join(Email, Email.lead_id == Lead.id)
        .join(EmailEvent, EmailEvent.email_id == Email.id)
        .distinct()
    )
    active_leads = result.scalars().all()

    for lead in active_leads:
        # Count opens and clicks from EmailEvent
        events_result = await session.execute(
            select(EmailEvent)
            .join(Email, Email.lead_id == lead.id)
            .filter(EmailEvent.event_type.in_(["open", "click", "reply"]))
        )
        events = events_result.scalars().all()

        open_count  = sum(1 for e in events if e.event_type == "open")
        click_count = sum(1 for e in events if e.event_type == "click")
        reply_count = sum(1 for e in events if e.event_type == "reply")

        old_score = lead.lead_score

        if reply_count > 0 or click_count > 0 or open_count >= HOT_LEAD_OPEN_THRESHOLD:
            lead.lead_score = "hot"
            lead.score = open_count * 10 + click_count * 25 + reply_count * 50
        elif open_count >= WARM_LEAD_OPEN_THRESHOLD:
            lead.lead_score = "warm"
            lead.score = open_count * 10
        elif open_count == 1:
            lead.lead_score = "low"
            lead.score = 10
        else:
            lead.lead_score = "cold"
            lead.score = 0

        if old_score != lead.lead_score:
            logger.info(f"📊 Lead {lead.email} re-scored: {old_score} → {lead.lead_score}")

    await session.commit()


# ─────────────────────────────────────────────
# SOURCING AGENT (PHASE 3)
# ─────────────────────────────────────────────
async def sourcing_tick(session: AsyncSession):
    """
    Looks for active campaigns with ICP filters defined.
    If today's fetched limit hasn't been reached, fetch new leads from Apollo
    and automatically assign them to the campaign.
    """
    result = await session.execute(
        select(Campaign).filter(Campaign.status == "active")
    )
    campaigns = result.scalars().all()

    for campaign in campaigns:
        settings = campaign.settings or {}
        icp = settings.get("icp", None)
        if not icp:
            continue
            
        limit = icp.get("limit_per_day", 5)
        # Check how many leads enrolled today for this campaign
        today = datetime.now(timezone.utc).date()
        
        # Count campaign leads enrolled today
        # Simplified: we just check total leads in campaign vs limit (or keep it simple and just run Apollo search)
        # Actually, let's just fetch up to the limit from Apollo right now
        # In a real production system, you'd track daily sourcing state in the DB.
        # For MVP, we'll just attempt a small query and add missing ones.
        
        # Only run sourcing once every 6 hours or similar? 
        # For demo purposes, we will just run it if the campaign has less leads than limit.
        cl_res = await session.execute(
            select(CampaignLead).filter(CampaignLead.campaign_id == campaign.id)
        )
        current_enrolled = len(cl_res.scalars().all())
        
        if current_enrolled >= limit:
            continue # We reached our desired ICP limit for this campaign (demo simplified)
            
        logger.info(f"🔎 Autopilot Sourcing running for campaign '{campaign.name}' (ICP: {icp})")
        
        # Build structured fields from ICP settings
        icp_role = icp.get("keywords", "").strip() or None
        icp_company = icp.get("company", "").strip() or None
        # Seniorities are handled as keyword additions for the free-tier contacts/search endpoint
        icp_sector = None  # Can be extended if ICP settings add a sector field

        service = ApolloService(session)
        org_id = campaign.organization_id
        
        remaining_limit = limit - current_enrolled
        total_imported = 0

        try:
            # Build keyword string combining role + seniority for targeted search
            seniorities_to_try = []
            if "seniorities" in icp and icp["seniorities"]:
                if isinstance(icp["seniorities"], list):
                    seniorities_to_try = icp["seniorities"]
                else:
                    seniorities_to_try = [s.strip() for s in icp["seniorities"].split(",")]
                    
            # Always add a final fallback with NO seniority restriction
            seniorities_to_try.append(None)

            for seniority in seniorities_to_try:
                if remaining_limit <= 0:
                    break
                
                # Combine role keywords with seniority for q_keywords
                role_with_seniority = icp_role
                if seniority and icp_role:
                    role_with_seniority = f"{icp_role} {seniority}"
                elif seniority:
                    role_with_seniority = seniority
                    
                imported_leads = await service.search_and_import_leads(
                    org_id=org_id,
                    role=role_with_seniority,
                    sector=icp_sector,
                    company=icp_company,
                    page=1,
                    per_page=remaining_limit,
                )
                
                if imported_leads:
                    logger.info(f"✅ Sourcing Agent found {len(imported_leads)} new leads for campaign {campaign.id} (Seniority: {seniority or 'ALL'})")
                    
                    for lead in imported_leads:
                        # check if already in campaign
                        cl_check = await session.execute(
                            select(CampaignLead).filter(CampaignLead.campaign_id == campaign.id, CampaignLead.lead_id == lead.id)
                        )
                        if not cl_check.scalars().first():
                            cl = CampaignLead(campaign_id=campaign.id, lead_id=lead.id)
                            session.add(cl)
                            
                    await session.commit()
                    
                    total_imported += len(imported_leads)
                    remaining_limit -= len(imported_leads)
                    
        except Exception as e:
            logger.error(f"Sourcing agent failed for campaign {campaign.id}: {e}")

# ─────────────────────────────────────────────
# STEP 2: ADVANCE ALL CAMPAIGNS
# ─────────────────────────────────────────────
async def advance_all_campaigns(session: AsyncSession):
    """Find every active campaign and advance its leads."""
    result = await session.execute(
        select(Campaign)
        .options(
            selectinload(Campaign.steps),
            selectinload(Campaign.campaign_leads)
        )
        .filter(Campaign.status == "active")
    )
    campaigns = result.scalars().all()

    if not campaigns:
        return

    logger.info(f"🔍 Agent found {len(campaigns)} active campaign(s)")

    for campaign in campaigns:
        # Sort steps by order_index — this is the "playbook"
        playbook = sorted(campaign.steps, key=lambda s: s.order_index)
        if not playbook:
            logger.warning(f"Campaign '{campaign.name}' is active but has no steps defined.")
            continue

        for cl in campaign.campaign_leads:
            if cl.status in ("completed", "exited", "bounced"):
                continue
            try:
                await advance_lead(session, campaign, playbook, cl)
            except Exception as e:
                logger.error(f"❌ Failed to advance lead {cl.lead_id} in campaign {campaign.id}: {e}", exc_info=True)


# ─────────────────────────────────────────────
# CORE DECISION ENGINE: advance one lead
# ─────────────────────────────────────────────
async def advance_lead(
    session: AsyncSession,
    campaign: Campaign,
    playbook: list[CampaignStep],
    cl: CampaignLead,
):
    """
    The heart of the agent. This function decides what to do with ONE lead
    at ONE moment in time by reading the campaign playbook.

    Decision flow:
      - Determine which step the lead is currently on
      - If it's an "email" step: check if email was already sent; if not, generate + send
      - If it's a "wait" step: check if the wait period has elapsed; if so, advance to next step
      - If it's an "ai_task" step: run the appropriate AI action (e.g. reply analysis)
      - Hot leads get routed differently — escalate immediately
    """
    # Fetch the full lead object for scoring context
    lead_result = await session.execute(select(Lead).filter(Lead.id == cl.lead_id))
    lead = lead_result.scalars().first()
    if not lead:
        return

    # ── Hot lead fast-path: skip cold outreach steps, jump to escalation ──
    if lead.lead_score == "hot" and cl.status == "enrolled":
        logger.info(f"🔥 Hot lead {lead.email} — escalating immediately")
        await escalate_hot_lead(session, campaign, lead, cl)
        return

    # ── Find which step the lead is currently on ──
    current_step = _get_current_step(playbook, cl.current_step_id)

    # If no step assigned yet, put them on step 0
    if current_step is None:
        current_step = playbook[0]
        cl.current_step_id = current_step.id
        await session.commit()

    # ── Route to the right handler based on step type ──
    if current_step.step_type == "email":
        await handle_email_step(session, campaign, playbook, lead, cl, current_step)

    elif current_step.step_type == "wait":
        await handle_wait_step(session, playbook, lead, cl, current_step)

    elif current_step.step_type == "ai_task":
        await handle_ai_task_step(session, campaign, lead, cl, current_step)


# ─────────────────────────────────────────────
# HANDLER: email step
# ─────────────────────────────────────────────
async def handle_email_step(
    session: AsyncSession,
    campaign: Campaign,
    playbook: list[CampaignStep],
    lead: Lead,
    cl: CampaignLead,
    step: CampaignStep,
):
    """
    For an email step:
      1. Check if an email for this exact step was already sent (idempotent)
      2. If not, generate a contextually appropriate email (cold vs. follow-up)
      3. Send it via Brevo
      4. Advance the lead to the next step
    """
    # Idempotency check: has this step's email already been sent?
    sent_check = await session.execute(
        select(Email).filter(
            Email.lead_id == lead.id,
            Email.campaign_step_id == step.id,
            Email.status == "sent",
        )
    )
    already_sent = sent_check.scalars().first()
    if already_sent:
        # Email sent — move lead to the next step
        await _advance_to_next_step(session, playbook, cl, step)
        return

    # Draft check: maybe we generated but failed to send last tick
    draft_check = await session.execute(
        select(Email).filter(
            Email.lead_id == lead.id,
            Email.campaign_step_id == step.id,
            Email.status.in_(["draft", "approved"]),
        )
    )
    email = draft_check.scalars().first()

    if not email:
        # No draft yet — generate one
        logger.info(f"✍️  Generating step-{step.order_index} email for {lead.email} ({lead.lead_score} lead)")
        generator = AIEmailGenerator(session)
        try:
            email = await generator.generate_email_for_step(
                lead=lead,
                campaign=campaign,
                step=step,
            )
        except Exception as e:
            logger.error(f"Generation failed for lead {lead.id}: {e}")
            return

    if email.status == "draft":
        # ── HUMAN-IN-THE-LOOP (Phase 3) ──
        # The agent generates the draft, but does NOT send it.
        # It waits for the moderator to approve via the frontend UI.
        logger.info(f"✋ Draft step-{step.order_index} for {lead.email} is waiting for Moderator Approval.")
        return

    if email.status == "approved":
        # Send the drafted email
        logger.info(f"📤 Sending APPROVED step-{step.order_index} email to {lead.email}")
        sender = EmailSenderService(session)
        success = await sender.send_email(email.id)

        if success:
            cl.status = "active"
            lead.sequence_step = step.order_index
            # Set next_contact_at for the wait step that follows (agent checks this)
            next_step = _get_next_step(playbook, step)
            if next_step and next_step.step_type == "wait":
                wait_hours = next_step.config.get("wait_hours", 72)
                lead.next_contact_at = datetime.now(timezone.utc) + timedelta(hours=wait_hours)
            await _advance_to_next_step(session, playbook, cl, step)
            await session.commit()


# ─────────────────────────────────────────────
# HANDLER: wait step
# ─────────────────────────────────────────────
async def handle_wait_step(
    session: AsyncSession,
    playbook: list[CampaignStep],
    lead: Lead,
    cl: CampaignLead,
    step: CampaignStep,
):
    """
    For a wait step, the agent checks if enough time has passed.
    If next_contact_at is in the future, do nothing — come back next tick.
    If it's passed, advance to the next step so the email step fires.

    This is what turns the agent from "fire immediately" into a proper
    drip sequence that respects timing.
    """
    now = datetime.now(timezone.utc)
    wait_hours = step.config.get("wait_hours", 72)  # default 3 days

    if lead.next_contact_at is None:
        # next_contact_at wasn't set (shouldn't happen, but handle it)
        lead.next_contact_at = now + timedelta(hours=wait_hours)
        await session.commit()
        return

    if now < lead.next_contact_at:
        remaining = (lead.next_contact_at - now).total_seconds() / 3600
        logger.debug(f"⏳ Lead {lead.email} waiting {remaining:.1f}h before next step")
        return

    # Wait is over — advance to the next step
    logger.info(f"⏰ Wait complete for {lead.email} — advancing to next step")
    await _advance_to_next_step(session, playbook, cl, step)
    await session.commit()


# ─────────────────────────────────────────────
# HANDLER: ai_task step
# ─────────────────────────────────────────────
async def handle_ai_task_step(
    session: AsyncSession,
    campaign: Campaign,
    lead: Lead,
    cl: CampaignLead,
    step: CampaignStep,
):
    """
    For an AI task step, run the task defined in step.config["task_name"].
    Currently supported:
      - "analyze_reply": run NLP sentiment on latest reply event
      - "update_score": force a re-score of this lead right now
    More tasks can be added here without touching the rest of the agent.
    """
    task_name = step.config.get("task_name")

    if task_name == "analyze_reply":
        await _analyze_latest_reply(session, campaign, lead, cl, step)

    elif task_name == "update_score":
        # Already handled globally in rescore_all_leads, just advance
        await _advance_to_next_step(
            session,
            sorted(campaign.steps, key=lambda s: s.order_index),
            cl,
            step,
        )
        await session.commit()

    else:
        logger.warning(f"Unknown ai_task '{task_name}' on step {step.id} — skipping")


async def _analyze_latest_reply(
    session: AsyncSession,
    campaign: Campaign,
    lead: Lead,
    cl: CampaignLead,
    step: CampaignStep,
):
    """
    Find the most recent inbound reply for this lead and run Gemini sentiment
    analysis on it. Store the result in the EmailEvent metadata.
    Then decide next action based on sentiment:
      - positive → mark hot, trigger escalation
      - negative → exit lead from campaign
      - neutral  → continue sequence
    """
    reply_result = await session.execute(
        select(EmailEvent)
        .join(Email, Email.lead_id == lead.id)
        .filter(EmailEvent.event_type == "reply")
        .order_by(EmailEvent.created_at.desc())
    )
    latest_reply = reply_result.scalars().first()

    if not latest_reply:
        logger.info(f"No reply found for lead {lead.email} on ai_task step — continuing sequence")
        playbook = sorted(campaign.steps, key=lambda s: s.order_index)
        await _advance_to_next_step(session, playbook, cl, step)
        await session.commit()
        return

    # Only analyse if not already analysed
    if latest_reply.metadata_payload and latest_reply.metadata_payload.get("sentiment"):
        sentiment = latest_reply.metadata_payload["sentiment"]
    else:
        generator = AIEmailGenerator(session)
        reply_text = (latest_reply.metadata_payload or {}).get("body", "")
        if reply_text:
            sentiment = await generator.analyze_reply_sentiment(reply_text)
            latest_reply.metadata_payload = {
                **(latest_reply.metadata_payload or {}),
                "sentiment": sentiment,
            }
            await session.commit()
        else:
            sentiment = "neutral"

    logger.info(f"💬 Reply from {lead.email} classified as: {sentiment}")

    if sentiment == "positive":
        lead.lead_score = "hot"
        cl.status = "active"
        await session.commit()
        await escalate_hot_lead(session, campaign, lead, cl)

    elif sentiment == "negative":
        cl.status = "exited"
        lead.lead_score = "cold"
        await session.commit()
        logger.info(f"❌ Lead {lead.email} exited campaign (negative reply)")

    else:
        # Neutral — continue the sequence
        playbook = sorted(campaign.steps, key=lambda s: s.order_index)
        await _advance_to_next_step(session, playbook, cl, step)
        await session.commit()


# ─────────────────────────────────────────────
# ESCALATION: hot lead fast-path
# ─────────────────────────────────────────────
async def escalate_hot_lead(
    session: AsyncSession,
    campaign: Campaign,
    lead: Lead,
    cl: CampaignLead,
):
    """
    Hot leads bypass the normal drip sequence.
    Currently: generate a high-urgency "let's talk" email immediately.
    Later: trigger Google Calendar booking link insertion.

    The step config can carry escalation_type: "book_meeting" | "urgent_email"
    """
    # Check if we already sent a hot-lead escalation email
    escalation_check = await session.execute(
        select(Email).filter(
            Email.lead_id == lead.id,
            Email.campaign_step_id == None,  # escalation emails aren't tied to a step
            Email.subject.like("%[HOT]%"),
        )
    )
    if escalation_check.scalars().first():
        logger.debug(f"Escalation email already sent to {lead.email}")
        return

    generator = AIEmailGenerator(session)
    email = await generator.generate_escalation_email(lead=lead, campaign=campaign)

    sender = EmailSenderService(session)
    success = await sender.send_email(email.id)

    if success:
        cl.status = "active"
        logger.info(f"🔥 Escalation email sent to hot lead {lead.email}")
        await session.commit()


# ─────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────
def _get_current_step(
    playbook: list[CampaignStep], step_id: Optional[UUID]
) -> Optional[CampaignStep]:
    if step_id is None:
        return None
    return next((s for s in playbook if s.id == step_id), None)


def _get_next_step(
    playbook: list[CampaignStep], current: CampaignStep
) -> Optional[CampaignStep]:
    sorted_steps = sorted(playbook, key=lambda s: s.order_index)
    for i, s in enumerate(sorted_steps):
        if s.id == current.id and i + 1 < len(sorted_steps):
            return sorted_steps[i + 1]
    return None


async def _advance_to_next_step(
    session: AsyncSession,
    playbook: list[CampaignStep],
    cl: CampaignLead,
    current_step: CampaignStep,
):
    next_step = _get_next_step(playbook, current_step)
    if next_step:
        cl.current_step_id = next_step.id
        logger.debug(f"Lead {cl.lead_id} → step {next_step.order_index} ({next_step.step_type})")
    else:
        # No more steps — lead has completed the full sequence
        cl.status = "completed"
        logger.info(f"✅ Lead {cl.lead_id} completed full campaign sequence")
    await session.commit()
