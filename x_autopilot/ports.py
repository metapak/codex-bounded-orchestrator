"""Application ports. Domain services depend on these protocols only."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from .domain import Draft, EvidenceRecord, RawResearchItem, ResearchItem


@dataclass(frozen=True)
class ModelRequest:
    purpose: str
    instructions: str
    input: dict[str, Any]
    schema_name: str
    schema: dict[str, Any]
    prompt_version: str


@dataclass(frozen=True)
class ModelResponse:
    data: dict[str, Any]
    provider: str
    model: str
    response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_tokens: int | None = None
    estimated_cost_usd: float | None = None
    cost_provenance: str | None = None


class ModelProvider(Protocol):
    name: str

    def generate(
        self,
        request: ModelRequest,
        *,
        model: str,
        reasoning_effort: str,
        max_output_tokens: int,
        timeout_seconds: float,
    ) -> ModelResponse: ...


class ResearchSource(Protocol):
    name: str

    def fetch(self, limit: int) -> list[RawResearchItem]: ...


class Repository(Protocol):
    def initialize(self) -> None: ...

    def add_research(self, item: RawResearchItem, canonical_url: str, fingerprint: str) -> tuple[int, bool]: ...

    def add_evidence(self, research_item_id: int, source_url: str, excerpt: str, evidence_type: str = "source_excerpt") -> int: ...

    def get_evidence(self, evidence_id: int) -> EvidenceRecord | None: ...

    def list_evidence(self, research_item_id: int) -> list[EvidenceRecord]: ...

    def list_research(self, status: str | None = None) -> list[ResearchItem]: ...

    def get_research(self, research_item_id: int) -> ResearchItem | None: ...

    def update_research_analysis(self, research_item_id: int, *, summary: str, category: str, confidence: float, status: str, near_duplicate_key: str | None = None) -> None: ...

    def replace_research_claims(self, research_item_id: int, claims: list[dict[str, Any]]) -> None: ...

    def list_research_claims(self, research_item_id: int) -> list[dict[str, Any]]: ...

    def create_draft(self, *, text: str, category: str, confidence: float, factual_risk: str, verification_status: str, research_item_id: int, provider: str, model: str, prompt_version: str, claims: list[dict[str, Any]], rejection_reason: str | None = None, hook_type: str | None = None, post_structure: str | None = None, source_type: str | None = None) -> int: ...

    def get_draft(self, draft_id: int) -> Draft | None: ...

    def list_drafts(self) -> list[Draft]: ...

    def list_claims(self, draft_id: int) -> list[dict[str, Any]]: ...

    def edit_draft(self, draft_id: int, text: str, expected_revision: int) -> Draft: ...

    def replace_claims_and_verification(self, draft_id: int, claims: list[dict[str, Any]], verification_status: str, expected_revision: int) -> Draft: ...

    def set_draft_status(self, draft_id: int, status: str, expected_revision: int, reason: str | None = None) -> Draft: ...

    def schedule_draft(self, draft_id: int, scheduled_at: str, expected_revision: int) -> Draft: ...

    def list_due_drafts(self, now: str) -> list[Draft]: ...

    def claim_publish(self, draft_id: int, expected_revision: int, *, scheduled_only: bool = False, now: str | None = None) -> Draft | None: ...

    def finish_publish(self, draft_id: int, *, post_id: str | None = None, error: str | None = None, ambiguous: bool = False) -> Draft: ...

    def create_run(self, kind: str) -> int: ...

    def finish_run(self, run_id: int, status: str, detail: dict[str, Any]) -> None: ...

    def record_model_call(self, run_id: int | None, role: str, response: ModelResponse, prompt_version: str) -> None: ...

    def list_model_calls(self, run_id: int | None = None) -> list[dict[str, Any]]: ...

    def claim_job_slot(self, job_name: str, slot: str) -> bool: ...

    def finish_job_slot(self, job_name: str, slot: str, status: str) -> None: ...

    def healthcheck(self) -> bool: ...


ProviderFactory = Callable[[], ModelProvider]
