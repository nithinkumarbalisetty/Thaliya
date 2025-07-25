from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime

class BaseHealthcareService(ABC):
    """
    Abstract base class for all healthcare services
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
    
    @abstractmethod
    async def process_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request for the specific service
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for the service
        """
        pass
    
    def _get_timestamp(self) -> str:
        """
        Get current timestamp
        """
        return datetime.utcnow().isoformat()
    
    def get_service_name(self) -> str:
        """
        Get the service name
        """
        return self.service_name

# Alias for backward compatibility
BaseService = BaseHealthcareService
