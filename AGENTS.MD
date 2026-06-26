# AGENTS.md — Regulatory Radar

> **Persistent project context for IBM Bob.** Bob loads this file at the start of every
> conversation (and BobShell reads it via `context.fileName`). Keep it current: re-run `/init`
> after major structural changes, but preserve the hand-written sections below (problem, model,
> data dictionary, rules, conventions) — Bob's auto-scan won't reconstruct them.
>
> **Project:** Regulatory Radar · IBM Bobathon (GenAI Builders Day, GDGoC TUM Campus Heilbronn)
> · partner challenge by **EcoComply** · built with **IBM Bob** + **Twilio**.
>
> **Stack:** Python 3.12+ end to end. **FastAPI** services, **Pydantic v2** as the contract layer,
> **Streamlit** dashboard, **uv** for env/deps, **ruff** for lint/format, **pytest** for tests.
> Chosen for minimal boilerplate and fast hackathon iteration.

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
                                                   +----- Finding[] -----+----> dashboard (Part 4)
```

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

### 2.3 Model routing (Bob)

Bob auto-routes each task to the best underlying model (Anthropic Claude, IBM Granite, Mistral) by
accuracy / latency / cost. **We do not pin a model.** Favour Plan/Ask modes for reasoning-heavy
rule extraction and gap logic, Code/Agent for implementation.

---

## 3. Architecture — four services + shared contracts

Each of the four parts is a **separate, independently runnable Python app** so the team can work in
parallel. The three backend services are small **FastAPI** apps (Pydantic in, Pydantic out, auto
OpenAPI docs at `/docs`); the dashboard is **Streamlit**. Services talk over REST (`httpx`); a
shared **SQLite** file holds state and the audit trail (swap to Postgres via docker-compose if you
prefer — not required for the demo).

| Service | Part | Stack | Port | Responsibility | Reads | Writes |
|---|---|---|---|---|---|---|
| `extraction_service` | 1 | FastAPI + httpx | 8081 | Pull + normalize current rules from CELLAR/ECHA; change-detection & provenance | live sources, `taxonomy.json` | `Requirement[]` (table `requirements`) |
| `assessment_service` | 2 | FastAPI | 8082 | Scope-match rules against the portfolio; emit gaps | `requirements`, `dataset/partners.json`, `taxonomy.json` | `Finding[]` (table `findings`) |
| `alerting_service` | 3 | FastAPI + twilio | 8083 | Dispatch one alert per gap on `preferred_channel` (to OUR test number); log delivery | `findings` | `alerts_log` |
| `dashboard` | 4 | Streamlit | 8501 | Findings UI: sort by deadline/severity, link to source, show audit trail | the services' REST APIs | — |
| `orchestrator` *(thin, optional)* | — | APScheduler / plain script | 8080 | Schedule + chain extraction → assessment → alerting | all services | — |

**Why separate services:** the two contracts are clean process boundaries. Once the Pydantic models
(and their exported schemas) are frozen, each teammate builds and tests their service against
fixtures (`contracts/fixtures/`) with no runtime dependency on the others. CI checks that the
committed `*.schema.json` still matches `model_json_schema()` — instant drift detection.

> Frontend note: the dashboard is Streamlit for speed (pure Python, no build step). If you'd rather
> use React + Vite + TS, swap only `dashboard/` — nothing else changes, since it reads the same REST APIs.

**Suggested ownership:** Part 1 (you) + orchestrator; Part 2 (teammate) is the cleanest parallel
complement; Parts 3 and 4 are shared float — alerting is demo-critical, so don't let it slip.

---

## 4. Repository structure

```
regulatory-radar/
├── AGENTS.md                       # this file — Bob reads it every session
├── README.md                       # the challenge brief
├── SOURCES.md                      # where to get CURRENT rules (start here for Part 1)
├── DATASET_README.md               # upstream data dictionary (mirrored in §5 below)
├── .gitignore                      # excludes build_dataset.py (maintainer-only generator)
├── pyproject.toml                  # uv workspace + shared dev deps (ruff, pytest)
├── docker-compose.yml              # all services (+ optional Postgres) for a one-command demo
├── .env.example                    # template for secrets (never commit the real .env)
│
├── .bob/                           # IBM Bob config (generated by /init, version-controlled)
│   ├── rules/                      # team-wide custom rules (loaded every conversation)
│   ├── rules-code/                 # mode-specific rules (e.g. for Code mode)
│   └── custom_modes.yaml           # optional per-part personas (see §12.2)
│
├── dataset/                        # FIXED inputs — DO NOT EDIT
│   ├── partners.json               # the portfolio: 22 companies, 53 products
│   ├── partners.csv                # same portfolio, flattened (1 row per product)
│   ├── taxonomy.json               # controlled vocabulary (the authoritative enums)
│   ├── regulatory_updates.json     # 50 EXAMPLE rules — shape only, NOT an answer key
│   ├── sample_expected_output.json # the shape of one Finding (gap + source + alert)
│   ├── dataset_stats.json          # summary counts
│   └── feed/                       # 10 of the example rules rendered as HTML notices
│
├── contracts/                      # the SEAMS — single source of truth for both interfaces
│   ├── models.py                   # Pydantic models: Requirement, Finding, Alert, enums
│   ├── export_schemas.py           # dumps model_json_schema() -> the two .json files below
│   ├── requirement.schema.json     # generated; CI fails if stale
│   ├── finding.schema.json         # generated; CI fails if stale
│   └── fixtures/
│       ├── requirements.sample.json
│       └── findings.sample.json
│
├── extraction_service/             # PART 1 — FastAPI
│   ├── main.py                     # app + GET /requirements
│   ├── clients.py                  # cellar_client (Formex via httpx), echa_client (SVHC list)
│   ├── normalize.py                # raw source -> Requirement (owns the output contract)
│   ├── change.py                   # conditional GET, cursors, content-hash dedup, provenance
│   ├── tests/
│   └── pyproject.toml
│
├── assessment_service/             # PART 2 — FastAPI
│   ├── main.py                     # app + POST /assess · GET /findings
│   ├── engine.py                   # scope matcher: market / category / substance / attribute
│   ├── portfolio.py                # loads & indexes partners.json + taxonomy.json
│   ├── tests/
│   └── pyproject.toml
│
├── alerting_service/               # PART 3 — FastAPI + Twilio
│   ├── main.py                     # app + POST /alerts
│   ├── channels.py                 # sms / whatsapp / email routing by preferred_channel
│   ├── templates.py                # one concise actionable message per gap
│   ├── tests/
│   └── pyproject.toml
│
├── dashboard/                      # PART 4 — Streamlit
│   └── app.py
│
└── orchestrator/                   # thin scheduler/glue (optional)
    └── run.py                      # APScheduler job: extraction -> assessment -> alerting
