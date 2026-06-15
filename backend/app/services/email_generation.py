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
from uuid import UUID

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

        # Step config can override the campaign goal
        step_goal = step.config.get("goal") or campaign.settings.get("goal") or "Book a 15-minute discovery call"

        prompt = f"""
You are {tone_config["persona"]}. You are writing a {tone_config["label"]} email.

TARGET LEAD:
  Name: {lead.first_name} {lead.last_name}
  Title: {lead.job_title}
  Company: {lead.company}
  Location: {lead.city or ""}, {lead.country or ""}
  Industry: {lead.industry or ""}
  Lead Score: {lead.lead_score} (cold/low/warm/hot)

CAMPAIGN GOAL: {step_goal}

RESEARCH (use this for personalisation — reference specific details):
{research_context}

PREVIOUS EMAILS SENT TO THIS LEAD (do NOT repeat these; build on them):
{email_history or "This is the first email to this lead."}

ENGAGEMENT HISTORY:
{engagement_summary or "No engagement data yet."}

TONE: {tone_config["tone"]}
CALL TO ACTION: End with {tone_config["cta"]}.

RULES:
- Under 120 words for the body
- Never use the word "synergy", "leverage", or "circle back"
- Do not start with "I hope this email finds you well"
- Reference at least one specific detail from the Research section
- Sound like a human, not a bot
- If this is a follow-up and you know the lead opened a previous email, acknowledge it subtly

Return a JSON object with exactly two keys: "subject" (string) and "body" (string).
The body should include a greeting and sign-off. Use plain text, no markdown.
"""

        email_data = await self._call_gemini(prompt, EmailOutput)
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
        response = self.client.models.generate_content(
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
        step: CampaignStep | None,
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
