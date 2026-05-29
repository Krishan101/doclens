# BLUEPRINT.md — DocLens: Document-Grounded RAG Application

---

## 1. Project Overview

DocLens is a document-centric RAG (Retrieval-Augmented Generation) web application where users upload PDF or text files, ask natural language questions, and receive AI-generated answers grounded in the document with visible source attribution. Unlike typical chat-based RAG demos, the document itself is the primary interface element — answers point back into the text via highlighted source passages, making the system transparent and trustworthy. The architecture prioritizes retrieval quality over LLM cleverness: a well-chunked document with honest similarity thresholds beats a powerful model hallucinating from weak context. Every design choice — from pgvector as a native Postgres column to character-offset metadata on chunks — serves this grounding-first philosophy. The result is a system that an interviewer can `docker compose up` in under two minutes and immediately see the difference between "RAG tutorial" and "production-minded engineering."

**Core thesis:** The source-highlighting interaction — where answers visually connect back to specific passages in the document view — is the single feature that elevates this from a weekend project to a portfolio piece. It demonstrates understanding of RAG's core value proposition (grounding), requires thoughtful schema design (character offsets, chunk metadata), and produces a UI that is impossible to mistake for a ChatGPT clone.

---

## 2. Tech Stack (Final, Locked In)

| Layer | Choice | Rationale |
|---|---|---|
| **Frontend** | React 18 + Vite + TypeScript | Fast builds, no SSR overhead, Vite HMR for dev speed |
| **Styling** | Tailwind CSS 3 | Utility-first, responsive, zero-cost abstraction, fully free |
| **HTTP Client** | Axios | Interceptors for JWT refresh, cleaner than fetch for error handling |
| **Backend** | FastAPI + Python 3.11 | Required by spec; async support, Pydantic validation, auto-docs |
| **Database** | PostgreSQL 16 + pgvector 0.7+ | Required by spec; vectors as native columns, relational integrity |
| **Migrations** | Alembic | Industry standard for SQLAlchemy, version-controlled schema changes |
| **ORM** | SQLAlchemy 2.0 (async) | Type-safe models, async session support, pgvector integration |
| **LLM (Primary)** | Llama 3.3 70B via Groq free tier | Best free inference; 128K context, ~300 tok/s, 1,000 RPD, 6K TPM |
| **LLM (Fallback)** | Llama 3.1 8B via Groq free tier | Separate RPD pool — doubles effective daily budget to 2,000 RPD |
| **LLM (Offline)** | Llama 3.2 3B via Ollama | Fully offline fallback; documented, configurable via env var |
| **Embeddings** | `all-MiniLM-L6-v2` via sentence-transformers | 384-dim, ~80MB, fast on CPU, multilingual-capable, proven for RAG |
| **PDF Extraction** | pdfplumber | Superior table extraction over PyMuPDF; handles structured content |
| **Auth** | python-jose + passlib[bcrypt] | JWT creation/verification + secure password hashing; fully free |
| **Redis** | Yes — included in Docker Compose | Three specific uses: (1) embedding cache for repeated similar queries, (2) Groq rate-limit + token budget tracking to preempt 429/exhaustion errors, (3) per-user daily query counter. Not used for sessions (JWT is stateless). |
| **Dev/Deploy** | Docker Compose (4 containers) | One-command startup: `docker compose up --build` |

### Key Libraries (All Free/Open-Source)

**Backend:**
- `fastapi`, `uvicorn[standard]` — ASGI server
- `sqlalchemy[asyncio]`, `asyncpg` — async Postgres driver
- `alembic` — migrations
- `pgvector` (Python package) — SQLAlchemy pgvector type
- `pdfplumber` — PDF text + table extraction
- `sentence-transformers` — local embedding model
- `groq` — Groq API client (free tier)
- `python-jose[cryptography]` — JWT encoding/decoding
- `passlib[bcrypt]` — password hashing
- `redis[hiredis]` — Redis client with C parser
- `python-multipart` — file upload handling

**Frontend:**
- `react`, `react-dom` — UI framework
- `react-router-dom` — client-side routing
- `axios` — HTTP client
- `tailwindcss`, `postcss`, `autoprefixer` — styling
- `lucide-react` — icon library (MIT licensed, free)
- `@tanstack/react-query` — server state management, polling, caching

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Port 5173)                     │
│                   React + Vite + TypeScript + Tailwind           │
│                                                                 │
│  ┌──────────────┐  ┌────────────────────────────────────────┐   │
│  │  Auth Views   │  │         Document Workspace             │   │
│  │  /login       │  │  ┌─────────────────┐ ┌─────────────┐  │   │
│  │  /signup      │  │  │  Document View   │ │ Query Panel  │  │   │
│  └──────────────┘  │  │  (65% width)     │ │ (35% width) │  │   │
│                    │  │  Parsed text with │ │ Question    │  │   │
│                    │  │  chunk boundaries │ │ input +     │  │   │
│                    │  │  + highlights     │ │ Q&A history │  │   │
│                    │  └─────────────────┘ └─────────────┘  │   │
│                    └────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API (JWT Bearer token in headers)
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                     FASTAPI BACKEND (Port 8000)                 │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Auth     │  │  Document    │  │  Query Service            │  │
│  │ Service  │  │  Service     │  │                           │  │
│  │          │  │              │  │  1. Embed question        │  │
│  │ JWT issue│  │ Upload →     │  │  2. pgvector similarity   │  │
│  │ JWT verify│ │ Extract →    │  │  3. Relevance threshold   │  │
│  │ Password │  │ Chunk →      │  │  4. Build prompt          │  │
│  │ hashing  │  │ Embed →      │  │  5. Call LLM (Groq)       │  │
│  │          │  │ Store        │  │  6. Return answer+sources │  │
│  └────┬─────┘  └──────┬──────┘  └────────┬──────────────────┘  │
│       │               │                   │                     │
│  ┌────▼───────────────▼───────────────────▼──────────────────┐  │
│  │              Repository Layer (SQLAlchemy)                 │  │
│  └────┬───────────────┬───────────────────┬──────────────────┘  │
└───────┼───────────────┼───────────────────┼─────────────────────┘
        │               │                   │
   ┌────▼────┐   ┌──────▼──────┐   ┌───────▼────────┐
   │Postgres │   │  Sentence   │   │   Groq API     │
   │+pgvector│   │  Transformers│   │  (Llama 3.3    │
   │         │   │  (local)    │   │   70B)         │
   │ users   │   │             │   │                │
   │ documents│   │ all-MiniLM- │   │  ┌───────────┐│
   │ chunks  │   │ L6-v2       │   │  │  Ollama   ││
   │ queries │   │ 384-dim     │   │  │ (fallback)││
   └─────────┘   └─────────────┘   │  └───────────┘│
                                    └───────────────┘
   ┌─────────┐
   │  Redis  │
   │         │
   │ embed   │
   │ cache + │
   │ rate    │
   │ limits  │
   └─────────┘
```

### Component Responsibilities

| Component | Responsibility |
|---|---|
| **Auth Service** | JWT token issue/verify, password hashing, signup/login validation |
| **Document Service** | File upload validation, PDF text extraction, chunking, embedding generation, storage orchestration |
| **Query Service** | Question embedding, pgvector similarity search, relevance filtering, prompt construction, LLM invocation, response formatting |
| **Repository Layer** | All database operations via SQLAlchemy async sessions; no SQL in service layer |
| **Sentence Transformers** | Local embedding model loaded once at startup, shared across requests |
| **Groq API** | Remote LLM inference — all calls routed through GroqBudgetManager |
| **Groq Budget Manager** | Tracks RPM + daily token usage in Redis, selects model tier, throttles/rejects when approaching limits, reads 429 headers to adapt |
| **Redis** | Embedding cache (TTL 1 hour) + Groq budget counters (RPM, TPM, daily tokens, daily requests) |

### Data Flow

```
UPLOAD FLOW:
User selects file
  → POST /api/documents (multipart form, JWT header)
  → Validate file type + size (≤20MB, .pdf or .txt)
  → Create document record (status: "processing")
  → Return 202 { document_id, status: "processing" }
  → BackgroundTask kicks off:
      → pdfplumber extracts text page-by-page
      → Validate: if <50 chars/page average → status: "failed" (image-only PDF)
      → RecursiveCharacterTextSplitter → chunks (512 tok, 50 tok overlap)
      → pdfplumber.extract_tables() → markdown-formatted table chunks (atomic)
      → sentence-transformers embeds each chunk → 384-dim vectors
      → Bulk INSERT chunks + vectors into pgvector
      → Update document status: "ready"
  → Frontend polls GET /api/documents/{id} every 2s until status ≠ "processing"

QUERY FLOW:
User types question
  → POST /api/queries { document_id, question }
  → Enrich query if vague (prepend last Q&A for short/pronominal queries)
  → Embed enriched query via sentence-transformers (check Redis cache first)
  → pgvector: SELECT chunks WHERE document_id = $1 ORDER BY embedding <=> $2 LIMIT 5
  → Check: if best_similarity < 0.3 → return "no relevant info" (skip LLM)
  → Trim chunks to 2000-token context budget (drop lowest-relevance first)
  → Construct prompt: terse system instructions + [SOURCE 1]..[SOURCE N] + question
  → Budget check: select model (70B primary, 8B when 70B RPD exhausted), enforce TPM spacing
  → Call Groq API with selected model, 30s timeout
  → Parse response, store in queries table with retrieved_chunk_ids
  → Return { answer, sources: [{ chunk_id, content, page_number, char_start, char_end, similarity }] }
  → Frontend renders answer + highlights source chunks in document view
