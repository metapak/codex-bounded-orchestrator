"""Provider- and storage-independent domain values."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DraftStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PUBLISH_FAILED = "publish_failed"
    PUBLISH_UNKNOWN = "publish_unknown"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RawResearchItem:
    source: str
    external_id: str
    title: str
    url: str
    excerpt: str
    author: str | None = None
    published_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchItem:
    id: int
    source: str
    external_id: str
    title: str
    canonical_url: str
    excerpt: str
    fingerprint: str
    author: str | None
    published_at: str | None
    discovered_at: str
    status: str
    summary: str | None = None
    category: str | None = None
    confidence: float | None = None
    near_duplicate_key: str | None = None


@dataclass(frozen=True)
class EvidenceRecord:
    id: int
    research_item_id: int
    source_url: str
    excerpt: str
    content_hash: str
    captured_at: str
    evidence_type: str


@dataclass(frozen=True)
class Claim:
    text: str
    kind: str
    evidence_ids: tuple[int, ...]
    supported: bool | None = None
    note: str | None = None


@dataclass(frozen=True)
class Draft:
    id: int
    text: str
    category: str
    status: DraftStatus
    revision: int
    confidence: float
    factual_risk: str
    verification_status: VerificationStatus
    research_item_id: int
    provider: str
    model: str
    prompt_version: str
    created_at: str
    updated_at: str
    rejection_reason: str | None = None
    approved_at: str | None = None
    rejected_at: str | None = None
    editor_notes: str | None = None
    hook_type: str | None = None
    post_structure: str | None = None
    source_type: str | None = None
    scheduled_at: str | None = None
    publish_attempted_at: str | None = None
    published_at: str | None = None
    x_post_id: str | None = None
    publish_error: str | None = None


class XAutopilotError(RuntimeError):
    """Base expected application error."""


class ConfigurationError(XAutopilotError):
    pass


class ProviderError(XAutopilotError):
    pass


class ProviderUnavailableError(ProviderError):
    pass


class StructuredOutputError(ProviderError):
    pass


class InvalidTransitionError(XAutopilotError):
    pass


class StaleRevisionError(XAutopilotError):
    pass


class EvidenceError(XAutopilotError):
    pass


class PublishError(XAutopilotError):
    """A publish request failed with a known, safe-to-display reason."""


class PublishAmbiguousError(PublishError):
    """A publish request may have reached X and must not be retried."""
