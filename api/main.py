from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize FastAPI
app = FastAPI(title="LRH Chatbot API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
qa_chain = None
user_usage = {}

# Request/Response models
class ChatRequest(BaseModel):
    question: str
    user_id: str
    max_sources: Optional[int] = 3

class Source(BaseModel):
    text: str
    source: str

class ChatResponse(BaseModel):
    response: str
    sources: List[Source]
    timestamp: str

@app.on_event("startup")
async def startup_event():
    """Initialize Pinecone and QA chain on startup"""
    global qa_chain

    print(">> Starting up LRH Chatbot API...")

    try:
        # Setup embeddings
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        # Connect to existing Pinecone index
        index_name = os.getenv("PINECONE_INDEX_NAME", "lrh-writings")
        vectorstore = PineconeVectorStore.from_existing_index(
            index_name=index_name,
            embedding=embeddings
        )

        # Setup LLM
        llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.7,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        # Custom prompt template
        prompt_template = """You are responding based on L. Ron Hubbard's writings.
Use the following passages from his works to inform your response.
Stay true to the concepts and terminology found in these writings.

Context from LRH's writings:
{context}

Question: {question}

Provide a thoughtful response based on these writings. If the passages don't contain
relevant information to answer the question, say so honestly."""

        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )

        # Create QA chain
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=vectorstore.as_retriever(
                search_kwargs={"k": 5}
            ),
            return_source_documents=True,
            chain_type_kwargs={"prompt": PROMPT}
        )

        print("OK: API initialized successfully!")

    except Exception as e:
        print(f"ERROR during startup: {str(e)}")
        raise

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "LRH Chatbot API is running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "qa_chain_initialized": qa_chain is not None,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint"""

    if qa_chain is None:
        raise HTTPException(
            status_code=503,
            detail="Service not ready. QA chain not initialized."
        )

    # Simple rate limiting (50 queries per day per user)
    user_id = request.user_id
    if user_id not in user_usage:
        user_usage[user_id] = []

    # Clean up old queries (older than 24 hours)
    now = datetime.now()
    user_usage[user_id] = [
        timestamp for timestamp in user_usage[user_id]
        if (now - timestamp).total_seconds() < 86400
    ]

    # Check limit
    if len(user_usage[user_id]) >= 50:
        raise HTTPException(
            status_code=429,
            detail="Daily limit of 50 queries reached. Try again tomorrow."
        )

    # Process query
    try:
        result = qa_chain({"query": request.question})

        # Record usage
        user_usage[user_id].append(now)

        # Format sources
        sources = []
        for doc in result["source_documents"][:request.max_sources]:
            sources.append(Source(
                text=doc.page_content[:200] + "...",
                source=doc.metadata.get("source", "Unknown")
            ))

        return ChatResponse(
            response=result["result"],
            sources=sources,
            timestamp=now.isoformat()
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

@app.get("/stats")
async def stats():
    """Get usage statistics"""
    total_queries = sum(len(queries) for queries in user_usage.values())
    return {
        "total_users": len(user_usage),
        "total_queries_today": total_queries,
        "users": {user_id: len(queries) for user_id, queries in user_usage.items()}
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
