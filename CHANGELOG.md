# Changelog

## Project Evolution

### Phase 4: Cleanup & Oracle Deployment (Jan 2025)
- `9250b15` - Cleaned up project structure, removed redundant docs
- `c169017` - Migrated API hosting to Oracle Cloud VM (free tier)

### Phase 3: LangChain Compatibility Fixes (Nov 2024)
- `72eeab6` - Pinned langchain to 0.3.7 for ConversationalRetrievalChain
- `ee9fbce` - Fixed imports for langchain v1.1.0 breaking changes
- `09653ba` - Fixed f-string syntax errors with nested quotes

### Phase 2: Model & Content Updates (Oct-Nov 2024)
- `5226ef3` - Upgraded to GPT-4o (initially tried GPT-5 which doesn't exist)
- `a7c30c3` - Fixed model name from gpt-5 to gpt-4o-mini
- `8810979` - Added 4 Buddhist/philosophical figures (Buddha, Dalai Lama, Thich Nhat Hanh, Alan Watts)
- `73705a7` - Improved paraphrased mode prompts for more natural conversation

### Phase 1: Core Features (Oct 2024)
- `b807979` - Added Google OAuth authentication via Supabase
- `d6679de` - Fixed authentication bugs, improved error handling
- `686d514` - Implemented conversation history persistence
- `b06bf34` - Fixed UUID generation for browser compatibility

### Initial Development
- RAG architecture with Pinecone vector search
- Multi-persona support with personality prompts
- Two response modes: Authentic (quotes) and Paraphrased (AI-generated)
- Copyright safety checker for paraphrased content
- Per-user memory via Supabase

## Architecture Decisions

**Why RAG over fine-tuning?**
- Responses grounded in actual source texts (verifiable)
- Easy to add new figures without retraining
- Citations provide educational value

**Why Oracle Cloud over Render?**
- Free tier VM with more control
- Can run background processes
- Better for long-running API server

**Why Pinecone + Supabase?**
- Pinecone: Optimized for vector similarity search
- Supabase: Free PostgreSQL with auth built-in
- Both have generous free tiers
