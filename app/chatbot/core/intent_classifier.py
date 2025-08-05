"""
AI-powered Intent Classification using Azure OpenAI
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage

# Load environment variables
load_dotenv('.env.example')  # Load from .env.example if exists

logger = logging.getLogger(__name__)

class AIIntentClassifier:
    """
    AI-powered intent classifier using Azure OpenAI for accurate intent detection
    """
    
    def __init__(self):
        """Initialize the AI intent classifier"""
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")
        self.azure_deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-35-turbo")
        
        # Debug logging
        logger.info(f"Azure Endpoint configured: {bool(self.azure_endpoint)}")
        logger.info(f"Azure API Key configured: {bool(self.azure_api_key)}")
        logger.info(f"Azure Deployment: {self.azure_deployment_name}")
        
        self.llm = None
        self._initialized = False
        
        # Define intent categories and their descriptions
        self.intent_definitions = {
            "rag_info": {
                "description": "User wants INFORMATION about medical center services, hours, staff, policies, insurance, location, etc.",
                "examples": [
                    "What are your office hours?",
                    "What services do you offer?",
                    "Who are your doctors?",
                    "What insurance do you accept?",
                    "Where are you located?",
                    "Tell me about your medical center",
                    "What are your policies?"
                ]
            },
            "appointment": {
                "description": "User wants to BOOK, SCHEDULE, CANCEL, or MODIFY an appointment - they want to take ACTION",
                "examples": [
                    "I want to book an appointment",
                    "Schedule me with Dr. Johnson",
                    "Cancel my appointment",
                    "Can you reschedule my visit?",
                    "Book me for next Tuesday",
                    "I need to see a doctor"
                ]
            },
            "ticket": {
                "description": "User needs help with prescriptions, billing, test results, referrals, or TECHNICAL ISSUES with booking/portal",
                "examples": [
                    "I need a prescription refill",
                    "Question about my bill",
                    "Where are my lab results?",
                    "I need a referral to a specialist",
                    "Having trouble with the patient portal",
                    "I'm having trouble booking online",
                    "The website won't let me schedule",
                    "Error when trying to book appointment",
                    "Can't login to my account"
                ]
            },
            "general": {
                "description": "General health questions, medical advice, or anything that doesn't fit other categories",
                "examples": [
                    "I have a headache, what should I do?",
                    "Is this symptom serious?",
                    "Health tips for diabetes",
                    "What causes high blood pressure?"
                ]
            }
        }
    
    async def _ensure_initialized(self):
        """Ensure the classifier is initialized"""
        if not self._initialized:
            await self._initialize_llm()
    
    async def _initialize_llm(self):
        """Initialize the Azure OpenAI LLM"""
        try:
            if self.azure_endpoint and self.azure_api_key:
                self.llm = AzureChatOpenAI(
                    azure_endpoint=self.azure_endpoint,
                    api_key=self.azure_api_key,
                    api_version=self.azure_api_version,
                    azure_deployment=self.azure_deployment_name,
                    temperature=0.1,  # Low temperature for consistent classification
                    max_tokens=100    # Short responses for classification
                )
                self._initialized = True
                logger.info("AI Intent Classifier initialized with Azure OpenAI")
            else:
                logger.warning("Azure OpenAI not configured for intent classification")
                self._initialized = False
        except Exception as e:
            logger.error(f"Failed to initialize AI Intent Classifier: {str(e)}")
            self._initialized = False
    
    def _create_classification_prompt(self) -> ChatPromptTemplate:
        """Create the prompt template for intent classification"""
        
        system_message = """You are an expert intent classifier for a medical center chatbot. 
Your job is to classify user messages into one of these intents:

INTENT CATEGORIES:
{intent_definitions}

CLASSIFICATION RULES:
1. If user wants INFORMATION (asking "what", "when", "where", "who", "how"), use "rag_info"
2. If user wants to take ACTION (book, schedule, cancel, "I want", "I need to"), use "appointment" 
3. If user needs help with billing, prescriptions, results, referrals, or has TECHNICAL PROBLEMS, use "ticket"
4. For health questions or medical advice, use "general"
5. When in doubt between rag_info and appointment, choose rag_info if they're asking "how to" do something

SPECIAL CASES:
- "I'm having trouble [doing something]" = ticket (technical issue)
- "Can't [do something]" = ticket (technical issue)  
- "Error when [doing something]" = ticket (technical issue)
- "Website won't let me" = ticket (technical issue)

Respond with ONLY the intent name: rag_info, appointment, ticket, or general"""

        human_message = "Classify this user message: {user_query}"
        
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", human_message)
        ])
    
    async def classify_intent(self, user_query: str) -> Dict[str, Any]:
        """
        Classify the intent of a user query
        """
        await self._ensure_initialized()
        
        if not self._initialized:
            # Fallback to simple classification if Azure OpenAI not available
            intent = self._classify_intent_simple(user_query)
            return {
                "intent": intent,
                "confidence": 0.5,
                "method": "fallback"
            }
        
        try:
            # Create the prompt
            prompt = self._create_classification_prompt()
            
            # Format intent definitions for the prompt
            intent_text = "\n".join([
                f"- {intent}: {details['description']}"
                for intent, details in self.intent_definitions.items()
            ])
            
            # Create messages
            formatted_prompt = prompt.format_messages(
                intent_definitions=intent_text,
                user_query=user_query
            )
            
            # Get response from Azure OpenAI
            response = await self.llm.ainvoke(formatted_prompt)
            intent = response.content.strip().lower()
            
            # Validate the intent
            if intent not in self.intent_definitions:
                intent = "general"
            
            return {
                "intent": intent,
                "confidence": 0.9,
                "method": "ai"
            }
            
        except Exception as e:
            logger.error(f"AI intent classification failed: {e}")
            # Fallback to simple classification
            intent = self._classify_intent_simple(user_query)
            return {
                "intent": intent,
                "confidence": 0.5,
                "method": "fallback"
            }

    def _classify_intent_simple(self, user_query: str) -> str:
        """Simple keyword-based fallback classification"""
        user_query_lower = user_query.lower()
        
        if any(word in user_query_lower for word in ['appointment', 'book', 'schedule', 'visit']):
            return "appointment"
        elif any(word in user_query_lower for word in ['ticket', 'issue', 'problem', 'help', 'refill', 'prescription']):
            return "ticket"
        elif any(word in user_query_lower for word in ['hours', 'location', 'address', 'services', 'doctors', 'insurance']):
            return "rag_info"
        else:
            return "general"

# Global instance
_ai_intent_classifier = None

async def get_ai_intent_classifier() -> AIIntentClassifier:
    """Get the global AI intent classifier instance"""
    global _ai_intent_classifier
    if _ai_intent_classifier is None:
        _ai_intent_classifier = AIIntentClassifier()
        await _ai_intent_classifier._ensure_initialized()
    return _ai_intent_classifier