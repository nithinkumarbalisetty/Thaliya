from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.core.auth import authenticate_client, create_access_token, get_service_credentials
from app.core.config import settings
from app.schemas.service import ClientCredentials, TokenResponse

router = APIRouter()
security = HTTPBasic()

@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(credentials: ClientCredentials):
    """
    OAuth2 client credentials flow for service authentication
    """
    # Authenticate the client
    client_data = authenticate_client(credentials.client_id, credentials.client_secret)
    
    if not client_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(hours=settings.ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(
        data={
            "sub": client_data["client_id"],
            "service_name": client_data["service_name"]
        },
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_HOURS * 3600,  # Convert to seconds
        service_name=client_data["service_name"]
    )

@router.get("/credentials")
async def get_client_credentials():
    """
    Get available client credentials (for testing/documentation purposes)
    Note: In production, this endpoint should be removed or secured
    """
    return {
        "message": "Available client credentials for testing",
        "credentials": get_service_credentials()
    }
