"""Checksum fixture and demo evidence used for degraded-mode backup verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = [
    ROOT / "app" / "fixtures" / "broken-signal-v1.json",
    ROOT / "app" / "fixtures" / "prophet-telemetry-v1.json",
    ROOT / "app" / "fixtures" / "perf-review-latest.json",
    ROOT.parents[0] / "docs" / "DEMO_RUNBOOK.md",
    ROOT.parents[0] / "docs" / "OPERATOR_RUNBOOK.md",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    payload = {
        "schema_version": 1,
        "purpose": "degraded-mode-backup-evidence",
        "files": [
            {
                "path": str(path.relative_to(ROOT.parents[0])).replace("\\", "/"),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in EVIDENCE
            if path.exists()
        ],
    }
    output = ROOT / "app" / "fixtures" / "backup-evidence-checksums.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
