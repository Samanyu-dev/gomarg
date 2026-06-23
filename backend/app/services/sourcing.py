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
        Searches Apollo's full database (mixed_people/search).
        """
        if not self.api_key:
            print("WARNING: Apollo API key not configured. Cannot search.")
            return []
            
        # Use mixed_people/search to search the entire Apollo database, not just saved contacts
        search_url = "https://api.apollo.io/v1/mixed_people/search"
        
        # Build the payload from structured fields
        payload: dict = {
            "page": page,
            "per_page": per_page,
            # To reveal emails on the fly (uses API credits):
            "reveal_emails": True 
        }
        
        # Role -> person_titles array (Apollo prefers array for titles)
        if role:
            payload["person_titles"] = [role.strip()]
            
        # Sector -> combined into q_keywords or organization_industries
        if sector:
            payload["q_keywords"] = sector.strip()
        
        # Company -> q_organization_name
        if company:
            payload["q_organization_name"] = company.strip()
        
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key
        }
        
        async with httpx.AsyncClient() as client:
            print(f"Fetching Apollo Leads from global database with payload: {payload}")
            response = await client.post(search_url, headers=headers, json=payload, timeout=30.0)
            
            if response.status_code != 200:
                print(f"Apollo API Contacts Search error: {response.text}")
                return []
                
            data = response.json()
            # mixed_people/search returns a 'people' array, not 'contacts'
            people = data.get("people", [])
            print(f"Found {len(people)} leads from global search. Importing...")
            
            imported_leads = []
            
            for person in people:
                # If we asked for reveal_emails, it might be in 'email' or we might need to handle cases where it fails
                email = person.get("email")
                if not email:
                    continue # Skip if we couldn't get an email
                first_name = person.get("first_name", "")
                last_name = person.get("last_name", "")
                title = person.get("title", "")
                company = person.get("organization_name", "")
                linkedin = person.get("linkedin_url", "")
                
                apollo_id = person.get("id")
                
                # Extract extra data
                phone_number = person.get("sanitized_phone")
                if not phone_number and person.get("phone_numbers"):
                    phone_number = person["phone_numbers"][0].get("sanitized_number") or person["phone_numbers"][0].get("raw_number")
                if not phone_number:
                    phone_number = person.get("phone_number", "")
                
                city = person.get("city", "")
                state = person.get("state", "")
                country = person.get("country", "")
                # Some apollo contacts have organization object inside
                org = person.get("organization", {})
                industry = org.get("industry") if org else person.get("industry", "")
                

                # Prevent duplicates (Check by apollo_id or email)
                from sqlalchemy import or_
                existing_lead = await self.session.execute(
                    select(Lead).filter(
                        Lead.organization_id == org_id,
                        or_(
                            Lead.apollo_id == apollo_id,
                            Lead.email == email
                        )
                    )
                )
                if existing_lead.scalars().first():
                    continue
                    
                # Create Lead
                new_lead = Lead(
                    organization_id=org_id,
                    email=email,
                    apollo_id=apollo_id,
                    first_name=first_name,
                    last_name=last_name,
                    company=company,
                    job_title=title,
                    linkedin_url=linkedin,
                    phone_number=phone_number,
                    city=city,
                    state=state,
                    country=country,
                    industry=industry,
                    status="new"
                )
                self.session.add(new_lead)
                await self.session.commit()
                await self.session.refresh(new_lead)
                
                # Save the raw contact data as research for the AI
                await self._save_research(new_lead, org_id, person)
                imported_leads.append(new_lead)
                print(f"Imported lead: {email}")
                
            return imported_leads
