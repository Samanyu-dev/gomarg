from pydantic import BaseModel
from typing import Optional, Dict, Any

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Optional[Dict[str, Any]] = None

class TokenPayload(BaseModel):
    sub: Optional[str] = None
