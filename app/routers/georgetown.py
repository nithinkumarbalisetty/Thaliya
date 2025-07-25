from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from app.routers.auth import get_current_service
from app.services.service_factory import ServiceFactory
from app.schemas.services import GeorgeTownResearchData, GeorgeTownResponse, BaseHealthcareRequest

router = APIRouter()

@router.get("/info")
async def get_georgetown_info(current_service: str = Depends(get_current_service)):
    """Get GeorgeTown service information"""
    if current_service != "georgetown":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for GeorgeTown service"
        )
    
    service = ServiceFactory.get_service("georgetown")
    return service.get_service_info()

@router.get("/health")
async def georgetown_health_check(current_service: str = Depends(get_current_service)):
    """GeorgeTown service health check"""
    if current_service != "georgetown":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for GeorgeTown service"
        )
    
    service = ServiceFactory.get_service("georgetown")
    return await service.health_check()

@router.post("/process", response_model=GeorgeTownResponse)
async def process_georgetown_request(
    request: BaseHealthcareRequest,
    current_service: str = Depends(get_current_service)
):
    """Process GeorgeTown research request"""
    if current_service != "georgetown":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for GeorgeTown service"
        )
    
    service = ServiceFactory.get_service("georgetown")
    return await service.process_request(request)

@router.get("/participants/{participant_id}")
async def get_participant_data(
    participant_id: str,
    current_service: str = Depends(get_current_service)
):
    """Get participant data from GeorgeTown research system"""
    if current_service != "georgetown":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for GeorgeTown service"
        )
    
    service = ServiceFactory.get_service("georgetown")
    participant_data = await service.get_patient_data(participant_id)
    
    if not participant_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found"
        )
    
    return participant_data

@router.post("/participants/enroll")
async def enroll_participant(
    participant_data: Dict[str, Any],
    current_service: str = Depends(get_current_service)
):
    """Enroll a new research participant"""
    if current_service != "georgetown":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for GeorgeTown service"
        )
    
    service = ServiceFactory.get_service("georgetown")
    result = await service.enroll_participant(participant_data)
    return result

@router.get("/studies/{study_id}")
async def get_study_data(
    study_id: str,
    current_service: str = Depends(get_current_service)
):
    """Get research study information"""
    if current_service != "georgetown":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for GeorgeTown service"
        )
    
    service = ServiceFactory.get_service("georgetown")
    study_data = await service.get_study_data(study_id)
    return study_data

@router.post("/studies/{study_id}/participants/{participant_id}/data")
async def submit_research_data(
    study_id: str,
    participant_id: str,
    research_data: Dict[str, Any],
    current_service: str = Depends(get_current_service)
):
    """Submit research data for a participant"""
    if current_service != "georgetown":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for GeorgeTown service"
        )
    
    service = ServiceFactory.get_service("georgetown")
    result = await service.submit_research_data(study_id, participant_id, research_data)
    return result
