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
| Search | Hybrid: pgvector cosine + BM25 full-text via Reciprocal Rank Fusion |
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

### Current Architecture (Local)

Docker Compose, 6 containers, single machine. Handles 1–100 concurrent users comfortably.

### Vertical Scaling (Scale Up)

Vertical scaling improves performance without changing architecture.

| Bottleneck | Current | Scaled Up |
|---|---|---|
| **Embedding inference** | CPU-bound, ~50ms/chunk | GPU instance (p3.2xlarge) → ~5ms/chunk, 10x throughput |
| **Postgres** | Default config, shared_buffers=128MB | Tuned: shared_buffers=4GB, work_mem=256MB, effective_cache_size=12GB |
| **pgvector index** | `ivfflat` (lists=100) | `HNSW` (m=16, ef_construction=200) → 3-5x faster queries at 1M+ vectors |
| **LLM inference** | Groq free tier (1,000 RPD/model) | Groq paid tier or self-hosted vLLM on GPU → unlimited requests |
| **Redis** | Single instance, default config | maxmemory=2GB with LRU eviction, persistence with AOF |

### Horizontal Scaling (Scale Out)

Horizontal scaling adds capacity by running multiple instances behind a load balancer. The API is **stateless by design** (JWT auth, no server-side sessions, all state in Postgres/Redis), making this straightforward.

```
                    ┌──────────────┐
                    │ Load Balancer│
                    │  (ALB/nginx) │
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
     ┌──────▼──────┐ ┌────▼───────┐ ┌────▼───────┐
     │  API Pod 1  │ │  API Pod 2 │ │  API Pod 3 │
     │  (FastAPI)  │ │  (FastAPI) │ │  (FastAPI) │
     └──────┬──────┘ └────┬───────┘ └────┬───────┘
            │              │              │
     ┌──────▼──────────────▼──────────────▼──────┐
     │            Shared Data Layer                │
     │  ┌──────────┐  ┌───────┐  ┌────────────┐  │
     │  │ Postgres  │  │ Redis │  │ Embedding   │  │
     │  │ (RDS)     │  │(Elast │  │ Service     │  │
     │  │ +pgvector │  │ Cache)│  │ (separate)  │  │
     │  └──────────┘  └───────┘  └────────────┘  │
     └────────────────────────────────────────────┘
```

| Component | Horizontal Strategy |
|---|---|
| **API (FastAPI)** | Deploy N replicas behind ALB. Each is stateless — any pod handles any request. Auto-scale on CPU/memory thresholds. |
| **Document Processing** | Move from FastAPI BackgroundTasks to Celery worker pool with Redis broker. Each worker processes documents independently. Scale worker count based on queue depth. |
| **Embedding Service** | Extract sentence-transformers into a dedicated microservice with its own scaling. API pods call it via internal HTTP. Batch embedding requests for GPU efficiency. |
| **PostgreSQL** | Read replicas for query-heavy workloads. Connection pooling via PgBouncer (single-transaction mode). At 10M+ vectors, partition chunks table by `document_id` hash. |
| **Redis** | Redis Cluster for horizontal sharding. Separate clusters for cache (volatile, LRU) vs. budget tracking (persistent, AOF). |
| **Frontend** | Static build → S3/CloudFront CDN. Zero scaling concerns — it's just files. |

### Scaling by User Tier

| Scale | Vertical Changes | Horizontal Changes | Estimated Cost |
|---|---|---|---|
| **1–100** | None (Docker Compose) | None | $0 (local) |
| **100–1K** | Postgres → RDS (db.r6g.large), Redis → ElastiCache | 2 API pods behind ALB | ~$150/month |
| **1K–10K** | HNSW index, GPU for embeddings | 4-8 API pods, Celery workers, embedding service | ~$800/month |
| **10K–100K** | pgvector → Qdrant cluster, vLLM on GPU | 16+ API pods, partitioned DB, Redis cluster, CDN | ~$5K/month |

### Key Design Decisions That Enable Scale

