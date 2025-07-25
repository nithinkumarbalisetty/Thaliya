from decouple import config
from typing import List, Dict

class Settings:
    PROJECT_NAME: str = "Thaliya Healthcare API Gateway"
    PROJECT_VERSION: str = "1.0.0"
    
    # Security
    SECRET_KEY: str = config("SECRET_KEY", default="thaliya-secret-key-change-in-production")
    ALGORITHM: str = config("ALGORITHM", default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = config("ACCESS_TOKEN_EXPIRE_MINUTES", default=30, cast=int)
    
    # Client Credentials for Each Service
    CLIENT_CREDENTIALS: Dict[str, Dict[str, str]] = {
        "ecare": {
            "client_id": config("ECARE_CLIENT_ID", default="ecare_client_id"),
            "client_secret": config("ECARE_CLIENT_SECRET", default="ecare_client_secret")
        },
        "georgetown": {
            "client_id": config("GEORGETOWN_CLIENT_ID", default="georgetown_client_id"),
            "client_secret": config("GEORGETOWN_CLIENT_SECRET", default="georgetown_client_secret")
        },
        "chroniccarebridge": {
            "client_id": config("CHRONICCAREBRIDGE_CLIENT_ID", default="chroniccarebridge_client_id"),
            "client_secret": config("CHRONICCAREBRIDGE_CLIENT_SECRET", default="chroniccarebridge_client_secret")
        },
        "anarcare": {
            "client_id": config("ANARCARE_CLIENT_ID", default="anarcare_client_id"),
            "client_secret": config("ANARCARE_CLIENT_SECRET", default="anarcare_client_secret")
        }
    }
    
    # External Service URLs
    SERVICE_URLS: Dict[str, str] = {
        "ecare": config("ECARE_SERVICE_URL", default="https://api.ecare.com"),
        "georgetown": config("GEORGETOWN_SERVICE_URL", default="https://api.georgetown.edu"),
        "chroniccarebridge": config("CHRONICCAREBRIDGE_SERVICE_URL", default="https://api.chroniccarebridge.com"),
        "anarcare": config("ANARCARE_SERVICE_URL", default="https://api.anarcare.com")
    }
    
    # CORS
    ALLOWED_HOSTS: List[str] = config(
        "ALLOWED_HOSTS",
        default="http://localhost:3000,http://127.0.0.1:3000",
        cast=lambda v: [i.strip() for i in v.split(',')]
    )
    
    # Debug
    DEBUG: bool = config("DEBUG", default=True, cast=bool)

settings = Settings()
