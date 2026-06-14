import httpx
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
import json

from app.core.config import settings
from app.models.lead import Lead, ResearchDocument

class ApolloService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.api_key = settings.APOLLO_API_KEY
        self.base_url = "https://api.apollo.io/v1/people/match"

    async def enrich_lead(self, lead_id: UUID, org_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Calls Apollo API to enrich lead data and saves it to research_documents.
        """
        # Fetch lead
        result = await self.session.execute(
            select(Lead).filter(Lead.id == lead_id, Lead.organization_id == org_id)
        )
        lead = result.scalars().first()
        if not lead:
            raise ValueError("Lead not found")

        if not self.api_key:
            print("WARNING: Apollo API key not configured. Skipping real enrichment.")
            # Return a mock payload for local testing if API key is not present
            mock_data = {
                "linkedin_url": lead.linkedin_url,
                "seniority": "Director",
                "departments": ["Sales", "Engineering"],
                "company_metrics": {"employees": 50, "revenue": "$10M"}
            }
            await self._save_research(lead, org_id, mock_data)
            return mock_data

        payload = {
            "api_key": self.api_key,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "email": lead.email,
            "organization_name": lead.company
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.base_url, json=payload)
            if response.status_code == 200:
                data = response.json()
                person_data = data.get("person", {})
                await self._save_research(lead, org_id, person_data)
                
                # Optionally update the lead object itself with fresh data
                if person_data.get("linkedin_url"):
                    lead.linkedin_url = person_data["linkedin_url"]
                if person_data.get("title"):
                    lead.job_title = person_data["title"]
                    
                await self.session.commit()
                return person_data
            else:
                print(f"Apollo API error: {response.text}")
                return None

    async def _save_research(self, lead: Lead, org_id: UUID, data: Dict[str, Any]):
        doc = ResearchDocument(
            organization_id=org_id,
            lead_id=lead.id,
            doc_type="apollo_enrichment",
            content=json.dumps(data)
        )
        self.session.add(doc)
        await self.session.commit()
