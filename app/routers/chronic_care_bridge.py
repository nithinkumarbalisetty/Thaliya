from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from app.routers.auth import get_current_service
from app.services.service_factory import ServiceFactory
from app.schemas.services import ChronicCareData, ChronicCareResponse, BaseHealthcareRequest

router = APIRouter()

@router.get("/info")
async def get_chronic_care_bridge_info(current_service: str = Depends(get_current_service)):
    """Get ChronicCareBridge service information"""
    if current_service != "chroniccarebridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for ChronicCareBridge service"
        )
    
    service = ServiceFactory.get_service("chroniccarebridge")
    return service.get_service_info()

@router.get("/health")
async def chronic_care_bridge_health_check(current_service: str = Depends(get_current_service)):
    """ChronicCareBridge service health check"""
    if current_service != "chroniccarebridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for ChronicCareBridge service"
        )
    
    service = ServiceFactory.get_service("chroniccarebridge")
    return await service.health_check()

@router.post("/process", response_model=ChronicCareResponse)
async def process_chronic_care_request(
    request: BaseHealthcareRequest,
    current_service: str = Depends(get_current_service)
):
    """Process ChronicCareBridge healthcare request"""
    if current_service != "chroniccarebridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for ChronicCareBridge service"
        )
    
    service = ServiceFactory.get_service("chroniccarebridge")
    return await service.process_request(request)

@router.get("/patients/{patient_id}")
async def get_chronic_care_patient_data(
    patient_id: str,
    current_service: str = Depends(get_current_service)
):
    """Get chronic care patient data"""
    if current_service != "chroniccarebridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for ChronicCareBridge service"
        )
    
    service = ServiceFactory.get_service("chroniccarebridge")
    patient_data = await service.get_patient_data(patient_id)
    
    if not patient_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return patient_data

@router.post("/care-plans")
async def create_care_plan(
    plan_data: Dict[str, Any],
    current_service: str = Depends(get_current_service)
):
    """Create a new chronic care plan"""
    if current_service != "chroniccarebridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for ChronicCareBridge service"
        )
    
    patient_id = plan_data.get("patient_id")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient ID is required"
        )
    
    service = ServiceFactory.get_service("chroniccarebridge")
    result = await service.create_care_plan(patient_id, plan_data)
    return result

@router.get("/care-plans/{plan_id}/status")
async def get_care_plan_status(
    plan_id: str,
    current_service: str = Depends(get_current_service)
):
    """Get the status of a care plan"""
    if current_service != "chroniccarebridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for ChronicCareBridge service"
        )
    
    service = ServiceFactory.get_service("chroniccarebridge")
    status_data = await service.get_care_plan_status(plan_id)
    return status_data

@router.post("/patients/{patient_id}/monitoring")
async def update_monitoring_data(
    patient_id: str,
    monitoring_data: Dict[str, Any],
    current_service: str = Depends(get_current_service)
):
    """Update patient monitoring data"""
    if current_service != "chroniccarebridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for ChronicCareBridge service"
        )
    
    service = ServiceFactory.get_service("chroniccarebridge")
    result = await service.update_monitoring_data(patient_id, monitoring_data)
    return result
