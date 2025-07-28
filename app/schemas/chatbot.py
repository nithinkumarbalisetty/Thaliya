from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

# ===============================
# CHAT MESSAGE SCHEMAS
# ===============================

class ChatMessage(BaseModel):
    """Individual chat message"""
    role: Literal["user", "assistant"] = Field(..., description="Message sender role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    intent: Optional[str] = Field(None, description="Classified intent")
    confidence: Optional[float] = Field(None, description="Intent confidence score")

class ChatRequest(BaseModel):
    """Request to send a message to chatbot"""
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")

class ChatResponse(BaseModel):
    """Response from chatbot"""
    message: str = Field(..., description="Chatbot response")
    intent: str = Field(..., description="Detected intent")
    confidence: float = Field(..., description="Intent confidence score")
    handler_used: str = Field(..., description="Handler that processed the request")
    session_id: str = Field(..., description="Session identifier")
    suggestions: Optional[List[str]] = Field(None, description="Suggested follow-up actions")
    requires_action: bool = Field(False, description="Whether user action is required")
    action_type: Optional[str] = Field(None, description="Type of action needed")

# ===============================
# APPOINTMENT SCHEMAS
# ===============================

class AppointmentRequest(BaseModel):
    """Request to book/manage appointments"""
    action: Literal["book", "update", "cancel", "reschedule"] = Field(..., description="Appointment action")
    patient_id: Optional[str] = Field(None, description="Patient identifier")
    doctor_name: Optional[str] = Field(None, description="Preferred doctor")
    specialty: Optional[str] = Field(None, description="Medical specialty")
    preferred_date: Optional[str] = Field(None, description="Preferred appointment date")
    preferred_time: Optional[str] = Field(None, description="Preferred appointment time")
    appointment_id: Optional[str] = Field(None, description="Existing appointment ID for updates/cancellations")
    reason: Optional[str] = Field(None, description="Reason for appointment")

class AppointmentResponse(BaseModel):
    """Response for appointment operations"""
    success: bool = Field(..., description="Operation success status")
    appointment_id: Optional[str] = Field(None, description="Appointment identifier")
    confirmation_number: Optional[str] = Field(None, description="Confirmation number")
    scheduled_date: Optional[str] = Field(None, description="Scheduled date")
    scheduled_time: Optional[str] = Field(None, description="Scheduled time")
    doctor_name: Optional[str] = Field(None, description="Assigned doctor")
    message: str = Field(..., description="Response message")
    next_steps: Optional[List[str]] = Field(None, description="Next steps for patient")

# ===============================
# TICKET SCHEMAS
# ===============================

class TicketRequest(BaseModel):
    """Request to create a support ticket"""
    category: Literal["medication_refill", "billing", "insurance", "medical_records", "general"] = Field(..., description="Ticket category")
    subject: str = Field(..., description="Ticket subject")
    description: str = Field(..., description="Detailed description")
    priority: Literal["low", "medium", "high", "urgent"] = Field(default="medium", description="Ticket priority")
    patient_id: Optional[str] = Field(None, description="Patient identifier")
    contact_method: Literal["email", "phone", "portal"] = Field(default="portal", description="Preferred contact method")

class TicketResponse(BaseModel):
    """Response for ticket creation"""
    success: bool = Field(..., description="Ticket creation success")
    ticket_id: str = Field(..., description="Generated ticket ID")
    estimated_response_time: str = Field(..., description="Estimated response time")
    message: str = Field(..., description="Confirmation message")
    tracking_info: Dict[str, Any] = Field(default_factory=dict, description="Ticket tracking information")

# ===============================
# RAG SCHEMAS
# ===============================

class RAGQuery(BaseModel):
    """Query for RAG-based information retrieval"""
    question: str = Field(..., description="User question")
    context_type: Literal["general", "services", "policies", "doctors", "locations"] = Field(default="general", description="Context type")
    max_results: int = Field(default=5, description="Maximum number of context results")

class RAGResponse(BaseModel):
    """Response from RAG system"""
    answer: str = Field(..., description="Generated answer")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source documents used")
    confidence: float = Field(..., description="Answer confidence score")
    context_used: List[str] = Field(default_factory=list, description="Context snippets used")

# ===============================
# CONVERSATION SCHEMAS
# ===============================

class ConversationSummary(BaseModel):
    """Summary of conversation"""
    session_id: str = Field(..., description="Session identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    message_count: int = Field(..., description="Number of messages")
    intents_detected: List[str] = Field(..., description="All intents detected in conversation")
    actions_taken: List[str] = Field(default_factory=list, description="Actions performed")
    created_at: datetime = Field(..., description="Conversation start time")
    updated_at: datetime = Field(..., description="Last message time")

class ConversationHistory(BaseModel):
    """Full conversation history"""
    conversation: ConversationSummary = Field(..., description="Conversation metadata")
    messages: List[ChatMessage] = Field(..., description="All messages in conversation")

# ===============================
# INTENT CLASSIFICATION SCHEMAS
# ===============================

class IntentPrediction(BaseModel):
    """Intent classification result"""
    intent: str = Field(..., description="Predicted intent")
    confidence: float = Field(..., description="Confidence score (0-1)")
    alternatives: List[Dict[str, float]] = Field(default_factory=list, description="Alternative intents with scores")

class IntentContext(BaseModel):
    """Context for intent classification"""
    message: str = Field(..., description="User message")
    conversation_history: List[ChatMessage] = Field(default_factory=list, description="Recent conversation history")
    user_profile: Optional[Dict[str, Any]] = Field(None, description="User profile information")

# ===============================
# GUARDRAILS SCHEMAS
# ===============================

class GuardrailCheck(BaseModel):
    """Result of guardrail validation"""
    passed: bool = Field(..., description="Whether content passed guardrails")
    violations: List[str] = Field(default_factory=list, description="List of violations found")
    severity: Literal["low", "medium", "high"] = Field(default="low", description="Severity of violations")
    filtered_content: Optional[str] = Field(None, description="Content after filtering")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for user")

# ===============================
# ERROR SCHEMAS
# ===============================

class ChatbotError(BaseModel):
    """Chatbot error response"""
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    error_type: Literal["validation", "processing", "external_api", "rate_limit"] = Field(..., description="Error type")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions to resolve error")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")
