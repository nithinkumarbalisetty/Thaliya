from typing import Dict, Any, Optional
from pydantic import BaseModel

class ServiceRequest(BaseModel):
    """Base request model for service operations"""
    data: Dict[str, Any]
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ServiceResponse(BaseModel):
    """Base response model for service operations"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class ClientCredentials(BaseModel):
    """Client credentials for authentication"""
    client_id: str
    client_secret: str

class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    service_name: str

# ========================================
# CHATBOT SCHEMAS
# ========================================

class ChatbotRequest(BaseModel):
    """Chatbot request model"""
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = "anonymous"

class ChatbotResponse(BaseModel):
    """Chatbot response model"""
    success: bool
    session_id: str
    intent: str
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str

class TicketRequest(BaseModel):
    """Ticket creation request"""
    category: str
    subject: str
    description: str
    user_id: str
    priority: Optional[str] = "medium"

class TicketResponse(BaseModel):
    """Ticket creation response"""
    ticket_id: str
    status: str
    category: str
    estimated_response_time: str
    created_at: str

class AppointmentRequest(BaseModel):
    """Appointment booking request"""
    patient_id: str
    doctor_preference: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    appointment_type: Optional[str] = "General Consultation"

class AppointmentResponse(BaseModel):
    """Appointment booking response"""
    appointment_id: str
    doctor: str
    date: str
    time: str
    status: str
    confirmation_sent: bool