from typing import List
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
    
    # CORS
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = ["*"]
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API
    API_V1_STR: str = "/api/v1"
    
    # Services
    ECARE_SERVICE_URL: str = "https://api.ecare.example.com"
    GEORGETOWN_SERVICE_URL: str = "https://api.georgetown.example.com"
    CHRONIC_CARE_BRIDGE_SERVICE_URL: str = "https://api.chroniccarebridge.example.com"
    ANARCARE_SERVICE_URL: str = "https://api.anarcare.example.com"
    
    model_config = {"env_file": ".env", "case_sensitive": True}

# Create settings instance
settings = Settings()
