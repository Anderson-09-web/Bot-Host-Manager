---
name: bcrypt-passlib incompatibility
description: passlib CryptContext fails with bcrypt>=4.0.0 installed in Replit Python 3.11 environment.
---

## Rule
Do NOT use `passlib` for password hashing in this project. Use `bcrypt` directly.

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

**Why:** Replit installs bcrypt 5.x. passlib's bcrypt backend reads `bcrypt.__about__.__version__` which no longer exists in bcrypt>=4.0.0. This causes passlib to enter a degraded mode and raises `"password cannot be longer than 72 bytes"` even for short passwords, breaking all auth seeding.

**How to apply:** Any time password hashing is needed in this Python FastAPI backend, import `bcrypt` directly. Never add passlib to requirements.txt.
