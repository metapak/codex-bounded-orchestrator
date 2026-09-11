"""Deterministic normalization and exact deduplication helpers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .domain import RawResearchItem

TRACKING_KEYS = {"fbclid", "gclid", "ref", "source"}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host if port is None or (scheme, port) in {("http", 80), ("https", 443)} else f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted((key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS))
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    return " ".join(value.casefold().split())


def fingerprint(item: RawResearchItem, canonical_url: str) -> str:
    material = "\n".join((canonical_url, normalize_text(item.title), normalize_text(item.excerpt)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
