from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from app.core.auth import get_current_service
from app.services.service_factory import ServiceFactory
from app.schemas.service import ChatbotRequest, ChatbotResponse
import uuid
from datetime import datetime
from app.core.database import db

router = APIRouter()  # Removed tags

class ChatRequest(BaseModel):
    user_query: str
    session_token: str  # Remove default None, make it required

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

@router.post("/chatbot/guest/session")
async def create_guest_session():
    """
    Create a new guest session token for anonymous users
    """
    session_token = str(uuid.uuid4())
    
    # Optionally store session creation in database
    await db.execute(
        """
        INSERT INTO guest_sessions (session_id, created_at, status)
        VALUES ($1, $2, $3)
        """,
        session_token, datetime.utcnow(), "active"
    )
    
    return {
        "success": True,
        "session_token": session_token,
        "expires_in": 3600,  # 1 hour
        "message": "Guest session created successfully"
    }

@router.post("/chatbot/guest")
async def chatbot_chat_guest(request: ChatRequest):
    """
    Chatbot endpoint for guest users (session_token required)
    """
    if not request.session_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_token is required. Call /chatbot/guest/session first."
        )
    
    ecare_service = ServiceFactory.get_service("ecare")
    response = await ecare_service.process_guest_chat(
        user_query=request.user_query,
        session_token=request.session_token
    )
    return response

@router.post("/chatbot", response_model=ChatbotResponse)
async def chatbot_chat(
    request: ChatbotRequest,
    current_service: dict = Depends(get_current_service)
):
    """
    E-Care Chatbot endpoint for authenticated users (JWT required).
    Handles: Appointments, RAG info, Tickets, General Q&A
    """
    if current_service["service_name"] != "ecare":
        print(current_service["service_name"])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This endpoint is only for E-Care service."
        )
    try:
        service = ServiceFactory.get_service("ecare")
        result = await service.process_chat(request.dict())
        return ChatbotResponse(**result)
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
