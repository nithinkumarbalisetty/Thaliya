from typing import Dict, Any, Optional
from pydantic import BaseModel

class ServiceRequest(BaseModel):
    """Base request model for service operations"""
    data: Dict[str, Any]
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ServiceResponse(BaseModel):
    """Base response model for service operations"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ClientCredentials(BaseModel):
    """Client credentials for authentication"""
    client_id: str
    client_secret: str

class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    service_name: str