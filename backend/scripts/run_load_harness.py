"""Developer-only synthetic load harness for Ghost Fabric (GF-52).

Produces labeled developer-baseline observations only. It does not validate
production capacity, failover latency, inference P99, or memory limits.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

RESULT_LABEL = "developer-fixture-only"
BASELINE_LABEL = "developer-baseline-only"
DEFAULT_READ_ROUTES = (
    "/api/v1/health",
    "/api/v1/mesh/topology",
    "/api/v1/prophet/scores",
    "/api/v1/observability",
)


@dataclass(frozen=True)
class LoadConfig:
    base_url: str
    confirm_local_simulation: bool
    output_dir: Path
    read_requests: int = 40
    mutation_advances: int = 20
    concurrency: int = 4
    seed: int = 42
    max_rate_per_second: int = 50
    allow_non_local: bool = False
    include_mesh_failover_observation: bool = False
    viewer_token: str = "viewer-token"
    operator_token: str = "operator-token"
    timeout_seconds: float = 10.0

    def validate(self) -> None:
        if self.read_requests < 1:
            raise ValueError("read_requests must be >= 1")
        if self.mutation_advances < 0:
            raise ValueError("mutation_advances must be >= 0")
        if self.concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        if self.max_rate_per_second < 1:
            raise ValueError("max_rate_per_second must be >= 1")
        if self.max_rate_per_second > 200:
            raise ValueError("max_rate_per_second capped at 200 for developer harness")
        if not self.confirm_local_simulation:
            raise ValueError("--confirm-local-simulation is required")
        ensure_allowed_target(self.base_url, allow_non_local=self.allow_non_local)


@dataclass
class RequestSample:
    phase: str
    method: str
    route: str
    status_code: int
    latency_ms: float
    ok: bool
    error: str | None = None
    request_id: str | None = None
    command_id: str | None = None
    started_at: float = 0.0


@dataclass
class PhaseSummary:
    name: str
    attempted: int
    completed: int
    errors: int
    error_rate: float
    throughput_rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    duration_seconds: float


@dataclass
class LoadResult:
    label: str
    baseline_label: str
    notice: str
    generated_at: str
    config: dict[str, Any]
    environment: dict[str, Any]
    samples: list[dict[str, Any]] = field(default_factory=list)
    phases: list[dict[str, Any]] = field(default_factory=list)
    buckets: list[dict[str, Any]] = field(default_factory=list)
    failover_observation: dict[str, Any] | None = None


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, round((p / 100) * (len(ordered) - 1))))
    return ordered[index]


def is_loopback_url(base_url: str) -> bool:
    host = (urlparse(base_url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def ensure_allowed_target(base_url: str, *, allow_non_local: bool = False) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("base_url must use http or https")
    if not parsed.hostname:
        raise ValueError("base_url must include a hostname")
    if not allow_non_local and not is_loopback_url(base_url):
        raise ValueError(
            "non-local targets are rejected; pass allow_non_local only for an approved operator override"
        )


def command_id_for(seed: int, index: int, prefix: str = "load") -> str:
    return f"{prefix}-{seed:04d}-{index:05d}"


def summarize_phase(name: str, samples: list[RequestSample]) -> PhaseSummary:
    latencies = [sample.latency_ms for sample in samples]
    errors = sum(1 for sample in samples if not sample.ok)
    duration = 0.0
    if samples:
        started = min(sample.started_at for sample in samples)
        ended = max(sample.started_at + (sample.latency_ms / 1000.0) for sample in samples)
        duration = max(ended - started, 1e-9)
    completed = len(samples)
    return PhaseSummary(
        name=name,
        attempted=completed,
        completed=completed,
        errors=errors,
        error_rate=round(errors / completed, 6) if completed else 0.0,
        throughput_rps=round(completed / duration, 3) if completed else 0.0,
        p50_ms=round(statistics.median(latencies), 3) if latencies else 0.0,
        p95_ms=round(percentile(latencies, 95), 3) if latencies else 0.0,
        p99_ms=round(percentile(latencies, 99), 3) if latencies else 0.0,
        max_ms=round(max(latencies), 3) if latencies else 0.0,
        duration_seconds=round(duration, 3),
    )


def bucket_samples(samples: list[RequestSample], bucket_seconds: float = 1.0) -> list[dict[str, Any]]:
    if not samples:
        return []
    origin = min(sample.started_at for sample in samples)
    buckets: dict[int, list[RequestSample]] = {}
    for sample in samples:
        index = int((sample.started_at - origin) // bucket_seconds)
        buckets.setdefault(index, []).append(sample)
    rows: list[dict[str, Any]] = []
    for index in sorted(buckets):
        group = buckets[index]
        latencies = [item.latency_ms for item in group]
        errors = sum(1 for item in group if not item.ok)
        rows.append(
            {
                "bucket": index,
                "offset_seconds": round(index * bucket_seconds, 3),
                "requests": len(group),
                "errors": errors,
                "error_rate": round(errors / len(group), 6),
                "throughput_rps": round(len(group) / bucket_seconds, 3),
                "p50_ms": round(statistics.median(latencies), 3),
                "p95_ms": round(percentile(latencies, 95), 3),
                "p99_ms": round(percentile(latencies, 99), 3),
            }
        )
    return rows


def render_svg_chart(buckets: list[dict[str, Any]], title: str = "Ghost Fabric developer load") -> str:
    width, height = 920, 360
    pad_l, pad_r, pad_t, pad_b = 56, 24, 36, 48
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    if not buckets:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<text x="24" y="40">No samples</text></svg>'
        )

    def series(key: str) -> list[float]:
        return [float(row[key]) for row in buckets]

    offsets = series("offset_seconds")
    latency = series("p95_ms")
    throughput = series("throughput_rps")
    errors = series("error_rate")

    max_x = max(offsets) or 1.0
    max_latency = max(latency) or 1.0
    max_throughput = max(throughput) or 1.0
    max_error = max(errors) or 1.0

    def x_pos(value: float) -> float:
        return pad_l + (value / max_x) * plot_w

    def y_pos(value: float, ceiling: float) -> float:
        return pad_t + plot_h - (value / ceiling) * plot_h

    def polyline(values: list[float], ceiling: float) -> str:
        points = " ".join(
            f"{x_pos(offsets[index]):.1f},{y_pos(values[index], ceiling):.1f}"
            for index in range(len(values))
        )
        return points

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            f'<rect width="100%" height="100%" fill="#0b1220"/>',
            f'<text x="{pad_l}" y="24" fill="#e2e8f0" font-size="16">{title} (developer-fixture-only)</text>',
            f'<polyline fill="none" stroke="#38bdf8" stroke-width="2" points="{polyline(latency, max_latency)}"/>',
            f'<polyline fill="none" stroke="#4ade80" stroke-width="2" points="{polyline(throughput, max_throughput)}"/>',
            f'<polyline fill="none" stroke="#f87171" stroke-width="2" points="{polyline(errors, max_error)}"/>',
            f'<text x="{pad_l}" y="{height - 16}" fill="#94a3b8" font-size="12">blue=p95_ms green=throughput_rps red=error_rate</text>',
            "</svg>",
        ]
    )


def write_artifacts(result: LoadResult, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "load-harness-latest.json"
    csv_path = output_dir / "load-harness-latest.csv"
    svg_path = output_dir / "load-harness-latest.svg"

    payload = asdict(result)
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "phase",
                "method",
                "route",
                "status_code",
                "latency_ms",
                "ok",
                "error",
                "request_id",
                "command_id",
            ],
        )
        writer.writeheader()
        for sample in result.samples:
            writer.writerow(
                {
                    "phase": sample["phase"],
                    "method": sample["method"],
                    "route": sample["route"],
                    "status_code": sample["status_code"],
                    "latency_ms": sample["latency_ms"],
                    "ok": sample["ok"],
                    "error": sample.get("error") or "",
                    "request_id": sample.get("request_id") or "",
                    "command_id": sample.get("command_id") or "",
                }
            )

    svg_path.write_text(render_svg_chart(result.buckets), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "svg": svg_path}


class _RateLimiter:
    def __init__(self, rate: int) -> None:
        self.interval = 1.0 / rate
        self._lock = threading.Lock()
        self._next = time.perf_counter()

    def wait(self) -> None:
        with self._lock:
            now = time.perf_counter()
            if now < self._next:
                time.sleep(self._next - now)
            self._next = max(self._next + self.interval, time.perf_counter())


def _http_request(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any] | None,
    timeout: float,
) -> tuple[int, float, str | None, str | None]:
    import httpx

    started = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, url, headers=headers, json=json_body)
        latency_ms = (time.perf_counter() - started) * 1000
        return response.status_code, latency_ms, response.headers.get("X-Request-ID"), None
    except Exception as exc:  # noqa: BLE001 - harness must capture transport failures
        latency_ms = (time.perf_counter() - started) * 1000
        return 0, latency_ms, None, str(exc)


def run_load_harness(
    config: LoadConfig,
    *,
    requester: Callable[..., tuple[int, float, str | None, str | None]] | None = None,
) -> LoadResult:
    config.validate()
    request_fn = requester or _http_request
    limiter = _RateLimiter(config.max_rate_per_second)
    samples: list[RequestSample] = []
    base = config.base_url.rstrip("/")

    def execute(
        *,
        phase: str,
        method: str,
        route: str,
        token: str,
        json_body: dict[str, Any] | None = None,
        command_id: str | None = None,
    ) -> RequestSample:
        limiter.wait()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Request-ID": f"req_{uuid.uuid4().hex[:12]}",
        }
        if command_id:
            headers["X-Command-ID"] = command_id
        started = time.perf_counter()
        status, latency_ms, request_id, error = request_fn(
            method=method,
            url=f"{base}{route}",
            headers=headers,
            json_body=json_body,
            timeout=config.timeout_seconds,
        )
        ok = error is None and 200 <= status < 400
        return RequestSample(
            phase=phase,
            method=method,
            route=route,
            status_code=status,
            latency_ms=latency_ms,
            ok=ok,
            error=error,
            request_id=request_id or headers["X-Request-ID"],
            command_id=command_id,
            started_at=started,
        )

    # Phase 1: fixed read mix
    read_jobs = [
        DEFAULT_READ_ROUTES[index % len(DEFAULT_READ_ROUTES)]
        for index in range(config.read_requests)
    ]
    with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        futures = [
            pool.submit(
                execute,
                phase="read",
                method="GET",
                route=route,
                token=config.viewer_token,
            )
            for route in read_jobs
        ]
        for future in as_completed(futures):
            samples.append(future.result())

    # Phase 2: single reset + fixed advances with deterministic command IDs
    samples.append(
        execute(
            phase="mutation",
            method="POST",
            route="/api/v1/scenario/reset",
            token=config.operator_token,
            json_body={},
            command_id=command_id_for(config.seed, 0, "reset"),
        )
    )
    with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        futures = [
            pool.submit(
                execute,
                phase="mutation",
                method="POST",
                route="/api/v1/scenario/advance",
                token=config.operator_token,
                json_body={"seconds": 1},
                command_id=command_id_for(config.seed, index + 1, "advance"),
            )
            for index in range(config.mutation_advances)
        ]
        for future in as_completed(futures):
            samples.append(future.result())

    failover_observation: dict[str, Any] | None = None
    if config.include_mesh_failover_observation:
        observation = execute(
            phase="failover_observation",
            method="POST",
            route="/api/v1/mesh/failover",
            token=config.operator_token,
            json_body={"node_id": "northstar"},
            command_id=command_id_for(config.seed, 99999, "failover"),
        )
        samples.append(observation)
        failover_observation = {
            "route": observation.route,
            "status_code": observation.status_code,
            "latency_ms": observation.latency_ms,
            "ok": observation.ok,
            "notice": "Single simulated /mesh/failover observation only; not a leader-kill or recovery-time claim.",
        }

    read_samples = [sample for sample in samples if sample.phase == "read"]
    mutation_samples = [sample for sample in samples if sample.phase == "mutation"]
    phases = [
        asdict(summarize_phase("read", read_samples)),
        asdict(summarize_phase("mutation", mutation_samples)),
    ]
    buckets = bucket_samples(samples)
    return LoadResult(
        label=RESULT_LABEL,
        baseline_label=BASELINE_LABEL,
        notice=(
            "Developer-fixture-only load observations. Not production capacity, "
            "failover latency, inference P99, or memory evidence."
        ),
        generated_at=datetime.now(UTC).isoformat(),
        config={
            **{key: (str(value) if isinstance(value, Path) else value) for key, value in asdict(config).items()},
            "rate_limit_note": "Process-local API rate limit may cap results; not multi-instance capacity.",
        },
        environment={
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        samples=[asdict(sample) for sample in samples],
        phases=phases,
        buckets=buckets,
        failover_observation=failover_observation,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ghost Fabric developer-only load harness (GF-52)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--confirm-local-simulation", action="store_true")
    parser.add_argument("--allow-non-local", action="store_true")
    parser.add_argument("--read-requests", type=int, default=40)
    parser.add_argument("--mutation-advances", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-rate-per-second", type=int, default=50)
    parser.add_argument("--include-mesh-failover-observation", action="store_true")
    parser.add_argument("--viewer-token", default="viewer-token")
    parser.add_argument("--operator-token", default="operator-token")
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "app" / "fixtures" / "load-harness"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = LoadConfig(
        base_url=args.base_url,
        confirm_local_simulation=args.confirm_local_simulation,
        allow_non_local=args.allow_non_local,
        read_requests=args.read_requests,
        mutation_advances=args.mutation_advances,
        concurrency=args.concurrency,
        seed=args.seed,
        max_rate_per_second=args.max_rate_per_second,
        include_mesh_failover_observation=args.include_mesh_failover_observation,
        viewer_token=args.viewer_token,
        operator_token=args.operator_token,
        output_dir=Path(args.output_dir),
    )
    result = run_load_harness(config)
    paths = write_artifacts(result, config.output_dir)
    print(json.dumps({"label": result.label, "phases": result.phases, "artifacts": {k: str(v) for k, v in paths.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
