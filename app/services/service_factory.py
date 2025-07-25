from typing import Dict
from app.services.base_service import BaseHealthcareService
from app.services.ecare_service import ECareService
from app.services.georgetown_service import GeorgeTownService
from app.services.chronic_care_bridge_service import ChronicCareBridgeService
from app.services.anarcare_service import AnarcareService

class ServiceFactory:
    """
    Factory pattern implementation for creating service instances.
    This allows for easy addition of new services and centralized service management.
    """
    
    _services: Dict[str, BaseHealthcareService] = {}
    
    @classmethod
    def get_service(cls, service_name: str) -> BaseHealthcareService:
        """Get or create service instance"""
        if service_name not in cls._services:
            cls._services[service_name] = cls._create_service(service_name)
        return cls._services[service_name]
    
    @classmethod
    def _create_service(cls, service_name: str) -> BaseHealthcareService:
        """Create service instance based on service name"""
        service_map = {
            "ecare": ECareService,
            "georgetown": GeorgeTownService,
            "chroniccarebridge": ChronicCareBridgeService,
            "anarcare": AnarcareService
        }
        
        if service_name not in service_map:
            raise ValueError(f"Unknown service: {service_name}")
        
        return service_map[service_name]()
    
    @classmethod
    def get_available_services(cls) -> list:
        """Get list of available services"""
        return ["ecare", "georgetown", "chroniccarebridge", "anarcare"]
    
    @classmethod
    def clear_cache(cls):
        """Clear service cache (useful for testing)"""
        cls._services.clear()
