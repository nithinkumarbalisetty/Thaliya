from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx

from app.services.base_service import BaseHealthcareService
from app.schemas.services import BaseHealthcareRequest, AnarcareResponse
from app.core.config import settings

class AnarcareService(BaseHealthcareService):
    """
    Anarcare service implementation for emergency and urgent care.
    Handles emergency responses, urgent care coordination, and crisis management.
    """
    
    def __init__(self):
        super().__init__("anarcare")
        self.base_url = settings.SERVICE_URLS["anarcare"]
    
    async def process_request(self, request_data: BaseHealthcareRequest) -> AnarcareResponse:
        """Process Anarcare specific emergency request"""
        # Simulate emergency response processing
        emergency_id = f"ANAR_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        response_time = 5  # minutes
        
        response_data = {
            "emergency_id": emergency_id,
            "response_team": "Emergency Team Alpha",
            "dispatch_status": "dispatched",
            "estimated_arrival": "5-7 minutes"
        }
        
        return AnarcareResponse(
            status="success",
            message="Emergency response initiated",
            data=response_data,
            timestamp=datetime.utcnow(),
            emergency_id=emergency_id,
            response_time=response_time
        )
    
    async def get_patient_data(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get emergency patient data"""
        try:
            # Mock emergency patient data
            return {
                "patient_id": patient_id,
                "emergency_contacts": [
                    {
                        "name": "Jane Doe",
                        "relationship": "spouse",
                        "phone": "555-0123"
                    },
                    {
                        "name": "Bob Smith",
                        "relationship": "brother",
                        "phone": "555-0456"
                    }
                ],
                "medical_alerts": [
                    "Allergic to Penicillin",
                    "Diabetic - carries insulin",
                    "History of heart condition"
                ],
                "insurance_info": {
                    "provider": "Emergency Care Plus",
                    "policy_number": "ECP123456789",
                    "group_number": "GRP001"
                },
                "last_emergency_visit": {
                    "date": "2023-11-15",
                    "reason": "Chest pain",
                    "outcome": "Discharged - anxiety related"
                }
            }
        except Exception as e:
            print(f"Error fetching emergency patient data: {e}")
            return None
    
    async def health_check(self) -> Dict[str, str]:
        """Health check for Anarcare service"""
        try:
            return {"status": "healthy", "external_service": "mock_reachable"}
        except Exception:
            return {"status": "unhealthy", "external_service": "unreachable"}
    
    async def create_emergency_response(self, emergency_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create emergency response"""
        emergency_id = f"ANAR_EMRG_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return {
            "emergency_id": emergency_id,
            "patient_id": emergency_data.get("patient_id"),
            "emergency_type": emergency_data.get("emergency_type"),
            "severity_level": emergency_data.get("severity_level", 3),
            "location": emergency_data.get("location"),
            "response_team": self._assign_response_team(emergency_data.get("severity_level", 3)),
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "estimated_response_time": self._calculate_response_time(emergency_data.get("severity_level", 3))
        }
    
    async def update_emergency_status(self, emergency_id: str, status_update: Dict[str, Any]) -> Dict[str, Any]:
        """Update emergency response status"""
        return {
            "emergency_id": emergency_id,
            "status": status_update.get("status"),
            "notes": status_update.get("notes"),
            "response_team_notes": status_update.get("response_team_notes"),
            "updated_at": datetime.utcnow().isoformat(),
            "updated_by": status_update.get("updated_by", "System")
        }
    
    async def get_emergency_history(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get patient's emergency history"""
        return [
            {
                "emergency_id": "ANAR_EMRG_20231115_1430",
                "date": "2023-11-15",
                "emergency_type": "chest_pain",
                "severity_level": 4,
                "outcome": "discharged",
                "response_time": "6 minutes"
            },
            {
                "emergency_id": "ANAR_EMRG_20230820_0930",
                "date": "2023-08-20", 
                "emergency_type": "allergic_reaction",
                "severity_level": 5,
                "outcome": "admitted",
                "response_time": "4 minutes"
            }
        ]
    
    def _assign_response_team(self, severity_level: int) -> str:
        """Assign response team based on severity"""
        if severity_level >= 4:
            return "Emergency Team Alpha"
        elif severity_level >= 2:
            return "Emergency Team Beta"
        else:
            return "Urgent Care Team"
    
    def _calculate_response_time(self, severity_level: int) -> str:
        """Calculate estimated response time based on severity"""
        if severity_level >= 4:
            return "3-5 minutes"
        elif severity_level >= 2:
            return "5-10 minutes"
        else:
            return "10-15 minutes"
