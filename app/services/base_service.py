from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.schemas.services import BaseHealthcareRequest, BaseHealthcareResponse

class BaseHealthcareService(ABC):
    """
    Abstract base class for all healthcare services.
    Implements the Strategy pattern for different service implementations.
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
    
    @abstractmethod
    async def process_request(self, request_data: BaseHealthcareRequest) -> BaseHealthcareResponse:
        """Process a healthcare request"""
        pass
    
    @abstractmethod
    async def get_patient_data(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get patient data"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, str]:
        """Health check for the service"""
        pass
    
    def get_service_info(self) -> Dict[str, str]:
        """Get basic service information"""
        return {
            "service_name": self.service_name,
            "status": "active",
            "version": "1.0.0"
        }
