import httpx
import asyncio
import json
import re
import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID

from app.core.config import settings
from app.models.lead import Lead, ResearchDocument


class ApolloService:
    """
    Two-stage sourcing pipeline:
      Stage 1 — DISCOVERY: Find people matching ICP using Apollo's search API
      Stage 2 — ENRICHMENT: Enrich each discovered person with verified email, phone, location
    
    Fallback: If Apollo key is missing, falls back to DuckDuckGo scraping (degraded mode).
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.api_key = settings.APOLLO_API_KEY
        self.base_url = "https://api.apollo.io/api/v1"

    # ─────────────────────────────────────────────
    # PUBLIC: Enrich a single lead (called from other parts of the app)
    # ─────────────────────────────────────────────
    async def enrich_lead(self, lead_id: UUID, org_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Calls Apollo people/match to enrich a single lead with verified data.
        """
        result = await self.session.execute(
            select(Lead).filter(Lead.id == lead_id, Lead.organization_id == org_id)
        )
        lead = result.scalars().first()
        if not lead:
            raise ValueError("Lead not found")

        if not self.api_key:
            print("WARNING: Apollo API key not configured. Skipping enrichment.")
            return None

        person_data = await self._apollo_enrich_person(
            first_name=lead.first_name,
            last_name=lead.last_name,
            company=lead.company,
            linkedin_url=lead.linkedin_url,
            email=lead.email,
        )

        if person_data:
            # Update lead with enriched data
            if person_data.get("email"):
                lead.email = person_data["email"]
            if person_data.get("title"):
                lead.job_title = person_data["title"]
            if person_data.get("linkedin_url"):
                lead.linkedin_url = person_data["linkedin_url"]
            if person_data.get("phone_number"):
                lead.phone_number = person_data["phone_number"]
            if person_data.get("city"):
                lead.city = person_data["city"]
            if person_data.get("state"):
                lead.state = person_data["state"]
            if person_data.get("country"):
                lead.country = person_data["country"]

            await self._save_research(lead, org_id, person_data)
            await self.session.commit()

        return person_data

    # ─────────────────────────────────────────────
    # PUBLIC: Search + Import pipeline (called from router & worker)
    # ─────────────────────────────────────────────
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
        Two-stage pipeline:
          1. Apollo mixed_people/search → discover people matching ICP
          2. Apollo people/match → enrich each person with verified contact data
        
        Falls back to DuckDuckGo scraping if Apollo key is missing.
        """
        # Prevent empty global search
        if not role and not company and not sector:
            print("Skipping empty global search to avoid generic results.")
            return []

        if settings.EXA_API_KEY:
            return await self._exa_search_pipeline(org_id, role, sector, company, page, per_page)
        elif self.api_key:
            return await self._apollo_search_pipeline(org_id, role, sector, company, page, per_page)
        else:
            print("WARNING: No Apollo or Exa API key. Falling back to DuckDuckGo scraper (degraded mode).")
            return await self._ddg_fallback_pipeline(org_id, role, sector, company, page, per_page)

    # ═════════════════════════════════════════════
    # STAGE 1: Apollo Search (Discovery)
    # ═════════════════════════════════════════════
    async def _apollo_search_pipeline(
        self, org_id: UUID, role: str, sector: str, company: str, page: int, per_page: int
    ) -> list[Lead]:
        """
        Uses Apollo's mixed_people/search endpoint to discover real people,
        then enriches each one via people/match for verified contact data.
        """
        print(f"🔎 Apollo Search: role={role}, company={company}, sector={sector}, page={page}")

        # Build Apollo search payload
        search_payload: Dict[str, Any] = {
            "page": page,
            "per_page": per_page,
        }

        # Job title filter
        if role:
            search_payload["person_titles"] = [role]

        # Company filter
        if company:
            search_payload["q_organization_name"] = company

        # Industry/sector filter  
        if sector:
            search_payload["q_keywords"] = sector

        imported_leads = []
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Stage 1: Search for people
            try:
                search_response = await client.post(
                    f"{self.base_url}/mixed_people/search",
                    json=search_payload,
                    headers=headers,
                )
                
                if search_response.status_code != 200:
                    print(f"Apollo search error ({search_response.status_code}): {search_response.text}")
                    # Fall back to DuckDuckGo if Apollo search fails
                    return await self._ddg_fallback_pipeline(org_id, role, sector, company, page, per_page)

                search_data = search_response.json()
                people = search_data.get("people", [])
                print(f"   Apollo found {len(people)} people")

            except Exception as e:
                print(f"Apollo search request failed: {e}")
                return await self._ddg_fallback_pipeline(org_id, role, sector, company, page, per_page)

            # Stage 2: Process each person
            for person in people:
                try:
                    lead = await self._process_apollo_person(client, person, org_id)
                    if lead:
                        imported_leads.append(lead)
                except Exception as e:
                    print(f"   Failed to process person: {e}")
                    continue

        return imported_leads

    async def _process_apollo_person(
        self, client: httpx.AsyncClient, person: Dict[str, Any], org_id: UUID
    ) -> Optional[Lead]:
        """
        Takes a person record from Apollo search results, enriches it,
        and creates a Lead in the database.
        """
        # Extract base data from search result
        first_name = person.get("first_name", "")
        last_name = person.get("last_name", "")
        apollo_id = person.get("id", "")
        email = person.get("email", "")
        linkedin_url = person.get("linkedin_url", "")
        title = person.get("title", "")
        phone_number = ""
        city = ""
        state = ""
        country = ""
        company_name = ""
        industry = ""

        # Extract organization info
        org_info = person.get("organization", {})
        if org_info:
            company_name = org_info.get("name", "")
            industry = org_info.get("industry", "")

        # Extract phone from person data
        phone_numbers = person.get("phone_numbers", [])
        if phone_numbers:
            # Prefer mobile, then work
            for pn in phone_numbers:
                if pn.get("type") == "mobile":
                    phone_number = pn.get("sanitized_number", pn.get("raw_number", ""))
                    break
            if not phone_number and phone_numbers:
                phone_number = phone_numbers[0].get("sanitized_number", phone_numbers[0].get("raw_number", ""))

        # Extract location
        city = person.get("city", "")
        state = person.get("state", "")
        country = person.get("country", "")

        # ── Stage 2: Enrichment via people/match ──
        # Only call if we're missing critical data (email or phone)
        if not email or not phone_number:
            enriched = await self._apollo_enrich_person(
                first_name=first_name,
                last_name=last_name,
                company=company_name,
                linkedin_url=linkedin_url,
                email=email,
            )
            if enriched:
                if not email and enriched.get("email"):
                    email = enriched["email"]
                if not phone_number and enriched.get("phone_number"):
                    phone_number = enriched["phone_number"]
                if not title and enriched.get("title"):
                    title = enriched["title"]
                if not city and enriched.get("city"):
                    city = enriched["city"]
                if not state and enriched.get("state"):
                    state = enriched["state"]
                if not country and enriched.get("country"):
                    country = enriched["country"]
                if not company_name and enriched.get("organization_name"):
                    company_name = enriched["organization_name"]

        # Skip leads without email — they're useless for outreach
        if not email:
            print(f"   Skipping {first_name} {last_name} — no email found")
            return None

        # Deduplicate: check if lead already exists
        existing = await self.session.execute(
            select(Lead).filter(
                Lead.organization_id == org_id,
                Lead.email == email,
            )
        )
        if existing.scalars().first():
            print(f"   Skipping duplicate: {email}")
            return None

        # Create the lead
        new_lead = Lead(
            organization_id=org_id,
            email=email,
            apollo_id=apollo_id or str(uuid.uuid4()),
            first_name=first_name,
            last_name=last_name,
            company=company_name or "Unknown",
            job_title=title or "Unknown",
            linkedin_url=linkedin_url,
            phone_number=phone_number,
            city=city,
            state=state,
            country=country,
            industry=industry,
            status="new",
        )
        self.session.add(new_lead)
        await self.session.commit()
        await self.session.refresh(new_lead)

        # Save full person data as research for AI email generation
        await self._save_research(new_lead, org_id, person)
        print(f"   ✅ Imported: {first_name} {last_name} <{email}> @ {company_name} | Phone: {phone_number or 'N/A'}")
        return new_lead

    # ═════════════════════════════════════════════
    # STAGE 2: Apollo Enrichment (single person)
    # ═════════════════════════════════════════════
    async def _apollo_enrich_person(
        self,
        first_name: str = "",
        last_name: str = "",
        company: str = "",
        linkedin_url: str = "",
        email: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Calls Apollo people/match to get verified email, phone, and location
        for a single person.
        """
        if not self.api_key:
            return None

        payload: Dict[str, Any] = {}

        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if company:
            payload["organization_name"] = company
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url
        if email:
            payload["email"] = email

        try:
            headers = {
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "X-Api-Key": self.api_key,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/people/match",
                    json=payload,
                    headers=headers,
                )

                if response.status_code != 200:
                    print(f"   Apollo enrich error: {response.status_code}")
                    return None

                data = response.json()
                person = data.get("person", {})

                if not person:
                    return None

                # Extract phone
                phone_number = ""
                phone_numbers = person.get("phone_numbers", [])
                if phone_numbers:
                    for pn in phone_numbers:
                        if pn.get("type") == "mobile":
                            phone_number = pn.get("sanitized_number", pn.get("raw_number", ""))
                            break
                    if not phone_number and phone_numbers:
                        phone_number = phone_numbers[0].get("sanitized_number", phone_numbers[0].get("raw_number", ""))

                org_info = person.get("organization", {})

                return {
                    "email": person.get("email", ""),
                    "title": person.get("title", ""),
                    "linkedin_url": person.get("linkedin_url", ""),
                    "phone_number": phone_number,
                    "city": person.get("city", ""),
                    "state": person.get("state", ""),
                    "country": person.get("country", ""),
                    "organization_name": org_info.get("name", "") if org_info else "",
                    "seniority": person.get("seniority", ""),
                    "departments": person.get("departments", []),
                }

        except Exception as e:
            print(f"   Apollo enrich request failed: {e}")
            return None

    # ═════════════════════════════════════════════
    # FALLBACK: DuckDuckGo Scraper (degraded mode)
    # ═════════════════════════════════════════════
    async def _ddg_fallback_pipeline(
        self, org_id: UUID, role: str, sector: str, company: str, page: int, per_page: int
    ) -> list[Lead]:
        """
        Falls back to DuckDuckGo scraping when Apollo key is missing.
        This provides names + guessed emails but NO phone numbers.
        """
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            print("WARNING: duckduckgo_search package not installed. Cannot scrape.")
            return []

        query_parts = ["site:linkedin.com/in"]
        if role:
            query_parts.append(f'"{role}"')
        if company:
            query_parts.append(f'"{company}"')
        if sector:
            query_parts.append(f'"{sector}"')

        query = " ".join(query_parts)
        print(f"🔎 DuckDuckGo fallback: {query}")

        imported_leads = []

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=per_page))

                for r in results:
                    title_text = r.get("title", "")
                    linkedin_url = r.get("href", "")
                    body_text = r.get("body", "")

                    parts = title_text.split("-")
                    if len(parts) >= 1:
                        name_part = parts[0].strip().replace(" | LinkedIn", "").strip()
                        name_tokens = name_part.split(" ")
                        first_name = name_tokens[0] if name_tokens else ""
                        last_name = " ".join(name_tokens[1:]) if len(name_tokens) > 1 else ""

                        # Extract job title from LinkedIn title if possible
                        job_title = parts[1].strip() if len(parts) >= 2 else (role or "Unknown")
                        # Clean up LinkedIn suffix
                        job_title = job_title.replace(" | LinkedIn", "").strip()

                        # Extract company from LinkedIn title
                        lead_company = parts[2].strip().replace(" | LinkedIn", "").strip() if len(parts) >= 3 else (company or "Unknown")

                        # Guess email
                        safe_company = re.sub(r"[^a-zA-Z0-9]", "", str(lead_company).lower())
                        safe_first = re.sub(r"[^a-zA-Z0-9]", "", first_name.lower())
                        safe_last = re.sub(r"[^a-zA-Z0-9]", "", last_name.lower())
                        email = f"{safe_first}.{safe_last}@{safe_company}.com" if safe_last else f"{safe_first}@{safe_company}.com"

                        # Deduplicate
                        existing = await self.session.execute(
                            select(Lead).filter(
                                Lead.organization_id == org_id,
                                Lead.email == email,
                            )
                        )
                        if existing.scalars().first():
                            continue

                        new_lead = Lead(
                            organization_id=org_id,
                            email=email,
                            apollo_id=str(uuid.uuid4()),
                            first_name=first_name,
                            last_name=last_name,
                            company=lead_company,
                            job_title=job_title,
                            linkedin_url=linkedin_url,
                            phone_number="",
                            city="",
                            state="",
                            country="",
                            industry=sector or "",
                            status="new",
                        )
                        self.session.add(new_lead)
                        await self.session.commit()
                        await self.session.refresh(new_lead)

                        await self._save_research(new_lead, org_id, {
                            "name": name_part,
                            "title": job_title,
                            "organization_name": lead_company,
                            "linkedin_url": linkedin_url,
                            "snippet": body_text,
                        })
                        imported_leads.append(new_lead)
                        print(f"   ✅ DDG Import: {email}")

        except Exception as e:
            print(f"DuckDuckGo scraping error: {e}")

        return imported_leads

    # ═════════════════════════════════════════════
    # STAGE 1: Exa AI Search (Discovery)
    # ═════════════════════════════════════════════
    async def _exa_search_pipeline(
        self, org_id: UUID, role: str, sector: str, company: str, page: int, per_page: int
    ) -> list[Lead]:
        """
        Uses Exa AI to search for LinkedIn profiles (highly accurate and unblocked).
        Then tries to enrich via Apollo if key is present (though free tier blocks it).
        """
        try:
            from exa_py import Exa
        except ImportError:
            print("WARNING: exa_py not installed. Falling back to Apollo/DDG.")
            return []

        exa = Exa(api_key=settings.EXA_API_KEY)
        query_parts = ["LinkedIn profile of"]
        if role:
            query_parts.append(role)
        if company:
            query_parts.append(f"at {company}")
        if sector:
            query_parts.append(f"in {sector}")

        query = " ".join(query_parts)
        print(f"🔎 Exa Search: {query}")

        imported_leads = []

        try:
            # Exa search focusing on LinkedIn profiles
            results = exa.search(
                query,
                use_autoprompt=True,
                num_results=per_page,
                include_domains=["linkedin.com"]
            )
            
            for r in results.results:
                title_text = r.title or ""
                linkedin_url = r.url or ""
                
                if "linkedin.com/in/" not in linkedin_url:
                    continue

                parts = title_text.split("-")
                if len(parts) >= 1:
                    name_part = parts[0].strip().replace(" | LinkedIn", "").strip()
                    name_tokens = name_part.split(" ")
                    first_name = name_tokens[0] if name_tokens else ""
                    last_name = " ".join(name_tokens[1:]) if len(name_tokens) > 1 else ""

                    # Extract job title from LinkedIn title if possible
                    job_title = parts[1].strip() if len(parts) >= 2 else (role or "Unknown")
                    job_title = job_title.replace(" | LinkedIn", "").strip()

                    # Extract company from LinkedIn title
                    lead_company = parts[2].strip().replace(" | LinkedIn", "").strip() if len(parts) >= 3 else (company or "Unknown")

                    # Guess email
                    safe_company = re.sub(r"[^a-zA-Z0-9]", "", str(lead_company).lower())
                    safe_first = re.sub(r"[^a-zA-Z0-9]", "", first_name.lower())
                    safe_last = re.sub(r"[^a-zA-Z0-9]", "", last_name.lower())
                    email = f"{safe_first}.{safe_last}@{safe_company}.com" if safe_last else f"{safe_first}@{safe_company}.com"

                    # Deduplicate
                    existing = await self.session.execute(
                        select(Lead).filter(
                            Lead.organization_id == org_id,
                            Lead.email == email,
                        )
                    )
                    if existing.scalars().first():
                        continue

                    # Try Apollo enrichment (silent fail if blocked)
                    phone_number = ""
                    city = ""
                    if self.api_key:
                        enriched = await self._apollo_enrich_person(
                            first_name=first_name,
                            last_name=last_name,
                            company=lead_company,
                            linkedin_url=linkedin_url,
                            email=email,
                        )
                        if enriched:
                            email = enriched.get("email") or email
                            phone_number = enriched.get("phone_number") or ""
                            city = enriched.get("city") or ""

                    new_lead = Lead(
                        organization_id=org_id,
                        email=email,
                        apollo_id=str(uuid.uuid4()),
                        first_name=first_name,
                        last_name=last_name,
                        company=lead_company,
                        job_title=job_title,
                        linkedin_url=linkedin_url,
                        phone_number=phone_number,
                        city=city,
                        state="",
                        country="",
                        industry=sector or "",
                        status="new",
                    )
                    self.session.add(new_lead)
                    await self.session.commit()
                    await self.session.refresh(new_lead)

                    await self._save_research(new_lead, org_id, {
                        "name": name_part,
                        "title": job_title,
                        "organization_name": lead_company,
                        "linkedin_url": linkedin_url,
                        "exa_score": getattr(r, "score", None)
                    })
                    imported_leads.append(new_lead)
                    print(f"   ✅ Exa Import: {email}")

        except Exception as e:
            print(f"Exa search error: {e}")
            # Fall back to DDG if Exa fails
            return await self._ddg_fallback_pipeline(org_id, role, sector, company, page, per_page)

        return imported_leads

    # ═════════════════════════════════════════════
    # UTIL: Save research document
    # ═════════════════════════════════════════════
    async def _save_research(self, lead: Lead, org_id: UUID, data: Dict[str, Any]):
        doc = ResearchDocument(
            organization_id=org_id,
            lead_id=lead.id,
            doc_type="apollo_enrichment",
            content=json.dumps(data),
        )
        self.session.add(doc)
        await self.session.commit()
