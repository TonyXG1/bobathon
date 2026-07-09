# CLAUDE.MD — Regulatory Radar

> **Persistent project context for the coding agent** (Claude Code loads this file at the start of
> every conversation). Keep it current after major structural changes, but preserve the
> hand-written sections below (problem, model, data dictionary, rules, conventions) — an auto-scan
> won't reconstruct them.
>
> **Project:** Regulatory Radar · started at the IBM Bobathon (GenAI Builders Day, GDGoC TUM
> Campus Heilbronn) · partner challenge by **EcoComply** · alerts via **Twilio**. Development now
> continues with **Claude Code** + the **OpenSpec** workflow (see §12).
>
> **Stack:** Python 3.12+ end to end. **FastAPI** services, **Pydantic v2** as the contract layer,
> **uv** for env/deps, **ruff** for lint/format, **pytest** for tests.
> Chosen for minimal boilerplate and fast iteration.

---

## 1. The problem we are solving

EU electronics SMEs are drowning in product regulations that change constantly (RoHS, REACH,
Battery Regulation, PPWR, GPSR, RED, ESPR, Toy Safety, MDR, POPs…). A missed rule means fines,
blocked shipments, or delisting. EcoComply does this **monitor → assess → alert** loop largely by
hand today. We are automating it.

The agent must:

1. **Find** current EU requirements from **live** legislation portals.
2. **Understand** each rule (categories / substances / markets / deadline / conditions).
3. **Assess** a **fixed** portfolio of companies and decide who is non-compliant **today**.
4. **Alert** each affected company with the gap, the **source URL**, the deadline, and the fix.

### Non-negotiables (these define correctness — do not violate)

- **Rules come from LIVE sources only** (see `SOURCES.md`). The bundled `regulatory_updates.json`
  and `feed/*.html` are **EXAMPLES of the shape of a rule** so we recognise one when we scrape —
  they are **NOT an answer key and NOT a dataset to match against**.
- **`dataset/partners.json` is the FIXED portfolio.** Never modify it; it is read-only input.
- **Every `Finding` must cite the `source_url`** it was derived from. No source → no finding.
- **Alerts go to OUR OWN Twilio test number/email.** All portfolio contacts are synthetic
  (`@example.com`, placeholder phones) — safe — but never wire alerts to portfolio contacts.
- **`EU` in any `markets`/`sells_in` field expands to all 27 member states.**

---

## 2. The core model

### 2.1 Domain model — the pipeline and its two contracts

```
  FIND (Part 1)         UNDERSTAND          ASSESS (Part 2)        ALERT (Part 3)
  extraction_service -> normalize       ->  assessment_service -> alerting_service
  live sources          to schema           vs. portfolio          Twilio dispatch
        |                                          |                      |
        +------------- Requirement[] -------------+                      |
                                                   +----- Finding[] -----+
```

(The originally planned Part 4 dashboard was never built — there is no `dashboard/` directory.)

Two contracts decouple every stage and are the **heart of the system**. In Python they live as
**Pydantic models** in `contracts/models.py` — those models are the single source of truth for
validation *and* the JSON Schemas (exported via `model_json_schema()`). Freeze them first; build
each part behind a fixture of the other.

- **`Requirement`** — one current obligation, extracted and **normalized** from a live source.
  Output of Part 1, input of Part 2. Same shape as an entry in `regulatory_updates.json`, **plus**
  a real `source_url` and access metadata.
- **`Finding`** — one concrete gap: a single product against a single requirement, plus the alert
  to send. Output of Part 2, input of Parts 3 and 4. Same shape as `sample_expected_output.json`.

Generated schemas (kept in sync with the models, checked in CI): `contracts/requirement.schema.json`,
`contracts/finding.schema.json`.

### 2.2 When does an obligation apply, and what is a gap?

An obligation applies to a product when **all** of these hold:

