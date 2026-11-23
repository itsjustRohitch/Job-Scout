# ⚡ JobScout: Autonomous Multi-Stream Ingestion & Local LLM Matching Engine

An autonomous, production-hardened job scouting pipeline designed to continuously ingest, deduplicate, enrich, and evaluate early-career software engineering and AI opportunities across global and domestic job markets.

Operates with a headless scraping layer, zero-cost local inference via **Ollama (Gemma 3:4B)**, multi-modal control interfaces (interactive **Telegram C2 Bot**, custom zero-framework **ReAct Agent**, and matte charcoal **FastAPI Mission Control**), and a decoupled SQLite persistence layer.

## 🏗️ System Architecture

![JobScout System Architecture](assets/architecture.png)

```
[ 6 Heterogeneous Ingestion Feeds ]
  ├── LinkedIn Guest API (India Early-Career)
  ├── Hacker News Who is Hiring (Algolia API)
  ├── RemoteOK API (ingest.py)
  ├── We Work Remotely (WWR RSS)
  ├── Remotive API
  └── Jobicy API
                 │
                 ▼
  [ ingest.py + adapters/ Package ]
                 │
                 ▼
┌──────────────────────────────────────────────┐
│        Deduplication & Data Layer            │
│  - Primary Key URL/ID deduplication          │
│  - Cross-Source Fuzzy Matching & Pruning     │
│  - SQLite Schema Auto-Migrations (db.py)     │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│       Hybrid Evaluation Engine               │
│  - Stage 1: Deterministic Heuristic Scoring  │
│  - Stage 2: Automatic Cutoff (<70% -> Pass)  │
│  - Stage 3: Deep JD Enrichment (enricher.py) │
│  - Stage 4: Ollama (Gemma 3:4B) Dossiers     │
└──────────────────────┬───────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────────────┐
│   Telegram C2    │ │ ReAct Agent  │ │    FastAPI Web UI    │
│  Inline Buttons  │ │  (agent.py)  │ │    Matte Charcoal    │
│  - /status       │ │ Zero-Wrapper │ │  - Last 7 Days Feed  │
│  - /saved        │ │ Tool-Calling │ │  - Match >= 70% Cut  │
│  - /pitch <id>   │ │ Investigation│ │  - Kanban Triage     │
│  - /run          │ │ & Pitching   │ │  - One-Click Purge   │
└──────────────────┘ └──────────────┘ └──────────────────────┘
```

## 🎯 Key Engineering Decisions

### 1. Headless, Zero-Selenium LinkedIn Guest Scraping

* **Challenge:** Scraping LinkedIn typically relies on browser automation drivers (Selenium, Playwright), consuming 500MB+ RAM and frequently hitting bot challenges or login walls.
* **Architecture:** Reverse-engineered LinkedIn's unauthenticated public guest endpoints. The ingestion stream captures lightweight metadata cards, while `enricher.py` performs on-demand extraction of raw HTML descriptions (7,000+ characters) with zero browser automation overhead.

### 2. Zero-Cost, Privacy-Preserving Local LLM Orchestration

* **Challenge:** Relying on commercial LLM APIs (OpenAI, Anthropic) incurs recurring costs and hard rate limits during high-volume ingestion sweeps.
* **Architecture:** Self-hosted **Gemma 3:4B** executed locally using **Ollama** over raw `httpx` calls. Evaluates job-to-profile alignment through structured scoring prompts, creates technical candidate dossiers, and generates tailored 120-word cold outreach messages citing specific engineering projects directly from `profile.json`.

### 3. Custom Zero-Framework ReAct Agent (`agent.py`)

* **Challenge:** Heavy agent frameworks add unnecessary dependency bloat and obscure tool-execution control flow.
* **Architecture:** Built a pure-Python Reason + Act (ReAct) supervisor loop with regex action parsing and a direct tool registry (`get_unreviewed_jobs`, `enrich_job`, `evaluate_and_pitch`, `dispatch_alert`, `update_status`) backed by SQLite state.

### 4. Strict 70% Fit Cutoff & Decoupled Persistence

* **Quality Filtering:** Postings scoring `< 70%` against profile criteria are automatically discarded as `pass` during evaluation, shielding the feed from low-signal noise.
* **Automated Maintenance:** Features built-in cross-source fuzzy deduplication (`GROUP BY position, company`) and one-click database pruning (`Purge < 70%` and non-Latin script filtering).
* **Safe Migrations:** Employs non-destructive SQLite schema migrations using `PRAGMA table_info` checks to evolve table definitions without wiping historical tracking data.

## 🛠️ Tech Stack

