import json
from typing import Dict, Any, List
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.lead import Lead, ResearchDocument
from app.models.ai import AIGeneration

from google import genai
from google.genai import types

class EmailOutput(BaseModel):
    subject: str
    intro_sentence: str
    full_body: str

class ReplyAnalysisOutput(BaseModel):
    sentiment: str # positive, neutral, negative
    intent_summary: str

class AIEmailGenerator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    async def generate_email(self, lead_id: UUID, org_id: UUID, campaign_goal: str = "Book a meeting for our AI outreach tool") -> Dict[str, Any]:
        """
        Uses Gemini to generate personalized email copy based on Research Documents.
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY is not configured.")

        # 1. Fetch Lead
        result = await self.session.execute(
            select(Lead).filter(Lead.id == lead_id, Lead.organization_id == org_id)
        )
        lead = result.scalars().first()
        if not lead:
            raise ValueError("Lead not found")

        # 2. Fetch Research Documents
        docs_result = await self.session.execute(
            select(ResearchDocument).filter(ResearchDocument.lead_id == lead_id)
        )
        research_docs = docs_result.scalars().all()
        research_context = "\n".join([f"[{doc.doc_type}]: {doc.content}" for doc in research_docs])

        # 3. Build Prompt
        prompt = f"""
        You are an expert Sales Development Representative. Write a highly personalized cold email.
        
        Target Lead: {lead.first_name} {lead.last_name} at {lead.company}
        Job Title: {lead.job_title}
        
        Campaign Goal: {campaign_goal}
        
        Research Context on the Lead:
        {research_context}
        
        Instructions:
        1. Write a catchy, short subject line.
        2. Write a highly personalized introductory sentence based strictly on the research context.
        3. Write the full email body keeping it under 100 words, focused on their likely pain points, and ending with a soft call to action.
        """

        # 4. Generate
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EmailOutput,
                temperature=0.7,
            ),
        )

        email_data = json.loads(response.text)

        # 5. Log Generation
        ai_log = AIGeneration(
            organization_id=org_id,
            lead_id=lead_id,
            task_type="email_generation",
            provider="gemini",
            model="gemini-2.5-flash",
            output=email_data
        )
        self.session.add(ai_log)
        await self.session.commit()

        return email_data

    async def analyze_reply(self, reply_body: str) -> Dict[str, Any]:
        """
        Uses Gemini to classify an inbound reply's sentiment and intent.
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY is not configured.")
            
        prompt = f"""
        Analyze the following inbound email reply from a sales prospect.
        Classify the sentiment as strictly one of: positive, neutral, negative.
        Provide a very brief 1-sentence summary of their intent.
        
        Email Reply:
        \"\"\"{reply_body}\"\"\"
        """
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReplyAnalysisOutput,
                temperature=0.1,
            ),
        )
        
        return json.loads(response.text)

    async def generate_followup_email(self, lead_id: UUID, org_id: UUID, sequence_step: int, prior_emails_context: str) -> Dict[str, Any]:
        """
        Uses Gemini to generate a follow-up email based on prior interaction context.
        """
        if not self.client:
            raise ValueError("GEMINI_API_KEY is not configured.")
            
        result = await self.session.execute(
            select(Lead).filter(Lead.id == lead_id, Lead.organization_id == org_id)
        )
        lead = result.scalars().first()
        if not lead:
            raise ValueError("Lead not found")
            
        prompt = f"""
        You are an expert Sales Development Representative. Write a follow-up email (Sequence Step {sequence_step}).
        
        Target Lead: {lead.first_name} {lead.last_name} at {lead.company}
        Lead Current Engagement Score: {lead.lead_score.upper()}
        
        Context of previous emails sent to them:
        {prior_emails_context}
        
        Instructions:
        1. Keep it very short (under 50 words).
        2. Reference the fact that you reached out previously.
        3. Provide a new, distinct angle or piece of value.
        4. End with a low-friction question.
        """
        
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=EmailOutput,
                temperature=0.7,
            ),
        )
        
        email_data = json.loads(response.text)
        
        ai_log = AIGeneration(
            organization_id=org_id,
            lead_id=lead_id,
            task_type="followup_generation",
            provider="gemini",
            model="gemini-2.5-flash",
            output=email_data
        )
        self.session.add(ai_log)
        await self.session.commit()
        
        return email_data
