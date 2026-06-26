# Dataset Documentation

> **Complete data dictionary for the bundled regulatory radar dataset**

This document provides detailed field-by-field documentation for all data files in the `dataset/` directory. These files are **FIXED inputs** — never modify them.

---

## 🎯 Purpose of the Dataset

The bundled dataset serves three purposes:

1. **Portfolio (partners.json)** — The 22 companies / 53 products to assess (FIXED, read-only)
2. **Taxonomy (taxonomy.json)** — Controlled vocabulary for categories, substances, regulation families (authoritative enums)
3. **Examples (regulatory_updates.json, feed/)** — Show the **shape** of a rule so you recognize one when scraping live sources (NOT an answer key)

**Critical:** `regulatory_updates.json` and `feed/*.html` are **NOT** the rules to match against. They teach you what a rule looks like. Your extraction service must pull from **live sources** (see `SOURCES.md`).

---

## 1. partners.json — The Portfolio (FIXED Input)

**Location:** `dataset/partners.json`  
**Format:** JSON  
**Size:** 22 companies, 53 products total

### 1.1 Top-Level Structure

```json
{
  "partners": [
    { /* Partner object */ },
    { /* Partner object */ },
    ...
  ]
}
```

### 1.2 Partner Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `partner_id` | string | Yes | Unique identifier: `P001` through `P022` |
| `company` | string | Yes | Legal company name |
| `hq_country` | string | Yes | ISO 3166-1 alpha-2 country code of headquarters (e.g., `DE`, `FR`, `NL`) |
| `sells_in` | string[] | Yes | Markets where company sells. `EU` expands to all 27 member states. Can also include individual countries (e.g., `["EU", "UK", "CH"]`) |
| `contact` | object | Yes | Contact information (see 1.3) |
| `products` | Product[] | Yes | Array of products (see 1.4) |
| `compliance_status` | object | No | **Only present on 5 partners** (P006, P008, P010, P013, P022) — see 1.5 |

### 1.3 Contact Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Contact person name |
| `email` | string | Yes | Email address (synthetic: `@example.com`) |
| `phone` | string | Yes | Phone number (synthetic placeholder) |
| `preferred_channel` | enum | Yes | `email` \| `sms` \| `whatsapp` — **The channel to use for alerts** |

**Important:** All contact details are synthetic and safe. However, alerts must go to **YOUR Twilio test number/email**, never to these portfolio contacts.

### 1.4 Product Object

