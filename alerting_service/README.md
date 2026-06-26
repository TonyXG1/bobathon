# Alerting Service (Part 3)

Dispatches one alert per compliance gap (`Finding`) on the partner's
`preferred_channel` via Twilio, to **OUR OWN test endpoints** (never a portfolio
contact). **Simplified, stateless build:** deliveries are kept in an in-memory
log for the session (no database).

## How it works

- Takes a list of `Finding` objects — supplied in the request, or fetched live
  from the assessment service (`GET /findings`).
- For each finding it formats a concise message (`templates.py`, SMS/WhatsApp
  capped < 300 chars) and sends it on the finding's channel (`channels.py`).
- **Safe by default:** if Twilio credentials are incomplete or `TEST_MODE=true`,
  the send is *simulated* (returns `status: "simulated"` with the reason) so the
  pipeline works end-to-end without sending anything. Fill in the missing
  credentials and it sends for real — no code change.

## API Endpoints

- `GET  /health` — health check.
- `POST /alerts` — send alerts for the findings in the request body
  (`Finding[]`). Supports `?limit=N` and `?only_channel=sms|whatsapp|email`.
- `POST /dispatch` — full pipeline: fetch findings from the assessment service,
  then send. Same `limit` / `only_channel` options.
- `GET  /alerts/log` — delivery history (this session).
- `GET  /alerts/log/{product_id}` — deliveries for one product.

## Running the full pipeline

```bash
# 1. extraction (8081), 2. assessment (8082) — see their READMEs, then:
cd alerting_service && ../.venv/Scripts/python -m uvicorn main:app --port 8083

# fire the whole chain (extraction -> assessment -> alerting):
curl -X POST http://localhost:8083/dispatch
# demo: send just one real SMS
curl -X POST "http://localhost:8083/dispatch?limit=1&only_channel=sms"
```

Interactive docs: http://localhost:8083/docs

## Twilio configuration (`.env`, gitignored)

Credentials are read from env only, never hardcoded or logged.

| Variable | Needed for | Notes |
|---|---|---|
| `TWILIO_API_KEY_SID` + `TWILIO_API_SECRET` | auth | API-key style auth (`SK...`) |
| `TWILIO_ACCOUNT_SID` | auth | your Account SID (`AC...`) — **required to send** |
| `TWILIO_PHONE_NUMBER` | SMS | a Twilio number you own (the "from") |
| `TWILIO_WHATSAPP_FROM` | WhatsApp | defaults to the Twilio sandbox sender |
| `TWILIO_TEST_NUMBER` | SMS/WhatsApp | OUR verified destination |
| `TWILIO_TEST_EMAIL` | email | OUR destination |
| `SENDGRID_API_KEY` | email | optional; without it, email is simulated |
| `TEST_MODE` | — | `true` forces dry-run even when fully configured |

To send a **real SMS**: set `TWILIO_ACCOUNT_SID`, `TWILIO_PHONE_NUMBER`, and a
Twilio-verified `TWILIO_TEST_NUMBER`, then `TEST_MODE=false`.

## Testing

```bash
../.venv/Scripts/python -m pytest tests       # 19 tests, offline; Twilio never called
```

Tests force dry-run (`TEST_MODE`) and inject a fake Twilio client, so they never
send real messages.

## Alert rules (enforced)

1. One message per gap.
2. Sent on the partner's `preferred_channel`.
3. Routed to OUR test endpoints — never a portfolio contact.
4. SMS/WhatsApp kept < 300 chars.
