---
name: Neon DB env var key
description: Must use NEON_DATABASE_URL, not DATABASE_URL, to avoid conflict with Replit's managed Postgres.
---

## Rule
Always use `NEON_DATABASE_URL` as the environment variable name for the Neon PostgreSQL connection string in this project.

**Why:** Replit auto-injects `DATABASE_URL` pointing to its own managed Postgres instance. Using that key would connect to the wrong database. The Pydantic settings class reads `NEON_DATABASE_URL` explicitly.

**How to apply:** In `app/core/config.py`, the field is `NEON_DATABASE_URL`. When seeding secrets, use `NEON_DATABASE_URL`. Never use `DATABASE_URL`.