```

> The bundled `dataset/` files originate from a maintainer script and are intentionally synthetic.
> `partners.json` is the portfolio we assess; everything else in `dataset/` is reference/illustration.

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

### 5.2 `partners.csv` — flattened portfolio

The same 22 companies / 53 products as **one row per product**, for spreadsheets. Multi-value
columns are **pipe-delimited** (`|`): `sells_in`, `substances`, `packaging`, `markets`,
`compliance_streams`. **Differences vs. JSON:** the CSV has **no** nested `compliance_status` and
**no** `battery_chemistry` column (it keeps only `battery_type`). Treat `partners.json` as the
source of truth; the CSV is convenience (easy to load with `pandas.read_csv`).

Columns: `partner_id, company, hq_country, sells_in, contact_email, contact_phone,
preferred_channel, product_id, product_name, category, intended_use, substances, has_battery,
battery_type, battery_capacity_wh, has_radio, connector, packaging, markets, compliance_streams`.

### 5.3 `taxonomy.json` — controlled vocabulary (authoritative enums)

| Key | Contents |
|---|---|
| `product_categories` | 17 categories (e.g. `led_lighting`, `battery_pack`, `emobility_battery`, `toy_electronic`, `medical_wearable`, `networking`, `drone`…) with descriptions |
| `substances` | 13 substances (e.g. `lead`, `cadmium`, `mercury`, `DEHP`, `BPA`, `decaBDE`, `TBBPA`, `MCCP`, `PFAS_PFHxA`, `dioxane`) with the regime each falls under |
| `regulation_families` | 20 families mapping a short tag to the legal instrument — see 6.2 |
| `markets_note` | "ISO country codes; `EU` expands to all 27 member states." |

When normalizing live-scraped rules into `Requirement`, **map categories/substances/families onto
these keys** so the assessment engine can match deterministically. Load them as Python enums /
`Literal` types in `contracts/models.py` for free validation.

### 5.4 `regulatory_updates.json` — EXAMPLE rules (shape only, NOT an answer key)

`{ "updates": [ Update, … ] }` — **50 examples**. They exist to teach the **shape** of a rule and
to show what **noise** looks like. **Do not match findings against this file.**

| Field | Type | Meaning |
|---|---|---|
| `update_id` | str | `REG-26-NNN` |
| `published_date` | date | When published |
| `source` | str | e.g. `EUR-Lex`, `ECHA`, `National EPR registry (DE/FR)` |
| `regulation_family` | enum | Key of `taxonomy.regulation_families` |
| `reference` | str | Legal reference (article/annex) |
| `title`, `summary` | str | Human description |
| `change_type` | enum | `new` \| `amendment` \| `correction` |
| `effective_date`, `deadline_date` | date | When it applies / the compliance deadline |
| `severity` | enum | `low` \| `medium` \| `high` |
| `action_required` | str | The fix |
| `scope.categories` | list[str] \| `"all"` | Categories in scope |
| `scope.substances` | list[str] | Substances named (empty if none) |
| `scope.markets` | list[str] | Markets in scope |
| `scope.conditions` | str | **Free-text carve-outs — often encodes the exclusion that creates look-alikes** |
| `corrects` | str? | If present, the `update_id` this entry duplicates/corrects → **de-dup** |

> The set deliberately mixes in **unrelated domains** (CBAM, F-gas, EUDR, food-contact, CLP — not
> finished electronics) and **duplicate/correction** entries, so your pipeline learns to ignore noise.

### 5.5 `sample_expected_output.json` — the Finding shape (output contract)

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

### 5.6 `dataset_stats.json` — summary counts

`partners: 22 · products: 53 · companies_with_seeded_gaps: 5 · sample_feed_updates: 50 ·
sample_noise: 6 · sample_duplicates: 6`.

### 5.7 `feed/` — example rules as HTML notices

10 of the `regulatory_updates.json` entries rendered as HTML pages (`index.html` plus
`REG-26-*.html`), mimicking a real legislation-portal notice. Use them to develop and test your
**HTML parsing path** (BeautifulSoup) before pointing it at the live web. Same content as the
matching JSON entries; not additional rules.

### 5.8 Other repo docs

`README.md` (full challenge), `DATASET_README.md` (upstream field guide), `SOURCES.md` (live
sources). `.gitignore` excludes `build_dataset.py` (the maintainer-only generator — not needed).

---

## 6. Live sources & how to fetch them (Part 1)

The task is to pull **current** rules from real portals. Prefer structured, machine-readable access
over scraping rendered HTML. Suggested Python libraries are noted per source.

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
- Log every send to `alerts_log` (who / channel / when / message / finding id).

---

## 9. Dashboard (Part 4)

**Streamlit** (`streamlit run dashboard/app.py`). Reads `Finding[]` (and the audit trail) from the
services over `httpx`. Sort by deadline and severity; each row links to its `source_url` and shows
the access date — the "auditable, would-EcoComply-use-it" angle the jury scores. Pure Python, no
build step. (Swap to React + Vite + TS if preferred — it reads the same REST APIs.)

---

## 10. Security & how we code

- **Safe XML parsing.** CELLAR Formex (and any SOAP) is third-party XML — parse with **`defusedxml`**
  (e.g. `defusedxml.ElementTree`), which blocks XXE / billion-laughs / external-entity attacks that
  plain `xml.etree` / `lxml` allow by default. If you must use `lxml`, set
  `etree.XMLParser(resolve_entities=False, no_network=True, dtd_validation=False)`.
- **Secrets via env only.** Load with **`pydantic-settings`** (`BaseSettings`) or `python-dotenv`.
  `.env` is **gitignored**; commit `.env.example`. Holds `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
  `TWILIO_FROM_NUMBER`, IBM Bob keys, DB URL. Never log secrets.
