# DocLens — Document-Grounded RAG Application

A document-centric RAG web app where users upload PDFs/text files, ask questions, and receive AI-generated answers grounded in the document with **source highlighting** — answers visually connect back to specific passages.

![Architecture](https://img.shields.io/badge/FastAPI-Python-009688?style=flat) ![Frontend](https://img.shields.io/badge/React-TypeScript-3178C6?style=flat) ![DB](https://img.shields.io/badge/PostgreSQL-pgvector-336791?style=flat) ![LLM](https://img.shields.io/badge/Groq-Llama_3.3_70B-FF6B35?style=flat)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Krishan101/doclens.git
cd doclens

# 2. Configure
cp .env.example .env
# Edit .env → add your GROQ_API_KEY (get one at console.groq.com)

# 3. Run
docker compose up --build

# 4. Open
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs

# 5. Quick test (optional — verifies everything works via API)
bash samples/test-api.sh
```

A sample document is included at `samples/sample-architecture.txt` for testing.

## All Services & Ports

| Port | Service | URL | Purpose |
|---|---|---|---|
| **5173** | Frontend | http://localhost:5173 | React app — main UI |
| **8000** | Backend API | http://localhost:8000/docs | FastAPI with Swagger UI |
| **8080** | Adminer | http://localhost:8080 | PostgreSQL browser — inspect tables, run queries |
| **8081** | Redis Commander | http://localhost:8081 | Redis browser — view budget keys, embedding cache |
| 5432 | PostgreSQL | (direct connection) | DB: `doclens` / user: `doclens` / pw: `doclens_secret` |
| 6379 | Redis | (direct connection) | Cache + budget tracking |

### Adminer Login (http://localhost:8080)

```
System:     PostgreSQL
Server:     postgres
Username:   doclens
Password:   doclens_secret
Database:   doclens
```

Once logged in, you can browse all tables: `users`, `documents`, `chunks`, `queries`. Click any table to see rows, run SQL queries, or export data.

### Redis Commander (http://localhost:8081)

View live Groq budget tracking keys:
- `groq:rpd:llama-3.3-70b-versatile:2026-05-30` — primary model request count today
- `groq:rpd:llama-3.1-8b-instant:2026-05-30` — fallback model request count today
- `groq:last_request_ts` — timestamp of last LLM call (for TPM spacing)
- `embed:*` — cached query embeddings (1-hour TTL)

## Data Storage & Security

### What's Stored Where

| Data | Storage | Encrypted? | Notes |
|---|---|---|---|
| User passwords | `users.hashed_pw` | **Yes** (bcrypt) | Salted + hashed, not reversible |
| User email | `users.email` | No (plaintext) | Indexed for login lookup |
| Original PDF/TXT file | **Not stored** | N/A | Only extracted text is kept |
| Extracted text | `documents.raw_text` | No (plaintext) | Needed for re-chunking without re-upload |
| Chunk text | `chunks.content` | No (plaintext) | Needed for retrieval display + highlighting |
| Embedding vectors | `chunks.embedding` | No (vector) | 384-dim floats, not human-readable |
| Questions & answers | `queries` table | No (plaintext) | Audit trail for Q&A history |
| JWT tokens | Client-side only | Signed (HMAC-SHA256) | Never stored in DB |

### Security Model

- **Authentication:** JWT with 24-hour expiry, bcrypt password hashing (cost factor 12)
- **Authorization:** Every document/query endpoint verifies `user_id` ownership before returning data
- **Data isolation:** Users can never access another user's documents, chunks, or queries
- **Cascade deletes:** Deleting a user atomically removes all their data (documents, chunks, vectors, queries)
- **No file storage:** Original uploaded files are processed in memory and discarded — only extracted text persists

### Production Security (Not Implemented, Documented)

In production, the following would be added:
- PostgreSQL TDE (Transparent Data Encryption) for encryption at rest
- TLS for all connections (API, database, Redis)
- Short-lived access tokens (15 min) + refresh tokens (7 days)
- Rate limiting per user (not just per Groq model)
- Input sanitization beyond Pydantic validation

## Architecture

```
┌──────────────────────────────────────────────────────┐
│              FRONTEND (React + TypeScript)            │
│         Document-centric split layout (65/35)        │
│    Document view with highlights ←→ Query panel      │
└────────────────────────┬─────────────────────────────┘
                         │ REST API + JWT
┌────────────────────────▼─────────────────────────────┐
│                  FASTAPI BACKEND                      │
│  Auth │ Document Pipeline │ RAG Query │ Budget Mgr    │
└───┬────────┬──────────────────┬───────────┬──────────┘
    │        │                  │           │
┌───▼───┐ ┌──▼────────┐ ┌──────▼───┐ ┌────▼─────┐
│Postgres│ │ Sentence  │ │ Groq API │ │  Redis   │
│pgvector│ │Transformers│ │(Llama 3) │ │(cache +  │
│        │ │ (local)   │ │          │ │ budget)  │
└────────┘ └───────────┘ └──────────┘ └──────────┘
```

## Key Design Decisions

1. **Source highlighting over chat UI** — Answers point back into the document via highlighted passages. The document is the hero, not the chat. This demonstrates RAG's core value: grounding.

2. **pgvector as native Postgres column** — Vectors live alongside relational data with `ON DELETE CASCADE`. Deleting a user atomically removes all their documents, chunks, and vectors. No orphaned data, no distributed transactions.

3. **Groq dual-model budget management** — Free tier limits are per-model (1,000 RPD each). By routing between Llama 3.3 70B and 3.1 8B, we get ~1,900 requests/day with graceful degradation. Redis tracks usage; the frontend shows remaining budget.

4. **Relevance threshold gating** — If the best retrieved chunk scores below 0.3 similarity, we skip the LLM entirely and tell the user honestly. False negatives are recoverable; hallucinated answers destroy trust.

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS |
| Backend | FastAPI + Python 3.11 |
| Database | PostgreSQL 16 + pgvector |
| Embeddings | all-MiniLM-L6-v2 (local, 384-dim) |
| LLM | Llama 3.3 70B + 3.1 8B via Groq free tier |
| Auth | JWT (python-jose + passlib) |
| Cache | Redis (embedding cache + budget tracking) |
| Infra | Docker Compose (4 containers) |

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Get at console.groq.com |
| `POSTGRES_USER` | No | `doclens` | Database user |
| `POSTGRES_PASSWORD` | No | `doclens_secret` | Database password |
| `JWT_SECRET_KEY` | No | (dev default) | Change in production |

See `.env.example` for the full list.

## API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | /api/auth/signup | No | Create account |
| POST | /api/auth/login | No | Get JWT token |
| POST | /api/documents | Yes | Upload PDF/TXT |
| GET | /api/documents | Yes | List user's docs |
| GET | /api/documents/:id | Yes | Document status |
| GET | /api/documents/:id/chunks | Yes | Document content |
| DELETE | /api/documents/:id | Yes | Delete document |
| POST | /api/queries | Yes | Ask a question |
| GET | /api/queries?document_id= | Yes | Query history |
| GET | /api/budget | Yes | Groq usage stats |
| GET | /api/health | No | System health |

## Scalability Path

**Local (now):** Docker Compose, 6 containers, single machine.

**Production scaling by tier:**

| Scale | Changes |
|---|---|
| **1–100 users** | Current Docker Compose setup handles this fine |
| **100–1K users** | Postgres → RDS/Cloud SQL, Redis → ElastiCache, API behind ALB, Celery for document processing |
| **1K–10K users** | pgvector `ivfflat` → `HNSW` index, embedding model as separate service, frontend → S3 + CloudFront |
| **10K+ users** | **pgvector → dedicated vector DB (Qdrant/Weaviate)** for advanced sharding, filtering, and multi-tenant isolation at 10M+ vectors. Partition chunks table by user/org. Groq → self-hosted vLLM on GPU instances |

**Why pgvector now, Qdrant later:** pgvector keeps vectors as a native Postgres column with full relational integrity (`ON DELETE CASCADE`, foreign keys, transactions). At <1M vectors, query latency is under 10ms. A dedicated vector DB like Qdrant adds operational complexity (separate cluster, separate backups, distributed consistency) that's only justified at 10M+ vectors where you need horizontal sharding, advanced multi-vector search, or payload-based filtering beyond what SQL `WHERE` clauses offer.

The API is stateless by design (JWT auth, no server sessions), so horizontal scaling requires only a load balancer.

## What Was Achieved

**Core RAG Pipeline (fully functional):**
- End-to-end document upload → text extraction → chunking → embedding → vector storage → retrieval → LLM answer
- PDF support with pdfplumber (table extraction, image-only detection, page boundary tracking)
- pgvector similarity search filtered by document, with relevance threshold gating
- Grounded answers via Groq (Llama 3.3 70B) with [SOURCE N] citations parsed and linked to UI

**Intelligent Features:**
- AI-generated suggested questions — the app analyzes uploaded documents and proposes 4 insightful questions
- Vague query enrichment — follow-up questions like "tell me more" automatically include prior Q&A context
- Dual-model Groq budget manager — tracks RPD per model in Redis, auto-switches from 70B → 8B when primary is exhausted, giving ~1,900 usable requests/day on free tier
- Source highlighting — answers reference specific chunks, clicking source pills scrolls the document view

**Production-Minded Design:**
- JWT authentication with bcrypt, user-scoped data isolation, `ON DELETE CASCADE` across all tables
- Background document processing (202 Accepted + polling) — large PDFs don't block the UI
- Global exception handler — no raw 500 errors reach the frontend
- Redis caching for embeddings (1hr TTL) and suggested questions
- All empty/error states designed (no white screens or raw JSON errors)
- Health endpoint checking Postgres, Redis, and embedding model status
- Admin tools: Adminer (DB browser), Redis Commander (cache viewer)

**Architecture & Code Quality:**
- Clean route → service → repository separation (no business logic in handlers)
- Typed Pydantic models for every request/response
- Async throughout (SQLAlchemy async, asyncpg, aioredis)
- Docker Compose with 6 containers, one-command startup

## What I'd Add Next (Future Improvements)

| Priority | Feature | Why It Matters |
|---|---|---|
| **High** | **Hybrid search (BM25 + vector)** | Pure vector search misses exact keyword matches. Combining Postgres full-text search with pgvector similarity would improve retrieval precision by 20-30%. |
| **High** | **OCR support (Tesseract)** | Image-only PDFs are currently rejected. Adding OCR opens the app to scanned contracts, receipts, and legacy documents. |
| **High** | **Evaluation harness** | Automated test suite with question-answer pairs to measure retrieval recall and answer faithfulness. Currently quality assessment is manual. |
| **Medium** | **Streaming responses (SSE)** | For longer answers, streaming gives better perceived performance. Groq's ~300 tok/s makes this less critical but still a UX improvement. |
| **Medium** | **Multi-document workspace** | Schema already supports multiple documents per user. UI would add a document switcher and cross-document queries. |
| **Medium** | **Dedicated vector DB at scale** | Migrate from pgvector to Qdrant/Weaviate at 10M+ vectors for horizontal sharding and advanced filtering. |
| **Low** | **Refresh token flow** | Replace 24-hour access tokens with short-lived (15min) access + 7-day refresh tokens. |
| **Low** | **Document structure awareness** | Detect headings, sections, and lists during chunking for more semantically meaningful splits instead of fixed-size. |

## Full Design Documentation

See [BLUEPRINT.md](./BLUEPRINT.md) for the complete system design, database schema, RAG pipeline details, edge case analysis, scalability path, and interview talking points.
