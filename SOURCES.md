# Live Data Sources Guide

> **Part 1 (Extraction Service) — Where to get CURRENT regulatory requirements**

This document describes how to access live EU regulatory data from official portals. The extraction service must pull **current, in-force** rules from these sources, not from the bundled example dataset.

---

## 🎯 Core Principle

**Rules come from LIVE sources only.** The bundled `regulatory_updates.json` and `feed/*.html` are **EXAMPLES of the shape of a rule** — they teach you what to look for when scraping. They are **NOT an answer key and NOT a dataset to match against.**

Every `Requirement` you persist must cite its `source_url` — the actual live portal URL where you read it.

---

## 1. EUR-Lex / CELLAR (Primary Source)

**What:** Official EU legislation portal. Contains all directives, regulations, and consolidated acts.

**Why:** This is where the 10 key regulations (RoHS, REACH, Battery, PPWR, GPSR, RED, ESPR, Toy Safety, MDR, POPs) are published and maintained.

### 1.1 SPARQL Endpoint (Metadata Queries)

**Purpose:** Query the CELLAR metadata graph to find what's in force and what changed.

**Endpoint:** `http://publications.europa.eu/webapi/rdf/sparql`

**Confirm URL:** Always verify in the [official query builder](https://op.europa.eu/en/advanced-sparql-query-editor) before hardcoding.

**Access:**
- Public, no authentication required
- Virtuoso RDF store
- 60-second timeout per query
- Always use `LIMIT` and `OFFSET` for pagination
- Keep < 5 concurrent connections
- Back off on 429 (rate limit) or 503 (service unavailable)

**Request Format:**
```http
POST /webapi/rdf/sparql
Content-Type: application/x-www-form-urlencoded
Accept: application/sparql-results+json

query=SELECT ...
```

**Python Libraries:**
- **SPARQLWrapper** (recommended): `pip install SPARQLWrapper`
  ```python
  from SPARQLWrapper import SPARQLWrapper, JSON
  
  sparql = SPARQLWrapper("http://publications.europa.eu/webapi/rdf/sparql")
  sparql.setQuery("""
      SELECT ?celex ?title ?date
      WHERE {
          ?doc cdm:work_has_resource-type <http://publications.europa.eu/resource/authority/resource-type/REGULATION> .
          ?doc cdm:resource_legal_id_celex ?celex .
          ?doc cdm:work_date_document ?date .
          FILTER(CONTAINS(?celex, "2023"))
      }
      LIMIT 100
  """)
  sparql.setReturnFormat(JSON)
  results = sparql.query().convert()
  ```

- **httpx** (alternative): Plain HTTP with `Accept: application/sparql-results+json`

**Example Query: Find Consolidated Versions**
```sparql
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

SELECT ?celex ?consolidationDate ?title
WHERE {
    ?doc cdm:resource_legal_id_celex ?celex .
    ?doc cdm:work_date_document ?consolidationDate .
    ?doc cdm:work_has_resource-type <http://publications.europa.eu/resource/authority/resource-type/REGULATION> .
    FILTER(STRSTARTS(?celex, "02023R1542"))
}
ORDER BY DESC(?consolidationDate)
LIMIT 1
```

**What to Extract:**
- CELEX number (e.g., `32023R1542` for original, `02023R1542-20240101` for consolidated)
- Consolidation date
- Document type (Regulation, Directive)
- Title
- Publication date

### 1.2 CELLAR REST API (Document Retrieval)

**Purpose:** Fetch the full text of a specific document by CELEX or ELI.

**Endpoint Pattern:** `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}`

**Formats:**
- **HTML:** Human-readable but harder to parse
- **Formex XML:** Structured, cleaner to parse (preferred)
  - URL: `https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:{celex}&format=XML`

**Python Libraries:**
- **httpx** for HTTP requests
- **defusedxml** for safe XML parsing (blocks XXE attacks)
  ```python
  import httpx
  from defusedxml import ElementTree as ET
  
  response = httpx.get(
      f"https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:32023R1542&format=XML",
      timeout=30.0
  )
  root = ET.fromstring(response.content)
  ```

**Security:** NEVER use plain `xml.etree.ElementTree` or `lxml` with default settings — they allow external entity injection. Use `defusedxml` or configure parsers with:
```python
from lxml import etree
parser = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    dtd_validation=False
)
```

### 1.3 RSS Feeds (Change Detection)

**Purpose:** Zero-auth way to detect new publications without polling SPARQL.

**Example Feed:** Official Journal L-series (acts)
- URL: `https://eur-lex.europa.eu/EN/display-feed.html?feedId=ojl`

**Strategy:**
1. Poll RSS feed (e.g., daily)
2. Extract CELEX numbers from new entries
3. Compare against your database
4. Fetch full documents for new/changed CELEX

**Python Libraries:**
- **feedparser**: `pip install feedparser`
- **httpx** for fetching

---

## 2. ECHA (Substance Restrictions)

**What:** European Chemicals Agency — manages REACH, SVHC Candidate List, and substance restrictions.

**Why:** Most of our gaps involve substances (PFAS, DEHP, mercury, etc.). ECHA is the authoritative source.

### 2.1 SVHC Candidate List

**Current URL (migrating):** 
- **New:** https://chem.echa.europa.eu/obligation-lists/candidateList
- **Legacy:** https://echa.europa.eu/candidate-list-table (maintained until Dec 2026)

**Format:** HTML table

**What to Extract:**
- Substance name
- EC number
- CAS number
- Date added to list
- Reason for inclusion (e.g., "Toxic for reproduction")

**Python Libraries:**
- **httpx** for fetching
- **BeautifulSoup** (`bs4`) + **lxml** for parsing
  ```python
  import httpx
  from bs4 import BeautifulSoup
  
  response = httpx.get(
      "https://echa.europa.eu/candidate-list-table",
      headers={"User-Agent": "RegulatoryRadar/1.0 (contact@example.com)"},
      timeout=30.0
  )
  soup = BeautifulSoup(response.content, "lxml")
  table = soup.find("table", {"id": "substancesTable"})
  ```

**Rate Limits:**
- ECHA rate-limits aggressive fetching
- Cache results for ~24 hours
- Send a clear User-Agent with contact info
- Respect `robots.txt`

### 2.2 REACH Annexes

**URL:** Via EUR-Lex (CELEX: `32006R1907`)

**What to Extract:**
- Annex XIV (Authorization List)
- Annex XVII (Restrictions)
- Substance concentration limits

---

## 3. The Watchlist (10 Key Regulations)

Pin these consolidated acts rather than crawling the entire corpus. **Always resolve to the consolidated version** (CELEX sector `0`, date-suffixed, e.g., `02011L0065-YYYYMMDD`) to get what's in force now.

| Family | Instrument | Original CELEX | Consolidated Pattern |
|--------|------------|----------------|---------------------|
| **RoHS** | Directive 2011/65/EU | `32011L0065` | `02011L0065-YYYYMMDD` |
| **REACH** | Regulation (EC) 1907/2006 | `32006R1907` | `02006R1907-YYYYMMDD` |
| **WEEE** | Directive 2012/19/EU | `32012L0019` | `02012L0019-YYYYMMDD` |
| **Battery** | Regulation (EU) 2023/1542 | `32023R1542` | `02023R1542-YYYYMMDD` |
| **PPWR** | Regulation (EU) 2025/40 | `32025R0040` | `02025R0040-YYYYMMDD` |
| **GPSR** | Regulation (EU) 2023/988 | `32023R0988` | `02023R0988-YYYYMMDD` |
| **RED** | Directive 2014/53/EU | `32014L0053` | `02014L0053-YYYYMMDD` |
| **ESPR** | Regulation (EU) 2024/1781 | `32024R1781` | `02024R1781-YYYYMMDD` |
| **Toy Safety** | Directive 2009/48/EC | `32009L0048` | `02009L0048-YYYYMMDD` |
| **MDR** | Regulation (EU) 2017/745 | `32017R0745` | `02017R0745-YYYYMMDD` |
| **POPs** | Regulation (EU) 2019/1021 | `32019R1021` | `02019R1021-YYYYMMDD` |

**Strategy:**
1. Query SPARQL for the latest consolidation date of each CELEX
2. Fetch the consolidated Formex XML
3. Parse for relevant articles (e.g., Battery Reg Art. 77 for passport)
4. Normalize to `Requirement` schema

---

## 4. Secondary Sources (Verification Only)

These are **NOT** for Part 1 extraction but useful for Part 3 (alerting) verification:

### 4.1 EPREL (Energy Labels)
- **URL:** https://ec.europa.eu/info/energy-climate-change-environment/standards-tools-and-labels/products-labelling-rules-and-requirements/energy-label-and-ecodesign/product-database_en
- **API:** Public REST API for product registrations
- **Use:** Verify energy label compliance

### 4.2 National EPR Registers
- **Germany (stiftung ear):** https://www.stiftung-ear.de/
- **France (ADEME):** https://www.ademe.fr/
- **Use:** Verify packaging/WEEE registration

### 4.3 Harmonised Standards Lists
- **RED Cybersecurity (EN 18031):** Check if a connected device has documented conformity
- **URL:** https://ec.europa.eu/growth/single-market/european-standards/harmonised-standards_en

---

## 5. Provenance Requirements (Mandatory)

On every persisted `Requirement`, record:

| Field | Source | Example |
|-------|--------|---------|
| `source_url` | The actual URL you fetched | `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1542` |
| `celex` | CELEX number | `32023R1542` or `02023R1542-20240101` |
| `consolidation_date` | Date of consolidation (if applicable) | `2024-01-01` |
| `access_timestamp` | When you fetched it (ISO 8601 UTC) | `2024-01-15T10:30:00Z` |

**Why:** This is both the "cite the source" requirement and the auditability the jury weights. A finding without a source_url is invalid.

---

## 6. Change Detection Strategy

### 6.1 Conditional GET (HTTP 304)
Use `If-None-Match` (ETag) and `If-Modified-Since` headers so most polls return `304 Not Modified`:

```python
import httpx

headers = {}
if last_etag:
    headers["If-None-Match"] = last_etag
if last_modified:
    headers["If-Modified-Since"] = last_modified

response = httpx.get(url, headers=headers, timeout=30.0)
if response.status_code == 304:
    # No change, skip processing
    return
```

### 6.2 Content Hashing
For sources without ETags, hash the content and compare:

```python
import hashlib

content_hash = hashlib.sha256(response.content).hexdigest()
if content_hash == stored_hash:
    # No change
    return
```

### 6.3 Cursors / Pagination
For SPARQL queries, use `OFFSET` to paginate:

```sparql
SELECT ?celex ?date
WHERE { ... }
ORDER BY DESC(?date)
LIMIT 100
OFFSET 0
```

Store the last processed date and query only newer entries.

---

## 7. Polite Client Guidelines

### 7.1 User-Agent
Always send a clear User-Agent with contact info:

```python
headers = {
    "User-Agent": "RegulatoryRadar/1.0 (contact@example.com; +https://github.com/yourorg/regulatory-radar)"
}
```

### 7.2 Rate Limiting
- **CELLAR SPARQL:** < 5 concurrent connections, back off on 429/503
- **ECHA:** Cache for ~24 hours, respect rate limits
- **EUR-Lex REST:** Reasonable delays between requests (1-2 seconds)

### 7.3 Timeouts
Always set explicit timeouts:

```python
response = httpx.get(url, timeout=30.0)
```

### 7.4 Respect robots.txt
Check and honor `robots.txt` for each domain.

---

## 8. Example Extraction Flow

```python
# 1. Query SPARQL for latest Battery Regulation consolidation
celex = "02023R1542"
sparql_query = f"""
    SELECT ?consolidationDate
    WHERE {{
        ?doc cdm:resource_legal_id_celex ?celex .
        FILTER(STRSTARTS(?celex, "{celex}"))
    }}
    ORDER BY DESC(?consolidationDate)
    LIMIT 1
"""
# Execute query, get latest date

# 2. Fetch Formex XML
url = f"https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:{celex}-{date}&format=XML"
response = httpx.get(url, timeout=30.0)

# 3. Parse with defusedxml
from defusedxml import ElementTree as ET
root = ET.fromstring(response.content)

# 4. Extract Article 77 (battery passport)
# ... parse XML for relevant articles ...

# 5. Normalize to Requirement
requirement = Requirement(
    update_id="REQ-BATTERY-PASSPORT-001",
    source="EUR-Lex",
    source_url=url,
    celex=f"{celex}-{date}",
    consolidation_date=date,
    access_timestamp=datetime.utcnow().isoformat() + "Z",
    regulation_family="battery",
    reference="Article 77",
    title="Battery passport requirement",
    # ... other fields ...
)

# 6. Persist to database
```

---

## 9. Testing with Bundled Examples

Before pointing at live sources, test your parsing logic with the bundled examples:

- **`dataset/feed/*.html`** — 10 example HTML notices
- **`dataset/regulatory_updates.json`** — 50 example rules (JSON shape)

Use these to develop your HTML/XML parsers, then switch to live URLs.

---

## 10. Troubleshooting

**SPARQL timeout:**
- Reduce query size, add `LIMIT`
- Use `OFFSET` for pagination
- Avoid complex joins

**ECHA rate limit:**
- Cache results for 24 hours
- Add delays between requests
- Send clear User-Agent

**XML parsing errors:**
- Use `defusedxml` to block XXE attacks
- Handle malformed XML gracefully
- Log parse errors for debugging

**No results from SPARQL:**
- Verify endpoint URL in official query builder
- Check CELEX format (sector `0` for consolidated)
- Ensure proper namespace prefixes

---

## 11. Python Libraries Summary

| Library | Purpose | Install |
|---------|---------|---------|
| **httpx** | HTTP client (async support) | `pip install httpx` |
| **SPARQLWrapper** | SPARQL queries | `pip install SPARQLWrapper` |
| **defusedxml** | Safe XML parsing | `pip install defusedxml` |
| **BeautifulSoup** | HTML parsing | `pip install beautifulsoup4` |
| **lxml** | XML/HTML parser backend | `pip install lxml` |
| **feedparser** | RSS/Atom feeds | `pip install feedparser` |
| **pydantic-settings** | Settings from env | `pip install pydantic-settings` |

---

## 12. Next Steps

1. Implement CELLAR SPARQL client in `extraction_service/clients.py`
2. Implement ECHA scraper in `extraction_service/clients.py`
3. Implement normalization logic in `extraction_service/normalize.py`
4. Implement change detection in `extraction_service/change.py`
5. Test with bundled examples first
6. Switch to live sources
7. Validate provenance metadata on every `Requirement`

---

**Remember:** The bundled dataset is for **shape reference only**. Your extraction service must pull from **live sources** and cite the **actual source_url** on every requirement.