1. **Market** — the company sells where the rule applies (`EU` = all 27; some rules are one country).
2. **Category** — the rule covers the product's `category` (or the rule's scope is `"all"`).
3. **Substance** — if the rule names substances, the product's `substances[]` actually contains one.
4. **Attributes** — battery `type`/`capacity_wh`, `has_radio`, `connector`, `packaging`,
   `intended_use` satisfy the rule's conditions.
5. **Exclusions** — respect carve-outs (e.g. consumer-safety rules exclude `medical`/`industrial`-only).

A **gap** = an obligation that **applies** *and* is **not yet satisfied**.

**Watch the look-alikes (the most common false positives):**

- Right category, **wrong market** (e.g. a UK-only SKU vs. an EU rule).
- A rule names a substance the product **does not actually contain**.
- An **attribute takes the product out of scope** — e.g. the battery-passport rule hits **LMT** and
  **industrial** batteries but **NOT portable consumer** batteries; a "14+" maker kit is **not a
  "toy"** under Toy Safety.
- **Duplicates / corrections** — entries that `corrects` another rule add no new obligation; de-dup.

### 2.3 Agent workflow

Favour plan-first exploration for reasoning-heavy rule extraction and gap logic, then implement.
Non-trivial changes go through the OpenSpec flow (`/opsx:propose` → `/opsx:apply` →
`/opsx:archive` — see §12).

---

## 3. Architecture — three services + shared contracts (stateless, no database)

Each part is a **separate, independently runnable FastAPI app** (Pydantic in, Pydantic out, auto
OpenAPI docs at `/docs`). Services talk over REST (`httpx`). **There is no database** — this is a
simplified stateless build: every request works on live data, and the alerting service keeps its
delivery log in memory for the session.

| Service | Part | Stack | Port | Responsibility | Reads | Emits |
|---|---|---|---|---|---|---|
| `extraction_service` | 1 | FastAPI + httpx | 8081 | Query the live CELLAR SPARQL endpoint for the ~11 watchlist acts; normalize with provenance | live CELLAR | `Requirement[]` (HTTP response) |
| `assessment_service` | 2 | FastAPI | 8082 | Deterministic gap rules against the portfolio | extraction API, `dataset/partners.json` | `Finding[]` (HTTP response) |
| `alerting_service` | 3 | FastAPI + twilio/sendgrid | 8083 | One alert per gap on `preferred_channel`; simulates when credentials missing | assessment API | deliveries + in-memory `ALERTS_LOG` |

**Not implemented:** the Part-4 dashboard was never built, and `orchestrator/` is an empty stub
(only a `pyproject.toml`, no code). The Docker/database scaffolding from the earlier
database-backed design has been removed — use `run_all.ps1` to start everything.

**Why separate services:** the two contracts are clean process boundaries. Once the Pydantic models
(and their exported schemas) are frozen, each teammate builds and tests their service against
fixtures (`contracts/fixtures/`) with no runtime dependency on the others. Re-run
`contracts/export_schemas.py` whenever a model changes so the committed `*.schema.json` stay in
sync (there is no CI in this repo — the check is manual).

---

## 4. Repository structure

