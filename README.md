# Report RAG - Production-Grade Agentic Technical Report Generator

A defensible, agentic technical report generator that produces 30-40 page LaTeX reports with strict evidence grounding, citation validation, and resumable execution.

## Features

- **Defensible Grounding**: Every claim is backed by verbatim evidence quotes with exact substring validation
- **Citation Validation**: All citations are server-validated with exact character offsets
- **Resumable Execution**: Job-based architecture allows resuming interrupted runs
- **Hybrid Retrieval**: FTS + vector search with MMR diversification
- **Multi-Agent Workflow**: 8 specialized agents for different report generation tasks
- **Production-Ready**: Complete with retry logic, error handling, and state persistence

## Architecture

```
┌─────────────┐
│  FastAPI    │  ← REST API
│     API     │
└──────┬──────┘
       │
       │
┌──────▼──────────────────────────────────┐
│         PostgreSQL + pgvector            │
│  (documents, chunks, runs, jobs, etc.)  │
└──────▲──────────────────────────────────┘
       │
       │
┌──────┴──────┐
│   Worker    │  ← Background job processor
│   (Agents)  │
└─────────────┘
```

### Agent Workflow

1. **OutlineAgent** → Creates hierarchical report structure
2. **RetrievalAgent** → Hybrid FTS + vector search per section
3. **EvidenceAgent** → Extracts validated quotes with offsets
4. **ClaimAgent** → Generates claims from evidence
5. **DraftAgent** → Writes LaTeX from claims
6. **GlobalMemoryAgent** → Tracks definitions/notation
7. **GlobalConsistencyAgent** → Checks cross-section consistency
8. **FinalAssembler** → Assembles complete LaTeX document

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- OpenRouter API key

## Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd report-rag
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set your `OPENROUTER_API_KEY`:

```env
OPENROUTER_API_KEY=your_api_key_here
```

### 3. Start Services

```bash
docker-compose up -d
```

This starts:
- PostgreSQL with pgvector (port 5432)
- Ollama for embeddings (port 11434)
- API server (port 8000)
- Background worker

### 4. Pull Embedding Model

```bash
docker exec -it report_rag_ollama ollama pull nomic-embed-text
```

### 5. Run Database Migrations

```bash
docker exec -it report_rag_api alembic upgrade head
```

### 6. Verify Setup

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "healthy"}
```

## Usage

### 1. Upsert Documents

```bash
curl -X POST http://localhost:8000/documents/upsert \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Deep Learning Survey",
    "author": "John Doe",
    "year": 2024,
    "content": "Full document text here..."
  }'
```

Response:
```json
{
  "doc_id": "uuid-here",
  "chunk_count": 15,
  "existed": false
}
```

### 2. Create Run

```bash
curl -X POST http://localhost:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Survey of Deep Learning Techniques"
  }'
```

Response:
```json
{
  "run_id": "uuid-here",
  "topic": "Survey of Deep Learning Techniques",
  "status": "initializing"
}
```

### 3. Start Run

```bash
curl -X POST http://localhost:8000/runs/{run_id}/start
```

Response:
```json
{
  "run_id": "uuid-here",
  "job_id": "uuid-here",
  "message": "Run started, outline job enqueued"
}
```

### 4. Check Status

```bash
curl http://localhost:8000/runs/{run_id}
```

Response:
```json
{
  "run_id": "uuid-here",
  "topic": "Survey of Deep Learning Techniques",
  "status": "running",
  "job_counts": {
    "queued": 5,
    "running": 1,
    "done": 10,
    "failed": 0
  },
  "progress_percent": 62.5
}
```

### 5. Get Artifacts

```bash
curl http://localhost:8000/runs/{run_id}/artifacts
```

Returns outline nodes, evidence summary, claims summary, and drafts.

### 6. Get Final LaTeX

Once status is "completed":

```bash
curl http://localhost:8000/runs/{run_id}/latex > report.tex
```

Compile to PDF:

```bash
pdflatex report.tex
```

## Development

### Local Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start services
docker-compose up postgres ollama -d

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload

# Start worker (in separate terminal)
python -m app.worker
```

### Running Tests

```bash
pytest tests/ -v
```

### Code Structure

```
report-rag/
├── app/
│   ├── agents/         # 8 specialized agents
│   ├── models/         # SQLAlchemy ORM models
│   ├── routes/         # FastAPI endpoints
│   ├── schemas/        # Pydantic schemas
│   ├── services/       # Business logic
│   ├── main.py         # FastAPI app
│   └── worker.py       # Job processor
├── alembic/           # Database migrations
├── tests/             # Test suite
└── docker-compose.yml # Local deployment
```

## Railway Deployment

### 1. Create Railway Project

