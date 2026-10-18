"""
Persistence interfaces and database repositories.

Architectural Rule:
- Parameterized queries / ORM only; prevent SQL injection.
- Persistence is decoupled from HTTP handlers and domain logic.
"""