```
bobathon/
├── CLAUDE.MD                       # this file — the agent reads it every session
├── README.md                       # the challenge brief + quick start
├── SOURCES.md                      # where to get CURRENT rules (start here for Part 1)
├── DATASET_README.md               # data dictionary (mirrored in §5 below)
├── run_all.ps1                     # start all three services in order (Windows)
├── pyproject.toml                  # uv workspace + shared dev deps (ruff, pytest)
├── .env.example                    # template for secrets (never commit the real .env)
│
├── .claude/                        # Claude Code config (OpenSpec commands + skills)
│   ├── commands/opsx/              # /opsx:propose · apply · archive · explore · sync
│   └── skills/openspec-*/          # the skills backing those commands
├── openspec/                       # OpenSpec workspace (config.yaml; changes/ + specs/ appear on use)
│
├── dataset/                        # FIXED inputs — DO NOT EDIT
│   ├── partners.json               # the portfolio: 22 companies, 53 products
│   ├── taxonomy.json               # controlled vocabulary (the authoritative enums)
│   └── sample_expected_output.json # the shape of one Finding (gap + source + alert)
│
├── contracts/                      # the SEAMS — single source of truth for both interfaces
│   ├── models.py                   # Pydantic models: Requirement, Finding, Alert, enums
│   ├── export_schemas.py           # dumps model_json_schema() -> the two .json files below
│   ├── requirement.schema.json     # generated — re-export after model changes
│   ├── finding.schema.json         # generated — re-export after model changes
│   └── fixtures/
│       ├── requirements.sample.json
│       └── findings.sample.json
│
├── extraction_service/             # PART 1 — FastAPI :8081
│   ├── main.py                     # GET /requirements · GET /requirements/{celex} · /health
│   ├── extractor.py                # WATCHLIST (family→CELEX) + concurrent live fetch
│   ├── clients.py                  # CellarClient: SPARQL metadata query over httpx
│   ├── normalize.py                # raw source -> Requirement (owns the output contract)
│   ├── config.py                   # pydantic-settings + sys.path bootstrap for contracts
│   ├── tests/                      # 22 offline + 1 live integration test
│   └── pyproject.toml
│
├── assessment_service/             # PART 2 — FastAPI :8082
│   ├── main.py                     # POST /assess · GET /findings · /health
│   ├── engine.py                   # 6 deterministic gap rules + Finding construction
│   ├── portfolio.py                # loads partners.json, EU-market expansion
│   ├── config.py
│   ├── tests/                      # 17 offline tests (incl. seeded gaps + look-alikes)
│   └── pyproject.toml
│
├── alerting_service/               # PART 3 — FastAPI :8083
│   ├── main.py                     # POST /alerts · /dispatch · /refresh · /test-email · GET /alerts/log
│   ├── channels.py                 # TwilioSender: sms/whatsapp/email + dry-run simulation
│   ├── templates.py                # one concise actionable message per gap
│   ├── config.py
│   ├── tests/                      # 19 offline tests (Twilio never called)
│   └── pyproject.toml
│
└── orchestrator/                   # STUB — pyproject.toml only, no code
```

> The bundled `dataset/` files are intentionally synthetic. `partners.json` is the portfolio we
> assess; everything else in `dataset/` is reference/illustration.

---

## 5. Data dictionary (the bundled dataset)

This is the authoritative reference for every data file. **Normalize all extracted data to the
enums in `taxonomy.json`.**

### 5.1 `partners.json` — the portfolio (FIXED input)

Top level: `{ "partners": [ Partner, … ] }` — **22 partners, 53 products total.**

**Partner object**

| Field | Type | Meaning |
|---|---|---|
| `partner_id` | str | `P001`…`P022` |
| `company` | str | Legal name |
| `hq_country` | str | ISO country code of HQ |
| `sells_in` | list[str] | Markets where the company sells (`EU` = all 27 states) |
| `contact` | obj | `{ name, email, phone, preferred_channel }` |
| `contact.preferred_channel` | enum | `email` \| `sms` \| `whatsapp` — **the channel to alert on** |
| `products` | list[Product] | The SKUs to assess |
| `compliance_status` | obj? | **Present on only 5 partners** — see 5.1.1 |

**Product object** (these attributes drive obligation reasoning)