```

---

## 4. Database Schema

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    hashed_pw   VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- DOCUMENTS
-- ============================================================
CREATE TABLE documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename    VARCHAR(255) NOT NULL,
    file_type   VARCHAR(10) NOT NULL,          -- 'pdf' or 'txt'
    file_size   INTEGER NOT NULL,              -- bytes
    raw_text    TEXT,                           -- full extracted text (for re-chunking)
    page_count  INTEGER,
    status      VARCHAR(20) NOT NULL DEFAULT 'processing',
                -- 'processing' | 'ready' | 'failed' | 'empty'
    error_msg   VARCHAR(500),                  -- populated on failure
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_status ON documents(status);

-- ============================================================
-- CHUNKS
-- ============================================================
CREATE TABLE chunks (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content      TEXT NOT NULL,
    chunk_type   VARCHAR(20) NOT NULL DEFAULT 'text',  -- 'text' | 'table'
    chunk_index  INTEGER NOT NULL,             -- ordering within document
    page_number  INTEGER,
    char_start   INTEGER NOT NULL,             -- offset in raw_text
    char_end     INTEGER NOT NULL,             -- offset in raw_text
    token_count  INTEGER,
    embedding    vector(384) NOT NULL          -- all-MiniLM-L6-v2 output
);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_embedding ON chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- QUERIES
-- ============================================================
CREATE TABLE queries (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id        UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    question           TEXT NOT NULL,
    enriched_question  TEXT,                    -- after vague-query expansion
    answer             TEXT NOT NULL,
    confidence         VARCHAR(10) NOT NULL DEFAULT 'high',
                       -- 'high' | 'medium' | 'low' | 'none'
    retrieved_chunk_ids UUID[] NOT NULL,        -- ordered by relevance
    llm_model          VARCHAR(50),             -- e.g. 'llama-3.3-70b-versatile'
    prompt_tokens      INTEGER,
    completion_tokens  INTEGER,
    latency_ms         INTEGER,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_queries_document_id ON queries(document_id);
CREATE INDEX idx_queries_user_id ON queries(user_id);
```

### Schema Design Notes

- **UUIDs everywhere:** Prevents enumeration attacks on user/document IDs. Slightly larger than serial ints but worth it for a security-conscious design.
- **`ON DELETE CASCADE` on all FKs:** Deleting a user removes all their documents, chunks (including vectors), and queries atomically. No orphaned data.
- **`raw_text` on documents:** Stores the full extracted text so we can re-chunk without re-uploading. Costs storage but enables iteration on chunk strategy.
- **`char_start`/`char_end` on chunks:** These character offsets are the backbone of the source-highlighting feature. They map each chunk back to its position in the original document text.
- **`chunk_type` on chunks:** Distinguishes text chunks from table chunks, enabling different rendering in the UI.
- **`retrieved_chunk_ids` as UUID array:** Audit trail linking each answer to its source chunks. Enables "past questions" display without re-running retrieval.
- **`confidence` on queries:** Derived from the highest similarity score among retrieved chunks. Drives UI treatment (muted styling for low-confidence answers).
- **`ivfflat` index with `lists = 100`:** Suitable for up to ~100K vectors. For MVP scale (thousands), this is more than sufficient. HNSW would be reconsidered at 1M+.

---

## 5. API Endpoints

### Authentication

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/signup` | No | Create account |
| `POST` | `/api/auth/login` | No | Get JWT access token |

```python
# POST /api/auth/signup
# Request
{ "email": "user@example.com", "password": "securepass123" }
# Response 201
{ "id": "uuid", "email": "user@example.com", "created_at": "iso8601" }

# POST /api/auth/login
# Request
{ "email": "user@example.com", "password": "securepass123" }
# Response 200
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400 }
```

### Documents

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/documents` | Yes | Upload file, begin processing |
| `GET` | `/api/documents` | Yes | List user's documents |
| `GET` | `/api/documents/{id}` | Yes | Get document details + status |
| `GET` | `/api/documents/{id}/chunks` | Yes | Get all chunks (for document view rendering) |
| `DELETE` | `/api/documents/{id}` | Yes | Delete document + all chunks and queries |

```python
# POST /api/documents (multipart/form-data)
# Request: file field with .pdf or .txt
# Response 202
{
  "id": "uuid",
  "filename": "contract.pdf",
  "status": "processing",
  "created_at": "iso8601"
}

# GET /api/documents/{id}
# Response 200
{
  "id": "uuid",
  "filename": "contract.pdf",
  "status": "ready",            # or "processing" | "failed" | "empty"
  "page_count": 12,
  "chunk_count": 47,
  "file_size": 2048576,
  "error_msg": null,
  "created_at": "iso8601"
}

# GET /api/documents/{id}/chunks
# Response 200
{
  "chunks": [
    {
      "id": "uuid",
      "content": "Section 3.1 Termination...",
      "chunk_type": "text",
      "chunk_index": 0,
      "page_number": 1,
      "char_start": 0,
      "char_end": 487
    }
    # ...
  ]
}
```

### Queries

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/queries` | Yes | Ask a question about a document |
| `GET` | `/api/queries?document_id={id}` | Yes | Get past queries for a document |

```python
# POST /api/queries
# Request
{
  "document_id": "uuid",
  "question": "What are the termination conditions?"
}
# Response 200
{
  "id": "uuid",
  "question": "What are the termination conditions?",
  "answer": "Based on Section 3.1, the contract can be terminated under three conditions...",
  "confidence": "high",
  "sources": [
    {
      "chunk_id": "uuid",
      "content": "Section 3.1 Termination. Either party may terminate...",
      "chunk_type": "text",
      "page_number": 4,
      "char_start": 3201,
      "char_end": 3687,
      "similarity": 0.82
    }
    # ... up to 5 sources
  ],
  "latency_ms": 1847,
  "model_used": "llama-3.3-70b-versatile",
  "budget": {
    "remaining_pct": 73,
    "model_tier": "primary",
    "daily_reset_utc": "2026-01-15T00:00:00Z"
  },
  "created_at": "iso8601"
}
```

### Health & Budget

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | No | Readiness check (DB + embedding model + Redis) |
| `GET` | `/api/budget` | Yes | Current Groq usage: RPM, daily tokens used/remaining, active model tier |

```python
# GET /api/budget
# Response 200
{
  "primary_model": "llama-3.3-70b-versatile",
  "primary_requests_today": 47,
  "primary_remaining": 903,
  "fallback_model": "llama-3.1-8b-instant",
  "fallback_requests_today": 0,
  "fallback_remaining": 950,
  "total_remaining": 1853,
  "remaining_pct": 97,
  "active_model": "llama-3.3-70b-versatile",
  "resets_at": "2026-01-15T00:00:00Z"
}
```

---

## 6. Frontend Architecture

### Page/View Structure

```
/login          → LoginPage          (public)
/signup         → SignupPage          (public)
/               → DashboardPage       (protected — document list + upload)
/doc/:id        → WorkspacePage       (protected — the main document workspace)
```

### Component Tree

```
<App>
├── <AuthProvider>              // JWT token state, login/logout, axios interceptor
│   ├── <PublicRoute>
│   │   ├── <LoginPage />
│   │   └── <SignupPage />
│   └── <ProtectedRoute>
│       ├── <DashboardPage>
│       │   ├── <UploadZone />           // Drag-and-drop + click upload
│       │   └── <DocumentList>
│       │       └── <DocumentCard />     // Filename, status badge, date, delete
│       └── <WorkspacePage>
│           ├── <WorkspaceHeader />      // Doc name, back button, status
│           ├── <DocumentPanel>          // 65% width on desktop
│           │   ├── <PageDivider />      // "— Page N —" separators
│           │   └── <ChunkBlock />       // Rendered text chunk with highlight state
│           └── <QueryPanel>             // 35% width on desktop
│               ├── <QueryInput />       // Text input + submit button
│               ├── <ActiveAnswer>       // Current answer + source pills
│               │   ├── <AnswerText />
│               │   ├── <ConfidenceBadge />
│               │   └── <SourcePill />   // Clickable → scrolls to chunk
│               └── <QueryHistory>       // Previous Q&A pairs, collapsed
│                   └── <QueryHistoryItem />
```

### State Management

No Redux, no Zustand. Keep it simple with two layers:

- **Server state:** `@tanstack/react-query` for all API calls. Handles caching, polling (document status), refetching, and loading/error states. This is the primary state management tool.
- **UI state:** React `useState` / `useContext` for local concerns:
  - `AuthContext` — JWT token, user info, login/logout functions
  - `HighlightContext` — which chunk IDs are currently highlighted (set by clicking source pills, cleared on new query)

```typescript
// Key query hooks
useDocuments()                    // GET /api/documents — dashboard list
useDocument(id)                   // GET /api/documents/{id} — polling for status
useDocumentChunks(id)             // GET /api/documents/{id}/chunks — document view
useDocumentQueries(id)            // GET /api/queries?document_id={id} — history
useAskQuestion()                  // POST /api/queries — mutation
```

### UI Concept: Document-Centric Design

**Layout principle:** The document is the hero. The query panel is a *tool* for exploring the document, not the main event. Think of it like a code editor with a terminal sidebar — the code (document) is primary, the terminal (query panel) is supplementary.

**Visual language:**
- Color palette: Warm neutrals (stone/slate from Tailwind) with a single accent color (amber-500) used exclusively for source highlights
- Typography: `font-mono` for chunk content (feels like reading a parsed document), `font-sans` for UI chrome
- No chat bubbles, no avatars, no typing indicators
- Answers render as structured blocks with a left border accent, not message bubbles
- Source pills are small clickable badges: `[Page 4, ¶3]` style

**Responsive behavior:**
- Desktop (≥1024px): Side-by-side split, 65/35
- Tablet (768–1023px): Side-by-side split, 55/45
- Mobile (<768px): Stacked vertically — document on top, query panel below, with a sticky "Ask" button that scrolls to the query input

**Empty states (all must be designed):**

| State | Design |
|---|---|
| No documents yet | Centered upload zone with drag-drop, icon, "Upload your first document" |
| Document processing | Pulsing skeleton loader with status text ("Extracting text...", "Generating embeddings...") |
| Document ready, no queries | Subtle prompt in query panel: "Ask a question about this document" with 2–3 example questions generated from first chunk |
| No relevant results (low similarity) | Muted answer block: "I couldn't find relevant information for this question in the document." |
| LLM error | Error card with retry button: "The AI service is temporarily unavailable. Please try again." |
| Rate limited | Countdown timer: "Rate limit reached. Please wait {n} seconds." |

---

## 7. RAG Pipeline (Step-by-Step)

### Upload Processing

```
1. VALIDATE
   - File type: accept only .pdf, .txt (check MIME type + extension)
   - File size: reject >20MB with 413 response
   - User auth: verify JWT, extract user_id

