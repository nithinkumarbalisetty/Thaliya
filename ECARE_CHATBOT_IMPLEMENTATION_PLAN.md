# 🤖 E-Care Chatbot Implementation Plan

## Overview
Implement a comprehensive chatbot for the E-Care website with four core functionalities:
1. **Appointment Management** (via Prognocis integration)
2. **RAG-based Website Information** 
3. **Ticket Creation System** (for medication refills, etc.)
4. **GPT-powered General Q&A** (with guardrails)

## 🏗️ Architecture Design

### Core Components Structure
```
app/
├── chatbot/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── chatbot_engine.py          # Main chatbot orchestrator
│   │   ├── intent_classifier.py       # Classify user intent
│   │   ├── response_generator.py      # Generate responses
│   │   └── guardrails.py             # Safety and content filtering
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── appointment_handler.py     # Prognocis integration
│   │   ├── rag_handler.py            # Website info RAG
│   │   ├── ticket_handler.py         # Ticket creation
│   │   └── gpt_handler.py            # General GPT responses
│   ├── models/
│   │   ├── __init__.py
│   │   ├── conversation.py           # Conversation history
│   │   ├── appointment.py            # Appointment models
│   │   ├── ticket.py                 # Ticket models
│   │   └── chat_message.py           # Chat message models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── prognocis_service.py      # Prognocis API integration
│   │   ├── rag_service.py            # RAG implementation
│   │   ├── ticket_service.py         # Ticket management
│   │   └── openai_service.py         # OpenAI API integration
│   └── utils/
│       ├── __init__.py
│       ├── text_processing.py        # Text preprocessing
│       ├── embeddings.py             # Vector embeddings
│       └── validation.py             # Input validation
├── routers/
│   └── chatbot.py                    # Chatbot API endpoints
└── schemas/
    └── chatbot.py                    # Pydantic schemas
```

## 🎯 Implementation Phases

### Phase 1: Core Infrastructure
- Set up chatbot engine and intent classification
- Implement basic conversation flow
- Create database models for conversations and tickets

### Phase 2: RAG Implementation  
- Website content indexing and vectorization
- Similarity search and context retrieval
- RAG-based response generation

### Phase 3: Appointment Management
- Prognocis API integration (mock for now)
- Appointment CRUD operations
- Natural language processing for appointment requests

### Phase 4: Ticket System
- Ticket creation and management
- Dashboard API for team access
- Notification system

### Phase 5: GPT Integration & Guardrails
- OpenAI API integration
- Content filtering and safety measures
- Response quality controls

## 📊 Database Schema

### Conversations Table
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    status VARCHAR(50)
);
```

### Messages Table
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    role VARCHAR(20), -- 'user' or 'assistant'
    content TEXT,
    intent VARCHAR(100),
    handler_used VARCHAR(100),
    created_at TIMESTAMP
);
```

### Tickets Table
```sql
CREATE TABLE tickets (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255),
    category VARCHAR(100),
    subject VARCHAR(255),
    description TEXT,
    status VARCHAR(50),
    priority VARCHAR(20),
    assigned_to VARCHAR(255),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## 🔄 Chatbot Flow Logic

### Intent Classification
1. **Appointment Intent**: "book", "schedule", "cancel", "reschedule"
2. **Information Intent**: "hours", "location", "services", "doctors"
3. **Ticket Intent**: "refill", "prescription", "billing", "insurance"
4. **General Intent**: Medical questions, general health info

### Response Strategy
```
User Input → Intent Classification → Route to Handler → Generate Response → Apply Guardrails → Return to User
```

## 🛡️ Guardrails Implementation
- Medical advice disclaimers
- Sensitive information protection
- Content filtering (inappropriate language)
- Response length limits
- Rate limiting per user

## 📈 Success Metrics
- Intent classification accuracy (>90%)
- Response relevance scores
- User satisfaction ratings
- Ticket resolution times
- Appointment booking success rates
