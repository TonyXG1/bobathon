# Assessment Service (Part 2)

Matches the live regulatory requirements (Part 1 output) against the fixed
partner portfolio and emits compliance gaps as `Finding[]`. **Simplified,
stateless build:** pure-Python matching, no database.

## How it works

1. Takes a list of `Requirement` objects — supplied directly in the request, or
   fetched live from the extraction service (`GET /requirements`).
2. Loads the fixed portfolio from `dataset/partners.json` (22 partners, 53 products).
3. Runs a small set of **deterministic gap rules** (`engine.py`). Each rule
   encodes one obligation's applicability predicate
   (market ∧ category ∧ substance ∧ attribute ∧ ¬exclusion) and is tied to a
   regulation family.
4. Emits one `Finding` per (product × matched rule), citing the **live
   `source_url`** from the requirement for that family (no source → no finding).

The rules re-derive the 5 seeded ground-truth gaps and the analogous gaps
elsewhere, while avoiding look-alikes (wrong market, absent substance,
out-of-scope attribute). Current portfolio → **15 findings**.

## API Endpoints

- `GET  /health`   — health check.
- `POST /assess`   — assess. Body may carry `requirements` (a `Requirement[]`);
  if omitted, the service fetches them live from the extraction service.
- `GET  /findings` — run the full pipeline: fetch live requirements from the
  extraction service, then assess.

## Key Files

- `main.py` — FastAPI app and endpoints.
- `engine.py` — deterministic gap rules + `Finding` construction (the matcher).
- `portfolio.py` — load `partners.json`, EU-market expansion.
- `config.py` — settings (`BaseSettings`).

## Running Locally

```bash
# 1. Start the extraction service (Part 1) on 8081:
cd ../extraction_service && ../.venv/Scripts/python -m uvicorn main:app --port 8081

# 2. Start the assessment service (Part 2) on 8082:
cd ../assessment_service && ../.venv/Scripts/python -m uvicorn main:app --port 8082
```

Then the full pipeline is one call:

```bash
curl http://localhost:8082/findings
```

Or assess requirements you already have, with no extraction service needed:

```bash
curl -X POST http://localhost:8082/assess \
     -H "Content-Type: application/json" \
     -d '{"requirements": [ ... Requirement[] ... ]}'
```

Interactive docs: http://localhost:8082/docs

## Testing

```bash
../.venv/Scripts/python -m pytest tests       # 17 tests, offline (extraction mocked)
```

The engine tests run against the real `dataset/partners.json` and assert the 5
seeded gaps are found and the documented look-alikes are not.

## Environment Variables (all optional)

- `EXTRACTION_SERVICE_URL` — extraction service base URL (default `http://localhost:8081`)
- `PARTNERS_PATH` — portfolio file (default `dataset/partners.json`)
- `TWILIO_TEST_NUMBER` / `TWILIO_TEST_EMAIL` — OUR alert recipients (never a
  portfolio contact)
- `HTTP_TIMEOUT`, `LOG_LEVEL`

## Ground Truth (re-derived from the rules)

| Partner | Product | Gap | Family |
|---|---|---|---|
| P006 FitTrack | PulseBand | PFAS/PFHxA coating | REACH |
| P008 PlayBright | RoboPup / SingAlong | DEHP in toy + button-cell access | Toy Safety / GPSR |
| P010 DisplayOne | Legacy CCFL Panel | mercury | RoHS |
| P013 RideVolt | e-Scooter / eBike battery | missing battery passport | Battery |
| P022 KidVision | LittleView | micro-USB charging port | RED |

Plus inferred gaps elsewhere (e.g. industrial batteries P003-B/P021-B, PFAS on
the SkyScout drone P017-A).
