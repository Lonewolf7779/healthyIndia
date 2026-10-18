"""
Domain models and pure business logic for healthyIndia.

Architectural Rule:
- Independent of FastAPI, HTTP libraries, databases, and OCR adapters.
- Pure Python data structures and validation rules.
- Missing nutrition values must never silently become zero.
"""
