from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx

from app.services.base_service import BaseHealthcareService
from app.schemas.services import BaseHealthcareRequest, GeorgeTownResponse
from app.core.config import settings

class GeorgeTownService(BaseHealthcareService):
    """
    GeorgeTown service implementation for research and academic healthcare.
    Handles research studies, participant data, and academic collaborations.
    """
    
    def __init__(self):
        super().__init__("georgetown")
        self.base_url = settings.SERVICE_URLS["georgetown"]
    
    async def process_request(self, request_data: BaseHealthcareRequest) -> GeorgeTownResponse:
        """Process GeorgeTown specific request"""
        # Simulate GeorgeTown research processing
        response_data = {
            "study_id": f"GT_STUDY_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "enrollment_status": "active",
            "research_phase": "data_collection"
        }
        
        return GeorgeTownResponse(
            status="success",
            message="GeorgeTown research request processed successfully",
            data=response_data,
            timestamp=datetime.utcnow(),
            study_status=response_data["enrollment_status"],
            research_data=response_data
        )
    
    async def get_patient_data(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get participant data from GeorgeTown research system"""
        try:
            # Mock research participant data
            return {
                "participant_id": patient_id,
                "study_enrollment": [
                    {
                        "study_id": "GT_COVID_STUDY_2024",
                        "enrollment_date": "2024-01-01",
                        "status": "active",
                        "data_points_collected": 15
                    },
                    {
                        "study_id": "GT_DIABETES_RESEARCH",
                        "enrollment_date": "2023-12-01",
                        "status": "completed",
                        "data_points_collected": 30
                    }
                ],
                "consent_status": "valid",
                "data_sharing_permissions": ["anonymized", "aggregate"]
            }
        except Exception as e:
            print(f"Error fetching participant data from GeorgeTown: {e}")
            return None
    
    async def health_check(self) -> Dict[str, str]:
        """Health check for GeorgeTown service"""
        try:
            return {"status": "healthy", "external_service": "mock_reachable"}
        except Exception:
            return {"status": "unhealthy", "external_service": "unreachable"}
    
    async def enroll_participant(self, participant_data: Dict[str, Any]) -> Dict[str, Any]:
        """GeorgeTown specific method for enrolling research participants"""
        participant_id = f"GT_PART_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return {
            "participant_id": participant_id,
            "study_id": participant_data.get("study_id"),
            "enrollment_date": datetime.utcnow().isoformat(),
            "consent_status": "obtained",
            "status": "enrolled"
        }
    
    async def get_study_data(self, study_id: str) -> Dict[str, Any]:
        """Get research study information"""
        return {
            "study_id": study_id,
            "title": "Georgetown Healthcare Research Study",
            "principal_investigator": "Dr. Research",
            "phase": "Phase II",
            "enrollment_target": 500,
            "current_enrollment": 245,
            "study_duration": "24 months",
            "irb_approval": "GT_IRB_2024_001"
        }
    
    async def submit_research_data(self, study_id: str, participant_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit research data for a participant"""
        submission_id = f"GT_SUB_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        return {
            "submission_id": submission_id,
            "study_id": study_id,
            "participant_id": participant_id,
            "submission_date": datetime.utcnow().isoformat(),
            "data_points": len(data),
            "status": "accepted"
        }
