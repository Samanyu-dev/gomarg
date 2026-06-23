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

    async def search_and_import_leads(
        self,
        org_id: UUID,
        role: str = None,
        sector: str = None,
        company: str = None,
        page: int = 1,
        per_page: int = 10,
    ) -> list[Lead]:
        """
        Uses DuckDuckGo to scrape LinkedIn profiles for free, bypassing Apollo.
        """
        try:
            from ddgs import DDGS
        except ImportError:
            print("WARNING: ddgs package not installed. Cannot scrape.")
            return []
            
        import re
        import uuid
        
        # Prevent empty global search
        if not role and not company and not sector:
            print("Skipping empty global search to avoid generic results.")
            return []
        
        # Build search query
        query_parts = ["site:linkedin.com/in"]
        if role:
            query_parts.append(f'"{role}"')
        if company:
            query_parts.append(f'"{company}"')
        if sector:
            query_parts.append(f'"{sector}"')
            
        query = " ".join(query_parts)
        print(f"Scraping LinkedIn with query: {query}")
        
        imported_leads = []
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=per_page))
                
                for r in results:
                    title_text = r.get('title', '')
                    linkedin_url = r.get('href', '')
                    body_text = r.get('body', '')
                    
                    # Usually "First Last - Role - Company | LinkedIn" or similar
                    parts = title_text.split('-')
                    if len(parts) >= 1:
                        name_part = parts[0].strip()
                        # Clean up " | LinkedIn" if present
                        name_part = name_part.replace(" | LinkedIn", "").strip()
                        
                        name_tokens = name_part.split(' ')
                        first_name = name_tokens[0] if name_tokens else ""
                        last_name = " ".join(name_tokens[1:]) if len(name_tokens) > 1 else ""
                        
                        # Guess email (e.g. first.last@company.com)
                        safe_company = re.sub(r'[^a-zA-Z0-9]', '', str(company or 'company').lower())
                        safe_first = re.sub(r'[^a-zA-Z0-9]', '', first_name.lower())
                        safe_last = re.sub(r'[^a-zA-Z0-9]', '', last_name.lower())
                        email = f"{safe_first}.{safe_last}@{safe_company}.com" if safe_last else f"{safe_first}@{safe_company}.com"
                        
                        # Use a fake Apollo ID to satisfy the schema/UI
                        fake_apollo_id = str(uuid.uuid4())
                        
                        from sqlalchemy import or_
                        existing_lead = await self.session.execute(
                            select(Lead).filter(
                                Lead.organization_id == org_id,
                                Lead.email == email
                            )
                        )
                        if existing_lead.scalars().first():
                            continue
                            
                        # Create Lead
                        new_lead = Lead(
                            organization_id=org_id,
                            email=email,
                            apollo_id=fake_apollo_id,
                            first_name=first_name,
                            last_name=last_name,
                            company=company or "Unknown Company",
                            job_title=role or "Unknown Role",
                            linkedin_url=linkedin_url,
                            phone_number="",
                            city="",
                            state="",
                            country="",
                            industry=sector or "",
                            status="new"
                        )
                        self.session.add(new_lead)
                        await self.session.commit()
                        await self.session.refresh(new_lead)
                        
                        # Save the snippet as research for the AI
                        fake_contact_data = {
                            "name": name_part,
                            "title": role,
                            "organization_name": company,
                            "linkedin_url": linkedin_url,
                            "snippet": body_text
                        }
                        await self._save_research(new_lead, org_id, fake_contact_data)
                        imported_leads.append(new_lead)
                        print(f"Scraped and imported lead: {email}")
                        
        except Exception as e:
            print(f"Scraping error: {e}")
            
        return imported_leads
