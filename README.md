# Brand Guardian AI — YouTube Ad Compliance Pipeline

![Python](https://img.shields.io/badge/Python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.128-green) ![LangGraph](https://img.shields.io/badge/LangGraph-1.0-orange) ![Azure](https://img.shields.io/badge/Azure-Container%20Apps-blue)

An AI-powered compliance pipeline that audits YouTube ads against **YouTube Ad Policies** and **FTC Influencer Guidelines**. Paste any YouTube URL and get a structured report of violations in seconds.

## How It Works

```
YouTube URL
    ↓
YouTube Data API v3 (extract title, description, tags)
    ↓
Azure AI Search (RAG — retrieve relevant compliance rules)
    ↓
GPT-4o Auditor (reason over content vs rules)
    ↓
Structured Compliance Report (PASS/FAIL + severity-graded violations)
```

The pipeline is built as a **LangGraph** directed graph with two nodes:
- **Indexer Node** — fetches video metadata from YouTube Data API v3
- **Auditor Node** — performs RAG against indexed compliance PDFs, then calls GPT-4o to detect violations

---

## Architecture

| Component | Service | Purpose |
|---|---|---|
| Workflow Engine | LangGraph | Orchestrates Indexer → Auditor pipeline |
| Video Metadata | YouTube Data API v3 | Extracts title, description, tags |
| Compliance Rules | Azure AI Search | Vector store of YouTube Ad Specs + FTC Influencer Guide PDFs |
| LLM | Azure OpenAI GPT-4o | Reasons over content vs retrieved rules |
| Embeddings | Azure OpenAI text-embedding-3-small | Embeds compliance rule chunks |
| API Server | FastAPI + Uvicorn | REST API serving the pipeline |
| Deployment | Azure Container Apps | Serverless container hosting |
| CI/CD | GitHub Actions | Auto build + deploy on every push to main |
| Observability | Azure Application Insights | Telemetry, tracing, structured logging |

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Azure account with the following resources:
  - Azure OpenAI (GPT-4o + text-embedding-3-small deployments)
  - Azure AI Search (Free tier works)
  - Azure Application Insights
- Google Cloud account with YouTube Data API v3 enabled

---

## Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/shubh209/Youtube-Ads-Compliance-Pipeline.git
cd Youtube-Ads-Compliance-Pipeline
```

### 2. Install dependencies

```bash
pip install uv
uv pip install --system .
```

### 3. Set up environment variables

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` and fill in all values (see Environment Variables section below).

### 4. Index the compliance documents

Before running the pipeline, you need to index the compliance PDFs into Azure AI Search:

```bash
python backend/scripts/index_documents.py
```

This reads the PDFs in `backend/data/` and uploads them as vector embeddings to your Azure AI Search index. You only need to do this once.

### 5. Run the API server

```bash
uv run uvicorn backend.src.api.server:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### 6. Test it

Open `http://localhost:8000/docs` in your browser — this is the auto-generated Swagger UI where you can run a test audit:

```json
POST /audit
{
  "video_url": "https://youtu.be/dT7S75eYhcQ"
}
```

Or use the CLI:

```bash
python main.py https://youtu.be/dT7S75eYhcQ

# Or interactive mode (will prompt for URL):
python main.py
```

---

## Environment Variables

Create a `.env` file in the project root with the following variables:

```env
# ── Azure OpenAI ──────────────────────────────────────────
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<your-api-key>
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# ── Azure AI Search ───────────────────────────────────────
AZURE_SEARCH_ENDPOINT=https://<your-resource>.search.windows.net
AZURE_SEARCH_API_KEY=<your-admin-key>
AZURE_SEARCH_INDEX_NAME=compliance-docs

# ── Azure Video Indexer (optional — for OCR) ──────────────
AZURE_VI_ACCOUNT_ID=<your-account-id>
AZURE_VI_LOCATION=eastus
AZURE_SUBSCRIPTION_ID=<your-subscription-id>
AZURE_RESOURCE_GROUP=<your-resource-group>
AZURE_VI_NAME=<your-vi-resource-name>

# ── YouTube Data API ──────────────────────────────────────
YOUTUBE_API_KEY=<your-google-api-key>

# ── Azure Application Insights ────────────────────────────
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=<key>;IngestionEndpoint=...

# ── LangSmith (optional — for tracing) ───────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your-langsmith-key>
LANGCHAIN_PROJECT=brand-guardian-ai
```

### How to get each key

**Azure OpenAI** — Azure Portal → Azure OpenAI resource → Keys and Endpoint

**Azure AI Search** — Azure Portal → Azure AI Search → Settings → Keys

**YouTube Data API** — [console.cloud.google.com](https://console.cloud.google.com) → Enable YouTube Data API v3 → Credentials → Create API Key

**Azure Application Insights** — Azure Portal → Application Insights → Properties → Connection String

**LangSmith** — [smith.langchain.com](https://smith.langchain.com) → Settings → API Keys (optional but recommended for debugging)

---

## Project Structure

```
Youtube-Ads-Compliance-Pipeline/
├── main.py                          # CLI entry point
├── Dockerfile                       # Container definition
├── pyproject.toml                   # Python dependencies
├── .env.example                     # Environment variable template
├── index.html                       # Frontend UI
├── backend/
│   ├── data/
│   │   ├── youtube-ad-specs.pdf     # YouTube Ad Policy document
│   │   └── 1001a-influencer-guide.pdf  # FTC Influencer Guide
│   ├── scripts/
│   │   └── index_documents.py       # One-time PDF indexing script
│   └── src/
│       ├── api/
│       │   ├── server.py            # FastAPI application
│       │   └── telemetry.py         # Azure Monitor setup
│       ├── graph/
│       │   ├── nodes.py             # Indexer + Auditor nodes
│       │   ├── state.py             # LangGraph state schema
│       │   └── workflow.py          # LangGraph graph definition
│       └── services/
│           └── video_indexer.py     # YouTubeTranscriptService
└── .github/
    └── workflows/
        └── deploy.yml               # GitHub Actions CI/CD
```

---

## API Reference

### `POST /audit`

Triggers a full compliance audit for a YouTube video.

**Request:**
```json
{
  "video_url": "https://youtu.be/dT7S75eYhcQ"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "video_id": "vid_xxxxxxxx",
  "status": "FAIL",
  "final_report": "Summary of findings...",
  "compliance_results": [
    {
      "category": "FTC Disclosure",
      "severity": "CRITICAL",
      "description": "No sponsorship disclosure found..."
    }
  ]
}
```

**Severity levels:**
- `CRITICAL` — Must be fixed before the ad can run
- `WARNING` — Should be reviewed
- `INFO` — Minor recommendation

### `GET /health`

Liveness check.

```json
{"status": "healthy", "service": "Brand Guardian AI"}
```

### `GET /docs`

Interactive Swagger UI for testing the API in the browser.

---

## Deployment

The project auto-deploys to **Azure Container Apps** on every push to `main` via GitHub Actions.

### Manual deployment

```bash
# Build image
docker build -t brand-guardian-api .

# Push to Azure Container Registry
az acr login --name <your-registry>
docker tag brand-guardian-api <your-registry>.azurecr.io/brand-guardian-api:latest
docker push <your-registry>.azurecr.io/brand-guardian-api:latest

# Update Container App
az containerapp update \
  --name brand-guardian-api \
  --resource-group <your-resource-group> \
  --image <your-registry>.azurecr.io/brand-guardian-api:latest
```

### Required GitHub Secrets for CI/CD

| Secret | Description |
|---|---|
| `AZURE_CREDENTIALS` | Azure service principal JSON (from `az ad sp create-for-rbac`) |
| `REGISTRY_NAME` | Azure Container Registry name (without `.azurecr.io`) |
| `BRANDGUARDIANAPI_REGISTRY_USERNAME` | ACR username |
| `BRANDGUARDIANAPI_REGISTRY_PASSWORD` | ACR password |

---

## Dependencies

All dependencies are managed via `pyproject.toml` and installed with `uv`.

| Package | Purpose |
|---|---|
| `langgraph` | Pipeline orchestration |
| `langchain-openai` | Azure OpenAI integration |
| `langchain-community` | Azure AI Search vector store |
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server |
| `pydantic` | Request/response validation |
| `azure-identity` | Azure managed identity auth |
| `azure-monitor-opentelemetry` | Application Insights telemetry |
| `python-dotenv` | Environment variable loading |
| `requests` | HTTP client for YouTube + VI APIs |
| `pypdf` | PDF loading for document indexing |

---

## License

MIT