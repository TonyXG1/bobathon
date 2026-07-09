# Dataset Documentation

> **Data dictionary for the bundled dataset in `dataset/` — FIXED inputs, never modify them.**

The dataset contains three files:

1. **`partners.json`** — the portfolio: 22 companies / 53 products to assess (read-only)
2. **`taxonomy.json`** — controlled vocabulary: categories, substances, regulation families (authoritative enums)
3. **`sample_expected_output.json`** — one example `Finding`, the shape every assessment output conforms to

> Earlier scaffolding (`partners.csv`, an empty `regulatory_updates.json`, `dataset_stats.json`,
> `feed/`) was removed in the 2026-07 cleanup — nothing in the code used it. The rule shape those
> examples were meant to illustrate is defined by the `Requirement` model in
> [contracts/models.py](contracts/models.py).

**Critical:** rules come from **live sources** (see `SOURCES.md`), never from bundled files.

---

## 1. partners.json — The Portfolio (FIXED Input)

**Location:** `dataset/partners.json`
**Size:** 22 companies, 53 products total

### 1.1 Top-Level Structure

```json
{
  "partners": [
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
| `email` | string | Yes | Email address (synthetic `@example.com`; P010 points at our own demo inbox) |
| `phone` | string | Yes | Phone number (synthetic placeholder) |
| `preferred_channel` | enum | Yes | `email` \| `sms` \| `whatsapp` — **The channel to use for alerts** |

**Important:** SMS/WhatsApp alerts go to **YOUR Twilio test number**, never to portfolio phone
numbers. Email alerts go to the partner's `contact.email` (all synthetic in this dataset).

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

**Purpose:** Ground truth to validate the gap engine — the assessment service re-derives these
independently (asserted in `assessment_service/tests/test_engine.py`).

**The 5 Seeded Gaps:**

1. **P006 FitTrack — PulseBand (P006-A)**
   - Gap: Strap uses PFAS/PFHxA coating now restricted under REACH
   - Regulation: REACH Annex XVII · Substance: `PFAS_PFHxA`

2. **P008 PlayBright — RoboPup (P008-A) & SingAlong (P008-B)**
   - Gap 1: RoboPup soft plastic exceeds tightened toy DEHP limit (Toy Safety)
   - Gap 2: SingAlong button-cell compartment not child-secured (GPSR)
   - Substance: `DEHP` · Battery type: `button_cell`

3. **P010 DisplayOne — CCFL Panel (P010-B)**
   - Gap: Legacy CCFL spare panel still contains mercury
   - Regulation: RoHS · Substance: `mercury`

4. **P013 RideVolt — e-Scooter Pro (P013-A)**
   - Gap: LMT battery ships without EU battery passport
   - Regulation: Battery Regulation 2023/1542 Art. 77 · Battery type: `lmt`

5. **P022 KidVision — LittleView (P022-A)**
   - Gap: Still uses micro-USB (common-charger rule); connected device without documented RED cybersecurity (EN 18031)
   - Regulation: RED · Connector: `micro_usb`, `has_radio: true`

**Most partners have NO `compliance_status`** — inferring their gaps from current requirements is
the actual challenge (the engine also finds e.g. industrial batteries P003-B/P021-B and PFAS on
drone P017-A).

---

## 2. taxonomy.json — Controlled Vocabulary (Authoritative Enums)

**Location:** `dataset/taxonomy.json`
**Purpose:** Defines all valid enums for categories, substances, and regulation families. Each key
carries a one-line description in the file itself — the file is the authority.

### 2.1 Product Categories (17)

`audio`, `battery_pack`, `camera`, `charging_equipment`, `computing`, `display`, `drone`,
`emobility_battery`, `gaming`, `industrial_equipment`, `iot_sensor`, `led_lighting`,
`medical_wearable`, `networking`, `smartphone`, `toy_electronic`, `wearable`

### 2.2 Substances (13)

| Key | Regime |
|-----|--------|
| `lead` | RoHS |
| `cadmium` | RoHS |
| `mercury` | RoHS |
| `chromium_vi` | RoHS (hexavalent chromium) |
| `PBB` | RoHS (polybrominated biphenyls) |
| `PBDE` | RoHS (polybrominated diphenyl ethers) |
| `DEHP` | REACH / Toy Safety (phthalate) |
| `BPA` | REACH (bisphenol A) |
| `decaBDE` | RoHS / POPs (flame retardant) |
| `TBBPA` | REACH (flame retardant) |
| `MCCP` | POPs (chlorinated paraffins) |
| `PFAS_PFHxA` | REACH (PFAS, specifically PFHxA) |
| `dioxane` | REACH (1,4-dioxane) |

### 2.3 Regulation Families (20)

`rohs`, `reach`, `weee`, `battery`, `ppwr`, `gpsr`, `red`, `espr`, `toy_safety`, `mdr`, `pops`,
`epr`, `epr_packaging`, `energy_label`, `emc`, `lvd`, `machinery`, `atex`, `chemical_safety`,
`cybersecurity` — each mapped to its legal instrument in `taxonomy.json`.

### 2.4 Relationship to contracts/models.py

The `Literal` enums in `contracts/models.py` mirror `taxonomy.json` exactly (aligned 2026-07),
with one addition: the `"other"` regulation family, an extraction-side fallback for live rules
that map to no taxonomy family. If `taxonomy.json` changes, update the Literals and re-run
`export_schemas.py` in the same change.

### 2.5 Usage in Normalization

When normalizing extracted rules into `Requirement`, map categories/substances/families onto
known keys (see the alias maps in `extraction_service/normalize.py`). Unknown values are dropped
or defaulted to `"other"` — never invent a new taxonomy key without adding it to `taxonomy.json`
first.

---

## 3. sample_expected_output.json — Finding Shape (Output Contract)

**Location:** `dataset/sample_expected_output.json`
**Size:** 1 example finding

Shows the **structure every Part-2 output must conform to** (i.e., the `Finding` Pydantic model).

### 3.1 Finding Object

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
| `alert` | object | Alert details (see 3.2) |

### 3.2 Alert Object

| Field | Type | Description |
|-------|------|-------------|
| `channel` | enum | `email` \| `sms` \| `whatsapp` — Partner's `preferred_channel` |
| `to` | string | SMS/WhatsApp: **YOUR Twilio test number**. Email: the partner's contact inbox (synthetic) |
| `message` | string | Concise actionable text (< 300 chars for SMS): product, deadline, source |

**Example Alert Message:**
```
URGENT: e-Scooter Pro (P013-A) non-compliant with EU Battery Regulation. LMT battery requires digital passport by 2027-02-18. Action: Implement battery passport system. Source: https://eur-lex.europa.eu/...
```

---

## 4. Common Pitfalls

- ❌ Modifying the dataset — it is FIXED, read-only input
- ❌ Introducing category/substance/family strings that exist nowhere — extend `taxonomy.json` first
- ❌ Emitting a finding without a `source_url` — no source, no finding
- ❌ Sending SMS/WhatsApp to portfolio phone numbers — use YOUR Twilio test number

## 5. Validation Checklist (all satisfied by the current build)

- [x] All findings cite a `source_url` from a live source (no requirement for a family → no finding)
- [x] The 5 seeded gaps are independently re-derived (asserted in `assessment_service/tests/test_engine.py`)
- [x] Documented look-alikes are NOT flagged (wrong market, absent substance, out-of-scope attribute)
- [x] Findings conform to the `Finding` model (valid by construction)
- [x] SMS/WhatsApp alerts go to OUR test endpoints, never portfolio phone numbers

---

**Remember:** The dataset is for **reference and testing only**. The system works with **live data** from real portals.