2. EXTRACT TEXT
   - PDF: pdfplumber → iterate pages → page.extract_text()
     - Also run page.extract_tables() for each page
     - Convert tables to markdown format: "| col1 | col2 |\n|---|---|\n| val1 | val2 |"
   - TXT: read as UTF-8 with fallback encoding detection (chardet)
   - Store concatenated text in documents.raw_text

3. VALIDATE EXTRACTION
   - Calculate: total_chars / page_count
   - If < 50 chars/page average → set status="failed", error_msg="image-only PDF"
   - If total_chars == 0 → set status="empty"

4. CHUNK
   - Text content: RecursiveCharacterTextSplitter
     - chunk_size=512 tokens (~2048 chars)
     - chunk_overlap=50 tokens (~200 chars)
     - separators=["\n\n", "\n", ". ", " ", ""]
   - Table content: each table is ONE atomic chunk (no splitting)
     - chunk_type="table"
   - Record char_start, char_end for every chunk (offsets into raw_text)
   - Record page_number for every chunk

5. EMBED
   - Load model once at app startup: SentenceTransformer('all-MiniLM-L6-v2')
   - Batch encode all chunks: model.encode(texts, batch_size=32, normalize_embeddings=True)
   - ~50ms per chunk on CPU, ~2s for a 40-chunk document

6. STORE
   - Bulk INSERT into chunks table (content + metadata + embedding vector)
   - Update document status → "ready"
```

### Chunking Strategy Details

| Parameter | Value | Reasoning |
|---|---|---|
| Chunk size | 512 tokens | Balance between context richness and retrieval precision. Smaller chunks retrieve more precisely but lose context. Larger chunks are noisier. 512 is the empirical sweet spot for QA. |
| Overlap | 50 tokens | Prevents information loss at chunk boundaries. Sentences that straddle a split appear in both chunks. |
| Separators | `\n\n` → `\n` → `. ` → ` ` | Prefer splitting at paragraph breaks, then sentences. Never split mid-word. |
| Table handling | Atomic chunks | Tables lose meaning when split. A single table chunk may exceed 512 tokens — that's acceptable. |

### Query-Time Pipeline

```
1. ENRICH QUERY (if needed)
   - If question is short (<5 words) or contains pronouns without referent
     ("it", "this", "that", "more"):
     - Fetch last query for this document from queries table
     - Prepend: "Previous Q: {last_q}\nPrevious A: {last_a}\nFollow-up: {question}"
     - Embed the enriched version, not the raw question

2. EMBED QUESTION
   - Check Redis cache: key = f"embed:{hash(question_text)}"
   - Cache hit → use cached vector (saves ~50ms)
   - Cache miss → model.encode(question, normalize_embeddings=True)
   - Cache result with TTL=3600s

3. VECTOR SEARCH
   - Query pgvector with document_id filter:
     SELECT id, content, chunk_type, page_number, char_start, char_end,
            1 - (embedding <=> $query_vec) AS similarity
     FROM chunks
     WHERE document_id = $doc_id
     ORDER BY embedding <=> $query_vec
     LIMIT 5
   - The WHERE clause ensures we only search within the user's document

4. RELEVANCE GATE
   - If top result similarity < 0.3:
     → Skip LLM entirely
     → Return { answer: "I couldn't find relevant information...",
                confidence: "none", sources: [] }
   - If top result similarity 0.3–0.5:
     → Proceed but set confidence: "low"
   - If top result similarity > 0.5:
     → confidence: "high"

5. CONTEXT BUDGET TRIMMING
   - MAX_CONTEXT_TOKENS = 2000 (aggressive — TPM is only 6,000/min total)
   - Iterate through retrieved chunks (sorted by similarity descending)
   - Accumulate token counts; stop adding when budget is exceeded
   - In practice, this means 3-4 chunks of ~512 tokens each
   - Keeps total request (system + context + question + response) under 3,500 tokens
   - Critical for staying under Groq's 6,000 TPM free tier limit

6. PROMPT CONSTRUCTION (token-efficient — every token counts under TPM)
   System prompt (terse — saves ~100 tokens vs verbose version):
   """
   Answer based ONLY on the SOURCE passages below.
   Cite sources as [SOURCE N]. If the context doesn't cover the question, say so.
   Never add outside information. Be concise.
   """

   User prompt:
   """
   [SOURCE 1] (p.{n}): {chunk_content}
   [SOURCE 2] (p.{n}): {chunk_content}
   ...

   Q: {user_question}
   """

   Note: we strip similarity scores from the prompt (saves tokens).
   Page numbers use abbreviated format "p.4" not "Page 4, similarity: 0.82".

7. GROQ BUDGET CHECK (before calling LLM)
   - Enforce minimum 2.5s spacing since last LLM call (TPM protection)
   - Select model: check RPD for 70B first, fall back to 8B if exhausted
   - If both models' RPD exhausted → reject with reset countdown
   - Estimate prompt tokens: len(system + context + question) // 4
   - Set max_tokens = min(512, safe margin under TPM)
   - Total per-request budget target: <3,500 tokens (prompt + completion)

8. LLM CALL
   - Client: groq.AsyncGroq(api_key=GROQ_API_KEY, timeout=30.0)
   - Model: selected by budget manager (70B primary, 8B fallback)
   - Temperature: 0.1 (low — we want deterministic, grounded answers)
   - max_tokens: 512 (conservative — TPM is only 6,000/min)
   - On success: record usage in Redis, read response headers for remaining TPM/RPM
   - On 429: read Retry-After, retry once after delay, then fail gracefully
   - On timeout/5xx: return friendly error, don't retry (preserves budget)

9. STORE + RESPOND
   - Save query record with answer, chunk_ids, token counts, latency, model used
   - Return answer + source chunk details + remaining daily budget to frontend
