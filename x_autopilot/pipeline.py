"""Deterministic coordinator for the Phase 1 research-to-draft flow."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .config import AppConfig
from .domain import EvidenceError, VerificationStatus
from .guards import draft_text_valid, review_claims as guard_review_claims
from .model import ModelGateway
from .normalize import canonicalize_url, fingerprint
from .ports import ModelRequest, Repository, ResearchSource

PACKAGE = Path(__file__).resolve().parent
BATCH_SIZE = 5
EXCERPT_CHARACTER_LIMIT = 1_200
EVIDENCE_CHARACTER_BUDGET = 2_400


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((PACKAGE / "schemas" / name).read_text(encoding="utf-8"))


def _prompt(name: str) -> str:
    return (PACKAGE / "prompts" / name).read_text(encoding="utf-8")


def _truncate(value: str, limit: int = EXCERPT_CHARACTER_LIMIT) -> str:
    clean = " ".join(value.split())
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def _balanced_batches(items: list[Any]) -> list[list[Any]]:
    """Use 3–5 item batches whenever at least three items are available."""
    if not items:
        return []
    batch_count = math.ceil(len(items) / BATCH_SIZE)
    base, extra = divmod(len(items), batch_count)
    batches: list[list[Any]] = []
    offset = 0
    for index in range(batch_count):
        size = base + int(index < extra)
        batches.append(items[offset : offset + size])
        offset += size
    return batches


def _evidence_payload(records: list[Any]) -> list[dict[str, Any]]:
    """Bound source text per candidate while retaining exact evidence IDs and URLs."""
    remaining = EVIDENCE_CHARACTER_BUDGET
    payload: list[dict[str, Any]] = []
    for record in records:
        if remaining <= 0:
            break
        excerpt = _truncate(record.excerpt, min(EXCERPT_CHARACTER_LIMIT, remaining))
        if not excerpt:
            continue
        payload.append({"id": record.id, "url": record.source_url, "excerpt": excerpt})
        remaining -= len(excerpt)
    return payload


def _safe_failure(exc: Exception) -> str:
    """Keep API response bodies, source text, and credentials out of run records."""
    return f"{type(exc).__name__}: runtime processing failed"


_NUMERICAL_SIGNAL = re.compile(
    r"(?:\d|[%$€£₺¥]|\b(?:yüzde|dolar|euro|avro|lira|tl|usd|eur|ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\b)",
    re.IGNORECASE,
)


def _claim_key(claim: dict[str, Any]) -> tuple[str, str]:
    text = " ".join(str(claim.get("text", "")).casefold().split())
    return str(claim.get("kind", "")), text


def _review_claims(
    draft_text: str,
    proposed: list[dict[str, Any]],
    reviewed: list[dict[str, Any]],
    valid_evidence_ids: set[int],
) -> tuple[list[dict[str, Any]], bool]:
    """Preserve proposed claims and conservatively validate reviewer coverage."""
    reviewed_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_review_keys: set[tuple[str, str]] = set()
    for claim in reviewed:
        key = _claim_key(claim)
        if key in reviewed_by_key:
            duplicate_review_keys.add(key)
        else:
            reviewed_by_key[key] = claim

    proposed_keys = [_claim_key(claim) for claim in proposed]
    duplicate_proposed_keys = {key for key in proposed_keys if proposed_keys.count(key) > 1}
    merged: list[dict[str, Any]] = []
    all_supported = not duplicate_proposed_keys and not duplicate_review_keys

    for original, key in zip(proposed, proposed_keys):
        review = reviewed_by_key.pop(key, None)
        refs = list(review.get("evidence_ids", [])) if review else list(original.get("evidence_ids", []))
        refs_valid = bool(refs) and all(ref in valid_evidence_ids for ref in refs)
        supported = bool(review and review.get("supported")) and refs_valid and key not in duplicate_review_keys and key not in duplicate_proposed_keys
        note = str(review.get("note", "")) if review else "Evidence reviewer omitted this proposed claim."
        merged.append({**original, "evidence_ids": refs, "supported": supported, "note": note})
        all_supported = all_supported and supported

    normalized_draft = " ".join(draft_text.casefold().split())
    for key, claim in reviewed_by_key.items():
        refs = list(claim.get("evidence_ids", []))
        refs_valid = bool(refs) and all(ref in valid_evidence_ids for ref in refs)
        appears_in_draft = bool(key[1]) and key[1] in normalized_draft
        supported = bool(claim.get("supported")) and refs_valid and appears_in_draft and key not in duplicate_review_keys
        merged.append({**claim, "evidence_ids": refs, "supported": supported})
        all_supported = all_supported and supported

    if not merged and _NUMERICAL_SIGNAL.search(draft_text):
        all_supported = False
    return merged, all_supported


class Pipeline:
    def __init__(self, config: AppConfig, repository: Repository, gateway: ModelGateway, sources: list[ResearchSource]) -> None:
        self.config=config; self.repository=repository; self.gateway=gateway; self.sources=sources

    def research(self) -> dict[str, Any]:
        run_id=self.repository.create_run("research"); added=duplicates=0; failures=[]
        for source in self.sources:
            remaining=self.config.max_research_items-added
            if remaining <= 0:
                break
            try:
                items=source.fetch(remaining)
                for raw in items:
                    canonical=canonicalize_url(raw.url); item_id,created=self.repository.add_research(raw,canonical,fingerprint(raw,canonical))
                    if not created:
                        duplicates+=1; continue
                    added+=1; self.repository.add_evidence(item_id,canonical,raw.excerpt)
            except Exception as exc:
                failures.append({"source":source.name,"error":_safe_failure(exc)})
        detail={"added":added,"duplicates":duplicates,"failures":failures}
        self.repository.finish_run(run_id,"partial" if failures and added else "failed" if failures else "completed",detail)
        return detail

    def generate(self) -> dict[str, Any]:
        run_id = self.repository.create_run("generate")
        drafted = rejected = filtered = candidates = 0
        failures: list[dict[str, Any]] = []
        selected = self.repository.list_research("new")[: self.config.max_drafts]
        verified_context = tuple(getattr(self.config, "verified_user_context", ()))
        for batch in _balanced_batches(selected):
            batch_evidence = {item.id: self.repository.list_evidence(item.id) for item in batch}
            batch_evidence_payload = {
                item.id: _evidence_payload(batch_evidence[item.id]) for item in batch
            }
            request_items = [
                {
                    "research_item_id": item.id,
                    "title": _truncate(item.title, 300),
                    "source": item.source,
                    "source_url": item.canonical_url,
                    "evidence": batch_evidence_payload[item.id],
                }
                for item in batch
            ]
            generation_request = ModelRequest(
                "luna_batch_generate",
                _prompt("luna_batch_generate_v1.md"),
                {
                    "items": request_items,
                    "language": self.config.language,
                    "categories": list(self.config.categories),
                    "verified_user_context": [
                        {"index": index, "fact": fact} for index, fact in enumerate(verified_context)
                    ],
                },
                "luna_batch_generate",
                _load_schema("luna_batch_generate_v1.json"),
                "luna_batch_generate_v1",
            )
            try:
                generation = self.gateway.run("luna", generation_request)
                self.repository.record_model_call(run_id, "luna", generation, "luna_batch_generate_v1")
            except Exception as exc:
                for item in batch:
                    failures.append({"research_item_id": item.id, "error": _safe_failure(exc)})
                    self.repository.update_research_analysis(
                        item.id,
                        summary=item.summary or item.title,
                        category=item.category or "unknown",
                        confidence=item.confidence or 0,
                        status="failed",
                    )
                continue

            output_candidates = list(generation.data.get("candidates", []))
            counts = {item.id: 0 for item in batch}
            by_id: dict[int, dict[str, Any]] = {}
            for candidate in output_candidates:
                item_id = candidate.get("research_item_id")
                if item_id in counts:
                    counts[item_id] += 1
                    by_id[item_id] = candidate
            generation_shape_valid = len(output_candidates) == len(batch) and all(
                count == 1 for count in counts.values()
            )
            eligible: list[dict[str, Any]] = []
            for item in batch:
                candidates += 1
                candidate = by_id.get(item.id)
                if candidate is None or not generation_shape_valid:
                    failures.append({"research_item_id": item.id, "error": "StructuredOutputError: candidate coverage failed"})
                    self.repository.update_research_analysis(item.id, summary=item.title, category="unknown", confidence=0, status="failed")
                    continue
                confidence = float(candidate["confidence"])
                category = str(candidate["category"])
                claims = list(candidate.get("claims", []))
                self.repository.replace_research_claims(item.id, claims)
                common = {
                    "summary": str(candidate["summary"]),
                    "category": category,
                    "confidence": confidence,
                    "near_duplicate_key": candidate.get("near_duplicate_key"),
                }
                if bool(candidate["noise"]) or confidence < self.config.min_confidence or (
                    self.config.categories and category not in self.config.categories
                ):
                    self.repository.update_research_analysis(item.id, status="filtered", **common)
                    filtered += 1
                    continue
                if not bool(candidate["accepted"]):
                    self.repository.update_research_analysis(item.id, status="editorial_rejected", **common)
                    rejected += 1
                    continue
                if not draft_text_valid(str(candidate["draft_text"])):
                    self.repository.update_research_analysis(item.id, status="editorial_rejected", **common)
                    rejected += 1
                    continue
                self.repository.update_research_analysis(item.id, status="ready", **common)
                eligible.append(candidate)

            if not eligible:
                continue
            review_items = []
            for candidate in eligible:
                item_id = int(candidate["research_item_id"])
                review_items.append(
                    {
                        "research_item_id": item_id,
                        "draft_text": candidate["draft_text"],
                        "proposed_claims": candidate.get("claims", []),
                        "evidence": batch_evidence_payload[item_id],
                    }
                )
            review_request = ModelRequest(
                "luna_batch_review",
                _prompt("luna_batch_review_v1.md"),
                {
                    "candidates": review_items,
                    "verified_user_context": [
                        {"index": index, "fact": fact} for index, fact in enumerate(verified_context)
                    ],
                },
                "luna_batch_review",
                _load_schema("luna_batch_review_v1.json"),
                "luna_batch_review_v1",
            )
            review_error: Exception | None = None
            try:
                review_response = self.gateway.run("luna", review_request)
                self.repository.record_model_call(run_id, "luna", review_response, "luna_batch_review_v1")
                reviews = list(review_response.data.get("reviews", []))
            except Exception as exc:
                review_response = None
                reviews = []
                review_error = exc
            review_counts: dict[int, int] = {}
            review_by_id: dict[int, dict[str, Any]] = {}
            for review in reviews:
                item_id = review.get("research_item_id")
                review_counts[item_id] = review_counts.get(item_id, 0) + 1
                review_by_id[item_id] = review
            eligible_ids = {int(candidate["research_item_id"]) for candidate in eligible}
            review_shape_valid = (
                len(reviews) == len(eligible)
                and set(review_counts) == eligible_ids
                and all(review_counts[item_id] == 1 for item_id in eligible_ids)
            )

            batch_items_by_id = {item.id: item for item in batch}
            for candidate in eligible:
                item_id = int(candidate["research_item_id"])
                item = batch_items_by_id[item_id]
                review = review_by_id.get(item_id) if review_shape_valid else None
                evidence_excerpts = {
                    record["id"]: record["excerpt"] for record in batch_evidence_payload[item_id]
                }
                enriched, coverage_supported = guard_review_claims(
                    str(candidate["draft_text"]),
                    list(candidate.get("claims", [])),
                    list(review.get("claims", [])) if review else [],
                    evidence_excerpts,
                    verified_context,
                )
                all_supported = bool(review and review.get("supported")) and coverage_supported
                status = VerificationStatus.SUPPORTED.value if all_supported else VerificationStatus.UNSUPPORTED.value
                self.repository.create_draft(
                    text=str(candidate["draft_text"]),
                    category=str(candidate["category"]),
                    confidence=float(candidate["confidence"]),
                    factual_risk=str(candidate["factual_risk"]),
                    verification_status=status,
                    research_item_id=item_id,
                    provider=generation.provider,
                    model=generation.model,
                    prompt_version="luna_batch_generate_v1+luna_batch_review_v1",
                    claims=enriched,
                    rejection_reason=None if all_supported else "Evidence or personal-context verification failed.",
                    hook_type=str(candidate["hook_type"]),
                    post_structure=str(candidate["post_structure"]),
                    source_type=item.source,
                )
                self.repository.update_research_analysis(
                    item_id,
                    summary=str(candidate["summary"]),
                    category=str(candidate["category"]),
                    confidence=float(candidate["confidence"]),
                    status="drafted" if all_supported else "evidence_rejected",
                    near_duplicate_key=candidate.get("near_duplicate_key"),
                )
                drafted += int(all_supported)
                rejected += int(not all_supported)
                if review_error is not None:
                    failures.append({"research_item_id": item_id, "error": _safe_failure(review_error)})
                elif review is None:
                    failures.append({"research_item_id": item_id, "error": "StructuredOutputError: review coverage failed"})

        detail={"candidates":candidates,"drafted":drafted,"rejected":rejected,"filtered":filtered,"failures":failures}
        self.repository.finish_run(run_id,"partial" if failures and (drafted or filtered or rejected) else "failed" if failures else "completed",detail)
        return detail

    def run(self) -> dict[str, Any]:
        return {"research":self.research(),"generate":self.generate()}

    def verify_draft(self, draft_id: int, expected_revision: int) -> dict[str, Any]:
        """Re-extract and verify claims after a human edit."""
        draft=self.repository.get_draft(draft_id)
        if not draft:
            raise KeyError(draft_id)
        if draft.revision != expected_revision:
            from .domain import StaleRevisionError
            raise StaleRevisionError("Draft was changed by another request.")
        evidence = self.repository.list_evidence(draft.research_item_id)
        evidence_payload = _evidence_payload(evidence)
        verified_context = tuple(getattr(self.config, "verified_user_context", ()))
        request = ModelRequest(
            "luna_draft_review",
            _prompt("luna_batch_review_v1.md"),
            {
                "candidates": [
                    {
                        "research_item_id": draft.research_item_id,
                        "draft_text": draft.text,
                        "proposed_claims": [],
                        "evidence": evidence_payload,
                    }
                ],
                "verified_user_context": [
                    {"index": index, "fact": fact} for index, fact in enumerate(verified_context)
                ],
            },
            "luna_batch_review",
            _load_schema("luna_batch_review_v1.json"),
            "luna_batch_review_v1",
        )
        run_id = self.repository.create_run("verify_draft")
        try:
            response = self.gateway.run("luna", request)
            self.repository.record_model_call(run_id, "luna", response, "luna_batch_review_v1")
            reviews = list(response.data.get("reviews", []))
            matching = [review for review in reviews if review.get("research_item_id") == draft.research_item_id]
            review = matching[0] if len(matching) == 1 else None
            claims, coverage_supported = guard_review_claims(
                draft.text,
                [],
                list(review.get("claims", [])) if review else [],
                {record["id"]: record["excerpt"] for record in evidence_payload},
                verified_context,
            )
            all_supported = bool(review and review.get("supported")) and coverage_supported and draft_text_valid(draft.text)
            status = VerificationStatus.SUPPORTED.value if all_supported else VerificationStatus.UNSUPPORTED.value
            updated = self.repository.replace_claims_and_verification(draft_id, claims, status, expected_revision)
            detail = {
                "draft_id": draft_id,
                "revision": updated.revision,
                "verification_status": status,
                "claims": len(claims),
            }
            self.repository.finish_run(run_id, "completed", detail)
            return detail
        except Exception as exc:
            self.repository.finish_run(run_id, "failed", {"draft_id": draft_id, "error": _safe_failure(exc)})
            raise
