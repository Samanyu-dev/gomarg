"""
GoMarg AI Email Generator — email_generation.py

The key upgrade over the original:
  - generate_email_for_step(): produces different emails based on which step in
    the sequence the lead is on (cold outreach, follow-up 1, follow-up 2, etc.)
  - generate_escalation_email(): urgent email for hot leads
  - analyze_reply_sentiment(): NLP classification of inbound replies
  - All prompts include the lead's engagement history so the AI has context
    about what's already been sent and what the lead has done
"""

import json
import logging
import asyncio
from uuid import UUID
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.campaign import Campaign, CampaignStep
from app.models.email import Email, EmailEvent
from app.models.lead import Lead, ResearchDocument
from app.models.ai import AIGeneration
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# PYDANTIC OUTPUT SCHEMAS (for Gemini JSON mode)
# ─────────────────────────────────────────────
class EmailOutput(BaseModel):
    subject: str
    body: str


class SentimentOutput(BaseModel):
    sentiment: str          # "positive", "neutral", "negative"
    intent: str             # "interested", "not_interested", "asking_question", "out_of_office", "other"
    reasoning: str          # one sentence explanation


# ─────────────────────────────────────────────
# STEP TYPE → TONE MAPPING
# The AI uses a different persona/tone per step in the sequence
# ─────────────────────────────────────────────
STEP_TONE_MAP = {
    0: {
        "label": "cold outreach",
        "persona": "an expert SDR making first contact",
        "tone": "warm, curious, and non-pushy. Lead with a genuine observation from their background.",
        "cta": "a soft question, not a hard ask for a meeting",
    },
    1: {
        "label": "first follow-up",
        "persona": "a helpful professional checking in",
        "tone": "brief and human — acknowledge you're following up, add a new angle or insight",
        "cta": "make it easy to reply with one word: 'interested?' or similar",
    },
    2: {
        "label": "final follow-up",
        "persona": "someone giving them one last chance before moving on",
        "tone": "honest and direct — mention this is your last reach-out. No hard feelings either way.",
        "cta": "one clear question: is now the right time, or should I check back later?",
    },
}

DEFAULT_TONE = {
    "label": "follow-up",
    "persona": "a sales professional",
    "tone": "professional and respectful",
    "cta": "a clear but soft call to action",
}


# ─────────────────────────────────────────────
# MAIN CLASS
# ─────────────────────────────────────────────
class AIEmailGenerator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.client = (
            genai.Client(api_key=settings.GEMINI_API_KEY)
            if settings.GEMINI_API_KEY
            else None
        )

    # ─────────────────────────────────────────
    # STANDALONE: generate a customised email for a specific lead
    # Used by the Sourcing page "Generate AI Email" button
    # ─────────────────────────────────────────
    async def generate_email(
        self,
        lead_id: UUID,
        org_id: UUID,
        campaign_goal: str = "Book a meeting",
        tone: str = "professional",
        writing_style: str = "concise",
        cta_type: str = "reply_question",
        sender_name: str = None,
        sender_company: str = None,
        custom_instructions: str = None,
    ) -> dict:
        """
        Generates a deeply personalised cold email for a single lead
        using their research data and the user's customization preferences.
        Returns a dict with subject, intro_sentence, and full_body.
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY is not configured.")

        # Fetch lead
        lead_result = await self.session.execute(
            select(Lead).filter(Lead.id == lead_id, Lead.organization_id == org_id)
        )
        lead = lead_result.scalars().first()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found in this organization.")

        # Pull research context for deep personalisation
        research_context = await self._get_research_context(lead_id)

        # Map CTA type to instruction
        cta_map = {
            "book_meeting": "End with a clear ask to book a 15-minute call. Include a placeholder [BOOKING_LINK].",
            "reply_question": "End with a single, thoughtful question that makes it easy to reply with one sentence.",
            "visit_link": "End by directing them to a specific resource. Include a placeholder [RESOURCE_LINK].",
        }
        cta_instruction = cta_map.get(cta_type, cta_map["reply_question"])

        # Map writing style to instruction
        style_map = {
            "concise": "Be extremely concise. Every sentence must earn its place. Target 60-80 words for the body.",
            "storytelling": "Open with a brief, vivid anecdote or scenario that the recipient would relate to. Target 100-120 words.",
            "data-driven": "Include 1-2 specific data points, stats, or metrics relevant to their industry or role. Target 80-100 words.",
        }
        style_instruction = style_map.get(writing_style, style_map["concise"])

        # Build the sender sign-off
        sign_off_parts = []
        if sender_name:
            sign_off_parts.append(sender_name)
        if sender_company:
            sign_off_parts.append(sender_company)
        sign_off_instruction = f"Sign off as: {', '.join(sign_off_parts)}" if sign_off_parts else "Use a simple sign-off like 'Best,' or 'Cheers,'"

        prompt = f"""