```

### Groq Token Management (Critical)

Groq free tier enforces multiple limits that reset on different schedules. Running
out mid-demo is unacceptable, so we track and manage usage proactively.

**Verified Groq Free Tier Limits (April 2026, per model, per API key):**

| Limit | Llama 3.3 70B | Llama 3.1 8B | Notes |
|---|---|---|---|
| Requests per minute (RPM) | 30 | 30 | Rolling 60s window |
| Tokens per minute (TPM) | 6,000 | 6,000 | Input + output combined — THIS IS THE BOTTLENECK |
| Requests per day (RPD) | 1,000 | 1,000 | Midnight UTC reset — limits are PER MODEL |
| Context window | 128K | 128K | |

**Critical insight: limits are tracked per-model.** Using both Llama 3.3 70B and
Llama 3.1 8B gives us 2,000 RPD combined. The budget manager exploits this by
rotating to the 8B model when the 70B daily budget is spent.

**6,000 TPM is brutally tight for RAG.** A typical RAG query uses ~3,000 tokens of
context + ~200 token question + ~500 token response = ~3,700 tokens. That's 61% of
the per-minute budget in ONE request. At best we can do ~1.5 RAG queries per minute
without hitting TPM. The budget manager must enforce minimum spacing between requests.

⚠️ **Groq does NOT expose RPD remaining in response headers.** We must track daily
request count ourselves in Redis. Headers that ARE available:
- `x-ratelimit-remaining-requests` (RPM remaining)
- `x-ratelimit-remaining-tokens` (TPM remaining)
- `x-ratelimit-reset-requests` (RPM reset timestamp)
- `x-ratelimit-reset-tokens` (TPM reset timestamp)

**Redis Key Schema for Tracking:**

```python
# Keys and their TTLs
"groq:rpm:{model}"                  # INCR per request, EXPIRE 60s
"groq:tpm:{model}"                  # INCRBY token_count, EXPIRE 60s
"groq:daily:reqs:{model}:{date}"    # INCR per request, EXPIRE 86400s
"groq:last_request_ts"              # timestamp of last LLM call (for spacing)
```

**Budget Manager Logic:**

```python
class GroqBudgetManager:
    """
    Sits between QueryService and the Groq client.
    Every LLM call goes through this — no direct Groq calls anywhere else.

    Key insight: limits are PER MODEL. We use both 70B and 8B to get
    2,000 combined RPD instead of 1,000.
    """
    MODEL_PRIMARY = "llama-3.3-70b-versatile"    # best quality
    MODEL_FALLBACK = "llama-3.1-8b-instant"      # separate RPD budget

    RPD_PER_MODEL = 1000           # hard daily cap per model
    RPD_RESERVE = 50               # keep 50 requests in reserve for demos
    TPM_LIMIT = 6000               # tokens per minute (input + output)
    MIN_REQUEST_SPACING_S = 2.5    # minimum seconds between LLM calls
                                   # (ensures we never exceed ~1.5 req/min
                                   #  given 3500+ tokens per RAG query)

    async def select_model(self) -> str:
        """Pick which model to use based on daily budget remaining."""
        primary_used = int(await self.redis.get(
            f"groq:daily:reqs:{self.MODEL_PRIMARY}:{today()}") or 0)
        fallback_used = int(await self.redis.get(
            f"groq:daily:reqs:{self.MODEL_FALLBACK}:{today()}") or 0)

        primary_remaining = self.RPD_PER_MODEL - self.RPD_RESERVE - primary_used
        fallback_remaining = self.RPD_PER_MODEL - self.RPD_RESERVE - fallback_used

        if primary_remaining > 0:
            return self.MODEL_PRIMARY
        elif fallback_remaining > 0:
            return self.MODEL_FALLBACK
        else:
            raise BudgetExhaustedError(
                "Daily AI quota reached for all models. Resets at midnight UTC.",
                reset_time=next_midnight_utc()
            )

    async def pre_request_throttle(self) -> float:
        """
        Enforce minimum spacing between requests to stay under TPM.
        A typical RAG request uses ~3,700 tokens. At 6,000 TPM we can
        safely do ~1.5 requests per minute. Spacing at 2.5s is conservative
        enough for bursty usage while preventing TPM 429s.
        """
        last_ts = await self.redis.get("groq:last_request_ts")
        if last_ts:
            elapsed = time.time() - float(last_ts)
            if elapsed < self.MIN_REQUEST_SPACING_S:
                delay = self.MIN_REQUEST_SPACING_S - elapsed
                await asyncio.sleep(delay)
                return delay
        return 0.0

    async def record_usage(self, model: str, prompt_tokens: int,
                           completion_tokens: int, response_headers: dict):
        """
        Record usage from both our counters AND Groq's response headers.
        Headers give us ground truth for RPM/TPM remaining.
        """
        total = prompt_tokens + completion_tokens
        pipe = self.redis.pipeline()
        pipe.incr(f"groq:daily:reqs:{model}:{today()}")
        pipe.expire(f"groq:daily:reqs:{model}:{today()}", 86400)
        pipe.set("groq:last_request_ts", str(time.time()), ex=120)
        await pipe.execute()

        # Store Groq's own remaining counts for the /api/budget endpoint
        if "x-ratelimit-remaining-tokens" in response_headers:
            await self.redis.set(
                f"groq:header:remaining_tpm:{model}",
                response_headers["x-ratelimit-remaining-tokens"],
                ex=60
            )

    async def get_budget_status(self) -> dict:
        """For GET /api/budget endpoint."""
        primary_used = int(await self.redis.get(
            f"groq:daily:reqs:{self.MODEL_PRIMARY}:{today()}") or 0)
        fallback_used = int(await self.redis.get(
            f"groq:daily:reqs:{self.MODEL_FALLBACK}:{today()}") or 0)

        total_budget = (self.RPD_PER_MODEL - self.RPD_RESERVE) * 2
        total_used = primary_used + fallback_used
        remaining_pct = max(0, round((1 - total_used / total_budget) * 100))

        return {
            "primary_model_requests_today": primary_used,
            "fallback_model_requests_today": fallback_used,
            "total_requests_remaining": total_budget - total_used,
            "remaining_pct": remaining_pct,
            "active_model": self.MODEL_PRIMARY if primary_used < (
                self.RPD_PER_MODEL - self.RPD_RESERVE) else self.MODEL_FALLBACK,
            "resets_at": next_midnight_utc().isoformat()
        }
```

**Token-Minimizing Prompt Strategy:**

Because TPM is so tight, every token in the prompt matters. Specific optimizations:

```python
# 1. Cap context aggressively — 4 chunks instead of 5, ~2,000 token context max
MAX_CONTEXT_TOKENS = 2000   # not 6000 — TPM is the constraint now

# 2. Terse system prompt (saves ~100 tokens vs verbose version)
SYSTEM_PROMPT = """Answer based ONLY on the SOURCE passages below.
Cite sources as [SOURCE N]. If the context doesn't cover the question, say so.
Never add outside information. Be concise."""

# 3. Cap response length
MAX_COMPLETION_TOKENS = 512  # not 1024 — keeps total under 3,000 per request

# 4. Estimate total before sending
estimated_total = prompt_tokens + MAX_COMPLETION_TOKENS
if estimated_total > TPM_LIMIT * 0.8:  # >80% of per-minute budget
    # Trim to fewer chunks
    chunks = chunks[:3]
```

**Fallback Chain:**

```
Request comes in
  → Enforce minimum 2.5s spacing (TPM protection)
  → Check daily RPD for primary model (70B)
     → <950 used → use llama-3.3-70b-versatile (best quality)
     → ≥950 used → switch to llama-3.1-8b-instant (separate 1,000 RPD pool)
  → Check daily RPD for fallback model (8B)
     → <950 used → use llama-3.1-8b-instant
     → ≥950 used → reject: "Daily quota reached. Resets at midnight UTC."
  → On 429 from Groq:
     → Read Retry-After header
     → If TPM-related: wait and retry once
     → If RPD-related: switch models or reject
  → Total effective budget: ~1,900 requests/day across both models
```

**Why per-model tracking is a superpower:** Most developers treat Groq's free
tier as "1,000 requests/day total." But limits are per-model. By routing to
both the 70B and 8B models, we effectively get 2× the daily budget. The 8B model
is the safety net that keeps the app functional after heavy 70B usage.

**Frontend Budget Indicator:**

The API returns `budget_remaining_pct` in every query response. The frontend
renders a subtle indicator in the QueryPanel header:

```
● 73% remaining (~1,387 queries left)        (green dot, >50%)
● 28% remaining (~532 queries left)           (amber dot, 20-50%)
● 8% remaining — using faster model           (red dot, <20%)
● Quota reached — resets in 3h 42m            (grey dot, 0%)
```

This sets user expectations and prevents surprise failures. The remaining
count is the combined RPD across both model pools (70B + 8B).

**Why not just use Ollama as primary to avoid all this?**

Ollama running Llama 3.2 3B locally gives unlimited tokens but dramatically worse
answer quality — small models hallucinate more on RAG synthesis tasks. The dual-model
Groq strategy gives us ~1,900 usable requests/day with 70B quality for the first
~950, then 8B for the rest. That's enough for dozens of demo sessions. Ollama remains
a documented fallback for fully offline usage or if Groq is down.

---

## 8. Build Phases (Ordered, Shippable)

### Phase 1: Core Skeleton (Days 1–2)

**Goal:** First end-to-end flow working — upload a text file, ask a question, get an answer with sources. No auth, no polish.

```
Tasks:
├── Docker Compose: postgres (pgvector), redis, api, frontend
├── Database: Alembic setup + initial migration (all tables)
├── Backend:
│   ├── FastAPI project structure (routes/, services/, repositories/, models/)
│   ├── POST /api/documents — accept .txt only (skip PDF complexity initially)
│   ├── Background task: chunk + embed + store
│   ├── GET /api/documents/{id} — status polling
│   ├── GET /api/documents/{id}/chunks — return chunks
│   ├── POST /api/queries — embed → search → prompt → LLM → respond
│   └── .env config for Groq API key
├── Frontend:
│   ├── Vite + React + TS + Tailwind scaffold
│   ├── Simple upload form → document status → workspace view
│   ├── Document view: render chunks as text blocks
│   ├── Query input → display answer + source chunk IDs
│   └── No styling beyond basic layout
└── Test: upload a .txt file, ask a question, verify answer references sources
```

**Shippable artifact:** Ugly but functional RAG pipeline.

### Phase 2: PDF Support + Auth (Days 3–4)

**Goal:** Real PDF extraction, JWT auth, multi-user isolation.

```
Tasks:
├── Backend:
│   ├── pdfplumber integration for PDF text + table extraction
│   ├── Image-only PDF detection + rejection
│   ├── Auth service: signup, login, JWT issue/verify
│   ├── Auth middleware: protect all /documents and /queries routes
│   ├── User-scoped queries: all document/chunk access filtered by user_id
│   └── File size validation (20MB limit)
├── Frontend:
│   ├── Login + Signup pages
│   ├── AuthContext + axios interceptor for JWT
│   ├── Protected routes
│   ├── Dashboard page with document list
│   └── Upload supports .pdf + .txt
└── Test: two users, each with own documents, cannot see each other's data
```

**Shippable artifact:** Secure, multi-user RAG app with PDF support.

### Phase 3: RAG Quality + Highlighting (Days 5–6)

**Goal:** Source highlighting, hallucination guardrails, query enrichment — the features that differentiate.

```
Tasks:
├── Backend:
│   ├── Relevance threshold gating (similarity < 0.3 → skip LLM)
│   ├── Confidence scoring on query responses
│   ├── Vague query enrichment (prepend last Q&A)
│   ├── Context budget trimming
│   ├── Redis embedding cache
│   ├── GroqBudgetManager: per-model RPD tracking, TPM spacing, dual-model fallback
│   ├── GET /api/budget endpoint (per-model usage + total remaining)
│   ├── 429 error handling with Retry-After header parsing + single retry
│   └── Auto-switch from 70B → 8B model when primary RPD exhausted
├── Frontend:
│   ├── Source highlighting: ChunkBlock gets highlight state
│   ├── Source pills in answer → click scrolls to chunk in document view
│   ├── Scroll-to-chunk with smooth scroll + pulse animation
│   ├── Confidence badge on answers (high/medium/low/none styling)
│   ├── Budget indicator dot in QueryPanel header (green/amber/red)
│   ├── Query history panel (previous Q&A pairs for this document)
│   └── All empty states implemented (including "budget exhausted" state)
└── Test: off-topic questions get rejected, vague follow-ups work,
          source pills scroll correctly, budget indicator changes color
