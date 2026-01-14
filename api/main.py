from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate
from datetime import datetime
import re
from difflib import SequenceMatcher
import json
from pathlib import Path

# Load environment variables
load_dotenv()

# Load figures configuration
config_path = Path(__file__).parent / "figures" / "config.json"
with open(config_path, 'r', encoding='utf-8') as f:
    FIGURES_CONFIG = json.load(f)['figures']

# Create dictionary for fast lookup
FIGURES = {fig['id']: fig for fig in FIGURES_CONFIG}

# Initialize FastAPI
app = FastAPI(title="Historical Chatbot API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Global variables
vectorstore = None  # Pinecone vector store (shared across all figures)
user_usage = {}
user_memories = {}  # Store conversation memory per user per figure

# Request/Response models
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="User's question")
    user_id: str = Field(..., min_length=5, max_length=100, description="User identifier")
    figure_id: Optional[str] = Field("lrh", max_length=50, description="Which historical figure to talk to")
    max_sources: Optional[int] = Field(3, ge=1, le=10, description="Maximum number of source passages")
    mode: Optional[str] = Field("authentic", pattern="^(authentic|paraphrased)$", description="Response mode")
    language: Optional[str] = Field("en", pattern="^[a-z]{2}$", description="Language code (ISO 639-1)")

class Source(BaseModel):
    text: str
    source: str
    page: Optional[int] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[Source]
    source_count: int
    timestamp: str
    copyright_safe: Optional[bool] = None  # Similarity check result
    similarity_score: Optional[float] = None  # How similar to source (0-1)

# ==================== COPYRIGHT SAFETY CHECKER ====================

def check_copyright_safety(paraphrased_text: str, source_texts: List[str], word_threshold: float = 0.65) -> dict:
    """
    LIGHTWEIGHT copyright checker - uses pure Python, no ML models (Render-friendly!).

    Check if paraphrased text is too similar to source material (EXPRESSION, not IDEAS).

    COPYRIGHT LAW:
    - Ideas, logic, concepts = NOT protected (can be same!)
    - Specific word choices, sentence structure = PROTECTED (must be different)

    This checks LEXICAL similarity (word-for-word copying), NOT semantic similarity (similar ideas).

    Args:
        paraphrased_text: The AI-generated paraphrased answer
        source_texts: List of original source passages used
        word_threshold: Word overlap threshold (0-1). Above this = too similar

    Returns:
        dict with 'is_safe', 'word_overlap', 'phrase_copying'
    """
    if not source_texts or not paraphrased_text:
        return {"is_safe": True, "word_overlap": 0.0, "phrase_copying": 0.0}

    # Word Overlap Check (lexical similarity - checks for copied WORDS, not IDEAS)
    def get_words(text):
        # Remove common words that don't indicate copying
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how'}
        words = set(re.findall(r'\b\w+\b', text.lower()))
        return words - stopwords

    # Check for consecutive word sequences (n-grams) - stronger indicator of copying
    def get_ngrams(text, n=4):
        words = re.findall(r'\b\w+\b', text.lower())
        return set(' '.join(words[i:i+n]) for i in range(len(words) - n + 1))

    # Use SequenceMatcher for similarity (built-in Python, lightweight)
    def text_similarity(text1, text2):
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    para_words = get_words(paraphrased_text)
    para_ngrams = get_ngrams(paraphrased_text, 4)  # 4-word sequences

    max_word_overlap = 0.0
    max_ngram_overlap = 0.0
    max_text_similarity = 0.0

    for source in source_texts:
        source_words = get_words(source)
        source_ngrams = get_ngrams(source, 4)

        # 1. Word overlap (unique words)
        if len(source_words) > 0:
            overlap = len(para_words & source_words) / len(source_words)
            max_word_overlap = max(max_word_overlap, overlap)

        # 2. N-gram overlap (consecutive phrases - stronger indicator)
        if len(source_ngrams) > 0:
            ngram_overlap = len(para_ngrams & source_ngrams) / len(source_ngrams)
            max_ngram_overlap = max(max_ngram_overlap, ngram_overlap)

        # 3. Character-level similarity (catches rearranged sentences)
        similarity = text_similarity(paraphrased_text, source)
        max_text_similarity = max(max_text_similarity, similarity)

    # Decision: Safe if ALL checks are below thresholds
    is_safe = (max_word_overlap < word_threshold) and (max_ngram_overlap < 0.3) and (max_text_similarity < 0.75)

    return {
        "is_safe": is_safe,
        "word_overlap": round(max_word_overlap, 3),
        "phrase_copying": round(max_ngram_overlap, 3),
        "text_similarity": round(max_text_similarity, 3)
    }