* **Core Runtime:** Python 3.10+
* **Storage:** SQLite3 (parameterized queries, `PRAGMA` auto-migrations)
* **Networking & Parsing:** `httpx`, `BeautifulSoup4`, `lxml`, `feedparser`
* **Data Validation:** `Pydantic`
* **Local Inference:** Ollama (`gemma3:4b`)
* **Agentic Orchestration:** Custom pure-Python tool-calling ReAct loop (`agent.py`)
* **Web Services:** FastAPI, Uvicorn, Tailwind CSS
* **Control & Telemetry:** Telegram Bot API (long-polling worker with inline callbacks)
* **Automation & Containers:** Docker, Docker Compose, GitHub Actions (Scheduled Cron)

## 📂 Project Structure

```
Job-Scout/
├── .github/
│   └── workflows/
│       └── scout_cron.yml        # Scheduled GitHub Actions sweep (every 6h)
├── adapters/                     # Ingestion source crawlers
│   ├── __init__.py
│   ├── hn_adapter.py             # Hacker News thread parser
│   ├── jobicy_adapter.py         # Jobicy API client
│   ├── linkedin_guest_adapter.py # Headless LinkedIn guest crawler
│   ├── remotive_adapter.py       # Remotive developer stream
│   └── wwr_adapter.py           # We Work Remotely RSS reader
├── assets/
│   └── architecture.png          # System architecture & data flow diagram
├── scripts/                      # Operational utilities
│   ├── run_scout.bat             # Manual execution script with logging
│   ├── start_scout.bat           # Headless startup launcher
│   └── inspect_jobs.py           # Quick database inspection tool
├── agent.py                      # Custom ReAct agent with Ollama tool loop
├── analyzer.py                   # Candidate profile matching & LLM dossier generator
├── bot_listener.py               # Interactive Telegram command deck & callback handler
├── dashboard.py                  # FastAPI mission control UI & triage deck
├── db.py                         # SQLite storage, queries, pruning & safe migrations
├── dispatch.py                   # LLM dossier generator & Telegram dispatcher
├── docker-compose.yml            # Multi-container orchestration (web + bot)
├── Dockerfile                    # Lightweight container image definition
├── enricher.py                   # On-demand full job description extractor
├── evaluate.py                   # Heuristic scoring and 70% threshold evaluation
├── ingest.py                     # Multi-stream crawler orchestrator (+ RemoteOK)
├── main.py                       # Master pipeline entry point (daemon & --once)
├── models.py                     # Typed Pydantic data definitions
├── profile.json                  # Candidate skills, projects, and pitch preferences
├── requirements.txt              # Project dependencies
└── .env.example                  # Configuration template
```

## 🚀 Quickstart & Setup

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/itsjustRohitch/Job-Scout.git
cd Job-Scout

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
# On Windows:
copy .env.example .env
# On Linux/macOS:
cp .env.example .env
```

Add your Telegram credentials:

```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
TELEGRAM_CHAT_ID="your_telegram_chat_id"
```

### 3. Initialize the Local Inference Model

Verify that [Ollama](https://ollama.ai) is installed, running, and pull the target model:

```bash
ollama pull gemma3:4b
ollama serve
```

### 4. Running the Pipeline Components

* **Run a single ingest-evaluate-dispatch sweep:**
  ```bash
  python main.py --once
  ```

* **Launch the full daemon orchestrator (recurring sweeps + Telegram listener):**
  ```bash
  python main.py
  # Optional custom schedule interval in hours (default: 6.0):
  python main.py --interval 4.0
  ```

* **Start the Web Mission Control Dashboard:**
  ```bash
  python dashboard.py
  ```
  Access the UI at `http://127.0.0.1:8000` (shows postings from the last 7 days with match score $\ge 70\%$).

* **Launch the Telegram Command Deck independently:**
  ```bash
  python bot_listener.py
  ```

* **Run the Autonomous ReAct Agent:**
  ```bash
  python agent.py
  ```

## 🐳 Docker Deployment

To run JobScout in production with Docker Compose:

```bash
# Start both the web dashboard and Telegram bot in background
docker compose up -d

# View service logs
docker compose logs -f

# Stop containers
docker compose down
```

## 🤖 Telegram Bot Commands

| Command | Action |
|---|---|
| `/status` (or `/stats`) | View total ingested, matched ($\ge 70\%$), and status tallies |
| `/saved` | List saved opportunities with corresponding IDs |
| `/pitch <job_id>` | Enrich JD and generate a tailored 120-word cold outreach message |
| `/run` | Trigger an immediate background scout sweep |
| `/help` (or `/start`) | Show command overview and usage instructions |