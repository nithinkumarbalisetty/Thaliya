from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token scheme
security = HTTPBearer()

# Client credentials for the 4 services
SERVICE_CREDENTIALS = {
    "ecare_client": {
        "client_secret": "ecare_secret_key_2025",
        "service_name": "ecare"
    },
    "georgetown_client": {
        "client_secret": "georgetown_secret_key_2025",
        "service_name": "georgetown"
    },
    "chronic_care_bridge_client": {
        "client_secret": "chronic_care_bridge_secret_key_2025",
        "service_name": "chronic_care_bridge"
    },
    "anarcare_client": {
        "client_secret": "anarcare_secret_key_2025",
        "service_name": "anarcare"
    }
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Dict[str, Any]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def authenticate_client(client_id: str, client_secret: str) -> Optional[Dict[str, Any]]:
    """Authenticate a client using client credentials"""
    if client_id not in SERVICE_CREDENTIALS:
        return None
    
    stored_credentials = SERVICE_CREDENTIALS[client_id]
    if stored_credentials["client_secret"] != client_secret:
        return None
    
    return {
        "client_id": client_id,
        "service_name": stored_credentials["service_name"]
    }

async def get_current_service(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get the current authenticated service from JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    
    client_id: str = payload.get("sub")
    service_name: str = payload.get("service_name")
    
    if client_id is None or service_name is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "client_id": client_id,
        "service_name": service_name
    }

def get_service_credentials() -> Dict[str, Dict[str, str]]:
    """Get all service credentials (for documentation/testing purposes)"""
    return {
        client_id: {
            "service_name": creds["service_name"],
            "client_secret": creds["client_secret"]  # In production, never expose secrets
        }
        for client_id, creds in SERVICE_CREDENTIALS.items()
    }