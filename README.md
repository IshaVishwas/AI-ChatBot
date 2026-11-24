# Lyftr AI — Full-Stack AI Chatbot with LiteLLM Gateway

A production-ready full-stack AI chatbot application featuring a React (Vite) frontend, FastAPI backend, SQLite conversation persistence, LiteLLM AI Gateway integration with automatic multi-key failover, sub-millisecond response caching, per-request token and latency telemetry, and dynamic failure simulation.

---

## 1. Live URLs

- **Frontend Application (Vercel)**: `https://lyftr-ai-chatbot.vercel.app` *(Production deployment target; see deployment guide below)*
- **Backend API (Docker / Cloud Run / VPS)**: `https://api-lyftr.example.com` *(Configured with `/health`, `/chat`, and `/sessions/{session_id}/messages`)*
- **Local Frontend**: [http://localhost:3000](http://localhost:3000)
- **Local Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

*(Note: Live deployment URLs require user cloud account credentials and DNS binding. Complete step-by-step instructions to deploy to Vercel and any Docker-compatible host are provided below).*

---

## 2. Run Locally: With Docker and Without

### Architecture Overview

```
                          ┌───────────────────────────┐
                          │ React + Vite Frontend UI  │
                          │   (Port 3000 / Vercel)    │
                          └─────────────┬─────────────┘
                                        │ HTTP / JSON
                                        ▼
                          ┌───────────────────────────┐
                          │   FastAPI Gateway Backend │
                          │     (Port 8000 / Docker)  │
                          └──────┬─────────────┬──────┘
                                 │             │
                ┌────────────────┴────┐   ┌────┴────────────────┐
                ▼                     ▼   ▼                     ▼
        ┌──────────────┐     ┌───────────────┐        ┌───────────────────┐
        │ SQLite DB    │     │ LiteLLM Cache │        │ Key Failover Pool │
        │ (/data volume│     │ (Local Memory)│        │ key_1 ──► key_2   │
        └──────────────┘     └───────────────┘        └─────────┬─────────┘
                                                                │
                                                                ▼
                                                      ┌───────────────────┐
                                                      │  AI Provider API  │
                                                      │ (Gemini / OpenAI) │
                                                      └───────────────────┘
```

---

### Option A: Running with Docker & Docker Compose (Recommended)

Ensure Docker and Docker Compose are installed.

1. **Clone the repository and enter the directory**:
   ```bash
   git clone <repo-url>
   cd Isha
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your real API keys if available
   ```

3. **Start all services with Makefile**:
   ```bash
   make up
   ```
   *Or using Docker Compose directly:*
   ```bash
   docker compose up --build -d
   ```

4. **Access the application**:
   - Frontend: [http://localhost:3000](http://localhost:3000)
   - Backend API: [http://localhost:8000](http://localhost:8000)
   - Health Check: [http://localhost:8000/health](http://localhost:8000/health)

5. **Stop services**:
   ```bash
   make down
   ```

---

### Option B: Running Locally Without Docker

#### Prerequisites
- Python 3.11+
- Node.js 18+ & npm

#### 1. Backend Setup

```bash
cd backend

# Create and activate virtual environment (optional but recommended)
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run backend with uvicorn
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend will initialize the SQLite schema automatically at `./app.db` and start listening on `http://localhost:8000`.

#### 2. Frontend Setup

In a separate terminal:

```bash
cd frontend

# Install npm dependencies
npm install

# Start Vite development server
npm run dev
```
The frontend will start on [http://localhost:5173](http://localhost:5173) or [http://localhost:3000](http://localhost:3000).

---

## 3. Design Decisions

### A. Key Fallback Layer
- **Rotation Architecture**: A pool of at least 2 API keys is parsed from the environment variable `LLM_API_KEYS=key1,key2`.
- **Internal Mapping**: Keys are mapped internally to `key_1`, `key_2`, `key_3`, etc. Real secret keys are **never** exposed in metadata, API responses, frontend, or logs.
- **Failover Logic**: If a provider call with `key_1` fails due to HTTP 429 (Rate Limit), quota errors, or provider 5xx errors (500, 502, 503), the gateway logs the incident, increments `fallback_attempts`, and automatically retries with `key_2`.
- **503 Exhaustion**: If all configured keys fail or are exhausted, the API cleanly returns HTTP 503:
  ```json
  {"detail": "all providers unavailable"}
  ```
  No stack traces or secret keys are ever leaked.

### B. LiteLLM Response Caching
- **Deterministic Cache Keys**: LiteLLM's local memory cache (`Cache(type="local")`) is enabled. Cache keys are strictly derived from the model identifier, optional system prompt, full conversation history, and current user message.
- **Session Compatibility**: Two distinct sessions asking the identical initial question produce the identical message sequence, triggering a cache hit (`LLM_CACHE`).
- **Isolation**: When conversation history diverges, the sequence of messages diverges, ensuring separate conversations never falsely share cached outputs.
- **Contract Adherence**: For cache hits:
  - `resolution_source` is strictly `"LLM_CACHE"`
  - `key_id` is strictly `null`
  - `fallback_attempts` is strictly `0`
  - Original token counts are preserved from the initial generation
  - Latency is sub-millisecond

### C. SQLite Session Storage & Transactions
- **Atomic Persistence**: Messages are persisted **only after successful completion** of the model inference. If all providers fail or return 503, no user or assistant messages are committed to the database.
- **Order Guarantee**: Messages are indexed by auto-incrementing ID and queried in ascending order (`Message.id.asc()`), guaranteeing chronological conversation flow.
- **Session Isolation**: Each conversation is segmented by `session_id`. Unknown sessions queried via `GET /sessions/{session_id}/messages` return HTTP 404:
  ```json
  {"detail": "session not found"}
  ```
- **System Prompt Exclusion**: System prompts are passed to model inference for steerability but are excluded from the returned history endpoint.

---

## 4. Verification: How to See Failover, Cache Hits and Token Telemetry

### 1. Verify Health Endpoint
```bash
curl -X GET http://localhost:8000/health
```
**Expected Response:**
```json
{
  "status": "ok",
  "keys_configured": 2,
  "cache_enabled": true
}
```

---

### 2. Verify Live Inference & Token Telemetry
Send a new user query:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "demo-session-1", "message": "What is Python?"}'
```
**Expected Response:**
```json
{
  "session_id": "demo-session-1",
  "reply": "...",
  "metadata": {
    "resolution_source": "LIVE_INFERENCE",
    "model": "gemini/gemini-1.5-flash",
    "latency_ms": 250,
    "input_tokens": 12,
    "output_tokens": 35,
    "key_id": "key_1",
    "fallback_attempts": 0
  }
}
```

---

### 3. Verify Cache Hit (`LLM_CACHE`)
Send the **exact same query** in a different session:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "demo-session-2", "message": "What is Python?"}'
```
**Expected Response:**
```json
{
  "session_id": "demo-session-2",
  "reply": "...",
  "metadata": {
    "resolution_source": "LLM_CACHE",
    "model": "gemini/gemini-1.5-flash",
    "latency_ms": 1,
    "input_tokens": 12,
    "output_tokens": 35,
    "key_id": null,
    "fallback_attempts": 0
  }
}
```
*Note that `resolution_source` is `LLM_CACHE`, `key_id` is `null`, `fallback_attempts` is `0`, and latency is < 5ms.*

---

### 4. Verify Automatic Failover with `X-Simulate-Failure`
Simulate a rate limit (HTTP 429) on `key_1`:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: key_1=429" \
  -d '{"session_id": "demo-failover", "message": "Explain key failover."}'
```
**Expected Response:**
```json
{
  "session_id": "demo-failover",
  "reply": "...",
  "metadata": {
    "resolution_source": "LIVE_INFERENCE",
    "model": "gemini/gemini-1.5-flash",
    "latency_ms": 210,
    "input_tokens": 14,
    "output_tokens": 40,
    "key_id": "key_2",
    "fallback_attempts": 1
  }
}
```
*Notice that `key_id` rotated to `key_2` and `fallback_attempts` is `1`.*

---

### 5. Verify All Providers Failing (503 Exhaustion)
Simulate failure across all keys using `*=429` or `key_1=429,key_2=500`:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-Simulate-Failure: *=429" \
  -d '{"session_id": "demo-exhaustion", "message": "Should fail gracefully."}'
```
**Expected Response (HTTP 503):**
```json
{
  "detail": "all providers unavailable"
}
```

Verify that no failed message was persisted:
```bash
curl -X GET http://localhost:8000/sessions/demo-exhaustion/messages
```
**Expected Response (HTTP 404):**
```json
{
  "detail": "session not found"
}
```

---

## 5. Setup Used: Editor and AI Tools

- **Operating System**: Windows 11 (64-bit)
- **Runtimes**: Python 3.11.9, Node.js v26.13.0, npm 11.20.0
- **Development Editor**: VS Code / Antigravity IDE
- **AI Tooling & Orchestration**: Antigravity Autonomous Agent (Google DeepMind Gemini 3.8 Flash)
- **Testing Framework**: Pytest 9.2.0 with `pytest-asyncio` and `httpx`
- **Frontend Bundler**: Vite 8.3.8 with React 19

---

## 6. Bonus Features

1. **Rich Markdown & Syntax Highlighting**:
   - Code blocks render in a dark terminal style with language tags and an interactive one-click "Copy Code" button.
   - Clean support for headers, bold, italics, blockquotes, and lists.
2. **Visual Telemetry Badges**:
   - Every AI response features a real-time status bar showing resolution source (`LIVE_INFERENCE` vs `LLM_CACHE`), model name, server-side latency in ms, input tokens, output tokens, and the serving key ID with fallback count badge.
3. **Interactive Pre-Built Prompt Suggestions**:
   - When a session starts, quick prompt pills allow instant demonstration of architecture, failover, and caching.
4. **Dynamic System Prompt Drawer**:
   - Collapsible system prompt input with exact `data-testid="system-prompt-input"` allows users to customize bot behavior on a per-session basis.
5. **Real-Time Health Monitor**:
   - The sidebar polls and displays gateway connectivity, configured key pool size, and caching status.
6. **Graceful Error Toast Banners**:
   - Validation errors (422) and provider exhaustion (503) are surfaced in elegant, dismissible UI alert banners rather than crashing the interface.

---

## 7. Automated Testing Suite

The repository includes a comprehensive 20-test Pytest suite covering all functional requirements.

To run tests:
```bash
cd backend
python -m pytest tests -v
```

### Test Coverage Summary:
- `tests/test_health.py`: Health endpoint status, key pool size >= 2, and cache enablement.
- `tests/test_validation.py`: Missing `session_id`, empty `session_id`, oversized `session_id` (>128), missing `message`, empty/whitespace `message`, oversized `message` (>4000), and invalid JSON.
- `tests/test_chat_and_memory.py`: Successful POST /chat response contract, multi-turn conversation memory, session isolation, session message history retrieval, and 404 for unknown sessions.
- `tests/test_cache.py`: Identical request cache hit, identical reply, token count preservation, `key_id=null`, `fallback_attempts=0`, and cache isolation across differing messages.
- `tests/test_failover.py`: Automatic key failover on provider exception, `X-Simulate-Failure: key_1=429`, `X-Simulate-Failure: key_1=500`, all keys failing (HTTP 503), non-persistence of failed requests, and disabled simulation behavior.

---

## 8. Deployment Preparation

### Frontend Deployment (Vercel)
1. Push this repository to GitHub / GitLab.
2. Go to [vercel.com](https://vercel.com) and import the project.
3. Set the **Root Directory** to `frontend`.
4. In **Environment Variables**, set:
   - `VITE_API_URL`: Your deployed backend URL (e.g., `https://api.yourdomain.com`).
5. Deploy. `frontend/vercel.json` ensures all single-page application routes are properly handled.

### Backend Deployment (Docker / Cloud Run / Railway / VPS)
1. The backend multi-stage `Dockerfile` is located in `backend/Dockerfile`.
2. Build and push image:
   ```bash
   docker build -t your-registry/lyftr-backend:latest -f backend/Dockerfile backend/
   docker push your-registry/lyftr-backend:latest
   ```
3. Run container with a persistent volume mounted at `/data`:
   ```bash
   docker run -d \
     -p 8000:8000 \
     -v lyftr_sqlite_data:/data \
     -e DATABASE_URL="sqlite:////data/app.db" \
     -e LLM_API_KEYS="your_key_1,your_key_2" \
     -e LLM_MODEL="gemini/gemini-1.5-flash" \
     -e ALLOWED_ORIGINS="https://your-frontend.vercel.app" \
     -e ENABLE_FAILURE_SIMULATION="false" \
     your-registry/lyftr-backend:latest
   ```

---

## 9. Environment Variables Reference

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `LLM_API_KEYS` | `mock-key-1,mock-key-2` | Comma-separated API keys (minimum 2 required). |
| `LLM_MODEL` | `gemini/gemini-1.5-flash` | Model identifier passed to LiteLLM. |
| `DATABASE_URL` | `sqlite:///./app.db` | SQLite connection URL (`sqlite:////data/app.db` in Docker). |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000` | Comma-separated CORS allowed origins. |
| `ENABLE_FAILURE_SIMULATION` | `true` | Allows `X-Simulate-Failure` header when true. |
| `LITELLM_CACHE_ENABLED` | `true` | Enables LiteLLM in-memory response caching. |
| `HOST` | `0.0.0.0` | Server listening interface. |
| `PORT` | `8000` | Server listening port. |
| `VITE_API_URL` | `http://localhost:8000` | Frontend configuration for backend base URL. |

---

## 10. Honest Limitations & Verification Status

- **Docker daemon on host**: The host machine does not have the `docker` binary installed in its Windows PATH. The multi-stage `Dockerfile`s, `docker-compose.yml`, and `Makefile` were authored strictly following Docker production standards and verified for syntactical correctness, but live container orchestration was not run locally.
- **Real Provider Inference**: In local testing, requests were tested with unit tests and simulated failures. When using real provider inference, users must supply valid API keys in `.env` (e.g. Google Gemini or OpenAI API keys).

