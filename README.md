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
```

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

**Local (now):** Docker Compose, 4 containers, single machine.

**Production:** Postgres → RDS/Cloud SQL. Redis → ElastiCache. API → ECS Fargate (stateless, horizontal scaling). Document processing → Celery workers. Frontend → S3 + CloudFront. pgvector ivfflat → HNSW at 1M+ vectors.

The API is stateless by design (JWT auth, no server sessions), so horizontal scaling requires only a load balancer.

## Known Limitations & Future Work

- **No OCR** — Image-only PDFs are detected and rejected with a clear message. Production would add Tesseract.
- **No streaming** — Groq is fast enough (~2s responses) that a loading state works. Production would add SSE.
- **Single document workspace** — Schema supports multi-doc; UI shows one at a time.
- **24-hour JWT** — Production would use short-lived access tokens + refresh tokens.

## Full Design Documentation

See [BLUEPRINT.md](./BLUEPRINT.md) for the complete system design, schema, RAG pipeline details, edge case analysis, and interview talking points.
