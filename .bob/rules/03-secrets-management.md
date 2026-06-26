# Secrets Management Rule

**Secrets ONLY via environment variables.**

## Why This Matters

- Hardcoded secrets in source code are a security risk
- Secrets in version control can be exposed
- Environment variables allow different configs per environment
- Secrets in logs can be leaked

## How to Manage Secrets

### Use pydantic-settings or python-dotenv

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    twilio_account_sid: str
    twilio_auth_token: str
    database_url: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### Load from Environment

```python
import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
```

## What Are Secrets?

Secrets include:
- API keys (Twilio, IBM, etc.)
- Database credentials
- Authentication tokens
- Private keys
- Passwords
- Session secrets

## File Management

### .env (gitignored)
```bash
# Actual secrets - NEVER commit
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_real_token_here
DATABASE_URL=postgresql://user:password@localhost/db
```

### .env.example (committed)
```bash
# Template - safe to commit
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
DATABASE_URL=sqlite:///./regulatory_radar.db
```

## Never Do This

❌ **Hardcoded secrets:**
```python
# WRONG - hardcoded in source
TWILIO_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

❌ **Secrets in logs:**
```python
# WRONG - logs the token
logger.info(f"Using token: {twilio_token}")
```

❌ **Secrets in error messages:**
```python
# WRONG - exposes in error
raise Exception(f"Failed to connect with {database_url}")
```

❌ **Secrets in version control:**
```bash
# WRONG - .env committed to git
git add .env
```

## Always Do This

✅ **Load from environment:**
```python
# RIGHT - from env
settings = Settings()
twilio_sid = settings.twilio_account_sid
```

✅ **Validate at startup:**
```python
# RIGHT - fail fast if missing
if not settings.twilio_account_sid:
    raise ValueError("TWILIO_ACCOUNT_SID not set")
```

✅ **Mask in logs:**
```python
# RIGHT - mask sensitive data
logger.info(f"Using SID: {twilio_sid[:8]}...")
```

✅ **Use .env.example:**
```bash
# RIGHT - template in git
git add .env.example
```

## Verification Checklist

Before committing:
- [ ] No secrets in source code
- [ ] .env is in .gitignore
- [ ] .env.example has placeholders only
- [ ] Secrets loaded from environment
- [ ] No secrets in logs
- [ ] Validation at startup

## Consequences of Violation

- Security breach (exposed credentials)
- Unauthorized access to services
- Data leaks
- Financial loss (Twilio charges)
- Fails security review
- Loses points in judging

## Best Practices

1. **Use pydantic-settings** for type-safe config
2. **Validate at startup** - fail fast if secrets missing
3. **Never log secrets** - mask or omit from logs
4. **Rotate regularly** - change secrets periodically
5. **Use different secrets per environment** - dev/staging/prod
6. **Document required secrets** in .env.example
7. **Use secret managers** in production (AWS Secrets Manager, etc.)

## Emergency Response

If secrets are accidentally committed:

1. **Rotate immediately** - change the exposed secrets
2. **Remove from history** - use git filter-branch or BFG
3. **Notify team** - inform everyone of the breach
4. **Review logs** - check for unauthorized access
5. **Update .gitignore** - ensure it won't happen again
