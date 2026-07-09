# Regulatory Radar 🎯

> **Automated EU regulatory compliance monitoring for electronics SMEs**
> IBM Bobathon · GenAI Builders Day · GDGoC TUM Campus Heilbronn
> Partner Challenge by **EcoComply** · Built with **IBM Bob** + **Twilio**

---

## 🎯 The Problem

EU electronics SMEs face a flood of constantly changing product regulations (RoHS, REACH, Battery Regulation, PPWR, GPSR, RED, ESPR, Toy Safety, MDR, POPs…). A missed rule means fines, blocked shipments, or delisting. EcoComply currently does this **monitor → assess → alert** loop largely by hand. We're automating it.

## 🏗️ Architecture

Three small, **stateless** FastAPI services chained over REST, plus a shared contracts package. No database — every request works on live data.

```
  FIND (Part 1)            ASSESS (Part 2)           ALERT (Part 3)
  extraction_service  -->  assessment_service  -->   alerting_service
  live EUR-Lex/CELLAR      vs. fixed portfolio       Twilio / SendGrid
        |                        |                         |
        +---- Requirement[] ----+------ Finding[] --------+
```

| Service | Port | Responsibility |
|---------|------|----------------|
| **extraction_service** | 8081 | Query the live CELLAR SPARQL endpoint for the ~11 watchlist acts and normalize each to a `Requirement` with real `source_url` provenance |
| **assessment_service** | 8082 | Match requirements against `dataset/partners.json` with deterministic gap rules; emit `Finding[]` (currently 15 findings) |
| **alerting_service** | 8083 | Send one alert per gap via Twilio SMS/WhatsApp or SendGrid email; simulates sends when credentials are missing |

**Two JSON contracts** decouple the stages — both are Pydantic v2 models in [contracts/models.py](contracts/models.py) (the single source of truth; JSON Schemas are generated from them):

- **`Requirement`** (Part 1 → Part 2): one current obligation from a live source
- **`Finding`** (Part 2 → Part 3): one concrete gap (product × requirement), including the alert to send

> **Not implemented:** there is no dashboard service, and `orchestrator/` is an empty stub (only a `pyproject.toml`, no code). The Docker/database scaffolding from an earlier design has been removed — use [run_all.ps1](run_all.ps1) to start the services.

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (`pip install uv`)

### One command (Windows)

```powershell
.\run_all.ps1
```

The script creates a shared `.venv`, installs the dependencies of all three services, starts them in dependency order (gating on each `/health`), and streams logs to `logs/`. It also copies `.env.example` → `.env` if missing.

### Manual (any platform)

```bash
cp .env.example .env          # optional: add Twilio/SendGrid credentials

cd extraction_service && uv sync && uv run uvicorn main:app --port 8081
cd assessment_service && uv sync && uv run uvicorn main:app --port 8082
cd alerting_service   && uv sync && uv run uvicorn main:app --port 8083
```

### Fire the whole pipeline

```bash
# extraction -> assessment -> alerting, one call:
curl -X POST http://localhost:8083/dispatch
# demo: send just one alert, SMS only:
curl -X POST "http://localhost:8083/dispatch?limit=1&only_channel=sms"
# one-button refresh: re-fetch live laws, re-assess, email a summary:
curl -X POST http://localhost:8083/refresh
```

