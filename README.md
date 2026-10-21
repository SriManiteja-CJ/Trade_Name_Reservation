# Trade Name Intelligence Service (TNIS)
### Department of Economic Development — Government of Umm Al Quwain (DED UAQ)

A high-performance, bilingual (Arabic & English), AI-assisted trade name verification, compliance screening, and recommendation system designed to modernize trade name reservation for the Government of Umm Al Quwain.

---

## 🏛️ System Architecture & Port Separation

The solution runs as a decoupled full-stack architecture with strict port separation:

| Service | Port | Host URL | Description |
| :--- | :---: | :---: | :--- |
| **Frontend** | **`3000`** | `http://localhost:3000` | Modern React 19 + Vite luxury UI (Bilingual English / Arabic RTL) |
| **Backend** | **`8000`** | `http://localhost:8000` | FastAPI asynchronous REST API, SQLite/PostgreSQL, Prometheus exporter |
| **Swagger Docs** | **`8000`** | `http://localhost:8000/docs` | Interactive OpenAPI Swagger UI documentation |
| **Metrics** | **`8000`** | `http://localhost:8000/metrics` | Zero-dependency Prometheus 0.0.4 metrics exporter |

```
                       ┌──────────────────────────────────────────────┐
                       │       React 19 Frontend (Port 3000)          │
                       │  - Validation & Suggestions Module           │
                       │  - Smart Hybrid Registry Search              │
                       │  - Lexicon Governance & Evasion Detection    │
                       │  - AI Reviewer Copilot Dossier               │
                       └──────────────────────┬───────────────────────┘
                                              │ HTTP JSON (CORS)
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │       FastAPI Backend (Port 8000)            │
                       │  - Deterministic Rule Gates (F1–F14)         │
                       │  - Hybrid Vector/Phonetic Search Engine      │
                       │  - vLLM AI Gateway (Fail-Closed Gatekeeper)  │
                       │  - Reviewer Copilot Closed-Loop Feedback     │
                       └──────────────────────┬───────────────────────┘
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │ PostgreSQL 16 + pgvector│                     │ Self-Hosted vLLM / TEI  │
         │ (Active Registry & DB)  │                     │ (Internal DED Gateway)  │
         └─────────────────────────┘                     └─────────────────────────┘
```

---

## 📂 Repository Layout

```
Trade Name Intelligence Service/
├── .gitignore                     # Git ignore rules (Python, Node, DBs, logs)
├── .env.example                   # Master environment configuration template
├── README.md                      # Comprehensive project documentation
│
├── backend/                       # FastAPI Backend Engine (Port 8000)
│   ├── .env                       # Active backend environment variables
│   ├── .env.example               # Backend environment variables template
│   ├── api/                       # API routes, middleware, and schemas
│   │   ├── routes/                # trade_name.py, admin.py
│   │   ├── auth.py                # Channel detection (online / walkin) & JWT
│   │   ├── metrics.py             # Zero-dependency Prometheus metrics exporter
│   │   └── main.py                # FastAPI application entrypoint
│   ├── config/                    # Pydantic BaseSettings & feature flags (off/shadow/on)
│   ├── db/                        # Database models (Lexicon, Registry, AiDecisionAudit)
│   ├── pipeline/                  # Deterministic gates, normalizers, decision policy
│   ├── index/                     # Hybrid search (trigram, phonetic, vector embeddings)
│   ├── llm/                       # Self-hosted vLLM gateway with circuit breaker
│   ├── copilot/                   # Reviewer Copilot dossier & feedback service
│   ├── eval/                      # Evaluation harness & gold set benchmark
│   ├── tests/                     # 131 automated unit, integration, and E2E tests
│   ├── Dockerfile                 # Production backend container definition
│   ├── docker-compose.yml         # Full-stack composition (Postgres, Redis, App)
│   └── pyproject.toml             # Python dependencies and project metadata
│
└── frontend/                      # React Frontend Application (Port 3000)
    ├── .env                       # Active frontend environment variables
    ├── .env.example               # Frontend environment variables template
    ├── index.html                 # HTML shell with Google Fonts (Outfit, Inter, Cairo)
    ├── vite.config.js             # Vite configuration pinned to port 3000
    ├── package.json               # Node dependencies (React 19, Vite)
    └── src/
        ├── index.css              # Custom Vanilla CSS luxury design system
        ├── config.js              # API destination resolver (VITE_API_BASE_URL)
        ├── App.jsx                # Main application tab router & health polling
        └── components/
            ├── Header.jsx         # Bilingual switch, channel toggle, status dot
            ├── ValidationTab.jsx  # Trade name validation, presets, legacy contract
            ├── RegistrySearchTab.jsx # Keyword search & fast duplicate check
            ├── LexiconTab.jsx     # AI evasion variants & human approval queue
            ├── ReviewerCopilotTab.jsx # Officer review dossier & decision buttons
            └── Footer.jsx         # DED UAQ compliance & legal declarations
```

