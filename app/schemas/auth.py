from pydantic import BaseModel
from typing import Optional

# Client Credential Authentication Schemas
class ClientCredentials(BaseModel):
    client_id: str
    client_secret: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    service: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    service: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