These attributes drive the obligation reasoning in Part 2 (assessment).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_id` | string | Yes | Unique identifier: `{partner_id}-{letter}` (e.g., `P001-A`) |
| `name` | string | Yes | Product name |
| `category` | enum | Yes | One of `taxonomy.product_categories` (e.g., `battery_pack`, `toy_electronic`, `emobility_battery`) |
| `substances` | string[] | Yes | Substances actually present (keys from `taxonomy.substances`). Empty array `[]` means none declared |
| `has_battery` | boolean | Yes | Whether product contains a battery |
| `battery_chemistry` | string\|null | No | Chemistry type: `li-ion`, `li-po`, `lithium-primary`, `button_cell`, or `null` |
| `battery_type` | enum | Yes | `none` \| `portable` \| `button_cell` \| `lmt` \| `industrial` — **Drives Battery Regulation scope** |
| `battery_capacity_wh` | number | Yes | Capacity in watt-hours. `0` if no battery. Thresholds matter (e.g., industrial > 2 kWh) |
| `has_radio` | boolean | Yes | Has radio functionality (drives RED scope: common charger, cybersecurity) |
| `connector` | enum | Yes | `none` \| `usb_c` \| `micro_usb` \| `barrel` — **`micro_usb` triggers common-charger risk** |
| `packaging` | string[] | Yes | Packaging materials (e.g., `cardboard`, `plastic_film`) — drives PPWR/packaging scope |
| `intended_use` | enum | Yes | `consumer` \| `toy` \| `industrial` \| `medical` — **Drives exclusions** (e.g., medical devices exempt from consumer safety rules) |
| `markets` | string[] | Yes | Markets this specific SKU is placed on (may be narrower than company's `sells_in`) |
| `compliance_streams` | string[] | Yes | Regulation families the product is already tracked under (keys from `taxonomy.regulation_families`) |

**Key Attributes for Scope Matching:**

- **`category`** — Must match rule's scope categories (or rule scope is `"all"`)
- **`substances`** — If rule names substances, product must actually contain one
- **`battery_type`** — Battery passport rule hits `lmt` and `industrial`, NOT `portable`
- **`intended_use`** — `toy` triggers Toy Safety; `medical` excludes consumer rules
- **`connector`** — `micro_usb` triggers RED common-charger rule (USB-C mandate)
- **`has_radio`** — Triggers RED cybersecurity requirements

### 1.5 Compliance Status (Ground Truth)

**Only present on 5 partners:** P006, P008, P010, P013, P022

```json
"compliance_status": {
  "certs_held": ["CE", "RoHS", "REACH"],
  "known_gaps": [
    "Free-text description of a concrete current failing"
  ]
}
```

**Purpose:** Ground truth to validate your gap engine. Your assessment service should independently re-derive these gaps from live sources.

**The 5 Seeded Gaps:**

1. **P006 FitTrack — PulseBand (P006-A)**
   - Gap: Strap uses PFAS/PFHxA coating now restricted under REACH
   - Regulation: REACH Annex XVII
   - Substance: `PFAS_PFHxA`

2. **P008 PlayBright — RoboPup (P008-A) & SingAlong (P008-B)**
   - Gap 1: RoboPup soft plastic exceeds tightened toy DEHP limit
   - Gap 2: SingAlong button-cell compartment not child-secured (GPSR)
   - Regulations: Toy Safety Directive, GPSR
   - Substance: `DEHP`

3. **P010 DisplayOne — CCFL Panel (P010-B)**
   - Gap: Legacy CCFL spare panel still contains mercury
   - Regulation: RoHS Directive
   - Substance: `mercury`

4. **P013 RideVolt — e-Scooter Pro (P013-A)**
   - Gap: LMT battery ships without EU battery passport
   - Regulation: Battery Regulation 2023/1542 Article 77
   - Battery type: `lmt`

5. **P022 KidVision — LittleView (P022-A)**
   - Gap 1: Still uses micro-USB (common-charger rule)
   - Gap 2: Connected device with no documented RED cybersecurity (EN 18031)
   - Regulation: RED Directive
   - Connector: `micro_usb`, `has_radio: true`

**Most partners have NO `compliance_status`** — inferring their gaps from current requirements is the actual challenge.

---

## 2. partners.csv — Flattened Portfolio

**Location:** `dataset/partners.csv`  
**Format:** CSV (comma-separated)  
**Size:** 53 rows (one per product)

### 2.1 Structure

Same 22 companies / 53 products as `partners.json`, flattened to one row per product.

**Multi-value columns** are **pipe-delimited** (`|`):
- `sells_in`
- `substances`
- `packaging`
- `markets`
- `compliance_streams`

**Example:**
```csv
partner_id,company,sells_in,substances,markets
P001,PowerCell GmbH,EU|UK,lead|cadmium,EU|UK
```

### 2.2 Differences from JSON

- **No nested `compliance_status`** — ground truth gaps not included
- **No `battery_chemistry`** column — only `battery_type` is kept
- **Pipe-delimited arrays** instead of JSON arrays

**Use Case:** Easy to load with `pandas.read_csv()` for analysis, but treat `partners.json` as the source of truth.

### 2.3 Columns

```
partner_id, company, hq_country, sells_in, contact_email, contact_phone,
preferred_channel, product_id, product_name, category, intended_use,
substances, has_battery, battery_type, battery_capacity_wh, has_radio,
connector, packaging, markets, compliance_streams
```

---

## 3. taxonomy.json — Controlled Vocabulary (Authoritative Enums)

**Location:** `dataset/taxonomy.json`  
**Format:** JSON  
**Purpose:** Defines all valid enums for categories, substances, and regulation families

### 3.1 Structure

```json
{
  "product_categories": {
    "battery_pack": "Standalone battery packs and power banks",
    "led_lighting": "LED bulbs, strips, and fixtures",
    ...
  },
  "substances": {
    "lead": "Restricted under RoHS (< 0.1% by weight)",
    "DEHP": "Phthalate restricted in toys and consumer products",
    ...
  },
  "regulation_families": {
    "rohs": "Restriction of Hazardous Substances Directive 2011/65/EU",
    "reach": "Registration, Evaluation, Authorization of Chemicals (EC) 1907/2006",
    ...
  },
  "markets_note": "ISO 3166-1 alpha-2 country codes. 'EU' expands to all 27 member states."
}
```

### 3.2 Product Categories (17 total)

| Key | Description |
|-----|-------------|
| `battery_pack` | Standalone battery packs and power banks |
| `led_lighting` | LED bulbs, strips, and fixtures |
| `power_supply` | AC/DC adapters and power supplies |
| `emobility_battery` | E-bike, e-scooter, and EV batteries |
| `toy_electronic` | Electronic toys and games |
| `wearable` | Fitness trackers, smartwatches |
| `medical_wearable` | Medical-grade wearable devices |
| `display` | Monitors, screens, and display panels |
| `networking` | Routers, switches, access points |
| `iot_sensor` | IoT sensors and smart home devices |
| `drone` | Consumer and commercial drones |
| `audio` | Headphones, speakers, audio equipment |
| `camera` | Cameras and imaging devices |
| `computing` | Laptops, tablets, peripherals |
| `industrial_control` | Industrial automation and control systems |
| `telecom` | Telecommunications equipment |
| `other_electronics` | Miscellaneous electronic products |

### 3.3 Substances (13 total)

| Key | Regime | Description |
|-----|--------|-------------|
| `lead` | RoHS | Restricted under RoHS (< 0.1% by weight) |
| `cadmium` | RoHS | Restricted under RoHS (< 0.01% by weight) |
| `mercury` | RoHS | Restricted under RoHS (< 0.1% by weight) |
| `hexavalent_chromium` | RoHS | Restricted under RoHS (< 0.1% by weight) |
| `DEHP` | REACH/Toy Safety | Phthalate restricted in toys and consumer products |
| `BPA` | REACH | Bisphenol A, restricted in certain applications |
| `decaBDE` | RoHS/POPs | Decabromodiphenyl ether, flame retardant |
| `TBBPA` | REACH | Tetrabromobisphenol A, flame retardant |
| `MCCP` | POPs | Medium-chain chlorinated paraffins |
| `PFAS_PFHxA` | REACH | Per- and polyfluoroalkyl substances (PFAS), specifically PFHxA |
| `dioxane` | REACH | 1,4-Dioxane, solvent and contaminant |
| `phthalates_general` | REACH/Toy Safety | General phthalates category |
| `flame_retardants` | RoHS/REACH | General flame retardants category |

### 3.4 Regulation Families (20 total)

| Key | Instrument |
|-----|------------|
| `rohs` | Restriction of Hazardous Substances Directive 2011/65/EU |
| `reach` | Registration, Evaluation, Authorization of Chemicals (EC) 1907/2006 |
| `weee` | Waste Electrical and Electronic Equipment Directive 2012/19/EU |
| `battery` | Battery Regulation (EU) 2023/1542 |
| `ppwr` | Packaging and Packaging Waste Regulation (EU) 2025/40 |
| `gpsr` | General Product Safety Regulation (EU) 2023/988 |
| `red` | Radio Equipment Directive 2014/53/EU |
| `espr` | Ecodesign for Sustainable Products Regulation (EU) 2024/1781 |
| `toy_safety` | Toy Safety Directive 2009/48/EC |
| `mdr` | Medical Devices Regulation (EU) 2017/745 |
| `pops` | Persistent Organic Pollutants Regulation (EU) 2019/1021 |
| `epr` | Extended Producer Responsibility (national implementations) |
| `energy_label` | Energy Labelling Regulation (EU) 2017/1369 |
| `emc` | Electromagnetic Compatibility Directive 2014/30/EU |
| `lvd` | Low Voltage Directive 2014/35/EU |
| `machinery` | Machinery Directive 2006/42/EC |
| `atex` | Equipment for Explosive Atmospheres Directive 2014/34/EU |
| `cbam` | Carbon Border Adjustment Mechanism (EU) 2023/956 |
| `eudr` | EU Deforestation Regulation (EU) 2023/1115 |
| `fgas` | Fluorinated Greenhouse Gases Regulation (EU) 2024/573 |

**Note:** The last 3 (CBAM, EUDR, F-gas) are **noise** — not relevant to finished electronics. They're included to test your filtering logic.

### 3.5 Usage in Normalization

When normalizing extracted rules into `Requirement`:

1. **Map categories** to `product_categories` keys
2. **Map substances** to `substances` keys
3. **Map regulation families** to `regulation_families` keys

This ensures deterministic matching in the assessment engine. Never introduce a new category/substance/family without adding it to `taxonomy.json` first.

**Python Example:**
```python
from typing import Literal

