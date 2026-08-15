#!/usr/bin/env python
"""Export the FastAPI OpenAPI document into contracts/openapi.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402


def main() -> None:
    target = ROOT / "contracts" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = app.openapi()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
