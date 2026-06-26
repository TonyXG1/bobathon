# Regulatory Radar 🎯

> **Automated EU regulatory compliance monitoring for electronics SMEs**  
> IBM Bobathon · GenAI Builders Day · GDGoC TUM Campus Heilbronn  
> Partner Challenge by **EcoComply** · Built with **IBM Bob** + **Twilio**

---

## 🎯 The Problem

EU electronics SMEs face a flood of constantly changing product regulations (RoHS, REACH, Battery Regulation, PPWR, GPSR, RED, ESPR, Toy Safety, MDR, POPs…). A missed rule means fines, blocked shipments, or delisting. EcoComply currently does this **monitor → assess → alert** loop largely by hand. We're automating it.

## 🏗️ Architecture

```
  FIND (Part 1)         UNDERSTAND          ASSESS (Part 2)        ALERT (Part 3)
  extraction_service -> normalize       ->  assessment_service -> alerting_service
  live sources          to schema           vs. portfolio          Twilio dispatch
        |                                          |                      |
        +------------- Requirement[] -------------+                      |
                                                   +----- Finding[] -----+----> dashboard (Part 4)
```

### Four Services + Shared Contracts

| Service | Port | Stack | Responsibility |
|---------|------|-------|----------------|
| **extraction_service** | 8081 | FastAPI + httpx | Pull & normalize current rules from CELLAR/ECHA |
| **assessment_service** | 8082 | FastAPI | Match rules against portfolio; emit gaps |
| **alerting_service** | 8083 | FastAPI + Twilio | Dispatch alerts via SMS/WhatsApp/Email |
| **dashboard** | 8501 | Streamlit | Findings UI with sorting, filtering, audit trails |
| **orchestrator** | 8080 | APScheduler | Schedule & chain the pipeline |

**Two JSON Contracts:**
- **`Requirement`** (Part 1 → Part 2): One current obligation from a live source
- **`Finding`** (Part 2 → Parts 3 & 4): One concrete gap (product × requirement)

Contracts are **Pydantic v2 models** in `contracts/models.py` — the single source of truth for validation and JSON schemas.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (install: `pip install uv`)
- Docker & Docker Compose (optional)

### 1. Clone & Install
```bash
git clone <repo-url>
cd regulatory-radar
uv sync
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Twilio credentials and other secrets
```

### 3. Run Services

**Option A: Individual Services**
```bash
# Terminal 1 - Extraction Service
cd extraction_service
uv run uvicorn main:app --reload --port 8081

# Terminal 2 - Assessment Service
cd assessment_service
uv run uvicorn main:app --reload --port 8082

# Terminal 3 - Alerting Service
cd alerting_service
uv run uvicorn main:app --reload --port 8083

# Terminal 4 - Dashboard
cd dashboard
uv run streamlit run app.py
```

**Option B: Docker Compose (All Services)**
```bash
docker-compose up
```

### 4. Access Services
- **Extraction API:** http://localhost:8081/docs
- **Assessment API:** http://localhost:8082/docs
- **Alerting API:** http://localhost:8083/docs
- **Dashboard:** http://localhost:8501

---

## 📚 Documentation

- **[AGENTS.md](./AGENTS.md)** — Complete project context (Bob reads this every session)
- **[SOURCES.md](./SOURCES.md)** — Live data sources (EUR-Lex/CELLAR, ECHA)
- **[DATASET_README.md](./DATASET_README.md)** — Data dictionary for bundled dataset
- **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)** — Scaffolding and structure plan
- **[SETUP.md](./SETUP.md)** — Detailed setup and troubleshooting guide

---

## 🛠️ Technology Stack

**Backend Services:**
- **FastAPI** — Modern, fast web framework with auto OpenAPI docs
- **Pydantic v2** — Data validation and settings management
- **httpx** — Async HTTP client for external APIs
- **defusedxml** — Safe XML parsing (CELLAR Formex)
- **BeautifulSoup** — HTML parsing (ECHA tables)
- **Twilio SDK** — SMS/WhatsApp/Email delivery

**Dashboard:**
- **Streamlit** — Pure Python UI (no build step)
- **pandas** — Data manipulation
- **plotly** — Interactive charts

**Database:**
- **SQLite** (default) or **PostgreSQL** (via docker-compose)

**Tooling:**
- **uv** — Fast Python package manager
- **ruff** — Linting and formatting
- **pytest** — Testing framework

---

## 📁 Repository Structure

