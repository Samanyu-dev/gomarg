from pydantic import BaseModel, Field
from typing import List, Optional

class ApolloSearchRequest(BaseModel):
    person_titles: Optional[List[str]] = Field(default=None, description="Job titles to search for")
    person_locations: Optional[List[str]] = Field(default=None, description="Locations of the people")
    person_seniorities: Optional[List[str]] = Field(default=None, description="owner, founder, c_suite, partner, vp, head, director, manager, senior, entry, intern")
    q_organization_domains_list: Optional[List[str]] = Field(default=None, description="Specific company domains")
    organization_num_employees_ranges: Optional[List[str]] = Field(default=None, description="e.g. 1,10 or 250,500")
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=5, ge=1, le=100) # Keep small default for MVP
    
class ApolloSearchResponse(BaseModel):
    success: bool
    message: str
    leads_imported: int
