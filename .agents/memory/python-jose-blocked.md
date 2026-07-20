---
name: python-jose blocked by package firewall
description: python-jose is blocked by Replit's package firewall. Use PyJWT instead.
---

## Rule
Do NOT use `python-jose` for JWT in this project. Use `PyJWT` instead.

```python
import jwt  # PyJWT

token = jwt.encode(payload, secret, algorithm="HS256")
payload = jwt.decode(token, secret, algorithms=["HS256"])
```

**Why:** Replit's package firewall returns HTTP 403 when pip tries to install `python-jose==3.3.0`. The workflow fails to start.

**How to apply:** requirements.txt should list `PyJWT>=2.10.1` not `python-jose`. The `jwt` import name is the same (`import jwt`) so code using PyJWT looks identical except there's no `[cryptography]` extra needed for HS256.
