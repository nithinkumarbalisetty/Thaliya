from datetime import datetime, timedelta
from typing import Any, Union, Optional
from jose import JWTError, jwt
from app.core.config import settings

def create_access_token(subject: Union[str, Any], service_name: str, expires_delta: timedelta = None):
    """Create access token with service information"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {
        "exp": expire, 
        "sub": str(subject),
        "service": service_name,
        "iat": datetime.utcnow()
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token and return the payload"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None

def authenticate_client(client_id: str, client_secret: str) -> Optional[str]:
    """Authenticate client credentials and return service name"""
    for service_name, credentials in settings.CLIENT_CREDENTIALS.items():
        if (credentials["client_id"] == client_id and 
            credentials["client_secret"] == client_secret):
            return service_name
    return None

def get_service_from_token(token: str) -> Optional[str]:
    """Extract service name from token"""
    payload = verify_token(token)
    if payload:
        return payload.get("service")
    return None