```

**Shippable artifact:** This is the impressive demo. Highlight interaction working, grounding visible.

### Phase 4: UI/UX Refinement (Day 7)

**Goal:** Visual polish, responsive design, error states, README.

```
Tasks:
├── Frontend:
│   ├── Final visual design pass (typography, spacing, color)
│   ├── Responsive layout (mobile stacking)
│   ├── Loading states (skeleton loaders for document processing)
│   ├── Error boundaries (catch React rendering errors)
│   ├── Toast notifications for upload success/failure
│   └── Delete document flow with confirmation
├── Backend:
│   ├── Input validation hardening (Pydantic models for all requests)
│   ├── Consistent error response format
│   └── GET /api/health endpoint
├── Docs:
│   ├── README.md: setup instructions, architecture diagram, env vars
│   ├── Demo GIF or 30-second video
│   └── Known limitations + production improvements
└── Docker: final docker-compose.yml with all env vars documented
```

**Shippable artifact:** Portfolio-ready submission.

### Phase 5: Scale-Readiness (Stretch / Time Permitting)

```
Tasks (pick 1–2 if time allows):
├── Ollama automatic failover (try Groq → on failure, switch to local Ollama)
├── Document re-chunking endpoint (change chunk size without re-upload)
├── Hybrid search: combine pgvector similarity + Postgres full-text BM25 ranking
├── Export query history as JSON/CSV
└── Suggested questions auto-generated from first few chunks
```

---

## 9. Edge Cases & Mitigations

### Top 10 Risks

| # | Risk | Impact | Phase | Mitigation |
|---|---|---|---|---|
| 1 | **Image-only PDF uploaded** — zero text extracted, all queries return garbage | Critical | MVP | Post-extraction validation: if <50 chars/page average, reject with clear error message. Store validation in `documents.status = "failed"` + `error_msg`. |
| 2 | **LLM hallucinates** — generates plausible answer not grounded in sources | Critical | MVP | Three-layer defense: (1) relevance threshold at 0.3 — skip LLM if no good matches, (2) aggressive system prompt with grounding rules, (3) show source chunks + similarity scores in UI so user can verify. |
| 3 | **Groq token/rate exhaustion** — 1,000 RPD per model, 6K TPM — runs out mid-demo | Critical | MVP | `GroqBudgetManager` exploits per-model limits: routes to 70B first (1,000 RPD), then 8B (separate 1,000 RPD) = ~1,900 usable/day. Enforces 2.5s inter-request spacing for TPM. Terse prompts + 2K context budget minimize tokens per request. Frontend shows remaining budget. See "Groq Token Management" in Section 7. |
| 4 | **Large PDF blocks request** — 200 pages, 60s embedding time, HTTP timeout | High | MVP | `BackgroundTasks` with 202 Accepted pattern. Frontend polls status. File size cap at 20MB. Status text shows processing stage. |
| 5 | **Question spans many chunks** — synthesis questions need >5 chunks | High | MVP | Retrieve top 8 chunks for broad questions. Context budget trimming prevents overflow. System prompt instructs LLM to state when information may be incomplete. |
| 6 | **Vague follow-up question** — "tell me more" embeds to meaningless vector | Medium | MVP | Detect short/pronominal queries. Prepend last Q&A context before embedding. Enriched query stored in `queries.enriched_question` for debugging. |
| 7 | **Tables in PDF mangled by extraction** — structured data becomes noise | Medium | MVP | pdfplumber `extract_tables()` → markdown format → atomic chunks with `chunk_type="table"`. Rendered differently in UI. |
| 8 | **User deletes account — orphaned vectors** | Medium | MVP | `ON DELETE CASCADE` on all foreign keys. One DELETE removes user + all documents, chunks, vectors, queries atomically. |
| 9 | **Context window overflow** — too many/large chunks exceed TPM budget | Medium | MVP | Hard token budget (2,000 tokens for context, 512 for response). Trim lowest-relevance chunks until under budget. Conservative to stay under Groq's 6,000 TPM. In practice: 3-4 chunks per query. |
| 10 | **Corrupted / password-protected PDF** — pdfplumber throws unhandled exception | Low | MVP | Wrap extraction in try/except. PyMuPDF raises `fitz.FileDataError` for corruption, specific exceptions for encrypted files. Map to `status="failed"` + clear error message. |

---

## 10. Scalability Story

### Local → Production Path

```
LOCAL (Docker Compose)                 PRODUCTION (Cloud)
========================               ========================
Postgres container          →          RDS / Cloud SQL (managed)
  pgvector extension                     pgvector extension (supported on both)
Redis container             →          ElastiCache / Memorystore
FastAPI container           →          ECS Fargate / Cloud Run (auto-scaling)
  BackgroundTasks                        Celery + Redis as broker
  sentence-transformers                  Dedicated embedding service or sidecar
