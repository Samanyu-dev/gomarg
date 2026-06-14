import json
from typing import Dict, Any
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.models.lead import Lead
from app.models.ai import AIGeneration

from google import genai
from google.genai import types

class ReplyAnalysisOutput(BaseModel):
    sentiment: str # Positive, Negative, Neutral
    intent: str # Meeting, Question, Unsubscribe, None
    suggested_action: str

class AIReplyAnalyzer:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else None

    async def analyze_reply(self, lead_id: UUID, org_id: UUID, email_text: str) -> Dict[str, Any]:
        """
        Uses Gemini to analyze an incoming email reply and update the Lead's status.
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

        # 2. Build Prompt
        prompt = f"""
        Analyze the following email reply from a sales prospect.
        
        Prospect: {lead.first_name} {lead.last_name}
        
        Email Text:
        "{email_text}"
        
        Instructions:
        1. Classify the sentiment as exactly "Positive", "Negative", or "Neutral".
        2. Classify the intent as exactly "Meeting", "Question", "Unsubscribe", or "None".
        3. Provide a brief suggested action for the sales rep.
        """

        # 3. Generate Analysis
        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReplyAnalysisOutput,
                temperature=0.1,
            ),
        )

        analysis = json.loads(response.text)

        # 4. Log AI Generation
        ai_log = AIGeneration(
            organization_id=org_id,
            lead_id=lead_id,
            task_type="reply_analysis",
            provider="gemini",
            model="gemini-2.5-flash",
            output=analysis
        )
        self.session.add(ai_log)

        # 5. Automatically Update Lead Status
        intent = analysis.get("intent")
        sentiment = analysis.get("sentiment")
        
        if intent == "Meeting":
            lead.status = "Qualified"
        elif intent == "Unsubscribe" or sentiment == "Negative":
            lead.status = "Unsubscribed"
        elif sentiment == "Positive" or intent == "Question":
            lead.status = "Warm"

        await self.session.commit()

        return analysis