1. **Stateless API** — JWT tokens carry auth state. No server sessions, no sticky sessions needed. Any API pod handles any request.
2. **Repository pattern** — All DB access through repos. Swapping Postgres for a read-replica or Qdrant means changing one repo file, not touching service logic.
3. **Redis for ephemeral state** — Budget tracking, embedding cache, rate limits — all in Redis with TTLs. If Redis dies, the app degrades gracefully (re-computes embeddings, loses budget count).
4. **Hybrid search via SQL** — BM25 + vector search runs entirely in Postgres. No external search service needed until 10M+ vectors.
5. **Background processing** — Document pipeline already runs async. Moving to Celery workers is a config change, not a rewrite.

## What Was Achieved

**Core RAG Pipeline (fully functional):**
- End-to-end document upload → text extraction → chunking → embedding → vector storage → retrieval → LLM answer
- PDF support with pdfplumber (table extraction, image-only detection, page boundary tracking)
- pgvector similarity search filtered by document, with relevance threshold gating
- Grounded answers via Groq (Llama 3.3 70B) with [SOURCE N] citations parsed and linked to UI

**Intelligent Features:**
- AI-generated suggested questions — the app analyzes uploaded documents and proposes 4 insightful questions
- Hybrid search (BM25 + vector) — combines Postgres full-text search with pgvector cosine similarity via Reciprocal Rank Fusion for better retrieval precision
- Streaming responses (SSE) — answers stream token-by-token with a blinking cursor; sources highlight in the document view before the answer finishes
- Vague query enrichment — follow-up questions like "tell me more" automatically include prior Q&A context
- Dual-model Groq budget manager — tracks RPD per model in Redis, auto-switches from 70B → 8B when primary is exhausted, giving ~1,900 usable requests/day on free tier
- Source highlighting — answers reference specific chunks, clicking source pills scrolls the document view
- Answer actions — copy answer, copy with sources, regenerate, ask follow-up

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

| Priority | Feature | Why It Matters | Scaling Impact |
|---|---|---|---|
| **High** | **Celery task queue** | Replace FastAPI BackgroundTasks with Celery + Redis broker for document processing. Enables horizontal worker scaling and retry logic for failed jobs. | Horizontal: N workers process N documents in parallel |
| **High** | **Evaluation harness** | Automated test suite with question-answer pairs measuring retrieval recall (P@5, MRR) and answer faithfulness (RAGAS). Currently quality assessment is manual. | Operational: catch retrieval regressions before they reach users |
| **High** | **OCR support (Tesseract)** | Image-only PDFs are currently rejected. Adding OCR unlocks scanned contracts, receipts, and legacy documents — the most common enterprise use case. | Feature: 40%+ of enterprise PDFs are scanned |
| **Medium** | **Dedicated vector DB (Qdrant)** | At 10M+ vectors, pgvector's single-node architecture becomes a bottleneck. Qdrant offers horizontal sharding, payload filtering, and quantization for memory efficiency. | Horizontal: shard vectors across N nodes |
| **Medium** | **Multi-document cross-referencing** | Schema supports multi-doc per user. Future: cross-document queries that search across all user documents simultaneously with document-level re-ranking. | Feature: "find contradictions between these two contracts" |
| **Medium** | **Kubernetes deployment** | Helm chart for production deployment with auto-scaling, health probes, config maps, and secrets management. Docker Compose → K8s is the natural next step. | Operational: auto-scale API pods 2→16 based on load |
| **Low** | **Embedding model fine-tuning** | Fine-tune MiniLM on domain-specific data (legal, medical, financial) for 15-25% retrieval improvement on specialized documents. | Vertical: better results without more compute |
| **Low** | **Document structure awareness** | Detect headings, sections, and lists during chunking for semantically meaningful splits. Use document hierarchy for hierarchical retrieval (section → paragraph → sentence). | Quality: more precise retrieval reduces hallucination |

## Full Design Documentation

See [BLUEPRINT.md](./BLUEPRINT.md) for the complete system design, database schema, RAG pipeline details, edge case analysis, and scalability architecture.