React (Vite dev server)     →          Static build → S3 + CloudFront / Vercel
Groq API (free tier)        →          Groq paid tier or self-hosted vLLM
Docker Compose              →          Kubernetes (EKS/GKE) or managed containers
```

### Scaling Landmarks

| Scale | What Changes | Why |
|---|---|---|
| **1–50 users** (MVP) | Nothing. Docker Compose handles this fine. | Single-digit concurrent requests, <10K vectors. |
| **50–1K users** | Move Postgres to managed DB. Add connection pooling (PgBouncer). Celery replaces BackgroundTasks. | Connection limits become real. Background processing needs parallelism. |
| **1K–10K users** | Horizontal API scaling behind LB. HNSW replaces ivfflat index. Embedding model becomes a separate service. Redis cluster. | Vector search latency matters at 1M+ rows. Embedding is CPU-bound — isolate it. |
| **10K–100K users** | Partition chunks table by user or document. Consider dedicated vector DB. CDN for frontend. Rate limiting per user. | Single pgvector table becomes a bottleneck. Need sharding strategy. |

### Free Hosting Path (If Required)

| Service | Free Tier Option | Limitation |
|---|---|---|
| **Postgres + pgvector** | Supabase free tier or Neon free tier | 500MB storage (Supabase), 512MB (Neon) |
| **API** | Render free tier or Railway trial | Sleeps after inactivity, cold starts |
| **Frontend** | Vercel free tier | Generous — no real limitation for this |
| **Redis** | Upstash free tier | 10K commands/day — sufficient for MVP |
| **LLM** | Groq free tier (already using) | 1,000 RPD per model, 6K TPM — dual-model gives ~1,900/day |

**Decision (locked in):** Docker Compose only for the submission. Free hosting path is documented in the README as a "production deployment option" but not implemented. This avoids cold-start risks during a live demo.

---

## 11. What's In Scope (MVP) vs. Future

### In Scope (Must Ship)

| Feature | Rationale |
|---|---|
| JWT signup/login | Explicit hard requirement |
| PDF + TXT upload with processing pipeline | Core functionality |
| Image-only PDF detection + rejection | Top edge case — silent failures are unacceptable |
| Chunking with char offsets + table handling | Enables the highlight feature |
| pgvector storage + similarity search | Hard requirement |
| Relevance threshold gating | Anti-hallucination — core value prop |
| Grounded LLM answers via Groq | Core functionality |
| Groq budget manager (RPM + daily token tracking, model fallback) | Prevents demo-killing token exhaustion — learned from experience |
| Budget indicator in frontend | Sets user expectations, prevents surprise failures |
| Source highlighting in document view | The differentiator feature |
| Clickable source pills → scroll to chunk | Key interaction |
| Confidence indicators on answers | Shows grounding awareness |
| Vague query enrichment | Handles the most common UX failure |
| All empty/error states designed | Production-mindedness signal |
| Query history per document | Expected by evaluators |
| Docker Compose one-command setup | Non-negotiable |
| README with architecture + setup + demo | First and last thing evaluators read |

### Out of Scope (Document But Don't Build)

| Feature | Why Deferred | README Mention |
|---|---|---|
| Streaming responses (SSE) | Groq is fast enough (~2s responses); SSE adds complexity | "Production would add SSE streaming for long answers" |
| Ollama automatic failover | Config structure in place; manual switch via env var | "LLM_PROVIDER env var supports 'groq' or 'ollama'" |
| Multi-document workspace | Spec says "a PDF" (singular); adds UX complexity | "Schema supports multi-document; UI scoped to one at a time" |
| OCR for image-only PDFs | Tesseract adds Docker image bloat (~500MB) | "Tesseract integration is the natural next step" |
| Refresh token flow | 24-hour access token is fine for demo | "Production would use short-lived access + refresh tokens" |
| Celery task queue | FastAPI BackgroundTasks is sufficient at MVP scale | "Document processing moves to Celery workers at scale" |
| Chat memory / conversation context | Risks creating "ChatGPT clone" feeling | "Query enrichment handles immediate follow-ups" |
| Re-chunking without re-upload | raw_text is stored, making this possible | "Re-chunking endpoint would allow chunk size experimentation" |
| User profile / settings | Zero value for evaluators | Not mentioned |
| File format support beyond PDF/TXT | DOCX, EPUB add complexity with no architectural insight | "Additional format parsers plug into the extraction service" |

---

## 12. Interview Talking Points

### Design Decisions to Defend

**1. "Why pgvector instead of a dedicated vector DB?"**

> pgvector keeps vectors as a native Postgres column alongside relational data — chunks, documents, users — in a single database with referential integrity. When a user deletes their account, `ON DELETE CASCADE` removes their vectors atomically. With Pinecone or Weaviate, I'd need distributed transactions or eventual consistency for the same guarantee. For <100K vectors, pgvector's ivfflat index is fast enough (~10ms queries), and upgrading to HNSW is a config change, not a migration. The tradeoff is that at 10M+ vectors, a dedicated vector DB would offer better query performance and sharding — but that's a problem you solve when you have it, not when you have 50 users.

**2. "Why a relevance threshold instead of always calling the LLM?"**

> Every RAG system has a retrieval failure mode: the user asks something the document doesn't cover, retrieval returns the "least bad" chunks, and the LLM hallucinates an answer from them. The 0.3 cosine similarity threshold short-circuits this — if the best chunk isn't meaningfully related to the question, we tell the user directly instead of generating a confident-sounding wrong answer. This is a deliberate UX choice: false negatives (missing a relevant chunk) are recoverable — the user rephrases. False positives (hallucinated answers) destroy trust. I'd rather my system says "I don't know" too often than lies.

**3. "Why source highlighting as the key feature instead of something like multi-doc or streaming?"**

> Multi-doc is additive scope that doesn't demonstrate architectural depth. Streaming is infrastructure plumbing that doesn't demonstrate RAG understanding. Source highlighting forces several hard engineering choices — chunk metadata with character offsets, a schema that links answers to their source chunks, and a frontend interaction model that treats the document as the primary interface element. It's also the feature that most directly addresses what makes RAG valuable: grounding. When an interviewer sees the answer and its source passages highlighted simultaneously, they immediately understand that the system is trustworthy. That's harder to communicate with a chat interface.

**4. "What would you change if you had two more weeks?"**

> Three things. First, hybrid search: right now I use pure vector similarity, but adding BM25 keyword search (via Postgres full-text search) and combining scores would catch cases where the user's question uses exact terminology from the document that embedding similarity misses. Second, evaluation: I'd build a small test harness that runs a set of question-answer pairs against the pipeline and measures retrieval recall and answer faithfulness — right now quality assessment is manual. Third, I'd add document structure awareness to the chunking — detecting headings, sections, and lists in the PDF and using that hierarchy to create more semantically meaningful chunks instead of fixed-size splits.

### What Raises the Bar

1. **Grounding-first design philosophy** — the relevance threshold, the source highlighting, the confidence scores. Every feature reinforces the idea that this system knows what it doesn't know.
2. **Schema quality** — UUIDs, cascade deletes, char offsets, chunk metadata, audit trail in queries table. An evaluator reading the migration file should think "this person has built production systems."
3. **Error state completeness** — every failure mode has an intentional UI. No white screens, no raw JSON. This signals more production experience than any architecture diagram.
4. **One-command reproducibility** — `docker compose up --build`, wait 60 seconds, open browser. If the evaluator can't run it, nothing else matters.

---

## Appendix: File Structure

```
doclens/
├── docker-compose.yml
├── .env.example
├── README.md
├── BLUEPRINT.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── config.py                # Settings from env vars (Pydantic BaseSettings)
│   │   ├── dependencies.py          # DB session, auth, embedding model
│   │   ├── routes/
│   │   │   ├── auth.py              # POST /signup, /login
│   │   │   ├── documents.py         # POST, GET, DELETE /documents
│   │   │   └── queries.py           # POST, GET /queries
│   │   ├── services/
│   │   │   ├── auth_service.py      # JWT + password logic
│   │   │   ├── document_service.py  # Upload, extract, chunk, embed
│   │   │   ├── query_service.py     # Retrieve, prompt, generate
│   │   │   ├── llm_service.py       # Groq/Ollama abstraction
│   │   │   └── groq_budget.py       # Token/RPM tracking, model fallback, Redis counters
│   │   ├── repositories/
│   │   │   ├── user_repo.py
│   │   │   ├── document_repo.py
│   │   │   ├── chunk_repo.py
│   │   │   └── query_repo.py
│   │   ├── models/
│   │   │   ├── database.py          # SQLAlchemy models
│   │   │   └── schemas.py           # Pydantic request/response models
│   │   └── utils/
│   │       ├── text_extraction.py   # pdfplumber + txt handling
│   │       ├── chunking.py          # RecursiveCharacterTextSplitter wrapper
│   │       └── embeddings.py        # sentence-transformers wrapper + Redis cache
│   └── tests/
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_documents.py
│       └── test_queries.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts            # Axios instance + interceptors
│       ├── hooks/
│       │   ├── useAuth.ts
│       │   ├── useDocuments.ts
│       │   └── useQueries.ts
│       ├── context/
│       │   ├── AuthContext.tsx
│       │   └── HighlightContext.tsx
│       ├── pages/
│       │   ├── LoginPage.tsx
│       │   ├── SignupPage.tsx
│       │   ├── DashboardPage.tsx
│       │   └── WorkspacePage.tsx
│       ├── components/
│       │   ├── auth/
│       │   │   └── AuthForm.tsx
│       │   ├── dashboard/
│       │   │   ├── UploadZone.tsx
│       │   │   └── DocumentCard.tsx
│       │   ├── workspace/
│       │   │   ├── WorkspaceHeader.tsx
│       │   │   ├── DocumentPanel.tsx
│       │   │   ├── ChunkBlock.tsx
│       │   │   ├── QueryPanel.tsx
│       │   │   ├── QueryInput.tsx
│       │   │   ├── ActiveAnswer.tsx
│       │   │   ├── SourcePill.tsx
│       │   │   ├── ConfidenceBadge.tsx
│       │   │   └── QueryHistory.tsx
│       │   └── shared/
│       │       ├── ProtectedRoute.tsx
│       │       └── EmptyState.tsx
│       └── types/
│           └── index.ts             # Shared TypeScript interfaces
```

---

## 13. Requirements Coverage Matrix

Mapping every grading criterion and requirement from the interview brief to where
it's addressed in this project.

### Grading Criteria Coverage

| Criterion | How We Address It | Where in Codebase |
|---|---|---|
| **App quality** | Clean route/service/repo separation, typed Pydantic models, no business logic in handlers | `backend/app/routes/`, `services/`, `repositories/` |
| **Front/back end separation** | React SPA (port 5173) ↔ FastAPI REST API (port 8000), no server-rendered HTML | `frontend/` and `backend/` are independent Docker containers |
| **System design** | Full architecture diagram, component responsibilities, data flow documentation | `BLUEPRINT.md` Sections 3–7, also summarized in `README.md` |
| **Scalability** | Docker Compose → K8s path documented, pgvector index strategy, horizontal API scaling | `BLUEPRINT.md` Section 10, README "Production Architecture" |
| **Distributed system architecture** | Stateless API (JWT, no sessions), external state in Postgres/Redis, ready for LB + replicas | Architecture diagram, no in-memory state in API layer |
| **UI/UX clean and usable** | Document-centric layout (not chat clone), source highlighting, all empty/error states designed | `frontend/src/pages/WorkspacePage.tsx`, component tree |
| **DB: Postgres** | PostgreSQL 16 + pgvector extension, 4 tables, proper FK cascades, migration-managed | `backend/alembic/versions/001_initial_schema.py` |
| **Redis (nice to have)** | Yes — embedding cache, Groq budget tracking (RPM/RPD), rate limiting | `backend/app/services/groq_budget.py`, `embeddings.py` |
| **Frontend: JS/TypeScript** | React 18 + TypeScript + Vite + Tailwind, fully typed | `frontend/src/**/*.tsx` |
| **API: FastAPI** | FastAPI with async endpoints, Pydantic validation, auto-generated OpenAPI docs | `backend/app/main.py`, `/docs` endpoint |
| **Login/signup** | JWT auth with bcrypt password hashing, protected routes, user-scoped data | `backend/app/services/auth_service.py`, `frontend/src/context/AuthContext.tsx` |
| **Upload PDF/text** | pdfplumber extraction, table handling, image-only detection, background processing | `backend/app/services/document_service.py` |
| **Ask questions, AI answers** | pgvector retrieval → relevance gating → Groq LLM → grounded response with sources | `backend/app/services/query_service.py` |
| **GitHub repo** | Single repo, clean commit history per phase, README with setup + architecture | Root of repo |

### Required Artifacts Checklist

| Artifact | Deliverable | Status |
|---|---|---|
| System Design | `BLUEPRINT.md` + architecture section in `README.md` | Designed |
| What achieved vs future | "In Scope vs Future" in `BLUEPRINT.md` Section 11, summarized in README | Designed |
| Scalability thoughts | `BLUEPRINT.md` Section 10 + README "Production Architecture" | Designed |
| GitHub repo | Single monorepo with `docker-compose.yml` at root | To build |

---

## 14. Claude Code Development Workflow

### What Claude Code Does (And Doesn't Do)

**Use Claude Code for:**
- Scaffolding: project structure, Docker configs, dependency files, boilerplate
- Implementation: route handlers, service classes, database models, React components
- Wiring: connecting services together, imports, configuration plumbing
- Testing: writing unit tests, integration test fixtures
- Debugging: reading error logs, fixing issues, iterating on failures
- Git: committing per phase, writing commit messages, pushing to GitHub

**You make the decisions on:**
- Architecture choices (already made in this blueprint)
- Prompt engineering (tuning the RAG system prompt — test manually)
- UX judgment (does the highlight interaction feel right? — test in browser)
- Edge case priorities (which to implement vs defer — already decided)

### GitHub Setup

```bash
# One-time setup before starting Phase 1
gh repo create doclens --private --clone
cd doclens
cp /path/to/BLUEPRINT.md .
git add BLUEPRINT.md && git commit -m "docs: add project blueprint"
git push origin main
```

### Phase-by-Phase Claude Code Prompts

Each phase is a focused Claude Code session. Start each session by pointing Claude
Code at the blueprint and the current state of the repo.

**Phase 1 — Core Skeleton (scaffold + first end-to-end flow)**

```
Read BLUEPRINT.md carefully — it's the complete spec for this project.

