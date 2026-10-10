# ⚡ JobScout: Autonomous Multi-Stream Ingestion & Local LLM Matching Engine

An autonomous, production-hardened job scouting pipeline designed to continuously ingest, deduplicate, enrich, and semantically evaluate early-career software engineering and AI opportunities across global and domestic job markets.

Operates with a headless scraping layer, zero-cost local inference via **Ollama (Gemma 3:4B)**, dual command interfaces (interactive **Telegram C2 Bot** + matte charcoal **FastAPI Mission Control**), and a decoupled SQLite persistence layer.

---

## 🏗️ System Architecture

```
[ 6 Heterogeneous Ingestion Feeds ]
  ├── LinkedIn Guest API (India Early-Career)
  ├── Hacker News Who is Hiring (Algolia API)
  ├── RemoteOK API
  ├── We Work Remotely (WWR RSS)
  ├── Remotive API
  └── Jobicy API
                 │
                 ▼
     [ adapters/ Package ]
                 │
                 ▼
┌──────────────────────────────────────────────┐
│        Deduplication & Data Layer            │
│  - Primary Key URL/ID deduplication          │
│  - SQLite Schema Auto-Migrations (db.py)     │
│  - Run-time Telemetry & Ingestion Yields     │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│       Hybrid Evaluation Engine               │
│  - Stage 1: Deterministic Heuristic Filter   │
│  - Stage 2: Deep JD Enrichment (enricher.py) │
│  - Stage 3: Ollama (Gemma 3:4B) Scoring      │
└──────────────────────┬───────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌──────────────────┐       ┌──────────────────────┐
│   Telegram C2    │       │   FastAPI Web UI     │
│  Action Buttons  │       │   Matte Charcoal     │
│  - /status       │       │   Kanban Triage      │
│  - /pitch <role> │       │   Real-time Stats    │
│  - /run          │       │   One-Click Tracking │
└──────────────────┘       └──────────────────────┘
```

---

## 🎯 Key Engineering Decisions

### 1. Headless, Zero-Selenium LinkedIn Guest Scraping
* **Challenge:** Scraping LinkedIn typically relies on browser automation drivers (Selenium, Playwright), consuming 500MB+ RAM and frequently hitting bot challenges or login walls.
* **Architecture:** Reverse-engineered LinkedIn's unauthenticated public guest endpoints. The ingestion stream captures lightweight metadata cards, while `enricher.py` performs on-demand extraction of raw HTML descriptions (7,000+ characters) in under $250\text{ ms}$ with zero browser automation overhead.

### 2. Zero-Cost, Privacy-Preserving Local LLM Orchestration
* **Challenge:** Relying on commercial LLM APIs (OpenAI, Anthropic) incurs recurring costs and hard rate limits during high-volume ingestion sweeps.
* **Architecture:** Self-hosted **Gemma 3:4B** executed locally using **Ollama**. Evaluates job-to-profile alignment through structured scoring prompts and generates tailored 120-word cold outreach messages citing specific engineering projects directly from the candidate profile.

### 3. Decoupled Persistence & Safe Migrations
* Data handling is centralized in `db.py`, isolating network ingestion modules from the storage layer.
* Employs non-destructive schema migrations using `PRAGMA table_info` checks to evolve table definitions without wiping historical application tracking data.

---

## 🛠️ Tech Stack

* **Core Runtime:** Python 3.10+
* **Storage:** SQLite3 (WAL mode, parameterized queries)
* **Networking & Parsing:** `httpx`, `BeautifulSoup4`
* **Local Inference:** Ollama (`gemma3:4b`)
* **Web Services:** FastAPI, Uvicorn, Tailwind CSS
* **Control & Telemetry:** Telegram Bot API (long-polling worker with inline callbacks)

---

## 📂 Project Structure

```
job_scout/
├── adapters/                    # Ingestion source crawlers
│   ├── __init__.py
│   ├── hn_adapter.py            # Hacker News thread parser
│   ├── jobicy_adapter.py        # Jobicy API client
│   ├── linkedin_guest_adapter.py# Headless LinkedIn guest crawler
│   ├── remotive_adapter.py      # Remotive developer stream
│   └── wwr_adapter.py           # We Work Remotely RSS reader
├── scripts/                     # Operational utilities
│   ├── run_scout.bat            # Manual execution script with logging
│   ├── start_scout.bat          # Headless startup launcher
│   └── inspect_jobs.py          # Quick database inspection tool
├── analyzer.py                  # Candidate profile matching rules
├── bot_listener.py              # Interactive Telegram command listener
├── dashboard.py                 # FastAPI mission control UI
├── db.py                        # SQLite storage, queries, and migrations
├── dispatch.py                  # Notification dispatcher
├── enricher.py                  # On-demand full job description extractor
├── evaluate.py                  # Semantic scoring and evaluation pipeline
├── ingest.py                    # Multi-stream orchestrator
├── main.py                      # Master pipeline entry point
├── models.py                    # Typed data definitions
├── profile.json                 # Candidate skills and preferences
├── requirements.txt             # Locked project dependencies
└── .env.example                 # Configuration template
```

---

## 🚀 Quickstart & Setup

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/<your-username>/job_scout.git
cd job_scout

python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Secrets

Create a `.env` file from the template:

```bash
copy .env.example .env
```

Add your Telegram credentials:

```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
TELEGRAM_CHAT_ID="your_telegram_chat_id"
```

### 3. Initialize the Local Inference Model

Verify that [Ollama](https://ollama.ai) is running and pull the model:

```bash
ollama pull gemma3:4b
ollama serve
```

### 4. Running the Pipeline Components

* **Execute a full scout cycle:**
  ```bash
  python main.py
  ```

* **Launch the Telegram Command Deck:**
  ```bash
  python bot_listener.py
  ```

* **Start the Web Mission Control Dashboard:**
  ```bash
  python dashboard.py
  ```
  Access the dashboard in your browser at `http://127.0.0.1:8000`.