| Field | Type | Meaning |
|---|---|---|
| `product_id` | str | e.g. `P001-A` |
| `name` | str | Product name |
| `category` | enum | One of `taxonomy.product_categories` (e.g. `battery_pack`, `toy_electronic`) |
| `substances` | list[str] | Substances actually present (keys of `taxonomy.substances`); `[]` = none declared |
| `has_battery` | bool | Whether it contains a battery |
| `battery_chemistry` | str\|null | e.g. `li-ion`, `li-po`, `lithium-primary`, `button_cell`, `null` |
| `battery_type` | enum | `none` \| `portable` \| `button_cell` \| `lmt` \| `industrial` — **drives Battery-Reg scope** |
| `battery_capacity_wh` | number | Watt-hours (`0` if no battery) — thresholds matter (e.g. industrial > 2 kWh) |
| `has_radio` | bool | Has a radio (drives RED scope: common charger, cybersecurity) |
| `connector` | enum | `none` \| `usb_c` \| `micro_usb` \| `barrel` — **`micro_usb` ⇒ common-charger risk** |
| `packaging` | list[str] | e.g. `cardboard`, `plastic_film` — drives PPWR/packaging scope |
| `intended_use` | enum | `consumer` \| `toy` \| `industrial` \| `medical` — **drives exclusions** |
| `markets` | list[str] | Markets this SKU is placed on (may be narrower than the company's `sells_in`) |
| `compliance_streams` | list[str] | Regulation families the product is already tracked under (keys of `taxonomy.regulation_families`) |

#### 5.1.1 `compliance_status` (only 5 partners: P006, P008, P010, P013, P022)

```jsonc
"compliance_status": {
  "certs_held": ["CE", "RoHS", ...],
  "known_gaps": ["free-text description of a concrete current failing", ...]
}
```

Use these as **ground truth to validate your gap engine** (it should independently re-derive them
from live sources). The seeded gaps are, in essence:

- **P006 FitTrack** — PulseBand strap uses a PFAS/PFHxA coating now restricted under REACH.
- **P008 PlayBright** — RoboPup soft plastic exceeds the tightened toy DEHP limit; SingAlong
  button-cell compartment not child-secured (GPSR).
- **P010 DisplayOne** — legacy CCFL spare panel still contains mercury (RoHS).
- **P013 RideVolt** — e-Scooter **LMT** battery ships without an EU **battery passport**.
- **P022 KidVision** — LittleView still uses **micro-USB** (common-charger rule); connected device
  with no documented RED cybersecurity (EN 18031) conformity.

> Most partners have **no** `compliance_status` on purpose — inferring their gaps from current
> requirements is the actual challenge.

### 5.2 `taxonomy.json` — controlled vocabulary (authoritative enums)

| Key | Contents |
|---|---|
| `product_categories` | 17 categories: `audio`, `battery_pack`, `camera`, `charging_equipment`, `computing`, `display`, `drone`, `emobility_battery`, `gaming`, `industrial_equipment`, `iot_sensor`, `led_lighting`, `medical_wearable`, `networking`, `smartphone`, `toy_electronic`, `wearable` |
| `substances` | 13 substances: `lead`, `cadmium`, `mercury`, `chromium_vi`, `PBB`, `PBDE`, `DEHP`, `BPA`, `decaBDE`, `TBBPA`, `MCCP`, `PFAS_PFHxA`, `dioxane` |
| `regulation_families` | 20 families: `rohs`, `reach`, `weee`, `battery`, `ppwr`, `gpsr`, `red`, `espr`, `toy_safety`, `mdr`, `pops`, `epr`, `epr_packaging`, `energy_label`, `emc`, `lvd`, `machinery`, `atex`, `chemical_safety`, `cybersecurity` |
| `markets_note` | "ISO country codes; `EU` expands to all 27 member states." |

When normalizing live-scraped rules into `Requirement`, **map categories/substances/families onto
taxonomy keys** so the assessment engine can match deterministically. The `Literal` enums in
`contracts/models.py` mirror `taxonomy.json` exactly (plus one extraction-side fallback family,
`"other"`). If `taxonomy.json` ever changes, update the Literals and re-run `export_schemas.py`
in the same change.

### 5.3 `sample_expected_output.json` — the Finding shape (output contract)

One example finding. **This is the structure every Part-2 output must conform to** (i.e. the
`Finding` Pydantic model).

| Field | Type | Meaning |
|---|---|---|
| `company` | str | Partner company name |
| `partner_id` | str | `P0NN` |
| `product_id` | str | `P0NN-X` |
| `product` | str | Product name |
| `regulation` | str | Human-readable rule + article (e.g. "EU Battery Regulation 2023/1542 — battery passport (Art. 77)") |
| `requirement` | str | What the rule requires, in one sentence |
| `source_url` | str | **The live source the rule was read from (mandatory)** |
| `gap` | str | Why this product is non-compliant today |
| `deadline` | date | Compliance deadline |
| `severity` | enum | `low` \| `medium` \| `high` |
| `recommended_action` | str | The fix |
| `alert` | obj | `{ channel, to, message }` — `channel` = the partner's `preferred_channel`; `to` = **YOUR Twilio test number**; `message` = concise actionable text incl. product, deadline, source |

### 5.4 Other repo docs

`README.md` (challenge brief + quick start), `DATASET_README.md` (data dictionary),
`SOURCES.md` (live-sources guide), per-service `README.md`s (accurate for the current build).

> Removed in the 2026-07 cleanup: `partners.csv` (unused duplicate of `partners.json`),
> `regulatory_updates.json` (empty placeholder), `dataset_stats.json`, and `feed/` (orphan sample
> page). The `Requirement` model in `contracts/models.py` documents the rule shape they were
> meant to illustrate.

---

## 6. Live sources & how to fetch them (Part 1)

The task is to pull **current** rules from real portals. Prefer structured, machine-readable access
over scraping rendered HTML. Suggested Python libraries are noted per source.

> **Implemented today:** the extraction service queries the **CELLAR SPARQL endpoint only** — one
> metadata query (English title + document date) per watchlist CELEX, fetched concurrently (≤ 5
> connections). Formex XML retrieval, ECHA scraping, RSS change detection, and conditional GET are
> documented below as the intended next steps but are **not built**.

### 6.1 Access methods

- **EUR-Lex / CELLAR** — the legislation portal. Use:
  - **SPARQL endpoint** (CELLAR metadata graph) for "what's in force / what changed". Public, no
    auth. Commonly `http://publications.europa.eu/webapi/rdf/sparql` — **confirm in the official
    query builder** (`op.europa.eu/en/advanced-sparql-query-editor`) before hardcoding. Virtuoso
    store: 60 s timeout, always use `LIMIT`/`OFFSET`, keep < 5 concurrent connections, back off on
    429/503. Query with `SPARQLWrapper` (set `returnFormat=JSON`) or plain `httpx` with
    `Accept: application/sparql-results+json`.
  - **CELLAR REST** to retrieve a document by CELEX/ELI — fetch **Formex XML** (cleaner than HTML).
    Parse with **`defusedxml`** (see §10), not stdlib `xml.etree` directly.
  - **Predefined RSS** for zero-auth change detection (e.g. the OJ-L acts feed) — poll and diff CELEX.
- **ECHA** — substance side (most of our gaps). SVHC **Candidate List** is migrating to ECHA CHEM
  (`chem.echa.europa.eu/obligation-lists/candidateList`); the legacy table at
  `echa.europa.eu/candidate-list-table` is maintained only until **Dec 2026**. Cache ~24 h; send a
  clear User-Agent + contact; ECHA rate-limits aggressive fetching. Parse tables with
  **BeautifulSoup** (`bs4` + `lxml`).
- **Secondary (Part-3 verification, not Part-1):** EPREL (energy labels, public API), national EPR
  registers (stiftung ear DE, ADEME FR), harmonised-standards lists (EN 18031 for RED cyber).

### 6.2 Regulation family → instrument → CELEX (the watchlist)

Pin these ~10 consolidated acts rather than crawling the corpus. **Resolve to the consolidated
version** (CELEX sector `0`, date-suffixed, e.g. `02011L0065-YYYYMMDD`) to get what's in force now.

| Family | Instrument | Original CELEX |
|---|---|---|
| RoHS | Directive 2011/65/EU | `32011L0065` |
| REACH | Regulation (EC) 1907/2006 (+ ECHA SVHC list) | `32006R1907` |
| WEEE | Directive 2012/19/EU | `32012L0019` |
| Battery | Regulation (EU) 2023/1542 | `32023R1542` |
| PPWR | Regulation (EU) 2025/40 | `32025R0040` |
| GPSR | Regulation (EU) 2023/988 | `32023R0988` |
| RED | Directive 2014/53/EU | `32014L0053` |
| ESPR | Regulation (EU) 2024/1781 | `32024R1781` |
| Toy Safety | Directive 2009/48/EC (+ revision) | `32009L0048` |
| MDR | Regulation (EU) 2017/745 | `32017R0745` |
| POPs | Regulation (EU) 2019/1021 | `32019R1021` |

### 6.3 Provenance (mandatory)

On every persisted `Requirement`, record: `source_url`, CELEX/ELI, consolidation date, and access
timestamp. This is both the "cite the source" requirement and the auditability the jury weights.

---

## 7. Gap-assessment rules (Part 2)

- Apply the **applicability predicate** from §2.2 (market ∧ category ∧ substance ∧ attribute ∧ ¬exclusion).
- Run the **look-alike checklist** before emitting any gap (wrong market / absent substance / out-of-scope
  attribute / duplicate-correction).
- **De-duplicate** rules whose `corrects` points at another rule.
- Index the portfolio by category/substance/market for fast matching; keep the matcher pure and
  deterministic and **unit-test it with pytest** against `contracts/fixtures/` and the 5 seeded
  `compliance_status` companies.
- Emit one `Finding` per (product × applicable-unmet-requirement), constructed via the `Finding`
  Pydantic model (valid by construction).

---

## 8. Alerting (Part 3)

- **One** message per gap, on the partner's `preferred_channel` (`email` / `sms` / `whatsapp`),
  delivered to **OUR own Twilio test number/email**.
- Keep SMS concise (< 300 chars): product, rule, deadline, one recommended action, source link.
- Use the official **`twilio`** Python SDK; credentials come from env (§10) — never hardcode. Promo
  code for hackathon credit: `TUM-TWILIO-50`. At least one **real** alert firing in the demo is the
  wow moment.
- Log every send to the in-memory `ALERTS_LOG` (who / channel / when / message / product id) —
  exposed at `GET /alerts/log`.
- **Dry-run safety net:** with incomplete credentials or `TEST_MODE=true`, sends are *simulated*
  (`status: "simulated"` with the reason) so the pipeline demos end-to-end without a Twilio account.
- Extra demo endpoints: `POST /test-email` (one verification email) and `POST /refresh`
  (re-fetch laws → re-assess → email a summary, returning the fresh findings).

---

## 9. Dashboard (Part 4) — NOT BUILT

There is no `dashboard/` directory. If one is added later, it should read the same REST APIs
(`GET :8082/findings`, `GET :8083/alerts/log`), sort by deadline/severity, and link each row to its
`source_url` — the "auditable, would-EcoComply-use-it" angle the jury scores. All three services
already ship CORS middleware (`CORS_ORIGINS` env var) so a browser frontend can call them directly.

---

## 10. Security & how we code

- **Safe XML parsing.** CELLAR Formex (and any SOAP) is third-party XML — parse with **`defusedxml`**
  (e.g. `defusedxml.ElementTree`), which blocks XXE / billion-laughs / external-entity attacks that
  plain `xml.etree` / `lxml` allow by default. If you must use `lxml`, set
  `etree.XMLParser(resolve_entities=False, no_network=True, dtd_validation=False)`.
- **Secrets via env only.** Load with **`pydantic-settings`** (`BaseSettings`); `.env` is
  **gitignored**, commit `.env.example`. Holds the Twilio/SendGrid credentials. Never log secrets.
- **Treat all scraped content as untrusted** — defensive parsing, size limits, request timeouts on `httpx`.
- **Be a polite client** — User-Agent with contact, honor `robots.txt`/rate limits, cache, use
  conditional GET (`If-None-Match` / `If-Modified-Since`) so most polls return `304`.
- Portfolio data is synthetic and safe, but SMS/WhatsApp alerts must still go only to our own
  test endpoints.

---

## 11. Build, run, test

- **Tooling:** **`uv`** for envs/deps (fast), **`ruff`** for lint+format, **`pytest`** for tests.
- **Everything at once (Windows):** `.\run_all.ps1` — builds one shared `.venv`, installs all
  service deps, starts the three services in dependency order gated on `/health`, logs to `logs/`.
- **Run one service:** `uv run uvicorn main:app --reload --port 8081` (from the service dir).
  Repeat with 8082 / 8083 for assessment / alerting. OpenAPI docs at `http://localhost:<port>/docs`.
- **Fire the pipeline:** `POST http://localhost:8083/dispatch` (or `/refresh` for the
  laws→gaps→summary-email loop).
- **Test:** offline suites per service (`uv run pytest`, network/Twilio mocked; use
  `-m "not integration"` in extraction). Live CELLAR smoke test: `uv run pytest -m integration`.
- **Lint / format:** `uv run ruff check .` · `uv run ruff format .`.
- **Regenerate schemas from the models:** `uv run python contracts/export_schemas.py`.
- **Contract validation:** the Pydantic models are the source of truth, so service outputs are
  valid by construction. There is **no CI** in this repo — re-run `export_schemas.py` manually in
  the same change whenever `contracts/models.py` changes, and keep the fixtures in sync.

---

## 12. Working with Claude Code + OpenSpec

Development uses **Claude Code** with the **OpenSpec** spec-driven workflow (config in
`openspec/config.yaml`; commands in `.claude/commands/opsx/`, backed by `.claude/skills/`).

### 12.1 The OpenSpec loop

- **`/opsx:explore`** — think through a problem or requirement before committing to a change.
- **`/opsx:propose <idea>`** — create a change proposal under `openspec/changes/<name>/`
  (proposal + design + delta specs + a task checklist) in one step. Review/edit it before building.
- **`/opsx:apply`** — implement the tasks from the active change, checking them off as they land.
- **`/opsx:archive`** — after implementation, merge the delta specs into `openspec/specs/` and
  move the change to the archive.
- **`/opsx:sync`** — sync delta specs into the main specs without archiving (for long-running changes).

Use the loop for non-trivial features (new service, contract change, new pipeline stage); trivial
fixes can go direct.

### 12.2 House rules (enforce in every change)

- Never edit `dataset/` — it is fixed input.
- Never change a contract model without regenerating the schemas (`export_schemas.py`) and
  updating `contracts/fixtures/` in the same change.
- Every finding cites a `source_url` — no source, no finding.
- Secrets only via env; SMS/WhatsApp alerts only to our own test endpoints.
- Prefer stdlib + the libraries already in the pyprojects — don't add heavy frameworks.

---

## 13. Conventions

- **Pydantic models mirror the contracts** (`contracts/models.py`). If a model changes, regenerate
  the schemas (`export_schemas.py`) and update the fixtures in the **same** change.
- Type-hint everything; let Pydantic do validation at the boundaries (request/response models).
- Use `httpx` (async where it helps) for all outbound HTTP; set explicit timeouts.
- Tests run against `contracts/fixtures/` so they don't depend on the live web.
- Format and lint with **`ruff`** (replaces black/isort/flake8). Keep functions small and pure where
  possible (especially the assessment matcher).
- Don't introduce a new substance/category/family string that isn't in `taxonomy.json` without
  adding it there first.

---

## 14. Definition of done (and judging alignment)

A correct **Core** slice on live data beats a flashy-but-wrong Stretch one. Target:

- **End-to-end (30%)** — a current rule (live source) → a real gap → a **real alert fires**.
- **Quality of insight (25%)** — the gap is real and correctly reasoned (no look-alike false
  positives), with the **source cited**.
- **Use of Bob (15%)** — Plan/Orchestrator/Code modes, custom modes/rules, contracts-first.
- **Alert delivery (10%)** — a real notification on the sensible channel.
- **Real-world fit (10%)** — actionable, **auditable** (provenance), correct deadline.
- **Demo & communication (10%)** — show a real source, a real gap, a real alert; explain the reasoning.