Build Phase 1: Core Skeleton. Here's what needs to work end-to-end:

1. Docker Compose with 4 services: postgres (with pgvector), redis,
   backend (FastAPI), frontend (React+Vite)
2. Backend project structure following the file tree in BLUEPRINT.md
   Section "Appendix: File Structure"
3. Alembic migration with the FULL schema from Section 4 (users, documents,
   chunks, queries tables with pgvector)
4. POST /api/documents — accept .txt files, extract text, chunk (512 tokens,
   50 overlap), embed with all-MiniLM-L6-v2, store in pgvector
5. GET /api/documents/{id} — return document with status
6. GET /api/documents/{id}/chunks — return all chunks
7. POST /api/queries — embed question, pgvector similarity search, build
   prompt, call Groq API (llama-3.3-70b-versatile), return answer + sources
8. Frontend: simple upload form, document status polling, basic document view
   showing chunks, query input, answer display with source chunk IDs

No auth yet. No styling beyond basic layout. .env.example with GROQ_API_KEY.
The goal is: upload a .txt file, ask a question, get a grounded answer with sources.

Use the exact schema, file structure, and data flow from the blueprint.
```

**Phase 2 — PDF Support + Auth**

```
Read BLUEPRINT.md Sections 4-5 for reference.

Build Phase 2 on top of the existing codebase:

1. PDF support: integrate pdfplumber for text + table extraction.
   - Tables → markdown format → atomic chunks with chunk_type="table"
   - Image-only PDF detection: if <50 chars/page avg, set status="failed"
   - File size validation: reject >20MB
2. JWT Auth:
   - POST /api/auth/signup and /api/auth/login
   - python-jose for JWT, passlib[bcrypt] for passwords
   - 24-hour token expiry
   - Auth middleware on all /documents and /queries routes
   - All queries scoped to authenticated user's data
3. Frontend auth:
   - Login and Signup pages
   - AuthContext with JWT token state
   - Axios interceptor that adds Bearer token
   - ProtectedRoute component
   - Dashboard page showing user's documents
4. Background processing with FastAPI BackgroundTasks:
   - POST /documents returns 202 with status:"processing"
   - Frontend polls GET /documents/{id} every 2s until ready

Test: two users can sign up, upload different files, cannot see each other's data.
```

**Phase 3 — RAG Quality + Groq Budget + Highlighting**

```
Read BLUEPRINT.md Section 7 (RAG Pipeline) and the Groq Token Management
subsection carefully.

Build Phase 3 — this is the phase that differentiates the project:

1. GroqBudgetManager (backend/app/services/groq_budget.py):
   - Track per-model RPD in Redis (70B and 8B are separate pools)
   - 2.5s minimum spacing between LLM calls (TPM protection)
   - Auto-switch from 70B → 8B when primary RPD exhausted
   - Read x-ratelimit-remaining-tokens from Groq response headers
   - GET /api/budget endpoint returning per-model usage
   - Handle 429 errors: parse Retry-After, retry once, then fail gracefully

2. RAG quality improvements:
   - Relevance threshold: if top chunk similarity < 0.3, skip LLM, return
     "no relevant info"
   - Confidence scoring: >0.5 = high, 0.3-0.5 = low
   - Vague query enrichment: if question <5 words or has pronouns,
     prepend last Q&A
   - Context budget: MAX_CONTEXT_TOKENS = 2000, trim lowest-relevance chunks
   - Terse system prompt from blueprint (saves tokens)
   - Redis embedding cache with 1-hour TTL

3. Frontend — source highlighting:
   - ChunkBlock component accepts highlight state (active/inactive)
   - SourcePill component in answers — shows [Page N, ¶M], clickable
   - Click source pill → scrollIntoView on the chunk with smooth scroll
   - Pulse animation on highlighted chunk (CSS keyframes, amber background)
   - ConfidenceBadge component (green/amber/red based on confidence)
   - Budget indicator dot in QueryPanel header
   - Query history panel (previous Q&A for this document)
   - ALL empty states from the blueprint table

Use the exact CSS from BLUEPRINT.md for highlight styles.
```

**Phase 4 — UI/UX Polish + README + Deliverables**

```
Read BLUEPRINT.md Sections 6, 12, and 13.

Phase 4 — make it portfolio-ready:

1. Visual design pass:
   - Tailwind: warm neutrals (stone/slate palette), amber-500 accent
   - font-mono for document content, font-sans for UI chrome
   - Generous whitespace, no visual clutter
   - Answers render as blocks with left border accent, NOT chat bubbles

2. Responsive layout:
   - Desktop (≥1024px): 65/35 split
   - Tablet (768-1023px): 55/45 split
   - Mobile (<768px): stacked, sticky "Ask" button

3. Error handling:
   - React error boundary at App level
   - Toast notifications for upload success/failure
   - Delete document confirmation dialog
   - Consistent error response format from backend

4. GET /api/health endpoint checking Postgres, Redis, embedding model

5. README.md:
   - Project description (2 sentences)
   - Architecture diagram (ASCII from blueprint)
   - One-command setup: docker compose up --build
   - Environment variables table
   - Key design decisions (3 bullets from Section 12)
   - Known limitations with production solutions noted
   - Screenshots or demo GIF

6. Clean up:
   - Remove console.logs
   - Type-check (tsc --noEmit)
   - All Pydantic models complete
   - Docker compose starts cleanly from scratch
```

### Git Workflow Per Phase

```bash
# Before each phase
git checkout -b phase-N-description

# During (Claude Code commits, but also manual checkpoints)
git add -A && git commit -m "feat: [description]"

# After phase passes testing
git checkout main && git merge phase-N-description
git push origin main && git tag phase-N-complete
```

### Claude Code Session Tips

1. **Start every session with:** "Read BLUEPRINT.md first, then look at the
   current codebase." Claude Code works best with full spec in context.

2. **One phase per focused session.** Don't try to build everything at once.

3. **Test after each phase before moving on.** Run Docker stack, upload a
   file, ask a question. Don't accumulate untested code across phases.

4. **Let Claude Code handle wiring, you handle testing.** It's excellent at
   connecting services and fixing imports. Less good at judging UX feel.

5. **For the Groq budget manager:** implement it, then test by asking 5-10
   questions rapidly. Verify Redis keys:
   `docker exec -it redis redis-cli KEYS "groq:*"`

6. **For the highlight feature:** get Claude Code to build scaffolding, then
   fine-tune scroll behavior and animation timing yourself in the browser.

---

## 15. ETA & Effort Estimate

### With Claude Code (Recommended)

| Phase | Calendar Time | Active Effort | Claude Code Handles | You Handle |
|---|---|---|---|---|
| **Phase 1** | 1 day | 3–4 hours | Docker, FastAPI scaffold, Alembic, SQLAlchemy, React scaffold, wiring | Verify Docker starts, test upload→query flow |
| **Phase 2** | 1 day | 3–4 hours | pdfplumber, JWT auth, middleware, login pages, AuthContext, protected routes | Test PDF quality, verify user isolation |
| **Phase 3** | 1.5–2 days | 5–6 hours | Budget manager, Redis, threshold logic, highlight components, empty states | **Tune RAG prompt**, test budget tracking, fine-tune highlight UX |
| **Phase 4** | 1 day | 3–4 hours | Tailwind polish, responsive, error boundaries, health endpoint, README | Visual review, mobile test, demo GIF, clean Docker test |
| **Buffer** | 0.5 day | — | — | Unexpected issues |
| **Total** | **5–6 days** | **~16–18 hours** | | |

### Without Claude Code

| Phase | Calendar Time | Active Effort |
|---|---|---|
| Phase 1 | 2–3 days | 10–12 hours |
| Phase 2 | 1.5–2 days | 8–10 hours |
| Phase 3 | 2–3 days | 12–14 hours |
| Phase 4 | 1–2 days | 6–8 hours |
| **Total** | **7–10 days** | **36–44 hours** |

### Where Your Time Goes (With Claude Code)

```
Phase 3 is heaviest — contains the two things Claude Code can't automate:
RAG prompt tuning and UX feel.

├── Boilerplate / scaffolding (Claude Code 90%)      ~2 hours you
├── Service implementation (Claude Code 70%)          ~4 hours you
├── Frontend components (Claude Code 80%)             ~3 hours you
├── RAG prompt engineering (you 100%)                 ~2 hours you
├── Highlight UX fine-tuning (you 90%)                ~2 hours you
├── Testing each phase (you 100%)                     ~3 hours you
├── Docker / env issues (split)                       ~1 hour you
├── README + docs (Claude Code 70%)                   ~1 hour you
└── Total                                            ~18 hours you
```

### Critical Path

```
Docker Compose + DB migration
          ↓
