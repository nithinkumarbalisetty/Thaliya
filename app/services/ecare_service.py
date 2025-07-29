from typing import Dict, Any, List, Optional
import re
import json
import uuid
import logging
from datetime import datetime, timedelta
from app.services.base_service import BaseHealthcareService
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)

class ECareService(BaseHealthcareService):
    """
    E-Care service implementation for electronic healthcare management
    """
    
    def __init__(self):
        super().__init__("ecare")
        # Mock databases (in production, use actual database)
        self.conversations = {}
        self.tickets = {}
        self.appointments = {}
        
        # Initialize RAG service (production-level)
        self.rag_service = None
        self._initialize_rag_service()
        
        # Fallback knowledge base for immediate responses
        self.fallback_knowledge_base = self._initialize_fallback_knowledge_base()
        self.intent_patterns = self._initialize_intent_patterns()
        
    def _initialize_rag_service(self):
        """Initialize the production RAG service"""
        try:
            # This will be set up async in the first RAG request
            logger.info("RAG service will be initialized on first use")
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {str(e)}")
            
    def _initialize_fallback_knowledge_base(self) -> Dict[str, str]:
        """Initialize fallback knowledge base for immediate responses"""
        return {
            "office_hours": "Our office hours are Monday-Friday 8:00 AM to 6:00 PM, Saturday 9:00 AM to 2:00 PM",
            "location": "E-Care Medical Center is located at 123 Healthcare Ave, Medical District, City 12345",
            "services": "We offer primary care, preventive medicine, chronic disease management, vaccinations, and telemedicine consultations",
            "doctors": "Our physicians include Dr. Sarah Johnson (Internal Medicine), Dr. Michael Chen (Family Medicine), and Dr. Emily Rodriguez (Pediatrics)",
            "insurance": "We accept most major insurance plans including Blue Cross, Aetna, UnitedHealth, and Medicare",
            "appointments": "Appointments can be scheduled online, by phone at (555) 123-4567, or through our patient portal",
            "prescriptions": "Prescription refills can be requested through our patient portal or by calling our pharmacy line",
            "emergency": "For medical emergencies, please call 911. For urgent but non-emergency care, call our after-hours line"
        }
        
    def _initialize_knowledge_base(self) -> Dict[str, str]:
        """Initialize RAG knowledge base with website information (DEPRECATED - now using RAG service)"""
        logger.warning("Using fallback knowledge base - RAG service should be used instead")
        return self.fallback_knowledge_base
    
    def _initialize_intent_patterns(self) -> Dict[str, List[str]]:
        """Initialize intent classification patterns"""
        return {
            "appointment": [
                r"\b(book|schedule|make|create|set up|arrange)\b.*\b(appointment|visit|consultation)\b",
                r"\b(cancel|reschedule|change|modify|update)\b.*\b(appointment|visit)\b",
                r"\bwhen\b.*\bavailable\b",
                r"\bappointment\b.*\b(today|tomorrow|this week|next week)\b"
            ],
            "rag_info": [
                r"\b(hours|open|closed|schedule)\b",
                r"\b(location|address|where|directions)\b",
                r"\b(services|treatments|what do you|specialties)\b",
                r"\b(doctors|physicians|providers|staff)\b",
                r"\b(insurance|coverage|accept|plans)\b"
            ],
            "ticket": [
                r"\b(refill|prescription|medication|medicine)\b",
                r"\b(billing|bill|invoice|payment|charge)\b",
                r"\b(test results|lab|blood work|x-ray)\b",
                r"\b(referral|specialist|authorization)\b",
                r"\b(problem|issue|concern|complaint)\b"
            ],
            "general": [
                r"\b(health|medical|symptoms|condition)\b",
                r"\b(advice|recommendation|suggest|help)\b",
                r"\bwhat\b.*\b(should|can|is|are)\b",
                r"\bhow\b.*\b(to|do|can|should)\b"
            ]
        }
    
    # ========================================
    # CHATBOT CORE FUNCTIONALITY
    # ========================================
    
    async def _process_chatbot_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main chatbot request processor
        """
        user_message = data.get("message", "")
        session_id = data.get("session_id") or str(uuid.uuid4())  # Ensure we always have a session_id
        user_id = data.get("user_id", "anonymous")
        
        # Initialize conversation if new
        if session_id not in self.conversations:
            self.conversations[session_id] = {
                "id": session_id,
                "user_id": user_id,
                "messages": [],
                "created_at": datetime.now(),
                "last_activity": datetime.now()
            }
        
        # Add user message to conversation
        self.conversations[session_id]["messages"].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now()
        })
        
        # Classify intent and route to appropriate handler
        intent = self._classify_intent(user_message)
        response = await self._route_to_handler(user_message, intent, session_id, user_id)
        
        # Apply guardrails
        response = self._apply_guardrails(response, intent)
        
        # Add assistant response to conversation
        self.conversations[session_id]["messages"].append({
            "role": "assistant",
            "content": response["message"],
            "intent": intent,
            "timestamp": datetime.now()
        })
        
        return {
            "success": True,
            "session_id": session_id,
            "intent": intent,
            "message": response["message"],
            "data": response.get("data"),
            "timestamp": self._get_timestamp()
        }
    
    def _classify_intent(self, message: str) -> str:
        """
        Classify user intent using pattern matching
        """
        message_lower = message.lower()
        
        # Check each intent category
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    return intent
        
        return "general"
    
    async def _route_to_handler(self, message: str, intent: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Route message to appropriate handler based on intent
        """
        if intent == "appointment":
            return await self._handle_appointment_intent(message, session_id, user_id)
        elif intent == "rag_info":
            return await self._handle_rag_info_intent(message, session_id, user_id)
        elif intent == "ticket":
            return await self._handle_ticket_intent(message, session_id, user_id)
        else:  # general intent
            return await self._handle_general_intent(message, session_id, user_id)
    
    # ========================================
    # HANDLER 1: APPOINTMENT MANAGEMENT
    # ========================================
    
    async def _handle_appointment_intent(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Handle appointment-related requests (Future: Prognocis integration)
        """
        message_lower = message.lower()
        
        # Determine appointment action
        if any(word in message_lower for word in ["book", "schedule", "make", "create"]):
            return await self._book_appointment(message, session_id, user_id)
        elif any(word in message_lower for word in ["cancel", "delete"]):
            return await self._cancel_appointment(message, session_id, user_id)
        elif any(word in message_lower for word in ["reschedule", "change", "modify"]):
            return await self._reschedule_appointment(message, session_id, user_id)
        else:
            return await self._get_appointment_info(message, session_id, user_id)
    
    async def _book_appointment(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Book a new appointment (Mock implementation - integrate with Prognocis later)
        """
        appointment_id = str(uuid.uuid4())
        
        # Mock appointment creation
        appointment = {
            "appointment_id": appointment_id,
            "user_id": user_id,
            "doctor": "Dr. Sarah Johnson",
            "date": "2025-08-05",
            "time": "10:00 AM",
            "status": "scheduled",
            "type": "General Consultation",
            "created_at": datetime.now().isoformat()
        }
        
        self.appointments[appointment_id] = appointment
        
        return {
            "message": f"Great! I've scheduled your appointment with Dr. Sarah Johnson for August 5th at 10:00 AM. Your appointment ID is {appointment_id[:8]}. You'll receive a confirmation email shortly.",
            "data": {
                "appointment": appointment,
                "next_action": "confirmation_sent"
            }
        }
    
    async def _cancel_appointment(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Cancel an existing appointment
        """
        return {
            "message": "I can help you cancel your appointment. Could you please provide your appointment ID or the date of your scheduled appointment?",
            "data": {
                "action_required": "appointment_id_needed",
                "next_step": "provide_appointment_details"
            }
        }
    
    async def _reschedule_appointment(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Reschedule an existing appointment
        """
        return {
            "message": "I'll help you reschedule your appointment. Please provide your current appointment ID and your preferred new date/time.",
            "data": {
                "action_required": "reschedule_details_needed",
                "available_slots": ["Aug 6 - 2:00 PM", "Aug 7 - 9:00 AM", "Aug 8 - 11:00 AM"]
            }
        }
    
    async def _get_appointment_info(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get appointment information
        """
        return {
            "message": "I can help you with appointment information. You can book appointments online, call us at (555) 123-4567, or use our patient portal. Our available doctors include Dr. Sarah Johnson (Internal Medicine), Dr. Michael Chen (Family Medicine), and Dr. Emily Rodriguez (Pediatrics).",
            "data": {
                "contact_info": "(555) 123-4567",
                "booking_methods": ["online", "phone", "patient_portal"],
                "available_doctors": ["Dr. Sarah Johnson", "Dr. Michael Chen", "Dr. Emily Rodriguez"]
            }
        }
    
    # ========================================
    # HANDLER 2: RAG-BASED INFORMATION (PRODUCTION)
    # ========================================
    
    async def _handle_rag_info_intent(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Handle information requests using LangChain RAG with Azure OpenAI
        """
        try:
            # Get or initialize LangChain RAG service
            if self.rag_service is None:
                self.rag_service = await get_rag_service()
            
            # Use LangChain RAG to retrieve relevant context from .txt file
            rag_result = await self.rag_service.retrieve_relevant_context(
                query=message,
                max_context_length=2000
            )
            
            # Log RAG performance for monitoring
            logger.info(f"LangChain RAG Query: {message}")
            logger.info(f"RAG Method: {rag_result.get('method', 'unknown')}")
            logger.info(f"RAG Confidence: {rag_result['confidence']}")
            logger.info(f"Sources Found: {rag_result['num_sources']}")
            
            # Check if we have a good LangChain QA response
            if (rag_result.get('answer') and 
                rag_result['confidence'] > 0.7 and 
                rag_result.get('method') == 'langchain_qa'):
                
                # Use the LangChain-generated answer directly
                response_message = rag_result['answer']
                
                # Add source attribution
                if rag_result['sources']:
                    response_message += "\n\n📚 Information from our medical center knowledge base."
                
                return {
                    "message": response_message,
                    "data": {
                        "source": "langchain_azure_openai",
                        "confidence": rag_result["confidence"],
                        "num_sources": rag_result["num_sources"],
                        "sources": rag_result["sources"],
                        "type": "langchain_qa_response",
                        "timestamp": rag_result["timestamp"],
                        "method": rag_result.get('method')
                    }
                }
            
            # If we have context but no LLM answer, use template-based response
            elif rag_result["context"] and rag_result["confidence"] > 0.5:
                response_message = self._generate_template_response_from_context(message, rag_result)
                
                return {
                    "message": response_message,
                    "data": {
                        "source": "langchain_context",
                        "confidence": rag_result["confidence"],
                        "num_sources": rag_result["num_sources"],
                        "sources": rag_result["sources"],
                        "type": "context_template_response",
                        "timestamp": rag_result["timestamp"],
                        "method": rag_result.get('method')
                    }
                }
            
            else:
                # Low confidence or no context - use basic fallback
                logger.warning(f"Low RAG confidence ({rag_result['confidence']}) for query: {message}")
                return await self._handle_basic_fallback(message, session_id, user_id)
                
        except Exception as e:
            logger.error(f"LangChain RAG service error: {str(e)}")
            # Fallback to basic responses
            return await self._handle_basic_fallback(message, session_id, user_id)
    
    def _generate_template_response_from_context(self, query: str, rag_result: Dict[str, Any]) -> str:
        """
        Generate response using context from LangChain document retrieval
        """
        context = rag_result["context"]
        query_lower = query.lower()
        
        # Limit context length for readability
        max_context_preview = 500
        context_preview = context[:max_context_preview] + "..." if len(context) > max_context_preview else context
        
        # Generate response based on query intent and retrieved context
        if any(word in query_lower for word in ["hours", "open", "time", "when", "schedule"]):
            if any(hour_word in context.lower() for hour_word in ["monday", "tuesday", "hours", "open", "am", "pm"]):
                return f"Here are our office hours based on our latest information:\n\n{context_preview}\n\nFor appointment scheduling, please call (555) 123-4567."
            else:
                return f"Based on our information:\n\n{context_preview}\n\nFor current hours and scheduling, please call (555) 123-4567."
        
        elif any(word in query_lower for word in ["location", "address", "where", "directions", "find"]):
            return f"Our location and contact information:\n\n{context_preview}\n\nFor detailed directions, please call (555) 123-4567."
        
        elif any(word in query_lower for word in ["services", "treatment", "procedure", "medical", "care", "offer"]):
            return f"Our medical services include:\n\n{context_preview}\n\nFor detailed information about specific services or to schedule a consultation, please call (555) 123-4567."
        
        elif any(word in query_lower for word in ["doctor", "doctors", "physician", "staff", "provider", "dr"]):
            return f"Our medical team:\n\n{context_preview}\n\nTo schedule with a specific provider or learn more about our physicians, call (555) 123-4567."
        
        elif any(word in query_lower for word in ["insurance", "payment", "billing", "coverage", "accept", "cost"]):
            return f"Insurance and billing information:\n\n{context_preview}\n\nFor insurance verification and billing questions, please call (555) 123-4567."
        
        elif any(word in query_lower for word in ["appointment", "book", "reserve", "visit"]):
            return f"Appointment information:\n\n{context_preview}\n\nTo schedule an appointment, call (555) 123-4567 or use our online patient portal."
        
        elif any(word in query_lower for word in ["contact", "phone", "call", "reach"]):
            return f"Contact information:\n\n{context_preview}\n\nOur main number is (555) 123-4567."
        
        else:
            # General information response
            return f"Based on our medical center information:\n\n{context_preview}\n\nFor more specific information, please contact our office at (555) 123-4567."
    
    async def _handle_basic_fallback(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Basic fallback when LangChain RAG system is not available or confident
        """
        message_lower = message.lower()
        
        # Basic pattern matching for common queries
        if any(word in message_lower for word in ["hours", "open", "time", "when"]):
            response = "I apologize, but I'm having trouble accessing our current hours information. Please call our office at (555) 123-4567 for the most up-to-date hours."
        
        elif any(word in message_lower for word in ["location", "address", "where", "directions"]):
            response = "For our current location and address information, please call our office at (555) 123-4567."
        
        elif any(word in message_lower for word in ["services", "treatment", "medical", "care"]):
            response = "For information about our medical services and treatments, please call (555) 123-4567 to speak with our staff."
        
        elif any(word in message_lower for word in ["appointment", "schedule", "book"]):
            response = "To schedule an appointment, please call our office at (555) 123-4567. Our scheduling staff will be happy to help you."
        
        elif any(word in message_lower for word in ["doctor", "physician", "staff"]):
            response = "For information about our physicians and medical staff, please call (555) 123-4567."
        
        elif any(word in message_lower for word in ["insurance", "billing", "payment"]):
            response = "For insurance and billing questions, please call our office at (555) 123-4567."
        
        else:
            response = "I'm sorry, I'm having trouble accessing that information right now. Please call our office at (555) 123-4567 for assistance with your question."
        
        return {
            "message": response,
            "data": {
                "source": "basic_fallback",
                "confidence": 0.3,
                "type": "fallback_response",
                "contact_info": "(555) 123-4567"
            }
        }
    
    async def _generate_rag_response(self, query: str, rag_result: Dict[str, Any]) -> str:
        """
        Generate a natural response based on RAG context
        """
        context = rag_result["context"]
        confidence = rag_result["confidence"]
        
        # Extract key information based on query type
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["hours", "open", "time", "when"]):
            return self._extract_hours_info(context)
        elif any(word in query_lower for word in ["location", "address", "where", "directions"]):
            return self._extract_location_info(context)
        elif any(word in query_lower for word in ["services", "treatment", "what do you", "offer"]):
            return self._extract_services_info(context)
        elif any(word in query_lower for word in ["doctors", "physician", "staff", "who"]):
            return self._extract_doctors_info(context)
        elif any(word in query_lower for word in ["insurance", "coverage", "accept", "plans"]):
            return self._extract_insurance_info(context)
        elif any(word in query_lower for word in ["appointment", "schedule", "book"]):
            return self._extract_appointment_info(context)
        else:
            # General response with context summary
            context_summary = context[:400] + "..." if len(context) > 400 else context
            return f"Based on our information: {context_summary}\n\nFor more specific details, please contact our office at (555) 123-4567."
    
    def _extract_hours_info(self, context: str) -> str:
        """Extract office hours information from context"""
        lines = context.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ["hours", "monday", "friday", "saturday", "open"]):
                return f"Our office hours are: {line.strip()}"
        return "Our office hours are Monday-Friday 8:00 AM to 6:00 PM, Saturday 9:00 AM to 2:00 PM. We're closed on Sundays and major holidays."
    
    def _extract_location_info(self, context: str) -> str:
        """Extract location information from context"""
        lines = context.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ["located", "address", "avenue", "street"]):
                return f"E-Care Medical Center is {line.strip()}"
        return "We're located at 123 Healthcare Avenue, Medical District, City 12345. Free parking is available on-site."
    
    def _extract_services_info(self, context: str) -> str:
        """Extract services information from context"""
        lines = context.split('\n')
        service_lines = []
        for line in lines:
            if any(word in line.lower() for word in ["care", "medicine", "service", "treatment", "health"]):
                service_lines.append(line.strip())
        
        if service_lines:
            return f"We offer comprehensive medical services including: {' '.join(service_lines[:3])}"
        return "We offer primary care, preventive medicine, chronic disease management, vaccinations, and telemedicine consultations."
    
    def _extract_doctors_info(self, context: str) -> str:
        """Extract doctors information from context"""
        lines = context.split('\n')
        doctor_lines = []
        for line in lines:
            if any(word in line.lower() for word in ["dr.", "doctor", "physician", "md", "np", "pa"]):
                doctor_lines.append(line.strip())
        
        if doctor_lines:
            return f"Our medical team includes: {' '.join(doctor_lines[:3])}"
        return "Our physicians include Dr. Sarah Johnson (Internal Medicine), Dr. Michael Chen (Family Medicine), and Dr. Emily Rodriguez (Pediatrics)."
    
    def _extract_insurance_info(self, context: str) -> str:
        """Extract insurance information from context"""
        lines = context.split('\n')
        insurance_lines = []
        for line in lines:
            if any(word in line.lower() for word in ["insurance", "blue cross", "aetna", "medicare", "accept"]):
                insurance_lines.append(line.strip())
        
        if insurance_lines:
            return f"Insurance information: {' '.join(insurance_lines[:2])}"
        return "We accept most major insurance plans including Blue Cross, Aetna, UnitedHealthcare, and Medicare. Please contact our billing department to verify your specific plan."
    
    def _extract_appointment_info(self, context: str) -> str:
        """Extract appointment information from context"""
        lines = context.split('\n')
        for line in lines:
            if any(word in line.lower() for word in ["appointment", "schedule", "portal", "phone"]):
                return f"Appointment scheduling: {line.strip()}"
        return "You can schedule appointments online through our patient portal, by calling (555) 123-4567, or using our mobile app."
    
    async def _handle_rag_fallback(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Fallback RAG handler using simple keyword matching
        """
        # Find most relevant information from fallback knowledge base
        relevant_info = self._retrieve_relevant_info_fallback(message)
        
        if relevant_info:
            return {
                "message": relevant_info["answer"],
                "data": {
                    "source": "fallback_kb",
                    "confidence": relevant_info["confidence"],
                    "type": "fallback_response"
                }
            }
        else:
            return {
                "message": "I don't have specific information about that. Please contact our office at (555) 123-4567 for more details, or check our website for comprehensive information.",
                "data": {
                    "type": "no_match_response",
                    "contact_info": "(555) 123-4567"
                }
            }
    
    def _retrieve_relevant_info_fallback(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Simple keyword-based retrieval fallback (when RAG service is unavailable)
        """
        query_lower = query.lower()
        
        # Keyword matching with fallback knowledge base
        for key, info in self.fallback_knowledge_base.items():
            if any(keyword in query_lower for keyword in key.split('_')):
                return {
                    "answer": info,
                    "source": key,
                    "confidence": 0.8
                }
        
        # Extended keyword matching
        keyword_mappings = {
            "hours": "office_hours",
            "address": "location", 
            "phone": "appointments",
            "cost": "insurance",
            "price": "insurance",
            "when": "office_hours",
            "where": "location",
            "who": "doctors"
        }
        
        for keyword, kb_key in keyword_mappings.items():
            if keyword in query_lower and kb_key in self.fallback_knowledge_base:
                return {
                    "answer": self.fallback_knowledge_base[kb_key],
                    "source": kb_key,
                    "confidence": 0.7
                }
        
        return None
    
    # ========================================
    # HANDLER 3: TICKET CREATION SYSTEM
    # ========================================
    
    async def _handle_ticket_intent(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Handle ticket creation for medication refills, billing, etc.
        """
        # Determine ticket category
        category = self._categorize_ticket(message)
        
        # Create ticket
        ticket = await self._create_ticket(message, category, session_id, user_id)
        
        return {
            "message": f"I've created a ticket for your {category} request. Your ticket ID is {ticket['ticket_id'][:8]}. Our team will review and respond within 24 hours. Is there anything else I can help you with?",
            "data": {
                "ticket": ticket,
                "estimated_response_time": "24 hours",
                "category": category
            }
        }
    
    def _categorize_ticket(self, message: str) -> str:
        """
        Categorize ticket based on message content
        """
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["refill", "prescription", "medication", "medicine"]):
            return "prescription_refill"
        elif any(word in message_lower for word in ["billing", "bill", "payment", "charge", "invoice"]):
            return "billing_inquiry"
        elif any(word in message_lower for word in ["test", "lab", "blood", "x-ray", "results"]):
            return "test_results"
        elif any(word in message_lower for word in ["referral", "specialist", "authorization"]):
            return "referral_request"
        else:
            return "general_inquiry"
    
    async def _create_ticket(self, message: str, category: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Create a new support ticket
        """
        ticket_id = str(uuid.uuid4())
        
        ticket = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "session_id": session_id,
            "category": category,
            "subject": f"{category.replace('_', ' ').title()} Request",
            "description": message,
            "status": "open",
            "priority": self._determine_priority(category),
            "assigned_to": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.tickets[ticket_id] = ticket
        
        return ticket
    
    def _determine_priority(self, category: str) -> str:
        """
        Determine ticket priority based on category
        """
        priority_mapping = {
            "prescription_refill": "high",
            "test_results": "high", 
            "billing_inquiry": "medium",
            "referral_request": "medium",
            "general_inquiry": "low"
        }
        return priority_mapping.get(category, "low")
    
    # ========================================
    # HANDLER 4: GENERAL GPT RESPONSES
    # ========================================
    
    async def _handle_general_intent(self, message: str, session_id: str, user_id: str) -> Dict[str, Any]:
        """
        Handle general health questions using GPT-like responses with guardrails
        """
        # Mock GPT response (integrate with OpenAI API later)
        response = self._generate_general_response(message)
        
        return {
            "message": response,
            "data": {
                "type": "general_response",
                "disclaimer": "This is general information only. Please consult with your healthcare provider for medical advice.",
                "source": "ai_assistant"
            }
        }
    
    def _generate_general_response(self, message: str) -> str:
        """
        Generate general health responses (Mock implementation)
        """
        message_lower = message.lower()
        
        # Common health topics with safe responses
        if any(word in message_lower for word in ["headache", "head hurt"]):
            return "Headaches can have various causes including stress, dehydration, or tension. Try rest, hydration, and over-the-counter pain relief if appropriate. If headaches persist or are severe, please consult your healthcare provider."
        
        elif any(word in message_lower for word in ["fever", "temperature"]):
            return "A fever is your body's natural response to infection. Stay hydrated, rest, and monitor your temperature. Contact your healthcare provider if fever exceeds 103°F (39.4°C) or persists for more than 3 days."
        
        elif any(word in message_lower for word in ["cold", "cough", "runny nose"]):
            return "Common cold symptoms typically resolve in 7-10 days. Rest, fluids, and over-the-counter medications can help manage symptoms. Seek medical attention if symptoms worsen or you develop difficulty breathing."
        
        else:
            return "I understand you have a health question. While I can provide general information, it's important to consult with your healthcare provider for personalized medical advice. You can schedule an appointment through our patient portal or call (555) 123-4567."
    
    # ========================================
    # GUARDRAILS AND SAFETY
    # ========================================
    
    def _apply_guardrails(self, response: Dict[str, Any], intent: str) -> Dict[str, Any]:
        """
        Apply safety guardrails to responses
        """
        message = response.get("message", "")
        
        # Medical disclaimer for health-related responses
        if intent == "general" and any(word in message.lower() for word in ["pain", "symptom", "treatment", "medication"]):
            message += "\n\n⚠️ **Medical Disclaimer**: This information is for educational purposes only and should not replace professional medical advice. Please consult your healthcare provider for medical concerns."
        
        # Content filtering
        message = self._filter_sensitive_content(message)
        
        # Length limiting
        if len(message) > 1000:
            message = message[:997] + "..."
        
        response["message"] = message
        return response
    
    def _filter_sensitive_content(self, message: str) -> str:
        """
        Filter out sensitive or inappropriate content
        """
        # Basic content filtering (enhance with more sophisticated filtering)
        sensitive_patterns = [
            r'\b(password|ssn|social security)\b',
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN pattern
            r'\b\d{16}\b'  # Credit card pattern
        ]
        
        for pattern in sensitive_patterns:
            message = re.sub(pattern, "[REDACTED]", message, flags=re.IGNORECASE)
        
        return message
    
    # ========================================
    # UTILITY METHODS
    # ========================================
    
    def get_conversation_history(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get conversation history for a session
        """
        return self.conversations.get(session_id)
    
    def get_user_tickets(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all tickets for a user
        """
        return [ticket for ticket in self.tickets.values() if ticket["user_id"] == user_id]
    
    def get_user_appointments(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all appointments for a user
        """
        return [apt for apt in self.appointments.values() if apt["user_id"] == user_id]
    
    async def _process_patient_records(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process patient records requests
        """
        return {
            "service": "ecare",
            "type": "patient_records",
            "records": {
                "patient_id": data.get("patient_id", "P12345"),
                "status": "active",
                "last_visit": "2025-07-20",
                "next_appointment": "2025-08-05"
            },
            "timestamp": self._get_timestamp(),
            "processed_data": data
        }
    
    async def _process_appointments(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process appointment requests
        """
        return {
            "service": "ecare",
            "type": "appointments",
            "appointment": {
                "appointment_id": "APT001",
                "doctor": "Dr. Johnson",
                "date": "2025-08-05",
                "time": "10:00 AM",
                "status": "scheduled"
            },
            "timestamp": self._get_timestamp(),
            "processed_data": data
        }
    
    async def _process_prescriptions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process prescription requests
        """
        return {
            "service": "ecare",
            "type": "prescriptions",
            "prescription": {
                "prescription_id": "RX001",
                "medication": "Lisinopril 10mg",
                "dosage": "Once daily",
                "refills": 3,
                "status": "active"
            },
            "timestamp": self._get_timestamp(),
            "processed_data": data
        }
    
    # ========================================
    # LEGACY METHODS (Backward Compatibility)
    # ========================================
    
    async def _process_patient_records(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process patient records requests (Legacy)
        """
        return {
            "service": "ecare",
            "type": "patient_records",
            "records": {
                "patient_id": data.get("patient_id", "P12345"),
                "status": "active",
                "last_visit": "2025-07-20",
                "next_appointment": "2025-08-05"
            },
            "timestamp": self._get_timestamp(),
            "processed_data": data
        }
    
    async def _process_appointments(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process appointment requests (Legacy)
        """
        return {
            "service": "ecare",
            "type": "appointments",
            "appointments": {
                "upcoming": [
                    {
                        "id": "A001",
                        "date": "2025-08-05",
                        "time": "10:00 AM",
                        "doctor": "Dr. Sarah Johnson",
                        "type": "General Consultation"
                    }
                ],
                "available_slots": [
                    "2025-08-06 2:00 PM",
                    "2025-08-07 9:00 AM",
                    "2025-08-08 11:00 AM"
                ]
            },
            "timestamp": self._get_timestamp(),
            "processed_data": data
        }
    
    async def _process_prescriptions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process prescription requests (Legacy)
        """
        return {
            "service": "ecare",
            "type": "prescriptions",
            "prescriptions": {
                "active": [
                    {
                        "medication": "Lisinopril 10mg",
                        "dosage": "Once daily",
                        "refills_remaining": 2,
                        "pharmacy": "Main Street Pharmacy"
                    }
                ],
                "refill_requests": "Available through patient portal"
            },
            "timestamp": self._get_timestamp(),
            "processed_data": data
        }
    
    async def _process_general_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process general requests (Legacy)
        """
        return {
            "service": "ecare",
            "type": "general",
            "message": "Request processed by E-Care service",
            "timestamp": self._get_timestamp(),
            "processed_data": data
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Health check for E-Care service including RAG system
        """
        base_health = {
            "service": "ecare",
            "status": "healthy",
            "uptime": "99.8%",
            "last_check": self._get_timestamp(),
            "chatbot_status": "operational",
            "active_conversations": len(self.conversations),
            "open_tickets": len([t for t in self.tickets.values() if t["status"] == "open"])
        }
        
        # Check RAG service health
        try:
            if self.rag_service is None:
                self.rag_service = await get_rag_service()
            
            rag_stats = await self.rag_service.get_system_stats()
            base_health["rag_service"] = {
                "status": "operational" if rag_stats["system_initialized"] else "initializing",
                "embeddings_model": rag_stats["embeddings_model"],
                "vector_store_size": rag_stats.get("vector_store_size", 0),
                "similarity_threshold": rag_stats["similarity_threshold"]
            }
        except Exception as e:
            base_health["rag_service"] = {
                "status": "fallback_mode",
                "error": str(e),
                "fallback_kb_size": len(self.fallback_knowledge_base)
            }
        
        return base_health
