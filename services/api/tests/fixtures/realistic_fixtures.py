"""
Loader and access helpers for realistic test fixtures.
"""

import json
from pathlib import Path
from typing import Any


def load_realistic_fixtures() -> list[dict[str, Any]]:
    """
    Loads synthetic test fixtures from data/fixtures/realistic_labels.json.
    """
    candidates = [
        Path(__file__).resolve().parents[4] / "data" / "fixtures" / "realistic_labels.json",
        Path(__file__).resolve().parents[3] / "data" / "fixtures" / "realistic_labels.json",
        Path("data/fixtures/realistic_labels.json").resolve(),
    ]
    target = next((p for p in candidates if p.is_file()), None)
    if not target:
        raise FileNotFoundError(f"Realistic fixtures not found in: {candidates}")

    with target.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("fixtures", [])


def get_fixture_by_id(fixture_id: str) -> dict[str, Any]:
    """
    Retrieves a single fixture by its unique ID.
    """
    fixtures = load_realistic_fixtures()
    match = next((f for f in fixtures if f["id"] == fixture_id), None)
    if not match:
        raise KeyError(f"Fixture with id '{fixture_id}' not found.")
    return match
