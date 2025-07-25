from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import timedelta

from app.core.security import authenticate_client, create_access_token, verify_token
from app.core.config import settings
from app.schemas.auth import ClientCredentials, TokenResponse

router = APIRouter()
security = HTTPBearer()

@router.post("/token", response_model=TokenResponse)
async def get_access_token(credentials: ClientCredentials):
    """
    Client Credentials OAuth2 flow endpoint.
    Each service authenticates with their client_id and client_secret.
    """
    service_name = authenticate_client(
        credentials.client_id, 
        credentials.client_secret
    )
    
    if not service_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=credentials.client_id,
        service_name=service_name,
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
        service=service_name
    )

@router.post("/verify")
async def verify_access_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify the validity of an access token.
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "valid": True,
        "service": payload.get("service"),
        "client_id": payload.get("sub"),
        "expires_at": payload.get("exp")
    }

# Dependency to get current service from token
async def get_current_service(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Dependency to extract and validate the service from the bearer token.
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    service = payload.get("service")
    if not service:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing service information",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return service
