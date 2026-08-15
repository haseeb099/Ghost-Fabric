from __future__ import annotations

import asyncio
from typing import Any, Protocol

from pydantic import BaseModel, Field, ValidationError


PROHIBITED_TERMS = ("target", "weapon", "strike", "kill", "deception")


class AnalysisOutput(BaseModel):
    """Non-authoritative, review-only explanation schema."""

    summary: str = Field(min_length=10, max_length=280)
    contributors: list[str] = Field(min_length=1, max_length=3)
    uncertainty: str = Field(min_length=10, max_length=180)
    recommendation: str = Field(min_length=10, max_length=240)
    mode: str = Field(pattern="^(provider|fixture)$")


class AnalysisProvider(Protocol):
    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        """Return an object matching AnalysisOutput; must not mutate scenario state."""


class DeterministicFixtureProvider:
    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        contributors = context["contributors"]
        confidence = context["confidence"]
        return {
            "summary": f"Synthetic evidence is at {confidence}% confidence and requires operator review.",
            "contributors": contributors[:3],
            "uncertainty": "Fixture calibration is bounded; partial-quality samples are never silently imputed.",
            "recommendation": "Review the labeled evidence and retain human approval for any simulated workflow recovery.",
            "mode": "fixture",
        }


class ProviderNeutralAdapter:
    def __init__(
        self,
        provider: AnalysisProvider | None = None,
        *,
        timeout_seconds: float = 0.5,
        retries: int = 1,
    ) -> None:
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.fixture = DeterministicFixtureProvider()

    async def analyze(self, context: dict[str, Any]) -> AnalysisOutput:
        if self.provider is None:
            return AnalysisOutput.model_validate(await self.fixture.analyze(context))
        for _ in range(self.retries + 1):
            try:
                raw = await asyncio.wait_for(
                    self.provider.analyze(context), timeout=self.timeout_seconds
                )
                output = AnalysisOutput.model_validate(raw)
                self._ensure_safe(output)
                return output
            except (TimeoutError, ValidationError, ValueError):
                continue
        return AnalysisOutput.model_validate(await self.fixture.analyze(context))

    @staticmethod
    def _ensure_safe(output: AnalysisOutput) -> None:
        content = " ".join(
            [output.summary, output.uncertainty, output.recommendation, *output.contributors]
        ).lower()
        if any(term in content for term in PROHIBITED_TERMS):
            raise ValueError("Provider output contains prohibited operational language")
