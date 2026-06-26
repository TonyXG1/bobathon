# Alerting Service (Part 3)

Dispatches alerts for compliance gaps via SMS/WhatsApp/Email using Twilio.

## Responsibilities

- Route by partner's `preferred_channel` (email/sms/whatsapp)
- Format concise messages (< 300 chars for SMS)
- Send via Twilio SDK
- Log all deliveries to `alerts_log` table

## API Endpoints

- `POST /alerts` - Send alert for a finding
- `GET /alerts/log` - View alert history
- `GET /alerts/log/{finding_id}` - Get alerts for specific finding
- `GET /health` - Health check

## Key Files

- `main.py` - FastAPI app and endpoints
- `channels.py` - Channel routing (SMS/WhatsApp/Email)
- `templates.py` - Message formatting
- `config.py` - Settings (Twilio credentials)
- `database.py` - SQLite/Postgres connection

## Technology Stack

- **FastAPI** - Web framework
- **Pydantic v2** - Data validation
- **Twilio SDK** - SMS/WhatsApp/Email delivery
- **httpx** - HTTP client (for calling assessment service)

## Running Locally

```bash
cd alerting_service
uv sync
uv run uvicorn main:app --reload --port 8083
```

Visit http://localhost:8083/docs for interactive API documentation.

## Running with Docker

```bash
docker build -t alerting-service .
docker run -p 8083:8083 --env-file ../.env alerting-service
```

## Testing

```bash
uv run pytest
uv run pytest --cov=. --cov-report=html
```

## Environment Variables

Required:
- `DATABASE_URL` - Database connection string
- `TWILIO_ACCOUNT_SID` - Twilio account SID
- `TWILIO_AUTH_TOKEN` - Twilio auth token
- `TWILIO_PHONE_NUMBER` - Your Twilio phone number (from)
- `TWILIO_TEST_NUMBER` - YOUR test phone number (to)
- `TWILIO_TEST_EMAIL` - YOUR test email (to)

Optional:
- `ASSESSMENT_SERVICE_URL` - URL of assessment service
- `LOG_LEVEL` - Logging level (default: INFO)

## Alert Requirements

1. **ONE message per gap**
2. **Use partner's preferred_channel** from contact object
3. **Send to OUR test endpoints** (NEVER to portfolio contacts)
4. **SMS must be < 300 chars**

## Message Template

```
URGENT: {product} ({product_id}) non-compliant with {regulation}.
{requirement} by {deadline}.
Action: {recommended_action}.
Source: {source_url}
```

## Channel Routing

```python
def route_alert(finding: Finding) -> str:
    channel = finding.alert.channel
    
    if channel == "sms":
        return send_sms(finding.alert.to, finding.alert.message)
    elif channel == "whatsapp":
        return send_whatsapp(finding.alert.to, finding.alert.message)
    elif channel == "email":
        return send_email(finding.alert.to, finding.alert.message)
```

## Twilio Setup

1. **Get credentials** from https://console.twilio.com/
2. **Get phone number** from Twilio Console
3. **Use promo code** `TUM-TWILIO-50` for hackathon credit
4. **Configure .env** with your credentials

## Security Notes

- **Never log Twilio credentials**
- **Validate recipient before sending**
- **Rate limit to prevent abuse**
- **Always send to OUR test endpoints** (not portfolio contacts)

## Development Guidelines

1. **Use official Twilio SDK**
   ```python
   from twilio.rest import Client
   
   client = Client(account_sid, auth_token)
   message = client.messages.create(
       body=text,
       from_=twilio_phone,
       to=recipient
   )
   ```

2. **Log every send attempt**
   - Success: store Twilio SID
   - Failure: store error message
   - Always log: finding_id, channel, recipient, timestamp

3. **Handle Twilio errors gracefully**
   ```python
   try:
       message = client.messages.create(...)
       return {"status": "sent", "sid": message.sid}
   except TwilioException as e:
       logger.error(f"Twilio error: {e}")
       return {"status": "failed", "error": str(e)}
   ```

4. **Keep SMS concise**
   - Product name + ID
   - Regulation (short form)
   - Deadline
   - One action
   - Source link

## Testing Alerts

**Test mode** (don't actually send):
```bash
export TEST_MODE=true
```

**Send test alert**:
```bash
curl -X POST http://localhost:8083/alerts \
  -H "Content-Type: application/json" \
  -d @../contracts/fixtures/findings.sample.json
```

## Troubleshooting

**Twilio authentication failed:**
- Verify TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN
- Check credentials are not expired

**Message not delivered:**
- Check recipient number format (+1234567890)
- Verify Twilio phone number is verified
- Check Twilio account balance

**Rate limiting:**
- Twilio has rate limits per account
- Add delays between bulk sends
- Use queue for large batches

**WhatsApp not working:**
- WhatsApp requires approved template
- Use SMS for hackathon demo