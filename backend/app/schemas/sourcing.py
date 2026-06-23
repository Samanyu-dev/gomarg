from pydantic import BaseModel, Field
from typing import List, Optional

class ApolloSearchRequest(BaseModel):
    """
    Structured search request for Apollo contacts/search API.
    Instead of a single q_keywords field, we expose Role, Sector, and Company
    as dedicated fields so the frontend can provide targeted filters.
    """
    role: Optional[str] = Field(default=None, description="Job title or role to search for (e.g. 'Data Engineer', 'VP Sales')")
    sector: Optional[str] = Field(default=None, description="Industry or sector to target (e.g. 'Healthcare', 'FinTech')")
    company: Optional[str] = Field(default=None, description="Specific company name to filter by (e.g. 'Apple', 'Optum')")
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    
class ApolloSearchResponse(BaseModel):
    success: bool
    message: str
    leads_imported: int
