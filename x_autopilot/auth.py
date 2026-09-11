"""Small HTTP Basic authentication helpers for the review server."""

from __future__ import annotations

import base64
import binascii
import hmac
import ipaddress
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ReviewAuth:
    username: str
    password: str = field(repr=False)

    def matches(self, authorization: str | None) -> bool:
        username, password = _decode_basic(authorization)
        username_matches = hmac.compare_digest(username.encode("utf-8"), self.username.encode("utf-8"))
        password_matches = hmac.compare_digest(password.encode("utf-8"), self.password.encode("utf-8"))
        return username_matches and password_matches


def is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def load_review_auth(host: str, config: object | None) -> tuple[ReviewAuth | None, bool, str | None]:
    """Return auth, secure-cookie flag, and the configured public origin."""
    if is_loopback_host(host):
        public_url = str(getattr(config, "public_url", "") or "")
        return None, public_url.lower().startswith("https://"), _origin(public_url) if public_url else None

    if config is None:
        raise ValueError("Uzak review sunucusu için yapılandırma gereklidir.")
    public_url = str(getattr(config, "public_url", "") or "").strip()
    parsed = urlsplit(public_url)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("Uzak review sunucusu için HTTPS public_url gereklidir.")
    username_env = str(getattr(config, "review_username_env", "REVIEW_USERNAME") or "")
    password_env = str(getattr(config, "review_password_env", "REVIEW_PASSWORD") or "")
    if not username_env or not password_env:
        raise ValueError("Review kimlik bilgisi ortam değişkenleri yapılandırılmalıdır.")
    username = os.environ.get(username_env, "")
    password = os.environ.get(password_env, "")
    if not username or ":" in username or len(password) < 20:
        raise ValueError("Uzak review sunucusu için kullanıcı adı ve en az 20 karakterli parola gereklidir.")
    return ReviewAuth(username, password), True, _origin(public_url)


def _decode_basic(authorization: str | None) -> tuple[str, str]:
    if not authorization:
        return "", ""
    scheme, separator, encoded = authorization.partition(" ")
    if separator != " " or scheme.lower() != "basic" or not encoded or " " in encoded:
        return "", ""
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return "", ""
    username, separator, password = decoded.partition(":")
    if separator != ":":
        return "", ""
    return username, password


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("public_url geçerli bir mutlak URL olmalıdır.")
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    default_port = (parsed.scheme.lower() == "https" and port == 443) or (parsed.scheme.lower() == "http" and port == 80)
    authority = host if port is None or default_port else f"{host}:{port}"
    return f"{parsed.scheme.lower()}://{authority.lower()}"