- **Treat all scraped content as untrusted** — defensive parsing, size limits, request timeouts on `httpx`.
- **Be a polite client** — User-Agent with contact, honor `robots.txt`/rate limits, cache, use
  conditional GET (`If-None-Match` / `If-Modified-Since`) so most polls return `304`.
- **Triage Bob's inline security findings** (Semgrep) before merging; don't dismiss them wholesale.
- Portfolio data is synthetic and safe, but alerts must still go only to our own test endpoints.

---

## 11. Build, run, test

- **Tooling:** **`uv`** for envs/deps (fast), **`ruff`** for lint+format, **`pytest`** for tests.
- **Install:** from the repo root, `uv sync` (or per service: `cd <service> && uv sync`).
- **Run a backend service:** `uv run uvicorn main:app --reload --port 8081` (from the service dir).
  Repeat with 8082 / 8083 for assessment / alerting. OpenAPI docs at `http://localhost:<port>/docs`.
- **Run the dashboard:** `uv run streamlit run dashboard/app.py` (serves on 8501).
- **Run the orchestrator:** `uv run python orchestrator/run.py`.
- **Everything at once:** `docker-compose up` (services + optional Postgres).
- **Regenerate schemas from the models:** `uv run python contracts/export_schemas.py`.
- **Lint / format / test:** `uv run ruff check .` · `uv run ruff format .` · `uv run pytest`.
- **Contract validation (CI):** the Pydantic models are the source of truth, so service outputs are
  valid by construction. CI re-runs `export_schemas.py` and **fails if the committed
  `*.schema.json` files are out of date** — that's the early warning that an interface drifted.