FastAPI skeleton + embedding model loading
          ↓
  ┌───────────────────┬──────────────────┐
  │ Document pipeline │  React scaffold  │  ← can parallelize
  └───────┬───────────┴────────┬─────────┘
          └──────┬─────────────┘
                 ↓
         Query pipeline (retrieval → LLM → response)
                 ↓
    ══ PHASE 1 DONE — first end-to-end works ══
                 ↓
         Auth + PDF extraction
                 ↓
    ══ PHASE 2 DONE — real app with login ══
                 ↓
         GroqBudgetManager + highlight interaction
                 ↓
    ══ PHASE 3 DONE — impressive demo ══
                 ↓
         Visual polish + README
                 ↓
    ══ PHASE 4 DONE — ship it ══
```

---

## 16. Model Training: NOT Required

| Component | What Happens | Training? |
|---|---|---|
| **Embedding model** (all-MiniLM-L6-v2) | Downloads pre-trained weights on first run (~80MB), cached in Docker volume. Called via `model.encode()`. | **No** — inference only |
| **LLM** (Llama 3.3 70B on Groq) | Pre-trained model hosted by Groq. We send prompts via API. | **No** — inference only |
| **LLM** (Llama 3.1 8B on Groq) | Same — pre-trained, API access, separate RPD pool. | **No** — inference only |
| **LLM fallback** (Ollama) | Downloads pre-trained weights via `ollama pull`. | **No** — inference only |
| **pgvector** | Stores and indexes pre-computed embedding vectors. | **No** — it's a database |

The intelligence in this app comes from:
1. **Chunking quality** — how we split the document
2. **Retrieval quality** — how we search pgvector
3. **Prompt engineering** — how we instruct the LLM to stay grounded
4. **System design** — relevance thresholds, source attribution, budget management

None of these require model training. This is an **engineering** project, not an
**ML** project — and that's a point worth making in the interview.

---

## 17. 48-Hour Sprint Plan (May 29 5PM → May 31 5PM)

### Revised Phase Structure (Compressed)

The original 4-phase plan assumed ~6 days. With 48 hours, we merge phases
and cut scope surgically — keeping everything evaluators will notice, dropping
things they won't.

### TONIGHT — Thu May 29 (5PM → Midnight, ~7 hours)

**Goal: Docker running + backend pipeline working end-to-end via curl.**

```
Hour 1-2: Project scaffold with Claude Code
  ├── GitHub repo created
  ├── Docker Compose: postgres+pgvector, redis, backend, frontend
  ├── Backend: FastAPI structure, Alembic migration (full schema)
  ├── Frontend: Vite+React+TS+Tailwind bare scaffold
  └── MILESTONE: docker compose up --build works, frontend shows hello world

Hour 2-4: Document pipeline (backend only)
  ├── POST /api/documents — accept .txt AND .pdf (do both now, skip phasing)
  ├── pdfplumber extraction + image-only detection
  ├── Chunking with char offsets + table handling
  ├── Embedding with all-MiniLM-L6-v2
  ├── Background processing with 202 Accepted pattern
  └── MILESTONE: curl upload a PDF, see chunks in database

Hour 4-6: Query pipeline (backend only)
  ├── POST /api/queries — embed → pgvector search → Groq LLM → respond
  ├── Relevance threshold (similarity < 0.3 → skip LLM)
  ├── Terse system prompt with source tagging
  ├── Basic Groq error handling (429 catch, timeout)
  └── MILESTONE: curl a question, get grounded answer with source chunks

Hour 6-7: Auth (backend only)
  ├── POST /api/auth/signup + /api/auth/login
  ├── JWT middleware on all protected routes
  ├── User-scoped document/query access
  └── MILESTONE: can signup, login, upload, query — all via curl

TONIGHT'S EXIT CRITERIA:
  ✓ docker compose up works
  ✓ Full backend API works via curl/Postman
  ✓ Auth, upload, chunk, embed, query, answer — all functional
  ✓ Git commit + push: "feat: complete backend API"
```

**Why backend-first:** The backend is the load-bearing wall. If the backend
works perfectly via curl, the frontend is "just" connecting to endpoints.
If you run out of time, a working API + basic frontend beats a pretty
frontend with a broken backend.

### FRIDAY — May 30 (10AM → 10PM, ~12 hours)

**Goal: Complete frontend + highlight feature + Groq budget manager.**

```
Hour 1-3: Core frontend (connect to backend)
  ├── AuthContext + login/signup pages
  ├── Axios client with JWT interceptor
  ├── Dashboard page: document list + upload zone (drag & drop)
  ├── Document status polling (react-query)
  └── MILESTONE: can login and upload a PDF in the browser

Hour 3-6: Workspace page (THE MONEY FEATURE)
  ├── WorkspacePage with 65/35 split layout
  ├── DocumentPanel: render chunks as text blocks with page dividers
  ├── QueryPanel: input + answer display
  ├── Source highlighting: ChunkBlock highlight state
  ├── SourcePill: clickable badges → scrollIntoView to chunk
  ├── Pulse animation on active highlight
  ├── ConfidenceBadge (high/medium/low/none)
  └── MILESTONE: ask question → see answer → click source → doc scrolls to it

Hour 6-8: Groq budget manager
  ├── groq_budget.py: per-model RPD tracking in Redis
  ├── 2.5s inter-request spacing
  ├── Dual-model fallback (70B → 8B)
  ├── GET /api/budget endpoint
  ├── Frontend budget indicator dot
  └── MILESTONE: budget endpoint returns real data, indicator shows in UI

Hour 8-10: RAG quality + empty states
  ├── Vague query enrichment (prepend last Q&A)
  ├── Redis embedding cache
  ├── Query history panel
  ├── ALL empty states (no docs, processing, no results, error, rate limited)
  └── MILESTONE: every UI state has intentional design

Hour 10-12: Visual polish (Tailwind pass)
  ├── Color palette: stone/slate + amber-500 accent
  ├── Typography: mono for doc content, sans for chrome
  ├── Spacing, borders, shadows — make it look designed
  ├── Responsive: mobile stacking at <768px
  └── MILESTONE: looks professional, not like a hackathon project

FRIDAY EXIT CRITERIA:
  ✓ Full app works in browser: signup → upload → query → highlighted sources
  ✓ Groq budget tracking active
  ✓ All empty/error states render correctly
  ✓ Visually polished
  ✓ Git commit + push: "feat: complete frontend + highlighting + budget mgmt"
```

### SATURDAY — May 31 (8AM → 3PM, ~7 hours, submit by 5PM)

**Goal: README, testing, Docker clean-test, submission.**

```
Hour 1-2: README.md
  ├── Project description
  ├── Architecture diagram (ASCII from blueprint)
  ├── Setup: docker compose up --build (one command)
  ├── .env.example with all variables documented
  ├── Design decisions (3 bullets from Section 12)
  ├── Screenshots (take 3-4 of key screens)
  ├── Known limitations + what you'd add next
  └── Scalability section (Docker Compose → production path)

Hour 2-3: Integration testing
  ├── Test happy path: signup → login → upload PDF → ask question → get answer
  ├── Test edge cases: image-only PDF, empty file, off-topic question
  ├── Test auth: verify user isolation
  ├── Test Groq budget: rapid-fire 5 questions, check Redis
  └── Fix any bugs found

Hour 3-5: Clean Docker test (CRITICAL)
  ├── docker system prune -a (nuke everything)
  ├── git clone fresh copy
  ├── cp .env.example .env, add GROQ_API_KEY
  ├── docker compose up --build
  ├── Verify: works from zero state
  ├── Time it: should be ready in <3 minutes
  └── Fix any first-run issues (missing deps, model download, etc.)

Hour 5-6: Final touches
  ├── Demo GIF or screenshots for README
  ├── Remove debug code, console.logs
  ├── Final git push
  └── Verify repo is clean and README renders on GitHub

Hour 6-7: BUFFER
  └── For anything that went wrong above

SUBMIT BY 3PM — gives 2 hours of safety margin before 5PM deadline.
```

### What We Cut (Compared to Original Plan)

| Feature | Original Plan | 48-Hour Plan | Why |
|---|---|---|---|
| Separate phases for .txt then .pdf | Phase 1 → Phase 2 | Do both in Hour 2-4 night one | No point in two passes |
| Ollama fallback implementation | Phase 5 stretch | Skip — document in README only | Zero evaluator impact |
| Refresh token flow | Deferred | Skip — 24h token is fine | Won't be tested |
| Unit tests | Phase 4 | Skip — do manual integration testing only | Time vs. impact |
| Toast notifications | Phase 4 | Skip if time is short | Basic alerts work |
| Document delete with confirmation | Phase 4 | Skip — evaluator won't test this | They'll upload, not delete |
| Demo video | Phase 4 | Screenshots only (faster) | 10 min vs 1 hour |

### What We DO NOT Cut

These are non-negotiable even at 48 hours:

```
✗ DO NOT CUT: Source highlighting          — it's THE differentiator
✗ DO NOT CUT: Relevance threshold          — prevents hallucination in demo
✗ DO NOT CUT: Groq budget manager          — prevents demo-killing token exhaustion
✗ DO NOT CUT: Empty states                 — signals production thinking
✗ DO NOT CUT: Clean Docker startup         — if they can't run it, you fail
✗ DO NOT CUT: README with architecture     — it's a required artifact
✗ DO NOT CUT: Visual polish                — "UI/UX clean and usable" is grading criteria
```
