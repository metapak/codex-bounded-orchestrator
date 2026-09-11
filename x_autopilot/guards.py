"""Fail-closed evidence and verified-personal-context checks."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


NUMERICAL_SIGNAL = re.compile(
    r"(?:\d|[%$€£₺¥]|\b(?:yüzde|dolar|euro|avro|lira|tl|usd|eur|"
    r"ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\b)",
    re.IGNORECASE,
)
PERSONAL_SIGNAL = re.compile(
    r"\b(?:ben|benim|bana|bende|beni|biz|bizim|bize|bugün|dün|"
    r"\w+(?:dım|dim|dum|düm|tım|tim|tum|tüm|yorum|yoruz|yordum|yorduk|mışım|mişim|muşum|müşüm))\b",
    re.IGNORECASE,
)
FACTUAL_SIGNAL = re.compile(
    r"\b(?:duyurdu|yayınlandı|çıktı|ulaştı|sunuyor|sağlıyor|destekliyor|"
    r"kullanıyor|içeriyor|çalışıyor|mevcut|açık kaynak|ücretsiz|ücretli)\b",
    re.IGNORECASE,
)
EMOJI_SIGNAL = re.compile(
    r"[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]"
)
_WORD = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE)
_STOP_WORDS = {
    "kullanıcı", "kullanicı", "kullanici", "ben", "benim", "bana", "bir", "bu",
    "ve", "ile", "için", "icin", "var", "olan", "olarak", "the", "user",
}


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def claim_key(claim: dict[str, Any]) -> tuple[str, str]:
    return str(claim.get("kind", "")), normalize_text(str(claim.get("text", "")))


def _tokens(value: str) -> set[str]:
    return {word.casefold() for word in _WORD.findall(value) if len(word) > 2 and word.casefold() not in _STOP_WORDS}


def _meaning_overlap(claim_text: str, support_text: str) -> bool:
    claim_tokens = _tokens(claim_text)
    support_tokens = _tokens(support_text)
    if not claim_tokens or not support_tokens:
        return False
    if NUMERICAL_SIGNAL.search(claim_text):
        claim_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", claim_text))
        support_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", support_text))
        if claim_numbers and not claim_numbers.issubset(support_numbers):
            return False
    return bool(claim_tokens & support_tokens)


def obvious_unreviewed_claim(text: str) -> bool:
    return bool(NUMERICAL_SIGNAL.search(text) or PERSONAL_SIGNAL.search(text) or FACTUAL_SIGNAL.search(text))


def draft_text_valid(text: str) -> bool:
    """Enforce X's raw text boundary and the permanent no-emoji policy."""
    return bool(text.strip()) and len(text) <= 280 and not EMOJI_SIGNAL.search(text)


def review_claims(
    draft_text: str,
    proposed: list[dict[str, Any]],
    reviewed: list[dict[str, Any]],
    evidence_excerpts: dict[int, str],
    verified_user_context: tuple[str, ...],
) -> tuple[list[dict[str, Any]], bool]:
    """Merge reviews while preserving proposals and independently checking references."""
    proposed_counts = Counter(claim_key(claim) for claim in proposed)
    reviewed_counts = Counter(claim_key(claim) for claim in reviewed)
    reviewed_by_key = {claim_key(claim): claim for claim in reviewed}
    merged: list[dict[str, Any]] = []
    all_supported = all(count == 1 for count in proposed_counts.values()) and all(
        count == 1 for count in reviewed_counts.values()
    )
    draft_normalized = normalize_text(draft_text)

    ordered: list[tuple[dict[str, Any], bool]] = [(claim, True) for claim in proposed]
    ordered.extend((claim, False) for claim in reviewed if claim_key(claim) not in proposed_counts)
    for source_claim, was_proposed in ordered:
        key = claim_key(source_claim)
        review = reviewed_by_key.get(key)
        claim = {**source_claim, **(review or {})}
        text = str(claim.get("text", ""))
        kind = str(claim.get("kind", ""))
        appears_in_draft = bool(key[1]) and key[1] in draft_normalized
        evidence_ids = list(claim.get("evidence_ids", []))
        context_indices = list(claim.get("verified_context_indices", []))
        references_valid = False
        personal_language = bool(PERSONAL_SIGNAL.search(text))

        if kind in {"factual", "numerical"} and not personal_language:
            evidence_quotes = list(claim.get("evidence_quotes", []))
            quote_by_id = {
                quote.get("evidence_id"): str(quote.get("quote", ""))
                for quote in evidence_quotes
                if isinstance(quote, dict)
            }
            references_valid = bool(evidence_ids) and len(evidence_ids) == len(set(evidence_ids))
            for evidence_id in evidence_ids:
                excerpt = evidence_excerpts.get(evidence_id)
                quote = quote_by_id.get(evidence_id, "")
                references_valid = bool(
                    references_valid
                    and excerpt
                    and quote
                    and normalize_text(quote) in normalize_text(excerpt)
                    and _meaning_overlap(text, quote)
                )
        elif kind == "personal":
            context_quotes = list(claim.get("context_quotes", []))
            quote_by_index = {
                quote.get("context_index"): str(quote.get("quote", ""))
                for quote in context_quotes
                if isinstance(quote, dict)
            }
            references_valid = bool(context_indices) and len(context_indices) == len(set(context_indices))
            for context_index in context_indices:
                valid_index = isinstance(context_index, int) and 0 <= context_index < len(verified_user_context)
                fact = verified_user_context[context_index] if valid_index else ""
                quote = quote_by_index.get(context_index, "")
                references_valid = bool(
                    references_valid
                    and quote
                    and normalize_text(quote) in normalize_text(fact)
                    and normalize_text(text) in normalize_text(quote)
                    and normalize_text(text) in normalize_text(fact)
                )

        duplicate_free = proposed_counts.get(key, 0) <= 1 and reviewed_counts.get(key, 0) == 1
        supported = bool(review and review.get("supported")) and appears_in_draft and references_valid and duplicate_free
        note = str(review.get("note", "")) if review else "Luna review omitted this proposed claim."
        merged.append(
            {
                "text": text,
                "kind": kind or "factual",
                "evidence_ids": evidence_ids,
                "supported": supported,
                "note": note,
            }
        )
        all_supported = all_supported and supported
        if was_proposed and not review:
            all_supported = False

    uncovered = draft_normalized
    reviewed_spans = sorted(
        {claim_key(claim)[1] for claim in reviewed if claim_key(claim)[1] in draft_normalized},
        key=len,
        reverse=True,
    )
    for span in reviewed_spans:
        uncovered = uncovered.replace(span, " ")
    if obvious_unreviewed_claim(uncovered):
        all_supported = False
    return merged, all_supported
