from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_service
from app.services.service_factory import ServiceFactory
from app.schemas.service import ServiceRequest, ServiceResponse

router = APIRouter()  # Removed tags

@router.post("/process", response_model=ServiceResponse)
async def process_ecare_request(
    request: ServiceRequest,
    current_service: dict = Depends(get_current_service)
):
    """
    Process a request for E-Care service
    """
    if current_service["service_name"] != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for E-Care service."
        )
    
    try:
        service = ServiceFactory.get_service("ecare")
        result = await service.process_request(request.data)
        
        return ServiceResponse(
            success=True,
            message="Request processed successfully",
            data=result
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing request: {str(e)}"
        )

@router.get("/health")
async def health_check(current_service: dict = Depends(get_current_service)):
    """
    Health check endpoint for E-Care service
    """
    if current_service["service_name"] != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for E-Care service."
        )
    
    return {"status": "healthy", "service": "ecare"}

@router.get("/info")
async def get_service_info(current_service: dict = Depends(get_current_service)):
    """
    Get information about E-Care service
    """
    if current_service["service_name"] != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for E-Care service."
        )
    
    return {
        "service_name": "ecare",
        "description": "E-Care Electronic Healthcare Management",
        "version": "1.0.0",
        "capabilities": ["patient_records", "appointments", "prescriptions"]
    }
