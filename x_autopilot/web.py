"""Authenticated, mobile-friendly review UI built with the standard library."""

from __future__ import annotations

import hmac
import html
import json
import secrets
import urllib.parse
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from .auth import load_review_auth
from .domain import XAutopilotError
from .ports import Repository
from .review import ReviewService

_MAX_BODY_BYTES = 64 * 1024
_IMMUTABLE_STATES = {"publishing", "published", "publish_failed", "publish_unknown"}


def _page(title: str, body: str) -> bytes:
    document = f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
:root{{color-scheme:light;font-family:system-ui,-apple-system,sans-serif}}*{{box-sizing:border-box}}body{{max-width:980px;margin:0 auto;padding:1rem;color:#202124;background:#f7f7f8}}nav{{display:flex;gap:1rem;position:sticky;top:0;padding:.8rem 0;background:#f7f7f8}}nav a{{font-weight:650}}article,.panel{{border:1px solid #d8d8dc;border-radius:12px;padding:1rem;margin:1rem 0;background:white}}textarea,input{{width:100%;font:inherit;padding:.75rem;border:1px solid #aaa;border-radius:8px}}textarea{{min-height:180px;resize:vertical}}button{{margin:.5rem .4rem .25rem 0;padding:.7rem 1rem;border:0;border-radius:8px;background:#1a56db;color:white;font-weight:650}}button.danger{{background:#a52a2a}}.risk,.error{{color:#8a3b12;font-weight:600}}.muted,small{{color:#5f6368}}code,.wrap,.draft-text{{overflow-wrap:anywhere}}.draft-text{{white-space:pre-wrap}}dl{{display:grid;grid-template-columns:max-content 1fr;gap:.35rem 1rem}}dt{{font-weight:650}}dd{{margin:0}}@media(max-width:600px){{body{{padding:.75rem}}h1{{font-size:1.55rem}}article,.panel{{padding:.85rem}}dl{{display:block}}dd{{margin:0 0 .6rem}}button{{width:100%;margin:.35rem 0}}}}
</style></head><body><nav><a href="/">Araştırma</a><a href="/drafts">Draft'lar</a></nav><main><h1>{html.escape(title)}</h1>{body}</main></body></html>"""
    return document.encode("utf-8")


def _safe_url(url: str) -> str | None:
    if any(ord(char) < 32 for char in url):
        return None
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        return None
    return html.escape(url, quote=True)


def _status_value(draft: object) -> str:
    status = getattr(draft, "status", "")
    return str(getattr(status, "value", status))


def _field(draft: object, name: str) -> Any:
    return getattr(draft, name, None)


def _model_calls(repository: Repository) -> str:
    list_calls = getattr(repository, "list_model_calls", None)
    if not callable(list_calls):
        return ""
    calls = list_calls(run_id=None)
    if not calls:
        return ""
    rows: list[str] = []
    total_input = total_output = 0
    total_cost = 0.0
    has_cost = False
    for call in calls:
        value = dict(call) if not isinstance(call, dict) else call
        input_tokens = int(value.get("input_tokens") or 0)
        output_tokens = int(value.get("output_tokens") or 0)
        total_input += input_tokens
        total_output += output_tokens
        cost = value.get("cost_usd", value.get("estimated_cost_usd"))
        if cost is not None:
            total_cost += float(cost)
            has_cost = True
        label = " / ".join(html.escape(str(value.get(key) or "-")) for key in ("role", "provider", "model", "prompt_version"))
        rows.append(f"<li>{label} · {input_tokens:,} giriş / {output_tokens:,} çıkış token</li>")
    cost_text = f" · Tahmini maliyet ${total_cost:.4f}" if has_cost else ""
    return f'<section class="panel"><h2>Model çağrıları</h2><p>{total_input:,} giriş / {total_output:,} çıkış token{cost_text}</p><ul>{"".join(rows)}</ul></section>'


def make_handler(
    repository: Repository,
    csrf_token: str,
    *,
    auth: object | None = None,
    secure_cookie: bool = False,
    public_origin: str | None = None,
    publisher: object | None = None,
    verify_callback: Callable[[int, int], dict[str, Any]] | None = None,
    readiness: Callable[[], object] | None = None,
    timezone_name: str = "Europe/Istanbul",
):
    review = ReviewService(repository, publisher)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def _security_headers(self) -> None:
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Cache-Control", "no-store")

        def _send(self, body: bytes, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._security_headers()
            cookie = f"xap_csrf={csrf_token}; Path=/; HttpOnly; SameSite=Strict"
            if secure_cookie:
                cookie += "; Secure"
            self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(body)

        def _status(self, status: int, ready: bool) -> None:
            body = json.dumps({"status": "ok" if ready else "unavailable"}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(body)

        def _authenticated(self) -> bool:
            if auth is None or auth.matches(self.headers.get("Authorization")):
                return True
            body = _page("Kimlik doğrulama gerekli", "<p>Bu sayfayı açmak için geçerli review kimlik bilgileri gereklidir.</p>")
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", 'Basic realm="X Autopilot Review", charset="UTF-8"')
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._security_headers()
            self.end_headers()
            self.wfile.write(body)
            return False

        def _redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
            self._security_headers()
            self.end_headers()

        def _unavailable(self) -> None:
            try:
                self._send(_page("Hizmet kullanılamıyor", "<p>Hizmet geçici olarak kullanılamıyor.</p>"), 503)
            except OSError:
                pass

        def do_GET(self) -> None:
            try:
                self._handle_get()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self._unavailable()

        def _handle_get(self) -> None:
            path = urllib.parse.urlsplit(self.path).path
            if path == "/health":
                self._status(200, True)
                return
            if path == "/ready":
                try:
                    result = True if readiness is None else readiness()
                    ready = bool(result.get("ready", False)) if isinstance(result, dict) else bool(result)
                except Exception:
                    ready = False
                self._status(200 if ready else 503, ready)
                return
            if not self._authenticated():
                return
            if path == "/":
                cards = []
                for item in repository.list_research():
                    cards.append(f'<article><h2><a href="/research/{item.id}">{html.escape(item.title)}</a></h2><p>{html.escape(item.summary or item.excerpt)}</p><small>{html.escape(item.source)} · {html.escape(item.status)}</small></article>')
                self._send(_page("Keşfedilen konular", "".join(cards) or "<p>Henüz araştırma kaydı yok.</p>"))
                return
            if path == "/drafts":
                cards = []
                for draft in repository.list_drafts():
                    cards.append(f'<article><h2><a href="/draft/{draft.id}">Draft #{draft.id}</a></h2><p>{html.escape(draft.text)}</p><small>{html.escape(_status_value(draft))} · evidence: {html.escape(draft.verification_status.value)}</small></article>')
                self._send(_page("Üretilen draft'lar", "".join(cards) or "<p>Henüz draft yok.</p>"))
                return
            if path.startswith("/research/"):
                try:
                    item = repository.get_research(int(path.rsplit("/", 1)[1]))
                except ValueError:
                    item = None
                if not item:
                    self._send(_page("Bulunamadı", "<p>Araştırma kaydı bulunamadı.</p>"), 404)
                    return
                evidence = repository.list_evidence(item.id)
                claims = repository.list_research_claims(item.id)
                source_url = _safe_url(item.canonical_url)
                source = f'<a rel="noreferrer" href="{source_url}">Kaynağı aç</a>' if source_url else "Güvenli kaynak bağlantısı yok."
                parts = [f"<p>{html.escape(item.summary or item.excerpt)}</p><p>{source}</p>"]
                if claims:
                    parts.append("<h2>Çıkarılan claim'ler</h2><ul>" + "".join(f'<li>{html.escape(c["text"])} ({html.escape(c["kind"])})</li>' for c in claims) + "</ul>")
                for evidence_item in evidence:
                    safe = _safe_url(evidence_item.source_url)
                    link = f'<a rel="noreferrer" href="{safe}">Evidence kaynağı</a>' if safe else "Güvenli bağlantı yok"
                    parts.append(f'<article>{link}<p>{html.escape(evidence_item.excerpt)}</p><small class="wrap">sha256: {html.escape(evidence_item.content_hash)}</small></article>')
                self._send(_page(item.title, "".join(parts)))
                return
            if path.startswith("/draft/"):
                try:
                    draft = repository.get_draft(int(path.rsplit("/", 1)[1]))
                except ValueError:
                    draft = None
                if not draft:
                    self._send(_page("Bulunamadı", "<p>Draft bulunamadı.</p>"), 404)
                    return
                item = repository.get_research(draft.research_item_id)
                evidence = repository.list_evidence(draft.research_item_id)
                claims = repository.list_claims(draft.id)
                hidden = f'<input type="hidden" name="csrf" value="{html.escape(csrf_token, quote=True)}"><input type="hidden" name="revision" value="{draft.revision}">'
                claim_html = "".join(f'<li>{html.escape(c["text"])} — {"destekli" if c["supported"] else "desteksiz"}; evidence {html.escape(str(c["evidence_ids"]))}</li>' for c in claims)
                evidence_parts = []
                for evidence_item in evidence:
                    safe = _safe_url(evidence_item.source_url)
                    link = f'<a rel="noreferrer" href="{safe}">Kaynak</a>' if safe else "<span>Güvenli bağlantı yok</span>"
                    evidence_parts.append(f'<article>{link}<p>{html.escape(evidence_item.excerpt)}</p></article>')
                verification = draft.verification_status.value
                warning = '<p class="risk">Bu draft evidence doğrulamasından geçmeden onaylanamaz.</p>' if verification != "supported" else ""
                status = _status_value(draft)
                attempted = status in _IMMUTABLE_STATES or bool(_field(draft, "publish_attempted_at"))
                actions: list[str] = []
                if not attempted:
                    actions.append(f'<form method="post" action="/draft/{draft.id}/edit">{hidden}<label for="draft-text">Draft metni</label><textarea id="draft-text" name="text">{html.escape(draft.text)}</textarea><button>Kaydet</button></form>')
                    if verification != "supported" and verify_callback is not None:
                        actions.append(f'<form method="post" action="/draft/{draft.id}/verify">{hidden}<button>Yeniden doğrula</button></form>')
                    if status == "pending":
                        actions.append(f'<form method="post" action="/draft/{draft.id}/approve">{hidden}<button>Onayla</button></form>')
                    if status not in {"rejected", "published"}:
                        actions.append(f'<form method="post" action="/draft/{draft.id}/reject">{hidden}<input name="reason" aria-label="Red nedeni" placeholder="Red nedeni"><button class="danger">Reddet</button></form>')
                    if status == "approved":
                        actions.append(f'<form method="post" action="/draft/{draft.id}/schedule">{hidden}<label for="scheduled-at">Yayın zamanı ({html.escape(timezone_name)})</label><input id="scheduled-at" type="datetime-local" name="scheduled_at" required><button>Zamanla</button></form>')
                        if publisher is not None:
                            actions.append(f'<form method="post" action="/draft/{draft.id}/publish">{hidden}<button>Şimdi yayınla</button></form>')
                else:
                    actions.append(f'<section class="panel"><h2>Draft metni</h2><p class="draft-text">{html.escape(draft.text)}</p></section>')
                publish_error = _field(draft, "publish_error")
                if publish_error:
                    actions.append(f'<p class="error">Yayın sonucu: {html.escape(str(publish_error))}</p>')
                details = [
                    ("Durum", status), ("Evidence", verification), ("Güven", f"{draft.confidence:.2f}"),
                    ("Risk", draft.factual_risk), ("Sağlayıcı", draft.provider), ("Model", draft.model), ("Prompt", draft.prompt_version),
                    ("Zamanlandı", _field(draft, "scheduled_at")), ("Yayın denemesi", _field(draft, "publish_attempted_at")),
                    ("Yayınlandı", _field(draft, "published_at")),
                ]
                detail_html = "".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(str(value))}</dd>" for label, value in details if value is not None)
                post_id = str(_field(draft, "x_post_id") or "")
                if post_id:
                    escaped_post_id = html.escape(post_id)
                    post_value = f'<a rel="noreferrer" href="https://x.com/i/web/status/{escaped_post_id}">{escaped_post_id}</a>' if post_id.isascii() and post_id.isdigit() else escaped_post_id
                    detail_html += f"<dt>X post ID</dt><dd>{post_value}</dd>"
                body = f'<section class="panel"><dl>{detail_html}</dl>{warning}</section>{"".join(actions)}<h2>Claim’ler</h2><ul>{claim_html}</ul><h2>Evidence</h2>{"".join(evidence_parts)}<h2>Araştırma</h2><p>{html.escape(item.title if item else "")}</p>{_model_calls(repository)}'
                self._send(_page(f"Draft #{draft.id}", body))
                return
            self._send(_page("Bulunamadı", "<p>Sayfa bulunamadı.</p>"), 404)

        def do_POST(self) -> None:
            try:
                self._handle_post()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self._unavailable()

        def _handle_post(self) -> None:
            if not self._authenticated():
                return
            if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site" or not self._same_origin():
                self._send(_page("İstek reddedildi", "<p>Çapraz kaynak isteği reddedildi.</p>"), 403)
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                length = -1
            if length < 0:
                self._send(_page("İstek reddedildi", "<p>Geçerli Content-Length gereklidir.</p>"), 400)
                return
            if length > _MAX_BODY_BYTES:
                self._send(_page("İstek reddedildi", "<p>İstek gövdesi çok büyük.</p>"), 413)
                return
            raw = self.rfile.read(length)
            try:
                data = urllib.parse.parse_qs(raw.decode("utf-8"), keep_blank_values=True, strict_parsing=False, max_num_fields=100)
            except (UnicodeDecodeError, ValueError):
                self._send(_page("İstek reddedildi", "<p>İstek kodlaması geçersiz.</p>"), 400)
                return
            if not self._valid_csrf(data):
                self._send(_page("İstek reddedildi", "<p>CSRF doğrulaması başarısız.</p>"), 403)
                return
            parts = urllib.parse.urlsplit(self.path).path.strip("/").split("/")
            try:
                if len(parts) != 3 or parts[0] != "draft":
                    raise ValueError("Geçersiz route.")
                draft_id = int(parts[1])
                action = parts[2]
                revision = int(data.get("revision", ["0"])[0])
                if action == "edit":
                    review.edit(draft_id, data.get("text", [""])[0], revision)
                elif action == "approve":
                    review.approve(draft_id, revision)
                elif action == "reject":
                    review.reject(draft_id, revision, data.get("reason", [None])[0])
                elif action == "schedule":
                    review.schedule(draft_id, data.get("scheduled_at", [""])[0], revision, timezone_name)
                elif action == "publish":
                    review.publish_now(draft_id, revision)
                elif action == "verify" and verify_callback is not None:
                    verify_callback(draft_id, revision)
                else:
                    raise ValueError("Geçersiz işlem.")
            except (ValueError, KeyError, XAutopilotError) as exc:
                self._send(_page("İşlem başarısız", f"<p>{html.escape(str(exc))}</p>"), 409)
                return
            self._redirect(f"/draft/{draft_id}")

        def _same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            try:
                parsed = urllib.parse.urlsplit(origin)
                host = parsed.hostname or ""
                if ":" in host:
                    host = f"[{host}]"
                port = parsed.port
            except ValueError:
                return False
            default_port = (parsed.scheme.lower() == "https" and port == 443) or (parsed.scheme.lower() == "http" and port == 80)
            authority = host if port is None or default_port else f"{host}:{port}"
            request_origin = f"{parsed.scheme.lower()}://{authority.lower()}" if parsed.scheme and authority else ""
            expected = public_origin
            if expected is None:
                expected = f"http://{self.headers.get('Host', '').lower()}"
            return bool(request_origin) and hmac.compare_digest(request_origin, expected)

        def _valid_csrf(self, data: dict[str, list[str]]) -> bool:
            form_token = data.get("csrf", [""])[0]
            cookie_header = self.headers.get("Cookie", "")
            try:
                cookie = SimpleCookie()
                cookie.load(cookie_header)
                morsel = cookie.get("xap_csrf")
                cookie_token = morsel.value if morsel is not None else ""
            except Exception:
                cookie_token = ""
            return hmac.compare_digest(form_token, csrf_token) and hmac.compare_digest(cookie_token, csrf_token)

    return Handler


def create_server(
    repository: Repository,
    host: str,
    port: int,
    csrf_token: str | None = None,
    *,
    config: object | None = None,
    publisher: object | None = None,
    verify_callback: Callable[[int, int], dict[str, Any]] | None = None,
    readiness: Callable[[], object] | None = None,
) -> ThreadingHTTPServer:
    auth, secure_cookie, public_origin = load_review_auth(host, config)
    timezone_name = str(getattr(config, "timezone", "Europe/Istanbul") or "Europe/Istanbul")
    handler = make_handler(
        repository,
        csrf_token or secrets.token_urlsafe(32),
        auth=auth,
        secure_cookie=secure_cookie,
        public_origin=public_origin,
        publisher=publisher,
        verify_callback=verify_callback,
        readiness=readiness,
        timezone_name=timezone_name,
    )
    return ThreadingHTTPServer((host, port), handler)
