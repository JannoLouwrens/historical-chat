# Historical Figures Chatbot

An educational chatbot that lets users converse with historical personas using RAG (Retrieval-Augmented Generation) and vector search.

## Live Demo

**Try it now:** [http://84.8.128.149](http://84.8.128.149)

Chat with Marcus Aurelius, Seneca, Bertrand Russell, and more!

**Author:** Janno Louwrens
**Created:** 2025

## Overview

This project creates an interactive learning experience where users can have conversations with historical figures. The system uses:

- **RAG Architecture** - Retrieves relevant passages from historical writings
- **Vector Search** - Pinecone for semantic similarity matching
- **LangChain** - Orchestrates LLM interactions with context
- **Multi-Persona Support** - Each figure has unique personality prompts

## Design Rationale

The core idea was to make historical texts conversational without losing accuracy. I chose a RAG architecture so every response is grounded in primary sources, then layered persona prompts on top to preserve the tone of each figure while keeping the output verifiable.

As the system grew, I added memory per user, citation handling, and a lightweight copyright safety check to keep paraphrased responses original. The end result is a deployable stack that balances educational authenticity with practical guardrails for real-world use.

## Features

- **Multi-Persona Chat** - Multiple historical figures with distinct personalities
- **Per-User Memory** - Conversation history persists per user per figure
- **Source Citations** - Every response includes source passages
- **Two Response Modes**:
  - **Authentic** - Direct quotes from source material
  - **Paraphrased** - AI-generated responses in the figure's style
- **Copyright Safety Checker** - Ensures paraphrased content isn't too similar to sources
- **Rate Limiting** - Per-user usage tracking
- **Multi-Language Support** - Configurable language output

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Frontend                              │
│                  (Static HTML/JS - Netlify)                     │
└─────────────────────────────┬───────────────────────────────────┘
                              │ API Calls
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
│                    (Oracle Cloud VM)                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  LangChain  │  │  OpenAI     │  │    Pinecone             │ │
│  │  Chains     │──│  GPT-4o     │──│    Vector Store         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│         │                                      ▲                 │
│         │         ┌─────────────┐              │                 │
│         └────────▶│  Supabase   │──────────────┘                │
│                   │  (Memory)   │  Document Embeddings          │
│                   └─────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
historical-figures-chatbot/
├── api/
│   ├── main.py              # FastAPI application
│   └── figures/
│       └── config.json      # Figure personalities and prompts
├── web/                     # Frontend static files
├── scripts/                 # Utility scripts
├── requirements.txt
└── README.md
```

## Technologies

- **Backend**: FastAPI, Python 3.9+
- **LLM**: OpenAI GPT-4o (via LangChain)
- **Vector Store**: Pinecone
- **Memory**: Supabase
- **Frontend**: Static HTML/JS
- **Deployment**: Render.com (API), Netlify (Web)

## Installation

### Prerequisites
- Python 3.9+
- OpenAI API key
- Pinecone API key
- Supabase project (for memory)

### Setup

```bash
# Clone repository
git clone https://github.com/JannoLouwrens/historical-chat.git
cd historical-chat

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
cd api
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

```bash
OPENAI_API_KEY=sk-your-openai-key
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENVIRONMENT=gcp-starter
PINECONE_INDEX_NAME=your-index-name
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
```

## Usage

### Start API Server

```bash
cd api
uvicorn main:app --reload --port 8000
```

### API Endpoints

**POST /chat**
```json
{
  "question": "What is your view on education?",
  "user_id": "user123",
  "figure_id": "socrates",
  "mode": "paraphrased",
  "max_sources": 3
}
```

**Response:**
```json
{
  "response": "Education, in my view, is not the filling of a vessel...",
  "sources": [
    {"text": "...", "source": "Republic", "page": 42}
  ],
  "source_count": 3,
  "copyright_safe": true,
  "similarity_score": 0.35
}
```

## Copyright Safety

The paraphrased mode includes a copyright safety checker:

- **Word Overlap Check** - Ensures lexical similarity is below threshold
- **N-gram Analysis** - Detects copied phrases
- **Lightweight** - Pure Python, no heavy ML models

This ensures generated content doesn't infringe on source material copyrights while still conveying the ideas.

## Adding New Figures

1. Add figure configuration to `api/figures/config.json`
2. Upload source documents to Pinecone with appropriate metadata
3. Configure personality prompts

## Deployment

- **API**: Oracle Cloud VM (free tier)
- **Frontend**: Netlify (static hosting)
- **Vector Store**: Pinecone (serverless)
- **Database**: Supabase (free tier)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for project history and architecture decisions.

## License

MIT License