```
regulatory-radar/
├── AGENTS.md                       # Project context for IBM Bob
├── README.md                       # This file
├── SOURCES.md                      # Live data sources guide
├── DATASET_README.md               # Data dictionary
├── IMPLEMENTATION_PLAN.md          # Scaffolding plan
├── SETUP.md                        # Setup guide
├── pyproject.toml                  # uv workspace + shared deps
├── docker-compose.yml              # All services + Postgres
├── .env.example                    # Secrets template
├── .gitignore                      # Git exclusions
│
├── .bob/                           # IBM Bob configuration
│   ├── rules/                      # Team-wide standards
│   ├── rules-code/                 # Mode-specific rules
│   └── custom_modes.yaml           # Per-service personas
│
├── dataset/                        # FIXED inputs (DO NOT EDIT)
│   ├── partners.json               # Portfolio: 22 companies, 53 products
│   ├── partners.csv                # Flattened portfolio
│   ├── taxonomy.json               # Controlled vocabulary
│   ├── regulatory_updates.json     # 50 EXAMPLE rules (shape only)
│   ├── sample_expected_output.json # Finding shape
│   └── feed/                       # Example HTML notices
│
├── contracts/                      # The SEAMS
│   ├── models.py                   # Pydantic models (source of truth)
│   ├── export_schemas.py           # Schema generator
│   ├── requirement.schema.json     # Generated (CI-validated)
│   ├── finding.schema.json         # Generated (CI-validated)
│   └── fixtures/                   # Test data
│
├── extraction_service/             # Part 1
│   ├── main.py                     # FastAPI app
│   ├── clients.py                  # CELLAR, ECHA clients
│   ├── normalize.py                # Raw → Requirement
│   ├── change.py                   # Change detection
│   └── tests/
│
├── assessment_service/             # Part 2
│   ├── main.py                     # FastAPI app
│   ├── engine.py                   # Scope matcher
│   ├── portfolio.py                # Portfolio indexing
│   └── tests/
│
├── alerting_service/               # Part 3
│   ├── main.py                     # FastAPI app
│   ├── channels.py                 # SMS/WhatsApp/Email
│   ├── templates.py                # Message formatting
│   └── tests/
│
├── dashboard/                      # Part 4
│   └── app.py                      # Streamlit app
│
└── orchestrator/                   # Pipeline scheduler
    └── run.py                      # APScheduler job
```

---

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run service-specific tests
cd extraction_service
uv run pytest

# Lint and format
uv run ruff check .
uv run ruff format .

# Regenerate schemas from Pydantic models
cd contracts
uv run python export_schemas.py
```

---

## 🔐 Security

- **XXE-safe XML parsing:** Use `defusedxml` for CELLAR Formex
- **Secrets via env only:** Never hardcode credentials
- **Defensive parsing:** Size limits, timeouts on all HTTP requests
- **Polite client:** User-Agent, rate limits, conditional GET
- **Test endpoints only:** Alerts go to OUR Twilio test number, not portfolio contacts

---

## 📊 The Dataset

### Fixed Portfolio (DO NOT EDIT)
- **22 companies, 53 products** in `dataset/partners.json`
- **5 companies with seeded gaps** (ground truth for validation):
  - **P006 FitTrack** — PFAS/PFHxA coating (REACH)
  - **P008 PlayBright** — DEHP in toy, button-cell safety (GPSR)
  - **P010 DisplayOne** — Mercury in CCFL panel (RoHS)
  - **P013 RideVolt** — Missing battery passport (Battery Reg)
  - **P022 KidVision** — Micro-USB connector, RED cybersecurity

### Taxonomy (Authoritative Enums)
- **17 product categories** (e.g., `battery_pack`, `toy_electronic`, `emobility_battery`)
- **13 substances** (e.g., `lead`, `DEHP`, `PFAS_PFHxA`)
- **20 regulation families** (e.g., `rohs`, `reach`, `battery`, `gpsr`)

All extracted data must map to these enums for deterministic matching.

---

## 🎯 Definition of Done

A correct **Core** slice on live data beats a flashy-but-wrong Stretch one.

**Judging Criteria:**
- **End-to-end (30%)** — Live rule → real gap → real alert fires
- **Quality of insight (25%)** — Gap is real, correctly reasoned, source cited
- **Use of Bob (15%)** — Plan/Orchestrator/Code modes, custom modes/rules
- **Alert delivery (10%)** — Real notification on sensible channel
- **Real-world fit (10%)** — Actionable, auditable (provenance), correct deadline
- **Demo & communication (10%)** — Show source, gap, alert; explain reasoning

---

## 🤝 Team Ownership

**Suggested split:**
- **Part 1 (Extraction) + Orchestrator** — You
- **Part 2 (Assessment)** — Teammate (cleanest parallel complement)
- **Parts 3 & 4 (Alerting + Dashboard)** — Shared float (alerting is demo-critical)

---

## 🔗 Key Resources

- **EUR-Lex SPARQL:** http://publications.europa.eu/webapi/rdf/sparql
- **ECHA CHEM:** https://chem.echa.europa.eu/obligation-lists/candidateList
- **Twilio Docs:** https://www.twilio.com/docs
- **Twilio Promo Code:** `TUM-TWILIO-50` (hackathon credit)

---

## 📝 Working with IBM Bob

### Modes
- **Plan** — Design before implementation
- **Code/Agent** — Day-to-day coding
- **Ask** — Explore without modifying
- **Advanced** — Browser automation, MCP servers
- **Orchestrator** — Cross-service features

### Custom Modes
See `.bob/custom_modes.yaml` for per-service personas:
- `extraction` — Scoped to extraction_service/
- `assessment` — Scoped to assessment_service/
- `alerting` — Scoped to alerting_service/
- `dashboard` — Scoped to dashboard/

### Team Rules
See `.bob/rules/` for shared standards:
- Never edit `dataset/`
- Contract changes require schema regeneration
- Every finding cites `source_url`
- Secrets only via env

---

## 🐛 Troubleshooting

**Services can't connect to database:**
- Check `DATABASE_URL` in `.env`

**Twilio alerts failing:**
- Verify `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` in `.env`
- Ensure test number is verified in Twilio console

**CELLAR SPARQL timeout:**
- Reduce query size, add `LIMIT`/`OFFSET`
- Keep < 5 concurrent connections

**Import errors between services:**
- Run `uv sync` in each service directory

---

## 📄 License

[Add your license here]

---

## 🙏 Acknowledgments

- **EcoComply** for the partner challenge
- **IBM** for Bob and the Bobathon
- **Twilio** for communication APIs
- **GDGoC TUM Campus Heilbronn** for hosting