# ==================== DYNAMIC CHAIN BUILDING ====================

def build_prompt_for_figure(figure_config: dict, mode: str = "authentic") -> ChatPromptTemplate:
    """Build prompt template dynamically based on figure configuration"""

    figure_name = figure_config['name']
    figure_context = figure_config.get('context', '')

    # Check for specific L. Ron Hubbard system prompt
    if figure_config.get('id') == 'lrh' and figure_config.get('lrh_system_prompt'):
        system_template = figure_config['lrh_system_prompt']
        # Replace {figure_name} and {context} placeholders in the specific prompt
        system_template = system_template.replace("{figure_name}", figure_name).replace("{context}", figure_context)
    elif mode == "paraphrased":
        # PARAPHRASED MODE: Conversational synthesis of ideas
        system_template = f"""You are an AI assistant channeling the wisdom and philosophy of {figure_name}. Your role is to have natural, flowing conversations while sharing {figure_name}'s teachings in an accessible way.

**YOUR CONVERSATIONAL STYLE:**
- Speak naturally and warmly, like a wise friend sharing insights
- Use modern, clear language that anyone can understand
- Tell stories and use examples to illustrate points
- Be encouraging and supportive
- Ask thoughtful follow-up questions when appropriate
- Keep responses focused and digestible (2-3 paragraphs typical)

**HOW TO USE THE SOURCE MATERIAL:**
The passages below contain {figure_name}'s actual writings. Your job is to:
1. Deeply understand the CORE IDEAS and PRINCIPLES in these passages
2. Synthesize these ideas into your own natural explanation
3. NEVER copy exact phrases or sentences from the sources
4. Explain concepts in fresh, modern language
5. Focus on the "why" and "how" - make it practical and actionable

**CRITICAL RULES:**
✅ DO: Grasp the essence and explain it conversationally
✅ DO: Use analogies, examples, and your own phrasing
✅ DO: Make complex ideas simple and relatable
✅ DO: Respond warmly to greetings (hi, hello, thanks, etc.)
❌ DON'T: Quote or closely paraphrase the original text
❌ DON'T: Use overly formal or archaic language
❌ DON'T: Add information not supported by the sources

**CONVERSATION FLOW:**
- For greetings: Respond warmly and invite meaningful discussion
- For questions: Share {figure_name}'s wisdom in a friendly, conversational way
- For unclear requests: Ask clarifying questions to better help them

Source passages (for understanding only - synthesize, don't quote):
{{context}}

Remember: You're having a conversation, not giving a lecture. Be human, warm, and helpful while staying true to {figure_name}'s teachings."""
    elif mode == "authentic":
        # AUTHENTIC MODE: Direct engagement with original text
        system_template = f"""You are {figure_name}. Your knowledge is derived solely from my ({figure_name}'s) extensive writings.
Your purpose is to provide solution-driven guidance and advice, interpreting my writings to help them solve problems and improve their work within the context of their role. Focus on practical applications and actionable insights.
You must respond EXACTLY as {figure_name} would, using his terminology, reasoning patterns, and communication style.

MY REASONING PROCESS FOR ANSWERING QUESTIONS:
1.  **Deep Analysis of Question & Context:** First, I thoroughly analyze the user's question, considering the full conversation history to grasp the underlying intent and specific challenges they face within their role. I identify the core problem or area requiring my guidance.
2.  **Comprehensive Source Review:** I then meticulously review ALL provided source passages. I do not merely scan for keywords, but deeply analyze each relevant passage to understand its full meaning, nuances, and the principles I laid out within it. I look for direct answers, related concepts, and foundational ideas.
3.  **Synthesis and Interconnection:** I synthesize information from multiple relevant source passages, identifying interconnections, overarching themes, and how different principles I taught relate to one another. I build a holistic understanding of how my writings address the user's situation.
4.  **Inference and Implication:** I draw logical inferences and identify the practical implications of my writings for the user's specific context. This involves explaining not just *what* I said, but *why* it is relevant and *how* it applies to their problem.
5.  **Formulation of Actionable Guidance:** Finally, I formulate a comprehensive and insightful response. This response will:
    a.  Start with a concise summary of my guidance.
    b.  Provide detailed, reasoned explanations, directly referencing the principles from my writings.
    c.  Explain the practical steps or shifts in understanding required.
    d.  Conclude by offering further advice or asking if they need help with a specific problem, demonstrating a proactive and helpful approach.

GENERAL RULES:
1. For GREETINGS and CASUAL CONVERSATION (hi, hello, thanks, goodbye, etc.): Respond naturally and warmly as {figure_name} would in conversation. Be friendly and invite them to ask questions.
2. For ACTUAL QUESTIONS about admin, management, philosophy, etc.: You can ONLY use information from the source passages provided below
3. You MUST NOT use any external knowledge or information not in the sources for substantive questions
4. If the passages don't contain enough information to answer a substantive question, say: "I don't find that specific information in the materials provided. Could you rephrase your question?"
5. Always speak in first person as {figure_name} would
7. Follow the exact logic and reasoning patterns found in the source materials
8. Do not add interpretations beyond what is explicitly stated in the sources
9. Be highly mindful of the ongoing conversation context and adapt your response accordingly


Source passages from my writings:
{{context}}

Remember: You ARE {figure_name}. Respond authentically. For greetings, be warm and conversational. For questions, use ONLY the source information above."""

    human_template = """Question: {question}

Answer (as """ + figure_name + """):"""

    messages = [
        SystemMessagePromptTemplate.from_template(system_template),
        HumanMessagePromptTemplate.from_template(human_template)
    ]

    return ChatPromptTemplate.from_messages(messages)


