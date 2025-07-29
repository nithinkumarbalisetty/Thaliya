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
load_dotenv()

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

        human_message = "Classify this message: {user_message}"
        
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", human_message)
        ])
    
    async def classify_intent(self, message: str) -> str:
        """
        Classify user intent using AI
        
        Args:
            message: User message to classify
            
        Returns:
            Intent classification: 'rag_info', 'appointment', 'ticket', or 'general'
        """
        await self._ensure_initialized()
        
        if not self._initialized:
            logger.warning("AI classifier not available, falling back to pattern matching")
            return self._fallback_classification(message)
        
        try:
            # Create the prompt
            prompt = self._create_classification_prompt()
            
            # Format intent definitions for the prompt
            intent_definitions_text = ""
            for intent, details in self.intent_definitions.items():
                intent_definitions_text += f"\n{intent.upper()}:\n"
                intent_definitions_text += f"- {details['description']}\n"
                intent_definitions_text += f"- Examples: {', '.join(details['examples'][:3])}\n"
            
            # Get AI classification
            formatted_prompt = prompt.format(
                intent_definitions=intent_definitions_text,
                user_message=message
            )
            
            response = await self.llm.ainvoke([
                SystemMessage(content=formatted_prompt.split("Human: ")[0].replace("System: ", "")),
                HumanMessage(content=f"Classify this message: {message}")
            ])
            
            # Extract and validate the intent
            predicted_intent = response.content.strip().lower()
            
            # Ensure the response is a valid intent
            valid_intents = list(self.intent_definitions.keys())
            if predicted_intent in valid_intents:
                logger.info(f"AI classified '{message}' as '{predicted_intent}'")
                return predicted_intent
            else:
                logger.warning(f"AI returned invalid intent '{predicted_intent}', using general")
                return "general"
                
        except Exception as e:
            logger.error(f"AI intent classification failed: {str(e)}")
            return self._fallback_classification(message)
    
    def _fallback_classification(self, message: str) -> str:
        """
        Fallback classification using simple keyword matching
        """
        message_lower = message.lower()
        
        # Appointment keywords
        if any(word in message_lower for word in [
            "book", "schedule", "make appointment", "cancel appointment", 
            "reschedule", "i want to see", "i need to see", "appointment with"
        ]):
            return "appointment"
        
        # Information keywords
        elif any(word in message_lower for word in [
            "what are", "what is", "when are", "where is", "who are", 
            "hours", "services", "doctors", "insurance", "location", "address"
        ]):
            return "rag_info"
        
        # Ticket keywords
        elif any(word in message_lower for word in [
            "prescription", "refill", "billing", "bill", "results", 
            "lab", "referral", "portal", "login"
        ]):
            return "ticket"
        
        # Default to general
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