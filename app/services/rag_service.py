"""
Production-level RAG (Retrieval-Augmented Generation) service using LangChain and Azure OpenAI
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Environment configuration
from dotenv import load_dotenv
load_dotenv('env.example')  # Load from .env.example if exists

# LangChain imports
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_community.document_loaders import TextLoader

# Try to import the new HuggingFace embeddings
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        HUGGINGFACE_AVAILABLE = True
    except ImportError:
        HUGGINGFACE_AVAILABLE = False

# Additional imports for text processing
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class ProductionRAGService:
    """
    Production-level RAG service using LangChain, FAISS, and Azure OpenAI
    """
    
    def __init__(self, 
                 data_path: str = "data/website_knowledge.txt",
                 vector_store_path: str = "data/vector_store",
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200,
                 use_azure_openai: bool = True):
        """
        Initialize the RAG service with LangChain and Azure OpenAI
        
        Args:
            data_path: Path to the knowledge base text file
            vector_store_path: Path to save/load the vector store
            chunk_size: Size of text chunks for splitting
            chunk_overlap: Overlap between chunks
            use_azure_openai: Whether to use Azure OpenAI (vs HuggingFace embeddings)
        """
        self.data_path = Path(data_path)
        self.vector_store_path = Path(vector_store_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_azure_openai = use_azure_openai
        
        # Azure OpenAI configuration
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.azure_embeddings_endpoint = os.getenv("AZURE_OPENAI_EMBEDDINGS_ENDPOINT")
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_embeddings_api_key = os.getenv("AZURE_OPENAI_EMBEDDINGS_API_KEY")
        self.azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.azure_deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        self.azure_embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
        
        # Initialize components
        self.embeddings = None
        self.vector_store = None
        self.text_splitter = None
        self.llm = None
        self.qa_chain = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialized = False
        
        # Configuration
        self.similarity_threshold = 0.7
        self.max_results = 5
        
        logger.info("RAG service configured with LangChain and Azure OpenAI")
    
    async def _ensure_initialized(self):
        """Ensure the RAG system is initialized (lazy initialization)"""
        if not self._initialized:
            await self._initialize_rag_system()
    
    async def _initialize_rag_system(self):
        """Initialize the complete LangChain RAG system"""
        try:
            logger.info("Initializing LangChain RAG system with Azure OpenAI...")
            # Initialize embeddings
            await self._initialize_embeddings()
            
            # Initialize text splitter
            self._initialize_text_splitter()
            
            # Initialize LLM
            await self._initialize_llm()
            
            # Load or create vector store
            await self._load_or_create_vector_store()
            
            # Initialize QA chain
            await self._initialize_qa_chain()
            
            self._initialized = True
            logger.info("LangChain RAG system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG system: {str(e)}")
            # Fallback to basic mode
            self._initialized = False
            raise
    
    async def _initialize_embeddings(self):
        """Initialize embeddings (Azure OpenAI preferred, fallback to text search)"""
        def _load_embeddings():
            if self.use_azure_openai and self.azure_endpoint and self.azure_api_key:
                try:
                    # Use Azure OpenAI embeddings
                    embeddings = AzureOpenAIEmbeddings(
                        azure_endpoint=self.azure_embeddings_endpoint,
                        api_key=self.azure_embeddings_api_key,
                        azure_deployment=self.azure_embedding_deployment,
                        chunk_size=1000
                    )
                    logger.info("Loaded Azure OpenAI embeddings")
                    return embeddings
                except Exception as e:
                    logger.warning(f"Failed to load Azure OpenAI embeddings: {e}")
            
            elif HUGGINGFACE_AVAILABLE:
                try:
                    # Fallback to HuggingFace embeddings if available
                    logger.warning("Azure OpenAI not configured, using HuggingFace embeddings")
                    embeddings = HuggingFaceEmbeddings(
                        model_name="all-MiniLM-L6-v2",
                        model_kwargs={'device': 'cpu'},
                        encode_kwargs={'normalize_embeddings': True}
                    )
                    logger.info("Loaded HuggingFace embeddings")
                    return embeddings
                except Exception as e:
                    logger.warning(f"Failed to load HuggingFace embeddings: {e}")
            
            # Last resort: use text-based search without embeddings
            logger.warning("No embeddings available, using text-based search")
            return None
        
        loop = asyncio.get_event_loop()
        self.embeddings = await loop.run_in_executor(self.executor, _load_embeddings)
        
        if self.embeddings:
            embedding_type = "Azure OpenAI" if (self.use_azure_openai and self.azure_endpoint) else "HuggingFace"
            logger.info(f"Successfully initialized {embedding_type} embeddings")
        else:
            logger.info("Using text-based search without embeddings")
    
    def _initialize_text_splitter(self):
        """Initialize the text splitter"""
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        logger.info("Initialized text splitter")
    
    async def _initialize_llm(self):
        """Initialize the Language Model (Azure OpenAI)"""
        def _load_llm():
            if self.use_azure_openai and self.azure_endpoint and self.azure_api_key:
                return AzureChatOpenAI(
                    azure_endpoint=self.azure_endpoint,
                    api_key=self.azure_api_key,
                    api_version=self.azure_api_version,
                    azure_deployment=self.azure_deployment_name,
                    temperature=0.3,
                    max_tokens=500
                )
            else:
                logger.warning("Azure OpenAI not configured, LLM features will be limited")
                return None
        
        loop = asyncio.get_event_loop()
        self.llm = await loop.run_in_executor(self.executor, _load_llm)
        
        if self.llm:
            logger.info("Loaded Azure OpenAI LLM")
        else:
            logger.warning("No LLM available - using template-based responses")
    
    async def _load_or_create_vector_store(self):
        """Load existing vector store or create new one from text file"""
        if self._vector_store_exists():
            await self._load_vector_store()
        else:
            await self._create_vector_store_from_file()
    
    def _vector_store_exists(self) -> bool:
        """Check if vector store files exist"""
        return (self.vector_store_path.exists() and 
                (self.vector_store_path / "index.faiss").exists())
    
    async def _create_vector_store_from_file(self):
        """Create vector store from the text file using LangChain loaders"""
        logger.info(f"Creating vector store from file: {self.data_path}")
        
        def _create_vectorstore():
            # Load documents using LangChain TextFileLoader
            if not self.data_path.exists():
                raise FileNotFoundError(f"Knowledge base file not found: {self.data_path}")
            
            # Load the text file
            loader = TextLoader(str(self.data_path), encoding='utf-8')
            documents = loader.load()
            
            if not documents:
                raise ValueError("No documents loaded from file")
            
            # Split documents into chunks
            chunks = self.text_splitter.split_documents(documents)
            
            # Add metadata to chunks
            for i, chunk in enumerate(chunks):
                chunk.metadata.update({
                    "source": str(self.data_path),
                    "chunk_id": i,
                    "timestamp": datetime.now().isoformat()
                })
            
            logger.info(f"Created {len(chunks)} text chunks from file")
            
            # Create FAISS vector store
            vector_store = FAISS.from_documents(chunks, self.embeddings)
            
            return vector_store
        
        loop = asyncio.get_event_loop()
        self.vector_store = await loop.run_in_executor(self.executor, _create_vectorstore)
        
        # Save vector store
        await self._save_vector_store()
        logger.info("Created and saved vector store from text file")
    
    async def _load_vector_store(self):
        """Load existing vector store"""
        def _load():
            return FAISS.load_local(
                str(self.vector_store_path), 
                self.embeddings,
                allow_dangerous_deserialization=True
            )
        
        loop = asyncio.get_event_loop()
        self.vector_store = await loop.run_in_executor(self.executor, _load)
        logger.info("Loaded existing vector store")
    
    async def _save_vector_store(self):
        """Save vector store to disk"""
        def _save():
            self.vector_store_path.mkdir(parents=True, exist_ok=True)
            self.vector_store.save_local(str(self.vector_store_path))
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, _save)
    
    async def _initialize_qa_chain(self):
        """Initialize the Question-Answering chain"""
        if not self.llm or not self.vector_store:
            logger.warning("Cannot initialize QA chain - missing LLM or vector store")
            return
        
        # Custom prompt template for medical center
        prompt_template = """
        You are a helpful assistant for E-Care Medical Center. Use the following context to answer the question about our medical center services, hours, staff, or policies.
        
        Context: {context}
        
        Question: {question}
        
        Instructions:
        - Provide accurate information based only on the context provided
        - Be helpful and professional
        - If you cannot find the answer in the context, say so politely
        - For medical advice questions, remind users to consult with healthcare providers
        - Keep responses concise but informative
        
        Answer:
        """
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        # Create retriever
        retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.max_results}
        )
        
        # Create QA chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            chain_type_kwargs={"prompt": prompt},
            return_source_documents=True
        )
        
        logger.info("Initialized QA chain with custom prompt")
    
    async def retrieve_relevant_context(self, 
                                      query: str, 
                                      max_context_length: int = 2000) -> Dict[str, Any]:
        """
        Retrieve relevant context using LangChain QA chain
        """
        try:
            await self._ensure_initialized()
            if self.qa_chain:
                # Use LangChain QA chain for full RAG
                def _run_qa():
                    result = self.qa_chain.invoke({"query": query})
                    return result
                
                loop = asyncio.get_event_loop()
                qa_result = await loop.run_in_executor(self.executor, _run_qa)
                
                # Extract information from QA result
                answer = qa_result.get("result", "")
                source_docs = qa_result.get("source_documents", [])
                
                # Calculate confidence based on source relevance
                confidence = 0.9 if source_docs else 0.5
                
                # Format sources
                sources = []
                combined_context = ""
                
                for doc in source_docs:
                    content = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                    sources.append({
                        "content": content,
                        "metadata": doc.metadata,
                        "confidence": 0.8  # Default confidence for retrieved docs
                    })
                    combined_context += doc.page_content + "\n\n"
                
                return {
                    "context": combined_context[:max_context_length],
                    "answer": answer,
                    "sources": sources,
                    "confidence": confidence,
                    "num_sources": len(sources),
                    "query": query,
                    "timestamp": datetime.now().isoformat(),
                    "method": "langchain_qa"
                }
            
            else:
                # Fallback to similarity search only
                return await self._similarity_search_fallback(query, max_context_length)
                
        except Exception as e:
            logger.error(f"Error in retrieve_relevant_context: {str(e)}")
            # Try text-based search as final fallback
            return await self._text_based_search_fallback(query, max_context_length)
    
    async def _similarity_search_fallback(self, query: str, max_context_length: int) -> Dict[str, Any]:
        """Fallback similarity search when QA chain is not available"""
        try:
            if not self.vector_store:
                raise ValueError("Vector store not initialized")
            
            def _search():
                docs = self.vector_store.similarity_search(query, k=self.max_results)
                return docs
            
            loop = asyncio.get_event_loop()
            docs = await loop.run_in_executor(self.executor, _search)
            
            # Combine contexts
            combined_context = ""
            sources = []
            
            for doc in docs:
                combined_context += doc.page_content + "\n\n"
                sources.append({
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata,
                    "confidence": 0.7
                })
            
            return {
                "context": combined_context[:max_context_length],
                "answer": self._generate_template_answer(query, combined_context),
                "sources": sources,
                "confidence": 0.7 if docs else 0.0,
                "num_sources": len(sources),
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "method": "similarity_search"
            }
            
        except Exception as e:
            logger.error(f"Similarity search fallback failed: {str(e)}")
            return {
                "context": "",
                "answer": "I'm sorry, I couldn't find specific information about that. Please contact our office at (555) 123-4567.",
                "sources": [],
                "confidence": 0.0,
                "num_sources": 0,
                "error": str(e),
                "method": "fallback_error"
            }
    
    def _generate_template_answer(self, query: str, context: str) -> str:
        """Generate a template-based answer when LLM is not available"""
        if not context:
            return "I don't have specific information about that. Please contact our office at (555) 123-4567 for more details."
        
        query_lower = query.lower()
        context_preview = context[:300] + "..." if len(context) > 300 else context
        
        if any(word in query_lower for word in ["hours", "open", "time"]):
            return f"Based on our information: {context_preview}"
        elif any(word in query_lower for word in ["location", "address", "where"]):
            return f"Here's our location information: {context_preview}"
        elif any(word in query_lower for word in ["services", "treatment"]):
            return f"Our medical services include: {context_preview}"
        elif any(word in query_lower for word in ["doctors", "staff"]):
            return f"Our medical team: {context_preview}"
        else:
            return f"Based on our medical center information: {context_preview}"
    
    async def _text_based_search_fallback(self, query: str, max_context_length: int) -> Dict[str, Any]:
        """Text-based search when no embeddings are available"""
        try:
            # Load the knowledge base file directly
            if not self.data_path.exists():
                raise FileNotFoundError(f"Knowledge base file not found: {self.data_path}")
            
            # Read the file content
            with open(self.data_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Simple keyword matching
            query_words = query.lower().split()
            
            # Find relevant sections
            relevant_sections = []
            confidence = 0.0
            
            # Split content into sections (by double newlines)
            sections = content.split('\n\n')
            
            for section in sections:
                section_lower = section.lower()
                matches = sum(1 for word in query_words if word in section_lower)
                if matches > 0:
                    section_confidence = matches / len(query_words)
                    relevant_sections.append({
                        "content": section.strip(),
                        "confidence": section_confidence
                    })
                    confidence = max(confidence, section_confidence)
            
            # Sort by confidence and take the best matches
            relevant_sections.sort(key=lambda x: x["confidence"], reverse=True)
            best_sections = relevant_sections[:3]  # Top 3 sections
            
            # Combine the best sections
            combined_context = "\n\n".join([s["content"] for s in best_sections])
            combined_context = combined_context[:max_context_length]
            
            # Generate a simple answer
            if combined_context:
                answer = self._generate_text_based_answer(query, combined_context)
            else:
                answer = "I couldn't find specific information about that. Please contact our office at (555) 123-4567 for assistance."
            
            return {
                "context": combined_context,
                "answer": answer,
                "sources": [{"content": s["content"][:200] + "..." if len(s["content"]) > 200 else s["content"], 
                            "confidence": s["confidence"]} for s in best_sections],
                "confidence": confidence,
                "num_sources": len(best_sections),
                "query": query,
                "timestamp": datetime.now().isoformat(),
                "method": "text_search"
            }
            
        except Exception as e:
            logger.error(f"Text-based search failed: {str(e)}")
            return {
                "context": "",
                "answer": "I'm sorry, I couldn't access the information right now. Please contact our office at (555) 123-4567 for assistance.",
                "sources": [],
                "confidence": 0.0,
                "num_sources": 0,
                "error": str(e),
                "method": "text_search_error"
            }
    
    def _generate_text_based_answer(self, query: str, context: str) -> str:
        """Generate a simple answer based on text search"""
        if not context:
            return "I don't have specific information about that."
        
        query_lower = query.lower()
        
        # Extract relevant information based on query type
        if any(word in query_lower for word in ["hours", "open", "time", "when"]):
            # Look for hours information
            lines = context.split('\n')
            for line in lines:
                if any(time_word in line.lower() for time_word in ["hours", "open", "am", "pm", "monday", "tuesday"]):
                    return f"Our hours are: {line.strip()}"
            return "Based on our information, we have regular business hours. Please call for specific times."
        
        elif any(word in query_lower for word in ["location", "address", "where"]):
            # Look for location information
            lines = context.split('\n')
            for line in lines:
                if any(loc_word in line.lower() for loc_word in ["located", "address", "avenue", "street", "district"]):
                    return f"Our location: {line.strip()}"
            return "Please contact us for our location information."
        
        elif any(word in query_lower for word in ["services", "treatment", "medical", "offer"]):
            # Look for services information
            services_section = ""
            in_services = False
            for line in context.split('\n'):
                if "MEDICAL SERVICES" in line.upper() or "SERVICES" in line.upper():
                    in_services = True
                    continue
                if in_services and line.strip():
                    if line.startswith('-'):
                        services_section += line + "\n"
                    elif not line.startswith(' ') and line.isupper():
                        break
            
            if services_section:
                return f"Our medical services include:\n{services_section.strip()}"
            return "We offer comprehensive medical services. Please contact us for detailed information."
        
        elif any(word in query_lower for word in ["doctor", "physician", "staff", "who"]):
            # Look for staff information
            lines = context.split('\n')
            for line in lines:
                if any(staff_word in line.lower() for staff_word in ["dr.", "doctor", "physician", "md"]):
                    return f"Our medical staff includes: {line.strip()}"
            return "We have qualified medical professionals on staff. Please contact us for specific provider information."
        
        elif any(word in query_lower for word in ["insurance", "coverage", "accept", "plans"]):
            # Look for insurance information
            lines = context.split('\n')
            for line in lines:
                if any(ins_word in line.lower() for ins_word in ["insurance", "coverage", "accept", "plans", "medicaid", "medicare"]):
                    return f"Insurance information: {line.strip()}"
            return "We accept various insurance plans. Please contact us to verify your specific coverage."
        
        # Default response with context
        context_preview = context[:300] + "..." if len(context) > 300 else context
        return f"Based on our information: {context_preview}"
    
    async def update_knowledge_base(self, new_content: str, section: str = "UPDATES"):
        """Update knowledge base with new content"""
        try:
            await self._ensure_initialized()
            
            # Create new document
            new_doc = Document(
                page_content=new_content,
                metadata={
                    "source": "update",
                    "section": section,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # Split into chunks
            chunks = self.text_splitter.split_documents([new_doc])
            
            # Add to vector store
            def _add_documents():
                self.vector_store.add_documents(chunks)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, _add_documents)
            
            # Save updated vector store
            await self._save_vector_store()
            
            logger.info(f"Updated knowledge base with {len(chunks)} new chunks")
            
        except Exception as e:
            logger.error(f"Error updating knowledge base: {str(e)}")
            raise
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics"""
        stats = {
            "vector_store_path": str(self.vector_store_path),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "similarity_threshold": self.similarity_threshold,
            "max_results": self.max_results,
            "system_initialized": self._initialized,
            "use_azure_openai": self.use_azure_openai,
            "has_llm": self.llm is not None,
            "has_qa_chain": self.qa_chain is not None,
            "azure_configured": bool(self.azure_endpoint and self.azure_api_key)
        }
        
        if self.vector_store:
            try:
                stats["vector_store_size"] = self.vector_store.index.ntotal
            except:
                stats["vector_store_size"] = "unknown"
        
        return stats
    
    def __del__(self):
        """Cleanup resources"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)

# Singleton instance for the application
_rag_service_instance = None

async def get_rag_service() -> ProductionRAGService:
    """Get or create the RAG service singleton"""
    global _rag_service_instance
    
    if _rag_service_instance is None:
        _rag_service_instance = ProductionRAGService()
    
    return _rag_service_instance

# Singleton instance for the application
_rag_service_instance = None

async def get_rag_service() -> ProductionRAGService:
    """Get or create the RAG service singleton"""
    global _rag_service_instance
    
    if _rag_service_instance is None:
        _rag_service_instance = ProductionRAGService()
        # Wait for initialization
        await asyncio.sleep(1)  # Give it time to start initialization
    
    return _rag_service_instance


# For testing and manual usage
if __name__ == "__main__":
    import asyncio
    
    async def test_rag_service():
        """Test the RAG service"""
        rag = ProductionRAGService()
        await asyncio.sleep(5)  # Wait for initialization
        
        # Test query
        result = await rag.retrieve_relevant_context("What are your office hours?")
        print("Query:", "What are your office hours?")
        print("Context:", result["context"][:200] + "...")
        print("Confidence:", result["confidence"])
        print("Sources:", len(result["sources"]))
        
        # Test stats
        stats = await rag.get_system_stats()
        print("\nRAG System Stats:", stats)
    
    # Run test
    asyncio.run(test_rag_service())