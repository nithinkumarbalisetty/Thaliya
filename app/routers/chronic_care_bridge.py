from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_service
from app.services.service_factory import ServiceFactory
from app.schemas.service import ServiceRequest, ServiceResponse

router = APIRouter()  # Removed tags

@router.post("/process", response_model=ServiceResponse)
async def process_chronic_care_bridge_request(
    request: ServiceRequest,
    current_service: dict = Depends(get_current_service)
):
    """
    Process a request for ChronicCareBridge service
    """
    if current_service["service_name"] != "chronic_care_bridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for ChronicCareBridge service."
        )
    
    try:
        service = ServiceFactory.get_service("chronic_care_bridge")
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
    Health check endpoint for ChronicCareBridge service
    """
    if current_service["service_name"] != "chronic_care_bridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for ChronicCareBridge service."
        )
    
    return {"status": "healthy", "service": "chronic_care_bridge"}

@router.get("/info")
async def get_service_info(current_service: dict = Depends(get_current_service)):
    """
    Get information about ChronicCareBridge service
    """
    if current_service["service_name"] != "chronic_care_bridge":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for ChronicCareBridge service."
        )
    
    return {
        "service_name": "chronic_care_bridge",
        "description": "ChronicCareBridge Disease Management System",
        "version": "1.0.0",
        "capabilities": ["care_plan", "monitoring", "medication_management"]
    }