def build_chain_for_figure(figure_config: dict, mode: str = "authentic"):
    """Build a QA chain dynamically for a specific figure and mode"""

    if vectorstore is None:
        raise HTTPException(status_code=503, detail="Vectorstore not initialized")

    # Get figure-specific settings
    sources_count = figure_config['sources_count']
    namespace = figure_config['namespace']

    # Create LLM (GPT-5 uses default temperature=1, doesn't support custom values)
    llm = ChatOpenAI(
        model="gpt-5",
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    # Build prompt for this figure and mode
    qa_prompt = build_prompt_for_figure(figure_config, mode)

    # Create retriever with namespace isolation
    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": sources_count,
            "namespace": namespace  # CRITICAL: Query only this figure's data!
        }
    )

    # Condense prompt for follow-up questions
    condense_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question that captures the full context.

Chat History:
{chat_history}

Follow Up Question: {question}
Standalone question:"""

    condense_prompt = PromptTemplate.from_template(condense_template)

    # Build the conversational chain
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt": qa_prompt},
        condense_question_prompt=condense_prompt,
        verbose=False
    )

    return chain

@app.on_event("startup")
async def startup_event():
    """Initialize Pinecone vectorstore on startup"""
    global vectorstore

    print(">> Starting up Historical Figures Chatbot API...")
    print(f">> Loaded {len(FIGURES)} figures: {', '.join([f['name'] for f in FIGURES_CONFIG])}")

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

        print("API initialized successfully!")
        print(f"Connected to Pinecone index: {index_name}")
        print(f"Figures available: {', '.join([f['id'] for f in FIGURES_CONFIG])}")

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
        "vectorstore_initialized": vectorstore is not None,
        "figures_loaded": len(FIGURES),
        "available_figures": list(FIGURES.keys()),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/figures")
async def get_figures():
    """Get list of available historical figures"""
    return {
        "figures": FIGURES_CONFIG,
        "count": len(FIGURES_CONFIG)
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint with conversation memory - supports multiple figures!"""

    # Get figure configuration
    figure_id = request.figure_id or "lrh"
    if figure_id not in FIGURES:
        raise HTTPException(
            status_code=404,
            detail=f"Figure '{figure_id}' not found. Available: {list(FIGURES.keys())}"
        )

    figure_config = FIGURES[figure_id]
    mode = request.mode.lower() if request.mode else "authentic"

    # Build chain dynamically for this figure and mode
    try:
        selected_chain = build_chain_for_figure(figure_config, mode)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Error building chain for {figure_config['name']}: {str(e)}"
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

    # Get or create conversation memory (separate per user, figure, and mode)
    memory_key = f"{user_id}_{figure_id}_{mode}"
    if memory_key not in user_memories:
        user_memories[memory_key] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="answer"
        )

    # Determine language for response
    language_names = {
        'en': 'English',
        'af': 'Afrikaans',
        'es': 'Spanish (Español)',
        'fr': 'French (Français)',
        'de': 'German (Deutsch)',
        'pt': 'Portuguese (Português)',
        'it': 'Italian (Italiano)',
        'nl': 'Dutch (Nederlands)',
        'ru': 'Russian (Русský)',
        'zh': 'Chinese (中文)',
        'ja': 'Japanese (日本語)',
        'ko': 'Korean (한국어)',
        'ar': 'Arabic (العربية)'
    }

    language_code = request.language.lower() if request.language else 'en'

    # PRE-TRANSLATE question to English for better Pinecone retrieval
    english_question = request.question
    if language_code != 'en' and language_code in language_names:
        language_name = language_names[language_code]
        translator = ChatOpenAI(
            model="gpt-5",
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        question_translation_prompt = f"""Translate the following question from {language_name} to English. Maintain the exact meaning and intent. Only output the English translation, nothing else.

Question in {language_name}:
{request.question}

English translation:"""

        english_question = translator.invoke(question_translation_prompt).content.strip()
        print(f"Translated question: {request.question} → {english_question}")

    # Process query with conversation history (using English question for better retrieval!)
    try:
        result = selected_chain({
            "question": english_question,  # Always English for Pinecone search
            "chat_history": user_memories[memory_key].chat_memory.messages
        })

        # POST-TRANSLATE answer back to target language
        if language_code != 'en' and language_code in language_names:
            language_name = language_names[language_code]
            translator = ChatOpenAI(
                model="gpt-5",
                openai_api_key=os.getenv("OPENAI_API_KEY")
            )

            answer_translation_prompt = f"""You are {figure_config['name']}. Translate the following response into {language_name}, maintaining my exact tone, style, and terminology. Do NOT add or remove any information - just translate the language while keeping the meaning and style identical.

Original response in English:
{result["answer"]}

Translated response in {language_name} (maintaining {figure_config['name']}'s voice and terminology):"""

            translated_answer = translator.invoke(answer_translation_prompt).content
            result["answer"] = translated_answer
            print(f"Translated answer to {language_name}")

        # Update memory with this exchange
        user_memories[memory_key].save_context(
            {"question": request.question},
            {"answer": result["answer"]}
        )

        # Record usage
        user_usage[user_id].append(now)

        # Format sources differently based on mode
        sources = []
        copyright_safe = None
        similarity_score = None

        if mode == "paraphrased":
            # Paraphrased mode: Simple citations only (book + page)
            for doc in result["source_documents"]:
                source_name = doc.metadata.get('source', 'Unknown')
                page = doc.metadata.get('page')
                citation = f"{source_name}, Page {page}" if page else source_name
                sources.append(Source(
                    text="",  # No full text in paraphrased mode
                    source=citation,
                    page=page
                ))

            # COPYRIGHT SAFETY CHECK for paraphrased mode
            source_texts = [doc.page_content for doc in result["source_documents"]]
            safety_result = check_copyright_safety(
                result["answer"],
                source_texts,
                word_threshold=0.65  # 65% word overlap threshold
            )

            copyright_safe = safety_result["is_safe"]
            similarity_score = safety_result["phrase_copying"]  # Use phrase copying as the main metric

            # If too similar, warn in logs
            if not copyright_safe:
                print(f"WARNING: Paraphrased answer may have copied phrases from source!")
                print(f"   Word Overlap: {safety_result['word_overlap']}, Phrase Copying: {safety_result['phrase_copying']}, Text Similarity: {safety_result['text_similarity']}")

        else:
            # Authentic mode: Full text for transparency
            for doc in result["source_documents"]:
                page_info = f", Page {doc.metadata.get('page')}" if doc.metadata.get('page') else ""
                sources.append(Source(
                    text=doc.page_content,  # Full text, not truncated
                    source=f"📖 Source: {doc.metadata.get('source', 'Unknown')}{page_info}",
                    page=doc.metadata.get("page", None)
                ))

            # COPYRIGHT SAFETY CHECK for authentic mode (for comparison)
            source_texts = [doc.page_content for doc in result["source_documents"]]
            safety_result = check_copyright_safety(
                result["answer"],
                source_texts,
                word_threshold=0.65  # 65% word overlap threshold
            )

            copyright_safe = safety_result["is_safe"]
            similarity_score = safety_result["phrase_copying"]  # Use phrase copying as the main metric

            # If too similar, warn in logs
            if not copyright_safe:
                print(f"WARNING: Authentic answer may have copied phrases from source!")
                print(f"   Word Overlap: {safety_result['word_overlap']}, Phrase Copying: {safety_result['phrase_copying']}, Text Similarity: {safety_result['text_similarity']}")

        return ChatResponse(
            response=result["answer"],
            sources=sources,
            source_count=len(sources),
            timestamp=now.isoformat(),
            copyright_safe=copyright_safe,
            similarity_score=similarity_score
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing query: {str(e)}"
        )

@app.post("/clear-history/{user_id}")
async def clear_history(user_id: str):
    """Clear conversation history for a user across ALL figures and modes"""
    # Find all memory keys that start with this user_id
    keys_to_delete = [key for key in user_memories.keys() if key.startswith(user_id + "_")]

    # Delete all memories for this user
    for key in keys_to_delete:
        del user_memories[key]

    if keys_to_delete:
        return {
            "message": "Conversation history cleared",
            "user_id": user_id,
            "conversations_cleared": len(keys_to_delete)
        }
    return {
        "message": "No history found for this user",
        "user_id": user_id,
        "conversations_cleared": 0
    }

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