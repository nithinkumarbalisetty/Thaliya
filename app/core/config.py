from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Application
    APP_NAME: str = "Thaliya Healthcare API Gateway"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API Gateway for Healthcare Services (E-Care, Georgetown, ChronicCareBridge, Anarcare)"
    
    # Security
    SECRET_KEY: str = "thaliya-healthcare-secret-key-2025-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = ["*"]
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API
    API_V1_STR: str = "/api/v1"
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_VERSION: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = None
    AZURE_OPENAI_EMBEDDINGS_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_EMBEDDINGS_API_KEY: Optional[str] = None
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: Optional[str] = None
    
    # Database
    DATABASE_URL: Optional[str] = None
    
    # External API Keys
    OPENAI_API_KEY: Optional[str] = None
    PROGNOCIS_API_URL: Optional[str] = None
    PROGNOCIS_API_KEY: Optional[str] = None
    
    # Vector Database
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: Optional[str] = None
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    # Client Credentials for Services
    ECARE_CLIENT_ID: str = "ecare_client_id"
    ECARE_CLIENT_SECRET: str = "ecare_client_secret"
    GEORGETOWN_CLIENT_ID: str = "georgetown_client_id"
    GEORGETOWN_CLIENT_SECRET: str = "georgetown_client_secret"
    CHRONICCAREBRIDGE_CLIENT_ID: str = "chroniccarebridge_client_id"
    CHRONICCAREBRIDGE_CLIENT_SECRET: str = "chroniccarebridge_client_secret"
    ANARCARE_CLIENT_ID: str = "anarcare_client_id"
    ANARCARE_CLIENT_SECRET: str = "anarcare_client_secret"
    
    # Services
    ECARE_SERVICE_URL: str = "https://api.ecare.example.com"
    GEORGETOWN_SERVICE_URL: str = "https://api.georgetown.example.com"
    CHRONIC_CARE_BRIDGE_SERVICE_URL: str = "https://api.chroniccarebridge.example.com"
    CHRONICCAREBRIDGE_SERVICE_URL: str = "https://api.chroniccarebridge.com"
    ANARCARE_SERVICE_URL: str = "https://api.anarcare.example.com"
    
    model_config = {"env_file": ".env", "case_sensitive": True}

# Create settings instance
settings = Settings()
