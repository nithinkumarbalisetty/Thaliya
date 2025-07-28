from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_service
from app.services.service_factory import ServiceFactory
from app.schemas.service import (
    ServiceRequest, ServiceResponse, ChatbotRequest, ChatbotResponse
)

router = APIRouter(tags=["ecare"])

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
        "description": "E-Care Electronic Healthcare Management with AI Chatbot",
        "version": "1.0.0",
        "capabilities": ["patient_records", "appointments", "prescriptions", "chatbot", "tickets", "rag_info"]
    }

# ========================================
# CHATBOT ENDPOINTS
# ========================================

@router.post("/chatbot", response_model=ChatbotResponse)
async def chatbot_chat(
    request: ChatbotRequest,
    current_service: dict = Depends(get_current_service)
):
    """
    E-Care Chatbot endpoint for conversational AI
    Handles: Appointments, RAG info, Tickets, General Q&A
    """
    if current_service["service_name"] != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for E-Care service."
        )
    
    try:
        service = ServiceFactory.get_service("ecare")
        
        # Prepare chatbot request data
        chatbot_data = {
            "request_type": "chatbot",
            "message": request.message,
            "session_id": request.session_id,
            "user_id": request.user_id
        }
        
        result = await service.process_request(chatbot_data)
        
        return ChatbotResponse(
            success=result["success"],
            session_id=result["session_id"],
            intent=result["intent"],
            message=result["message"],
            data=result.get("data"),
            timestamp=result["timestamp"]
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chatbot error: {str(e)}"
        )

@router.get("/chatbot/conversation/{session_id}")
async def get_conversation_history(
    session_id: str,
    current_service: dict = Depends(get_current_service)
):
    """
    Get conversation history for a specific session
    """
    if current_service["service_name"] != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for E-Care service."
        )
    
    try:
        service = ServiceFactory.get_service("ecare")
        conversation = service.get_conversation_history(session_id)
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        return {
            "session_id": session_id,
            "conversation": conversation,
            "message_count": len(conversation.get("messages", []))
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving conversation: {str(e)}"
        )

@router.get("/tickets/user/{user_id}")
async def get_user_tickets(
    user_id: str,
    current_service: dict = Depends(get_current_service)
):
    """
    Get all tickets for a specific user
    """
    if current_service["service_name"] != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for E-Care service."
        )
    
    try:
        service = ServiceFactory.get_service("ecare")
        tickets = service.get_user_tickets(user_id)
        
        return {
            "user_id": user_id,
            "tickets": tickets,
            "total_tickets": len(tickets),
            "open_tickets": len([t for t in tickets if t["status"] == "open"])
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving tickets: {str(e)}"
        )

@router.get("/appointments/user/{user_id}")
async def get_user_appointments(
    user_id: str,
    current_service: dict = Depends(get_current_service)
):
    """
    Get all appointments for a specific user
    """
    if current_service["service_name"] != "ecare":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for E-Care service."
        )
    
    try:
        service = ServiceFactory.get_service("ecare")
        appointments = service.get_user_appointments(user_id)
        
        return {
            "user_id": user_id,
            "appointments": appointments,
            "total_appointments": len(appointments),
            "upcoming_appointments": len([a for a in appointments if a["status"] == "scheduled"])
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving appointments: {str(e)}"
        )
