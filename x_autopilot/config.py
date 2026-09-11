"""TOML configuration loading with explicit runtime model routes."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .domain import ConfigurationError


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    reasoning_effort: str = "low"
    max_output_tokens: int = 1800
    timeout_seconds: float = 45.0
    retries: int = 0
    enabled: bool = True


@dataclass(frozen=True)
class AppConfig:
    database_path: Path
    host: str
    port: int
    min_confidence: float
    max_research_items: int
    max_drafts: int
    language: str
    categories: tuple[str, ...]
    routes: dict[str, ModelRoute]
    sources: dict[str, dict[str, Any]]
    verified_user_context: tuple[str, ...] = ()
    database_url_env: str = "DATABASE_URL"
    cloud: bool = False
    public_url: str = ""
    review_username_env: str = "REVIEW_USERNAME"
    review_password_env: str = "REVIEW_PASSWORD"
    timezone: str = "Europe/Istanbul"
    scheduler_enabled: bool = True
    research_interval_seconds: int = 21600
    generation_time: str = "09:00"
    generation_every_days: int = 1
    publish_interval_seconds: int = 60
    scheduler_tick_seconds: int = 15
    publish_enabled: bool = False

    def route(self, role: str) -> ModelRoute:
        try:
            route = self.routes[role]
        except KeyError as exc:
            raise ConfigurationError(f"No model route configured for runtime role {role!r}.") from exc
        if not route.enabled:
            raise ConfigurationError(f"Runtime role {role!r} is disabled.")
        if not route.provider or not route.model:
            raise ConfigurationError(f"Runtime role {role!r} requires provider and model.")
        return route


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    try:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"Cannot load config {config_path}: {exc}") from exc
    app = raw.get("app", {})
    scheduler = raw.get("scheduler", {})
    publishing = raw.get("publishing", {})
    model_raw = raw.get("models", {})
    routes: dict[str, ModelRoute] = {}
    for role in ("luna", "sol", "astra"):
        values = model_raw.get(role)
        if not isinstance(values, dict):
            raise ConfigurationError(f"Missing [models.{role}] configuration.")
        routes[role] = ModelRoute(
            provider=str(values.get("provider", "")),
            model=str(values.get("model", "")),
            reasoning_effort=str(values.get("reasoning_effort", "low")),
            max_output_tokens=int(values.get("max_output_tokens", 1800)),
            timeout_seconds=float(values.get("timeout_seconds", 45)),
            retries=int(values.get("retries", 0)),
            enabled=bool(values.get("enabled", role == "luna")),
        )
    database_path = Path(os.path.expandvars(str(app.get("database_path", "var/x-autopilot.sqlite3"))))
    if not database_path.is_absolute():
        database_path = (config_path.parent.parent / database_path).resolve()
    host = os.environ.get("HOST", str(app.get("host", "127.0.0.1")))
    max_research_items=int(app.get("max_research_items", 20)); max_drafts=int(app.get("max_drafts", 5)); min_confidence=float(app.get("min_confidence", 0.65))
    if max_research_items < 1 or max_drafts < 1:
        raise ConfigurationError("Research and draft limits must be positive.")
    if not 0 <= min_confidence <= 1:
        raise ConfigurationError("min_confidence must be between 0 and 1.")
    if any(route.retries < 0 or route.timeout_seconds <= 0 or route.max_output_tokens < 1 for route in routes.values()):
        raise ConfigurationError("Model retries, timeouts, and output limits are invalid.")
    if routes["sol"].enabled or routes["astra"].enabled:
        raise ConfigurationError("Phase 2 permits Luna runtime only; disable Sol and Astra.")
    luna = routes["luna"]
    if not luna.enabled or (luna.provider == "openai" and luna.model != "gpt-5.6-luna"):
        raise ConfigurationError("The active OpenAI runtime model must be gpt-5.6-luna.")
    zone = str(scheduler.get("timezone", "Europe/Istanbul"))
    try:
        ZoneInfo(zone)
        daily_time = time.fromisoformat(str(scheduler.get("generation_time", "09:00")))
        if daily_time.tzinfo is not None:
            raise ValueError("Use local wall-clock time without an offset.")
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ConfigurationError("Invalid scheduler timezone or generation_time.") from exc
    research_interval = int(scheduler.get("research_interval_seconds", 21600))
    generation_days = int(scheduler.get("generation_every_days", 1))
    publish_interval = int(scheduler.get("publish_interval_seconds", 60))
    tick_seconds = int(scheduler.get("tick_seconds", 15))
    if min(research_interval, generation_days, publish_interval, tick_seconds) < 1:
        raise ConfigurationError("Scheduler frequencies must be positive.")
    public_url = os.environ.get("PUBLIC_URL", str(app.get("public_url", ""))).rstrip("/")
    if public_url:
        parsed = urlsplit(public_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise ConfigurationError("PUBLIC_URL must be an HTTPS origin without credentials or a path.")
    cloud = bool(app.get("cloud", False)) or bool(os.environ.get("RAILWAY_ENVIRONMENT_ID"))
    database_url_env = str(app.get("database_url_env", "DATABASE_URL"))
    if cloud and not os.environ.get(database_url_env):
        raise ConfigurationError("Cloud mode requires DATABASE_URL for PostgreSQL; SQLite is local only.")
    context = app.get("verified_user_context", [])
    if not isinstance(context, list) or any(not isinstance(value, str) for value in context):
        raise ConfigurationError("verified_user_context must be an array of human-verified facts.")
    return AppConfig(
        database_path=database_path,
        host=host,
        port=int(os.environ.get("PORT", app.get("port", 8765))),
        min_confidence=min_confidence,
        max_research_items=max_research_items,
        max_drafts=max_drafts,
        language=str(app.get("language", "tr")),
        categories=tuple(str(value) for value in app.get("categories", [])),
        routes=routes,
        sources={str(k): dict(v) for k, v in raw.get("sources", {}).items()},
        verified_user_context=tuple(context),
        database_url_env=database_url_env,
        cloud=cloud,
        public_url=public_url,
        review_username_env=str(app.get("review_username_env", "REVIEW_USERNAME")),
        review_password_env=str(app.get("review_password_env", "REVIEW_PASSWORD")),
        timezone=zone,
        scheduler_enabled=_environment_bool("SCHEDULER_ENABLED", bool(scheduler.get("enabled", True))),
        research_interval_seconds=research_interval,
        generation_time=daily_time.isoformat(),
        generation_every_days=generation_days,
        publish_interval_seconds=publish_interval,
        scheduler_tick_seconds=tick_seconds,
        publish_enabled=_environment_bool("X_PUBLISH_ENABLED", bool(publishing.get("enabled", False))),
    )


def _environment_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    if value.lower() not in {"true", "false"}:
        raise ConfigurationError(f"{name} must be true or false.")
    return value.lower() == "true"
