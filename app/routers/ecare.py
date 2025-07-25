from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any

from app.routers.auth import get_current_service
from app.services.service_factory import ServiceFactory
from app.schemas.services import ECarePatientData, ECareResponse, BaseHealthcareRequest

router = APIRouter()

@router.get("/info")
async def get_ecare_info(current_service: str = Depends(get_current_service)):
    """Get E-Care service information"""
    if current_service != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for E-Care service"
        )
    
    service = ServiceFactory.get_service("ecare")
    return service.get_service_info()

@router.get("/health")
async def ecare_health_check(current_service: str = Depends(get_current_service)):
    """E-Care service health check"""
    if current_service != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for E-Care service"
        )
    
    service = ServiceFactory.get_service("ecare")
    return await service.health_check()

@router.post("/process", response_model=ECareResponse)
async def process_ecare_request(
    request: BaseHealthcareRequest,
    current_service: str = Depends(get_current_service)
):
    """Process E-Care healthcare request"""
    if current_service != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for E-Care service"
        )
    
    service = ServiceFactory.get_service("ecare")
    return await service.process_request(request)

@router.get("/patients/{patient_id}")
async def get_patient_data(
    patient_id: str,
    current_service: str = Depends(get_current_service)
):
    """Get patient data from E-Care system"""
    if current_service != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for E-Care service"
        )
    
    service = ServiceFactory.get_service("ecare")
    patient_data = await service.get_patient_data(patient_id)
    
    if not patient_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    
    return patient_data

@router.post("/appointments/schedule")
async def schedule_appointment(
    appointment_data: Dict[str, Any],
    current_service: str = Depends(get_current_service)
):
    """Schedule an appointment through E-Care"""
    if current_service != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for E-Care service"
        )
    
    patient_id = appointment_data.get("patient_id")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Patient ID is required"
        )
    
    service = ServiceFactory.get_service("ecare")
    result = await service.schedule_appointment(patient_id, appointment_data)
    return result

@router.get("/patients/{patient_id}/appointments")
async def get_patient_appointments(
    patient_id: str,
    current_service: str = Depends(get_current_service)
):
    """Get all appointments for a patient"""
    if current_service != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This endpoint is only available for E-Care service"
        )
    
    service = ServiceFactory.get_service("ecare")
    appointments = await service.get_patient_appointments(patient_id)
    return {"patient_id": patient_id, "appointments": appointments}
