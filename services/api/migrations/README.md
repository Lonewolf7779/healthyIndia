# Database Migrations

This directory will contain database migration scripts (e.g. Alembic for PostgreSQL) once persistence models are introduced in later phases.

## Rules:
1. All migrations must be deterministic, versioned, and reversible.
2. Never store real credentials or production connection strings in migration scripts.
3. Parameterized schema operations only.