Interactive OpenAPI docs: [8081/docs](http://localhost:8081/docs) · [8082/docs](http://localhost:8082/docs) · [8083/docs](http://localhost:8083/docs)

Without Twilio/SendGrid credentials the alerting service **simulates** deliveries (`status: "simulated"` with the reason), so the pipeline works end-to-end out of the box. See [alerting_service/README.md](alerting_service/README.md) for the credential matrix.

## 📚 Documentation

- **[CLAUDE.MD](./CLAUDE.MD)** — complete project context (loaded by the coding agent every session)
- **[SOURCES.md](./SOURCES.md)** — live data sources guide (EUR-Lex/CELLAR, ECHA)
- **[DATASET_README.md](./DATASET_README.md)** — data dictionary for the bundled dataset
- Per-service READMEs: [extraction](extraction_service/README.md) · [assessment](assessment_service/README.md) · [alerting](alerting_service/README.md)

## 🛠️ Technology Stack

- **FastAPI** + **uvicorn** — the three services (auto OpenAPI docs)
- **Pydantic v2** + **pydantic-settings** — contracts and env-based config
- **httpx** — outbound HTTP (SPARQL, service-to-service)
- **Twilio SDK** / **SendGrid** — SMS/WhatsApp / email delivery
- **uv**, **ruff**, **pytest** — tooling

## 📁 Repository Structure

```
bobathon/
├── README.md                       # this file
├── CLAUDE.MD                       # project context for the coding agent
├── SOURCES.md                      # live data sources guide
├── DATASET_README.md               # data dictionary
├── run_all.ps1                     # start all three services (Windows)
├── pyproject.toml                  # uv workspace + shared dev deps
├── .env.example                    # secrets template (never commit .env)
│
├── contracts/                      # the SEAMS
│   ├── models.py                   # Pydantic models: Requirement, Finding, Alert, enums
│   ├── export_schemas.py           # regenerates the two *.schema.json files
│   ├── requirement.schema.json     # generated from models.py
│   ├── finding.schema.json         # generated from models.py
│   └── fixtures/                   # sample Requirement[]/Finding[] test data
│
├── dataset/                        # FIXED inputs (DO NOT EDIT)
│   ├── partners.json               # portfolio: 22 companies, 53 products
│   ├── taxonomy.json               # controlled vocabulary (authoritative enums)
│   └── sample_expected_output.json # the shape of one Finding
│
├── extraction_service/             # Part 1 — FastAPI, port 8081
│   ├── main.py                     # GET /requirements, GET /requirements/{celex}
│   ├── extractor.py                # watchlist + concurrent live fetch
│   ├── clients.py                  # CellarClient (SPARQL over httpx)
│   ├── normalize.py                # raw source → Requirement (taxonomy mapping)
│   └── tests/                      # 22 offline + 1 live integration test
│
├── assessment_service/             # Part 2 — FastAPI, port 8082
│   ├── main.py                     # POST /assess, GET /findings
│   ├── engine.py                   # 6 deterministic gap rules (the matcher)
│   ├── portfolio.py                # portfolio loading, EU-market expansion
│   └── tests/                      # 17 offline tests
│
├── alerting_service/               # Part 3 — FastAPI, port 8083
│   ├── main.py                     # POST /alerts, /dispatch, /refresh, /test-email, GET /alerts/log
│   ├── channels.py                 # Twilio/SendGrid senders + dry-run simulation
│   ├── templates.py                # message formatting (SMS < 300 chars)
│   └── tests/                      # 19 offline tests
│
└── orchestrator/                   # stub — pyproject.toml only, no code
```

## 🧪 Testing

```bash
# per service (offline — network and Twilio are mocked):
cd extraction_service && uv run pytest -m "not integration"
cd assessment_service && uv run pytest
cd alerting_service   && uv run pytest

# live smoke test against the real CELLAR endpoint:
cd extraction_service && uv run pytest -m integration

# lint / format:
uv run ruff check .
uv run ruff format .

# regenerate JSON schemas after changing contracts/models.py:
uv run python contracts/export_schemas.py
```

The assessment engine tests run against the real `dataset/partners.json` and assert that the 5 seeded ground-truth gaps are found and the documented look-alikes are **not**.

## 🔐 Security

- **Secrets via env only** — Twilio/SendGrid credentials load from `.env` via pydantic-settings; never hardcoded or logged
- **Explicit timeouts** on every outbound HTTP request
- **Polite client** — clear User-Agent with contact, ≤ 5 concurrent CELLAR connections
- **Safe alerts** — SMS/WhatsApp go to OUR OWN Twilio test number; without credentials sends are simulated

## 📊 The Dataset

### Fixed Portfolio (DO NOT EDIT)
- **22 companies, 53 products** in `dataset/partners.json`
- **5 companies with seeded gaps** (ground truth, re-derived by the engine):
  - **P006 FitTrack** — PFAS/PFHxA coating (REACH)
  - **P008 PlayBright** — DEHP in toy (Toy Safety), button-cell access (GPSR)
  - **P010 DisplayOne** — mercury in CCFL panel (RoHS)
  - **P013 RideVolt** — missing battery passport (Battery Reg)
  - **P022 KidVision** — micro-USB connector (RED common charger)

### Taxonomy (Authoritative Enums)
`dataset/taxonomy.json` defines 17 product categories, 13 substances, and 20 regulation families. All extracted data is normalized onto these keys for deterministic matching (unknown values are dropped or mapped to `"other"`, never invented).

## 🎯 Definition of Done

A correct **Core** slice on live data beats a flashy-but-wrong Stretch one.

**Judging Criteria:**
- **End-to-end (30%)** — Live rule → real gap → real alert fires
- **Quality of insight (25%)** — Gap is real, correctly reasoned, source cited
- **Use of Bob (15%)** — Plan/Orchestrator/Code modes, custom modes/rules
- **Alert delivery (10%)** — Real notification on sensible channel
- **Real-world fit (10%)** — Actionable, auditable (provenance), correct deadline
- **Demo & communication (10%)** — Show source, gap, alert; explain reasoning

## 🐛 Troubleshooting

**`/requirements` is slow (~8 s) or returns 502:**
The EU SPARQL endpoint can be slow or briefly unavailable. Raise `HTTP_TIMEOUT` in `.env`, retry, and check connectivity to `publications.europa.eu`.

**Twilio alerts show `"simulated"`:**
That's the safe default. Set `TWILIO_ACCOUNT_SID`, `TWILIO_PHONE_NUMBER`, a verified `TWILIO_TEST_NUMBER` (and `SENDGRID_API_KEY` for email), then `TEST_MODE=false`.

**`ModuleNotFoundError: No module named 'contracts'`:**
Run the service from its own directory; each service's `config.py` bootstraps the repo root onto `sys.path`.

**Port already in use:**
```powershell
Get-NetTCPConnection -LocalPort 8081 | Select-Object OwningProcess
Stop-Process -Id <PID>
```

## 🔗 Key Resources

- **EUR-Lex SPARQL:** http://publications.europa.eu/webapi/rdf/sparql
- **ECHA CHEM:** https://chem.echa.europa.eu/obligation-lists/candidateList
- **Twilio Docs:** https://www.twilio.com/docs

## 🙏 Acknowledgments

- **EcoComply** for the partner challenge
- **IBM** for Bob and the Bobathon
- **Twilio** for communication APIs
- **GDGoC TUM Campus Heilbronn** for hosting
