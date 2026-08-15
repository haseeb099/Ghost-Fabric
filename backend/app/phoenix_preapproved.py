"""Load simulation-only PHOENIX pre-approved policy catalog (read model)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "phoenix-preapproved-templates-v1.json"


@lru_cache(maxsize=1)
def load_preapproved_templates() -> dict[str, Any]:
    payload = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported pre-approved template schema_version")
    for template in payload.get("templates", []):
        if not template.get("requires_operator_confirm", False):
            raise ValueError("Every pre-approved template must require operator confirm")
    return payload


def preapproved_projection() -> dict[str, Any]:
    catalog = load_preapproved_templates()
    return {
        "schema_version": catalog["schema_version"],
        "label": catalog["label"],
        "notice": catalog["notice"],
        "templates": catalog["templates"],
        "auto_execute": False,
    }
