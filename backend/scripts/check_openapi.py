#!/usr/bin/env python
"""Fail CI when the committed OpenAPI contract drifts from the live app schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402


def main() -> int:
    committed = ROOT / "contracts" / "openapi.json"
    if not committed.exists():
        print("Missing contracts/openapi.json — run backend/scripts/export_openapi.py")
        return 1
    expected = json.loads(committed.read_text(encoding="utf-8"))
    actual = app.openapi()
    if json.dumps(expected, sort_keys=True) != json.dumps(actual, sort_keys=True):
        print("OpenAPI contract drift detected. Re-run backend/scripts/export_openapi.py")
        return 1
    print("OpenAPI contract matches application schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