---

## ⚙️ Environment Variables

### Backend Configuration (`backend/.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `API_PORT` | `8000` | Port for the FastAPI server |
| `DATABASE_URL` | `postgresql+asyncpg://tnis:tnis_secure_password@localhost:5432/tnis_db` | PostgreSQL connection string |
| `VLLM_BASE_URL` | `http://localhost:8080/v1` | Self-hosted OpenAI-compatible vLLM endpoint |
| `TEI_BASE_URL` | `http://localhost:8081` | Text Embeddings Inference endpoint |
| `AI_ANALYZER` | `shadow` | Mode: `off`, `shadow`, or `on` (Spec §5.3) |
| `AI_SUGGESTIONS` | `shadow` | Mode: `off`, `shadow`, or `on` |
| `AI_REVIEWER_BRIEF` | `shadow` | Mode: `off`, `shadow`, or `on` |
| `AI_SEARCH` | `shadow` | Mode: `off`, `shadow`, or `on` |
| `AI_LEXICON_PROPOSALS`| `shadow` | Mode: `off`, `shadow`, or `on` |
| `LLM_TIMEOUT_SECONDS`| `2.5` | Fast timeout for validation path |

### Frontend Configuration (`frontend/.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Backend API URL accessed from the browser |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.11+**
- **Node.js 18+** and **npm**

---

### 2. Running the Backend (Port 8000)

Open a terminal and execute:

```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- Prometheus Metrics: `http://localhost:8000/metrics`
- System Health: `http://localhost:8000/health`

---

### 3. Running the React Frontend (Port 3000)

Open a second terminal and execute:

```powershell
cd frontend
npm run dev
```
- React Application: `http://localhost:3000`

---

### 4. Running with Docker Compose

To start the full stack including PostgreSQL with pgvector, Redis, and the FastAPI application:

```bash
cd backend
docker-compose up -d
```

---

## 🧪 Testing & Quality Assurance

### Run Automated Backend Test Suite
The backend contains **131 comprehensive tests** covering deterministic gates, phonetic indexing, decision policies, reviewer briefs, and lexicon proposals:

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -v
```
*Current Status: 131 passed in ~15s (100% passing).*

### Run Gold Benchmark Evaluation Harness
Runs the 100 gold standard trade name test cases through the complete intelligence pipeline:

```powershell
cd backend
.venv\Scripts\python.exe -m eval.harness
```
*Benchmark Results: 100% Accuracy, 0% False Block Rate, 100% Prompt Injection Safety Pass.*

### Build Frontend Production Bundle
```powershell
cd frontend
npm run build
```
*Builds production assets to `frontend/dist/` with zero errors.*

---

## 📜 Compliance & Legal Framework

This service is engineered in strict accordance with:
- **UAE Federal Law No. (37) of 1992** on Trademarks and its amendments.
- **Federal Decree-Law No. (36) of 2021** on Trademarks.
- **Executive Regulations of Umm Al Quwain Department of Economic Development**.
- **N1 Fail-Closed Guarantee**: In case of LLM unavailability, the system falls back safely without unverified auto-approvals.
- **N3 Audit Logging**: Every transaction, decision, and risk score is permanently audited.
- **N9 Additive Backward Compatibility**: All legacy DED boolean response flags are preserved intact.