1. Sign up at [railway.app](https://railway.app)
2. Create new project from GitHub
3. Select the `zod1ach/reportrag` repository

### 2. Add PostgreSQL Database

1. In your Railway project, click **+ New**
2. Select **Database** → **PostgreSQL**
3. Wait for provisioning
4. Click on PostgreSQL service → **Data** tab → **Query**
5. Run: `CREATE EXTENSION IF NOT EXISTS vector;`

### 3. Configure Web Service (API + Frontend)

The first service Railway creates will be the web service:

1. Click on the GitHub service
2. Go to **Settings** → **Deploy**
3. **Start Command** should be: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - (This is already configured in `railway.json`)
4. Go to **Variables** tab and add:
   - `DATABASE_URL` (copy from PostgreSQL service connection string)
   - `OPENROUTER_API_KEY` (get from openrouter.ai)
   - All other variables from `.env.example`
5. Deploy

### 4. Add Worker Service

1. In your Railway project, click **+ New**
2. Select **GitHub Repo** → choose `zod1ach/reportrag`
3. **Important**: Go to **Settings** → **Deploy** IMMEDIATELY
4. **Override the start command** to: `python -m app.worker`
   - Railway will try to use the web command by default - you must override it
5. Go to **Variables** tab and add the **same environment variables** as web service
6. Deploy

### 5. Run Migrations

1. Click on your **Web service**
2. Go to **Deployments** tab
3. Click on the latest deployment
4. Open the service console/shell
5. Run: `alembic upgrade head`

### 6. Access Your Application

- Railway will provide a public URL (e.g., `https://reportrag-production.up.railway.app`)
- Visit the URL to access the frontend UI
- Upload documents and create report runs!

### Notes

- **Port Configuration**: Web service uses port 8000 (configured in `railway.json`)
- **Worker Service**: Must manually set start command to `python -m app.worker` in Railway settings
- **Ollama**: For embeddings, either:
  - Use external Ollama instance and set `OLLAMA_BASE_URL`
  - Or skip embeddings (system handles gracefully)

## Model Routing

The system uses specific OpenRouter models for different tasks:

- **Outline/Evidence/Claims/Memory**: `google/gemini-2.0-flash-exp:free`
- **Draft Generation**: `meta-llama/llama-3.3-70b-instruct:free`
- **Global Consistency/Assembly**: `amazon/nova-2-lite-v1:free`

See `app/services/llm_client.py` for the full allowed models list.

## Resumability

If the worker crashes or is stopped:

1. Jobs in "queued" or "failed" (with retries remaining) status will be picked up
2. Completed jobs are not re-executed
3. Simply restart the worker: `python -m app.worker`

The system will continue from where it left off.

## Troubleshooting

### "pgvector extension not found"

Run in postgres container:
```bash
docker exec -it report_rag_postgres psql -U postgres -d report_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### "Ollama model not found"

Pull the model:
```bash
docker exec -it report_rag_ollama ollama pull nomic-embed-text
```

### Worker not processing jobs

Check logs:
```bash
docker logs report_rag_worker -f
```

Ensure:
- Database is accessible
- OpenRouter API key is valid
- Ollama is running (if using server-side embeddings)

### Evidence validation failures

The system will automatically retry evidence extraction with corrective prompts. Check job error messages:

```sql
SELECT job_id, agent, status, last_error FROM jobs WHERE status = 'failed';
```

## Configuration

All configuration is via environment variables (see `.env.example`):

- **Database**: `DATABASE_URL`
- **LLM**: `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`
- **Embeddings**: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `EMBED_DIM`
- **Retrieval**: `FTS_SHORTLIST_SIZE`, `VECTOR_RERANK_SIZE`, `MMR_LAMBDA`
- **Chunking**: `CHUNK_TARGET_SIZE`, `CHUNK_OVERLAP_PERCENT`
- **Worker**: `WORKER_POLL_INTERVAL`, `MAX_JOB_RETRIES`

## Performance

- **Chunking**: ~6-10k characters per chunk with 10-15% overlap
- **Retrieval**: FTS shortlist of 200, vector rerank to 50, MMR diversification
- **Evidence Validation**: Exact substring matching with offset validation
- **Concurrency**: Single-threaded worker (configurable for multiple workers)

## Security

- Prompt injection warnings in all LLM calls
- Content hash deduplication prevents reprocessing
- API key validation and secure headers
- SQL injection protection via SQLAlchemy ORM

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes with tests
4. Submit pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
- GitHub Issues: [repository-url]/issues
- Documentation: This README

## Acknowledgments

Built with:
- FastAPI
- SQLAlchemy + PostgreSQL + pgvector
- OpenRouter API
- Ollama
- Pydantic

---

**Version**: 0.1.0
**Status**: Production-ready