ProductCategory = Literal[
    "battery_pack", "led_lighting", "power_supply", ...
]

Substance = Literal[
    "lead", "cadmium", "mercury", "DEHP", ...
]

RegulationFamily = Literal[
    "rohs", "reach", "weee", "battery", ...
]
```

---

## 4. regulatory_updates.json — EXAMPLE Rules (Shape Only)

**Location:** `dataset/regulatory_updates.json`  
**Format:** JSON  
**Size:** 50 example rules

### 4.1 Purpose

**NOT an answer key.** These examples teach the **shape** of a rule and show what **noise** looks like. Your extraction service must pull from **live sources**, not match against this file.

### 4.2 Structure

```json
{
  "updates": [
    { /* Update object */ },
    { /* Update object */ },
    ...
  ]
}
```

### 4.3 Update Object

| Field | Type | Description |
|-------|------|-------------|
| `update_id` | string | Unique identifier: `REG-26-NNN` |
| `published_date` | date | When published (ISO 8601: `YYYY-MM-DD`) |
| `source` | string | Source portal (e.g., `EUR-Lex`, `ECHA`, `National EPR registry (DE/FR)`) |
| `regulation_family` | enum | Key from `taxonomy.regulation_families` |
| `reference` | string | Legal reference (article/annex, e.g., `Article 77`, `Annex XVII`) |
| `title` | string | Human-readable title |
| `summary` | string | Brief description |
| `change_type` | enum | `new` \| `amendment` \| `correction` |
| `effective_date` | date | When it takes effect |
| `deadline_date` | date | Compliance deadline |
| `severity` | enum | `low` \| `medium` \| `high` |
| `action_required` | string | What companies must do |
| `scope` | object | Scope definition (see 4.4) |
| `corrects` | string\|null | If present, the `update_id` this entry duplicates/corrects → **de-duplicate** |

### 4.4 Scope Object

| Field | Type | Description |
|-------|------|-------------|
| `categories` | string[] \| `"all"` | Product categories in scope. `"all"` means all categories |
| `substances` | string[] | Substances named (empty if none) |
| `markets` | string[] | Markets in scope (e.g., `["EU"]`, `["DE", "FR"]`) |
| `conditions` | string | **Free-text carve-outs** — often encodes the exclusion that creates look-alikes (e.g., "Applies to LMT and industrial batteries only, not portable consumer batteries") |

### 4.5 Noise and Duplicates

The set deliberately includes:

- **Unrelated domains** (CBAM, F-gas, EUDR, food-contact, CLP) — not finished electronics
- **Duplicate/correction entries** — entries where `corrects` points to another `update_id`

**Purpose:** Test your filtering and de-duplication logic.

**Example Duplicate:**
```json
{
  "update_id": "REG-26-042",
  "change_type": "correction",
  "corrects": "REG-26-015",
  ...
}
```

**Action:** When `corrects` is present, de-duplicate — don't create a new obligation.

---

## 5. sample_expected_output.json — Finding Shape (Output Contract)

**Location:** `dataset/sample_expected_output.json`  
**Format:** JSON  
**Size:** 1 example finding

### 5.1 Purpose

Shows the **structure every Part-2 output must conform to** (i.e., the `Finding` Pydantic model).

### 5.2 Finding Object

| Field | Type | Description |
|-------|------|-------------|
| `company` | string | Partner company name |
| `partner_id` | string | `P0NN` |
| `product_id` | string | `P0NN-X` |
| `product` | string | Product name |
| `regulation` | string | Human-readable rule + article (e.g., "EU Battery Regulation 2023/1542 — battery passport (Art. 77)") |
| `requirement` | string | What the rule requires, in one sentence |
| `source_url` | string | **The live source the rule was read from (MANDATORY)** |
| `gap` | string | Why this product is non-compliant today |
| `deadline` | date | Compliance deadline (ISO 8601: `YYYY-MM-DD`) |
| `severity` | enum | `low` \| `medium` \| `high` |
| `recommended_action` | string | The fix |
| `alert` | object | Alert details (see 5.3) |

### 5.3 Alert Object

| Field | Type | Description |
|-------|------|-------------|
| `channel` | enum | `email` \| `sms` \| `whatsapp` — Partner's `preferred_channel` |
| `to` | string | **YOUR Twilio test number/email** (never portfolio contacts) |
| `message` | string | Concise actionable text (< 300 chars for SMS): product, deadline, source |

**Example Alert Message:**
```
URGENT: e-Scooter Pro (P013-A) non-compliant with EU Battery Regulation. LMT battery requires digital passport by 2027-02-18. Action: Implement battery passport system. Source: https://eur-lex.europa.eu/...
```

---

## 6. dataset_stats.json — Summary Counts

**Location:** `dataset/dataset_stats.json`  
**Format:** JSON

```json
{
  "partners": 22,
  "products": 53,
  "companies_with_seeded_gaps": 5,
  "sample_feed_updates": 50,
  "sample_noise": 6,
  "sample_duplicates": 6
}
```

---

## 7. feed/ — Example HTML Notices

**Location:** `dataset/feed/`  
**Files:** `index.html` + 10 `REG-26-*.html` files

### 7.1 Purpose

10 of the `regulatory_updates.json` entries rendered as HTML pages, mimicking a real legislation-portal notice.

**Use:** Develop and test your **HTML parsing path** (BeautifulSoup) before pointing at live web.

### 7.2 Content

Same content as matching JSON entries; not additional rules. Each HTML file has:
- Title
- Publication date
- Source
- Summary
- Scope details
- Action required

**Example:** `REG-26-015.html` corresponds to `update_id: "REG-26-015"` in `regulatory_updates.json`.

---

## 8. How to Use This Dataset

### 8.1 For Part 1 (Extraction)

- **DO NOT** match against `regulatory_updates.json`
- **DO** use `feed/*.html` to test your HTML parser
- **DO** pull from live sources (see `SOURCES.md`)
- **DO** normalize to `taxonomy.json` enums

### 8.2 For Part 2 (Assessment)

- **DO** load `partners.json` as the portfolio
- **DO** use `taxonomy.json` for enum validation
- **DO** validate against the 5 seeded gaps (ground truth)
- **DO** emit findings conforming to `sample_expected_output.json` shape

### 8.3 For Part 3 (Alerting)

- **DO** use `preferred_channel` from partner contact
- **DO NOT** send to portfolio contacts (use YOUR test number)
- **DO** keep SMS < 300 chars

### 8.4 For Part 4 (Dashboard)

- **DO** display findings with source_url links
- **DO** show access timestamps (auditability)
- **DO** sort by deadline and severity

---

## 9. Common Pitfalls

### 9.1 Treating Examples as Ground Truth

❌ **Wrong:** Match findings against `regulatory_updates.json`  
✅ **Right:** Pull from live sources, use examples to learn the shape

### 9.2 Modifying the Dataset

❌ **Wrong:** Edit `partners.json` to add/remove products  
✅ **Right:** Dataset is FIXED input, read-only

### 9.3 Ignoring Taxonomy

❌ **Wrong:** Introduce new category strings not in `taxonomy.json`  
✅ **Right:** Map all extracted data to taxonomy enums

### 9.4 Missing Source Citation

❌ **Wrong:** Finding without `source_url`  
✅ **Right:** Every finding cites the live source

### 9.5 Alerting to Portfolio Contacts

❌ **Wrong:** Send alerts to `contact.email` from `partners.json`  
✅ **Right:** Send to YOUR Twilio test number/email

---

## 10. Validation Checklist

Before considering Part 2 complete:

- [ ] All findings cite a `source_url` from a live source
- [ ] All categories/substances/families map to `taxonomy.json` keys
- [ ] The 5 seeded gaps are independently re-derived
- [ ] No findings match against `regulatory_updates.json` (they come from live sources)
- [ ] Fixtures in `contracts/fixtures/` conform to schemas
- [ ] Alerts go to YOUR test endpoints, not portfolio contacts

---

## 11. Next Steps

1. Load `partners.json` and `taxonomy.json` in your assessment service
2. Index portfolio by category/substance/market
3. Implement applicability predicate (market ∧ category ∧ substance ∧ attribute ∧ ¬exclusion)
4. Test against the 5 seeded gaps
5. Emit findings conforming to `sample_expected_output.json` shape
6. Validate every finding has a `source_url`

---

**Remember:** The dataset is for **reference and testing only**. Your system must work with **live data** from real portals.
