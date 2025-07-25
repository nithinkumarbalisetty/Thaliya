from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_service import BaseHealthcareService

class ServiceFactory:
    """
    Factory pattern implementation for creating service instances
    """
    
    _services: Dict[str, "BaseHealthcareService"] = {}
    
    @classmethod
    def get_service(cls, service_name: str) -> "BaseHealthcareService":
        """
        Get or create a service instance based on service name
        """
        if service_name not in cls._services:
            cls._services[service_name] = cls._create_service(service_name)
        
        return cls._services[service_name]
    
    @classmethod
    def _create_service(cls, service_name: str) -> "BaseHealthcareService":
        """
        Create a new service instance based on service name
        """
        # Import here to avoid circular imports
        if service_name == "ecare":
            from .ecare_service import ECareService
            return ECareService()
        elif service_name == "georgetown":
            from .georgetown_service import GeorgetownService
            return GeorgetownService()
        elif service_name == "chronic_care_bridge":
            from .chronic_care_bridge_service import ChronicCareBridgeService
            return ChronicCareBridgeService()
        elif service_name == "anarcare":
            from .anarcare_service import AnarcareService
            return AnarcareService()
        else:
            raise ValueError(f"Unknown service: {service_name}")
    
    @classmethod
    def get_available_services(cls) -> list:
        """
        Get list of available services
        """
        return ["ecare", "georgetown", "chronic_care_bridge", "anarcare"]
    
    @classmethod
    def clear_cache(cls):
        """
        Clear the service cache (useful for testing)
        """
        cls._services.clear()