You are an elite B2B sales SDR writing a cold outreach email.

TARGET LEAD:
  Name: {lead.first_name} {lead.last_name}
  Title: {lead.job_title or 'Unknown'}
  Company: {lead.company or 'Unknown'}
  Industry: {lead.industry or 'Unknown'}
  Location: {lead.city or ''}{', ' + lead.country if lead.country else ''}
  LinkedIn: {lead.linkedin_url or 'N/A'}

RESEARCH DATA (use this for deep personalisation — reference specific details):
{research_context}

CAMPAIGN GOAL: {campaign_goal}

TONE: Write in a {tone} tone.
  - casual: Like texting a smart colleague. Short sentences, contractions, lowercase energy.
  - professional: Polished but human. No corporate jargon.
  - bold: Confident and direct. Make a strong claim. Challenge their status quo.
  - friendly: Warm and approachable. Like a helpful neighbor who happens to work in their industry.

WRITING STYLE: {style_instruction}

CALL TO ACTION: {cta_instruction}

SIGN-OFF: {sign_off_instruction}

{f'ADDITIONAL INSTRUCTIONS FROM USER: {custom_instructions}' if custom_instructions else ''}

HARD RULES:
- NEVER use these words: "synergy", "leverage", "circle back", "just checking in", "hope this email finds you well"
- Reference at least ONE specific detail from the Research Data section (company info, role specifics, industry context)
- The subject line must be under 60 characters, curiosity-inducing, and NOT clickbait
- The first sentence must hook them — mention something specific about THEM, not about you
- Sound like a real human wrote this, not an AI or a template
- Do NOT use markdown formatting in the email body — plain text only

Return a JSON object with exactly three keys:
  "subject" (string) — the email subject line
  "intro_sentence" (string) — just the opening sentence for preview
  "full_body" (string) — the complete email body including greeting and sign-off