---

## 12. Working with IBM Bob

### 12.1 Modes & workflow

- **Plan** mode first for any new service or non-trivial feature — review the plan before code.
- **Orchestrator** mode for cross-service features that touch more than one part.
- **Code / Agent** mode for day-to-day implementation.
- **Ask** mode to explore the repo or a rule without modifying files.
- **Advanced** mode when you need browser automation or MCP servers (e.g. live-fetching a portal).
- Re-run **`/init`** after adding a service so this file stays accurate.
- Keep tasks **small and focused**; don't dump the whole repo at Bob. Use **context mentions**:
  `@/dataset/partners.json`, `@/contracts/models.py`, `@problems`, `@terminal`.
- Use the **approval workflow** (approve edit/tool/subagent steps) to stay in control.

### 12.2 Suggested custom modes (`.bob/custom_modes.yaml`)

Optional per-part personas with tool restrictions, so each teammate's Bob "wakes up" knowing its
service. Example slugs: `extraction` (read + terminal + MCP, scope to `extraction_service/`),
`assessment` (read + edit, restrict edits to `\.py$`, scope to `assessment_service/`), `alerting`,
`dashboard`. Commit the YAML so the whole team inherits them from Git. Each `roleDefinition` should
say "You are a Python engineer working in FastAPI/Pydantic" so Bob defaults to the right stack.

### 12.3 Team rules (`.bob/rules/`)

Keep shared standards here (they load in every conversation): "never edit `dataset/`", "never
change a Pydantic contract model without updating the generated schemas and the fixtures", "every
finding cites a `source_url`", "secrets only via env", "prefer stdlib + the libraries in §11 — don't
add heavy frameworks".

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