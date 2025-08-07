"""
Chat processing handler for E-Care service
Handles intent classification, RAG queries, and authenticated chat flows
"""

import uuid
from typing import Dict, Any
from datetime import datetime
from app.services.rag_service import get_rag_service
from app.chatbot.core.intent_classifier import AIIntentClassifier
from app.core.database import db
from .session_manager import ECareSessionManager
from .parsers import ECareDataParsers


class ECareChatHandler:
    """Handles chat processing and responses"""

    def __init__(self):
        self.session_manager = ECareSessionManager()
        self.parsers = ECareDataParsers()
        self.rag_service = None
        self.intent_classifier = None

    async def _get_intent_classifier(self):
        """Get or initialize the AI intent classifier"""
        if self.intent_classifier is None:
            self.intent_classifier = AIIntentClassifier()
            await self.intent_classifier._ensure_initialized()
        return self.intent_classifier

    async def classify_intent_ai(self, user_query: str) -> str:
        """AI-powered intent classification using Azure OpenAI"""
        try:
            classifier = await self._get_intent_classifier()
            result = await classifier.classify_intent(user_query)
            return result.get("intent", "general")
        except Exception as e:
            # Fallback to simple classification if AI fails
            print(f"AI intent classification failed: {e}")
            return self._classify_intent_simple(user_query)

    def _classify_intent_simple(self, user_query: str) -> str:
        """Simple keyword-based intent classification (fallback)"""
        user_query_lower = user_query.lower()
        
        if any(word in user_query_lower for word in ['appointment', 'book', 'schedule', 'visit']):
            return "appointment"
        elif any(word in user_query_lower for word in ['ticket', 'issue', 'problem', 'help', 'refill', 'prescription']):
            return "ticket"
        elif any(word in user_query_lower for word in ['hours', 'location', 'address', 'services', 'doctors', 'insurance']):
            return "rag_info"
        else:
            return "general"

    async def handle_regular_chat(self, user_query: str, session_token: str) -> Dict[str, Any]:
        """Handle regular chat and trigger auth if needed"""
        intent = await self.classify_intent_ai(user_query)
        
        if intent == "rag_info":
            # No auth needed - serve immediately
            if self.rag_service is None:
                self.rag_service = await get_rag_service()
            
            try:
                rag_result = await self.rag_service.retrieve_relevant_context(
                    query=user_query, max_context_length=2000
                )
                bot_response = rag_result.get("answer", "Sorry, I couldn't find relevant information.")
            except Exception as e:
                print(f"RAG service error: {e}")
                # Fallback response for general healthcare questions
                bot_response = self._get_fallback_response(user_query)
            
            await self.session_manager.store_chat_history(
                session_token, user_query, bot_response, "general", intent
            )
            
            return {
                "success": True,
                "intent": "rag_response",
                "output": bot_response,
                "session_token": session_token
            }
        
        elif intent in ["appointment", "ticket"]:
            # Auth required - store original intent and start auth flow
            await self.session_manager.store_auth_temp_data(session_token, intent, user_query)
            
            bot_response = (
                f"I understand you want to {intent.replace('_', ' ')}. "
                "To proceed, I'll need to verify your identity first. "
                "Please provide your first name and last name."
            )
            
            await self.session_manager.update_session_status(session_token, "awaiting_auth_details")
            await self.session_manager.store_chat_history(
                session_token, user_query, bot_response, "awaiting_auth_details", intent
            )
            
            return {
                "success": True,
                "intent": "awaiting_auth",
                "output": bot_response,
                "session_token": session_token,
                "requires_auth": True,
                "original_intent": intent
            }
        
        else:
            # General chat
            bot_response = "Sorry, I can not answer that! I can help you with other things."
            await self.session_manager.store_chat_history(
                session_token, user_query, bot_response, "general", intent
            )
            
            return {
                "success": True,
                "intent": "general",
                "output": bot_response,
                "session_token": session_token
            }

    async def handle_authenticated_flow(self, user_query: str, session_token: str, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat for already authenticated users"""
        # Get user info from authenticated_user_sessions
        auth_session = await self.session_manager.get_authenticated_session(session_token)
        
        if not auth_session:
            # Session expired, restart auth
            await self.session_manager.update_session_status(session_token, "active")
            return await self.handle_regular_chat(user_query, session_token)
        
        user_id = auth_session["user_id"]
        intent = await self.classify_intent_ai(user_query)
        
        # Now handle as authenticated user
        if intent == "rag_info":
            return await self._handle_rag_query(user_query, session_token, user_id)
        elif intent == "appointment":
            return await self._handle_appointment_booking(user_query, session_token, user_id)
        elif intent == "ticket":
            return await self._handle_ticket_creation(user_query, session_token, user_id)
        else:
            return await self._handle_general_authenticated(user_query, session_token, user_id)

    async def _handle_rag_query(self, user_query: str, session_token: str, user_id: int) -> Dict[str, Any]:
        """Handle RAG information queries"""
        if self.rag_service is None:
            self.rag_service = await get_rag_service()
        
        rag_result = await self.rag_service.retrieve_relevant_context(
            query=user_query, max_context_length=2000
        )
        bot_response = rag_result.get("answer", "Sorry, I couldn't find relevant information.")
        
        await self.session_manager.store_chat_history(
            session_token, user_query, bot_response, "authenticated", "rag_info"
        )
        
        return {
            "success": True,
            "intent": "rag_response",
            "output": bot_response,
            "session_token": session_token,
            "user_id": user_id,
            "authenticated": True
        }

    async def _handle_appointment_booking(self, user_query: str, session_token: str, user_id: int) -> Dict[str, Any]:
        """Handle appointment booking for authenticated users"""
        booking_id = str(uuid.uuid4())
        appointment_type = self.parsers.extract_appointment_type(user_query)
        
        # Create appointment record in database
        appointment_result = await self._create_appointment(user_id, booking_id, user_query, appointment_type)
        
        if appointment_result["success"]:
            bot_response = f"Your {appointment_type} appointment has been booked successfully! Booking ID: {booking_id[:8]}. You'll receive a confirmation email shortly."
        else:
            bot_response = f"I've received your appointment request (ID: {booking_id[:8]}). Our team will contact you within 24 hours to confirm the details."
        
        await self.session_manager.store_chat_history(
            session_token, user_query, bot_response, "authenticated", "appointment"
        )
        
        return {
            "success": True,
            "intent": "booking",
            "booking_id": booking_id,
            "appointment_type": appointment_type,
            "output": bot_response,
            "session_token": session_token,
            "user_id": user_id,
            "authenticated": True,
            "appointment_details": appointment_result.get("appointment_data")
        }

    async def _handle_ticket_creation(self, user_query: str, session_token: str, user_id: int) -> Dict[str, Any]:
        """Handle support ticket creation for authenticated users"""
        ticket_id = str(uuid.uuid4())
        ticket_type = self.parsers.extract_ticket_type(user_query)
        priority = self.parsers.determine_ticket_priority(user_query)
        
        # Create support ticket in database
        ticket_result = await self._create_support_ticket(user_id, ticket_id, user_query, ticket_type, priority)
        
        bot_response = f"Your {ticket_type} support ticket has been created successfully! Ticket ID: {ticket_id[:8]}. We'll respond within 2 business hours."
        
        await self.session_manager.store_chat_history(
            session_token, user_query, bot_response, "authenticated", "ticket"
        )
        
        return {
            "success": True,
            "intent": "ticket",
            "ticket_id": ticket_id,
            "ticket_type": ticket_type,
            "priority": priority,
            "output": bot_response,
            "session_token": session_token,
            "user_id": user_id,
            "authenticated": True,
            "ticket_details": ticket_result.get("ticket_data")
        }

    async def _handle_general_authenticated(self, user_query: str, session_token: str, user_id: int) -> Dict[str, Any]:
        """Handle general queries for authenticated users"""
        bot_response = "I'm here to help! You can book appointments, create tickets, or ask any questions about our healthcare services."
        
        await self.session_manager.store_chat_history(
            session_token, user_query, bot_response, "authenticated", "general"
        )
        
        return {
            "success": True,
            "intent": "general",
            "output": bot_response,
            "session_token": session_token,
            "user_id": user_id,
            "authenticated": True
        }

    async def _create_appointment(self, user_id: int, booking_id: str, user_query: str, appointment_type: str) -> Dict[str, Any]:
        """Create appointment record in database"""
        try:
            appointment_data = await db.fetch(
                """
                INSERT INTO appointments (booking_id, user_id, appointment_type, request_details, status, created_at)
                VALUES ($1, $2, $3, $4, 'pending', CURRENT_TIMESTAMP)
                RETURNING appointment_id, booking_id, appointment_type, status, created_at
                """,
                booking_id, user_id, appointment_type, user_query
            )
            
            return {
                "success": True,
                "appointment_data": dict(appointment_data[0]) if appointment_data else None
            }
            
        except Exception as e:
            print(f"Error creating appointment: {e}")
            return {"success": False, "error": str(e)}

    async def _create_support_ticket(self, user_id: int, ticket_id: str, user_query: str, 
                                   ticket_type: str, priority: str) -> Dict[str, Any]:
        """Create support ticket record in database"""
        try:
            ticket_data = await db.fetch(
                """
                INSERT INTO support_tickets (ticket_id, user_id, ticket_type, description, priority, status, created_at)
                VALUES ($1, $2, $3, $4, $5, 'open', CURRENT_TIMESTAMP)
                RETURNING ticket_id, ticket_type, priority, status, created_at
                """,
                ticket_id, user_id, ticket_type, user_query, priority
            )
            
            return {
                "success": True,
                "ticket_data": dict(ticket_data[0]) if ticket_data else None
            }
            
        except Exception as e:
            print(f"Error creating support ticket: {e}")
            return {"success": False, "error": str(e)}

    def _get_fallback_response(self, user_query: str) -> str:
        """Provide fallback responses when RAG service is unavailable"""
        query_lower = user_query.lower()
        
        # Common healthcare questions with static responses
        if any(word in query_lower for word in ['hours', 'time', 'open', 'close']):
            return "Our office hours are Monday through Friday, 8:00 AM to 6:00 PM. We're closed on weekends and holidays."
        
        elif any(word in query_lower for word in ['location', 'address', 'where']):
            return "We're located at 123 Healthcare Drive, Medical City, State 12345. We have convenient parking available."
        
        elif any(word in query_lower for word in ['appointment', 'schedule', 'book']):
            return "To schedule an appointment, please call us at (555) 123-4567 or use our online booking system. I can also help you if you complete authentication first."
        
        elif any(word in query_lower for word in ['insurance', 'cost', 'price', 'payment']):
            return "We accept most major insurance plans. For specific coverage questions, please contact our billing department at (555) 123-4568."
        
        elif any(word in query_lower for word in ['emergency', 'urgent']):
            return "For medical emergencies, please call 911 immediately. For urgent care needs, visit our urgent care center or call (555) 123-URGENT."
        
        elif any(word in query_lower for word in ['covid', 'vaccine', 'vaccination']):
            return "We offer COVID-19 vaccinations and testing. Please call (555) 123-4567 to schedule your vaccination appointment."
        
        else:
            return ("I'm here to help with your healthcare needs! I can provide information about our services, "
                   "hours, location, and help you schedule appointments. For specific medical questions, "
                   "please consult with our healthcare providers directly.")