"""

        result = await self._call_gemini(prompt, EmailOutput)
        
        # Extract intro_sentence from the body if not provided separately
        body = result.get("body", "")
        subject = result.get("subject", "")
        
        # The prompt asks for intro_sentence but the EmailOutput schema only has subject/body
        # Split the first sentence from the body as the intro
        lines = body.strip().split('\n')
        # Skip greeting line to find the actual intro
        intro = ""
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.lower().startswith(('hi ', 'hey ', 'hello ', 'dear ')):
                intro = stripped
                break
        if not intro and lines:
            intro = lines[0].strip()

        return {
            "subject": subject,
            "intro_sentence": intro,
            "full_body": body,
        }

    # ─────────────────────────────────────────
    # PRIMARY: generate email for a specific campaign step
    # ─────────────────────────────────────────
    async def generate_email_for_step(
        self,
        lead: Lead,
        campaign: Campaign,
        step: CampaignStep,
    ) -> Email:
        """
        Generates a context-aware email based on:
          - Which step in the sequence this is (cold / follow-up 1 / follow-up 2)
          - What emails were already sent to this lead (so we don't repeat ourselves)
          - The lead's engagement history (did they open? click?)
          - The research documents for deep personalisation
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY is not configured.")

        # Pull research context
        research_context = await self._get_research_context(lead.id)

        # Pull history of previously sent emails (so AI knows what's already been said)
        email_history = await self._get_email_history(lead.id)

        # Pull engagement summary
        engagement_summary = await self._get_engagement_summary(lead.id)

        # Determine tone based on step order
        tone_config = STEP_TONE_MAP.get(step.order_index, DEFAULT_TONE)

        url = "https://www.getrightdata.com/solutions/industry/insurance/whitepaper?utm_content=learn_more_button&utm_source=brevo&utm_medium=email&utm_campaign=Insurance%20Outreach%20Batch%207%20%20June%202026&utm_id=74"
        html_body = f"""
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
    <p>Hi {lead.first_name or 'there'},</p>
    <br/>
    <p>Around 68% of enterprise AI initiatives slow down because of inconsistent and poorly governed data.</p>
    <br/>
    <p>How is {lead.company or 'your team'} approaching this challenge?</p>
    <br/>
    <p>RightData supports insurers in building trusted, governed data foundations that enable reliable AI and automation.</p>
    <br/>
    <p>Learn how insurers are approaching this challenge through a few practical approaches and use cases.</p>
    <br/>
    <p style="text-align: center; margin: 30px 0;">
        <a href="{url}" style="display: inline-block; padding: 12px 30px; background-color: #1a2b3c; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: bold;">Learn More</a>
    </p>
    <br/>
    <p>Regards,<br>Akhil Viswan<br>Team RightData</p>
</div>
"""
        
        email_data = {
            "subject": "AI Needs Trust",
            "body": html_body
        }
        return await self._save_email(
            lead=lead,
            campaign=campaign,
            step=step,
            subject=email_data["subject"],
            body=email_data["body"],
            task_type="email_generation",
        )

    # ─────────────────────────────────────────
    # ESCALATION: hot lead email (bypasses steps)
    # ─────────────────────────────────────────
    async def generate_escalation_email(
        self,
        lead: Lead,
        campaign: Campaign,
    ) -> Email:
        """
        Called when a lead is classified as hot. Generates an urgent,
        high-intent email designed to book a meeting NOW.
        The subject is prefixed with [HOT] so worker.py can identify it.
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY is not configured.")

        research_context = await self._get_research_context(lead.id)
        engagement_summary = await self._get_engagement_summary(lead.id)

        prompt = f"""
You are an expert SDR. This lead is HOT — they have shown strong engagement
(multiple opens, a click, or a positive reply). Act immediately with a direct,
confident email designed to book a meeting.

LEAD: {lead.first_name} {lead.last_name}, {lead.job_title} at {lead.company}
ENGAGEMENT: {engagement_summary}
RESEARCH: {research_context}

INSTRUCTIONS:
- Be direct and confident — they know who you are
- Acknowledge their engagement without being weird about it ("Noticed you've been checking us out")
- Propose a specific time or a 1-click Calendly link placeholder: [BOOKING_LINK]
- Keep body under 80 words
- Sound human and urgent, not robotic

Return JSON with "subject" and "body" keys. Prefix the subject with [HOT].
"""

        email_data = await self._call_gemini(prompt, EmailOutput)

        # Ensure the [HOT] prefix is present (worker.py uses it to detect escalation emails)
        subject = email_data["subject"]
        if not subject.startswith("[HOT]"):
            subject = f"[HOT] {subject}"

        return await self._save_email(
            lead=lead,
            campaign=campaign,
            step=None,  # escalation emails are not tied to a step
            subject=subject,
            body=email_data["body"],
            task_type="escalation_email",
        )

    # ─────────────────────────────────────────
    # NLP: analyse inbound reply sentiment
    # ─────────────────────────────────────────
    async def analyze_reply_sentiment(self, reply_text: str) -> str:
        """
        Classify an inbound email reply as positive / neutral / negative.
        Returns the sentiment string.
        """
        if not self.client:
            return "neutral"

        prompt = f"""
Analyse this email reply from a sales prospect and classify it.

REPLY:
\"\"\"{reply_text}\"\"\"

Classify the sentiment as one of:
  - "positive": interested, wants more info, asks to schedule, says yes
  - "neutral": out of office, asking a clarifying question, vague response
  - "negative": not interested, unsubscribe, wrong person, too busy

Also classify the intent as one of:
  "interested", "not_interested", "asking_question", "out_of_office", "other"

Return JSON with keys: "sentiment", "intent", "reasoning" (one sentence).
"""

        result = await self._call_gemini(prompt, SentimentOutput)
        logger.info(f"📨 Reply analysis: {result}")
        return result.get("sentiment", "neutral")

    # ─────────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────────
    async def _get_research_context(self, lead_id: UUID) -> str:
        docs_result = await self.session.execute(
            select(ResearchDocument).filter(ResearchDocument.lead_id == lead_id)
        )
        docs = docs_result.scalars().all()
        if not docs:
            return "No additional research available."
        return "\n".join(f"[{doc.doc_type.upper()}]: {doc.content}" for doc in docs)

    async def _get_email_history(self, lead_id: UUID) -> str:
        """
        Returns a summary of emails already sent so the AI doesn't repeat itself.
        """
        history_result = await self.session.execute(
            select(Email)
            .filter(Email.lead_id == lead_id, Email.status == "sent")
            .order_by(Email.sent_at.asc())
        )
        sent_emails = history_result.scalars().all()
        if not sent_emails:
            return ""
        lines = []
        for i, e in enumerate(sent_emails, 1):
            sent_date = e.sent_at.strftime("%Y-%m-%d") if e.sent_at else "unknown date"
            lines.append(f"Email {i} (sent {sent_date}):\n  Subject: {e.subject}\n  Body: {e.body[:300]}...")
        return "\n\n".join(lines)

    async def _get_engagement_summary(self, lead_id: UUID) -> str:
        """
        Returns a plain-English summary of what this lead has done.
        """
        events_result = await self.session.execute(
            select(EmailEvent)
            .join(Email, Email.lead_id == lead_id)
            .order_by(EmailEvent.created_at.desc())
        )
        events = events_result.scalars().all()
        if not events:
            return ""

        open_count  = sum(1 for e in events if e.event_type == "open")
        click_count = sum(1 for e in events if e.event_type == "click")
        reply_count = sum(1 for e in events if e.event_type == "reply")

        parts = []
        if open_count:
            parts.append(f"opened {open_count} email(s)")
        if click_count:
            parts.append(f"clicked {click_count} link(s)")
        if reply_count:
            parts.append(f"replied {reply_count} time(s)")
        return "Lead has " + ", ".join(parts) + "." if parts else ""

    async def _call_gemini(self, prompt: str, schema: type) -> dict:
        """
        Calls Gemini with structured JSON output. Handles the response parsing.
        Raises on failure so the caller can decide how to handle it.
        """
        # Sleep for 4 seconds to avoid hitting the 15 RPM free tier rate limit
        await asyncio.sleep(4)
        
        response = await self.client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.7,
            ),
        )
        return json.loads(response.text)

    async def _save_email(
        self,
        lead: Lead,
        campaign: Campaign,
        step: Optional[CampaignStep],
        subject: str,
        body: str,
        task_type: str,
    ) -> Email:
        """
        Saves the generated email as a draft and logs the AI generation event.
        """
        email = Email(
            organization_id=campaign.organization_id,
            lead_id=lead.id,
            campaign_step_id=step.id if step else None,
            subject=subject,
            body=body,
            status="draft",
        )
        self.session.add(email)

        ai_log = AIGeneration(
            organization_id=campaign.organization_id,
            lead_id=lead.id,
            task_type=task_type,
            provider="gemini",
            model="gemini-2.5-flash",
            output={"subject": subject, "body": body[:500]},
        )
        self.session.add(ai_log)

        await self.session.commit()
        await self.session.refresh(email)
        return email
