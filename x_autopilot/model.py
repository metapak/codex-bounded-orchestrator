"""Model gateway plus OpenAI Responses API and deterministic fake providers."""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from typing import Any

from .config import AppConfig
from .costs import LUNA_PRICE_PROVENANCE, estimate_luna_cost_usd
from .domain import ConfigurationError, ProviderError, ProviderUnavailableError, StructuredOutputError
from .ports import ModelProvider, ModelRequest, ModelResponse


LUNA_MODEL = "gpt-5.6-luna"


def _usage_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


class OpenAIResponsesProvider:
    name = "openai"

    def __init__(self, api_key_env: str = "OPENAI_API_KEY", endpoint: str = "https://api.openai.com/v1/responses", opener: Callable[..., Any] | None = None) -> None:
        self.api_key_env = api_key_env
        self.endpoint = endpoint
        self._opener = opener or urllib.request.urlopen

    def generate(self, request: ModelRequest, *, model: str, reasoning_effort: str, max_output_tokens: int, timeout_seconds: float) -> ModelResponse:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise ConfigurationError(f"{self.api_key_env} is required for provider 'openai'.")
        body = {
            "model": model,
            "instructions": request.instructions,
            "input": json.dumps(request.input, ensure_ascii=False),
            "max_output_tokens": max_output_tokens,
            "reasoning": {"effort": reasoning_effort},
            "store": False,
            "text": {"format": {"type": "json_schema", "name": request.schema_name, "strict": True, "schema": request.schema}},
            "metadata": {"purpose": request.purpose, "prompt_version": request.prompt_version},
        }
        encoded = json.dumps(body).encode("utf-8")
        http_request = urllib.request.Request(
            self.endpoint,
            data=encoded,
            method="POST",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "X-Client-Request-Id": str(uuid.uuid4())},
        )
        try:
            with self._opener(http_request, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                if exc.code in {400, 404}:
                    raise ProviderUnavailableError(f"Configured model is unavailable or invalid (HTTP {exc.code}).") from exc
                raise ProviderError(f"OpenAI Responses API request failed (HTTP {exc.code}).") from exc
            finally:
                exc.close()
        except (urllib.error.URLError, socket.timeout, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(f"OpenAI Responses API request failed ({type(exc).__name__}).") from exc
        text = payload.get("output_text")
        if not isinstance(text, str):
            for output in payload.get("output", []):
                for content in output.get("content", []):
                    if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                        text = content["text"]
                        break
        try:
            data = json.loads(text) if isinstance(text, str) else None
        except json.JSONDecodeError as exc:
            raise StructuredOutputError("Provider returned invalid JSON structured output.") from exc
        if not isinstance(data, dict):
            raise StructuredOutputError("Provider response did not contain an object output.")
        usage = payload.get("usage", {})
        usage = usage if isinstance(usage, dict) else {}
        input_details = usage.get("input_tokens_details", {})
        input_details = input_details if isinstance(input_details, dict) else {}
        input_tokens = _usage_int(usage.get("input_tokens"))
        output_tokens = _usage_int(usage.get("output_tokens"))
        cached_input_tokens = _usage_int(input_details.get("cached_tokens"))
        cache_write_tokens = _usage_int(input_details.get("cache_write_tokens"))
        estimated_cost = None
        cost_provenance = None
        if model == LUNA_MODEL:
            estimated_cost = estimate_luna_cost_usd(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_input_tokens=cached_input_tokens,
                cache_write_tokens=cache_write_tokens,
            )
            cost_provenance = LUNA_PRICE_PROVENANCE if estimated_cost is not None else None
        return ModelResponse(
            data=data,
            provider=self.name,
            model=model,
            response_id=payload.get("id") if isinstance(payload.get("id"), str) else None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_tokens=cache_write_tokens,
            estimated_cost_usd=estimated_cost,
            cost_provenance=cost_provenance,
        )


class FakeModelProvider:
    """Credential-free provider with overridable purpose handlers."""

    name = "fake"

    def __init__(self, handlers: dict[str, Callable[[ModelRequest], dict[str, Any]] | dict[str, Any]] | None = None) -> None:
        self.handlers = handlers or {}
        self.calls: list[tuple[str, str]] = []

    def generate(self, request: ModelRequest, *, model: str, reasoning_effort: str, max_output_tokens: int, timeout_seconds: float) -> ModelResponse:
        self.calls.append((request.purpose, model))
        handler = self.handlers.get(request.purpose)
        if callable(handler):
            data = handler(request)
        elif isinstance(handler, dict):
            data = handler
        elif request.purpose == "luna_batch_generate":
            data = {
                "candidates": [
                    {
                        "research_item_id": item["research_item_id"],
                        "accepted": True,
                        "summary": item["title"],
                        "category": "developer_observation",
                        "confidence": 0.85,
                        "noise": False,
                        "near_duplicate_key": None,
                        "draft_text": "küçük bir değişiklik bazen bütün öğleden sonrayı yiyor.",
                        "factual_risk": "low",
                        "hook_type": "observation",
                        "post_structure": "standalone",
                        "claims": [],
                        "rejection_reason": None,
                    }
                    for item in request.input.get("items", [])
                ]
            }
        elif request.purpose in {"luna_batch_review", "luna_draft_review"}:
            data = {
                "reviews": [
                    {
                        "research_item_id": candidate["research_item_id"],
                        "supported": True,
                        "claims": [],
                    }
                    for candidate in request.input.get("candidates", [])
                ]
            }
        else:
            raise ProviderError(f"Fake provider has no handler for purpose {request.purpose!r}.")
        return ModelResponse(data=data, provider=self.name, model=model, response_id=f"fake-{len(self.calls)}", input_tokens=0, output_tokens=0)


class ModelGateway:
    def __init__(self, config: AppConfig, providers: dict[str, ModelProvider]) -> None:
        self.config = config
        self.providers = providers

    def run(self, role: str, request: ModelRequest) -> ModelResponse:
        if role != "luna":
            raise ConfigurationError("Normal X Autopilot runtime permits only the Luna role.")
        route = self.config.route(role)
        try:
            provider = self.providers[route.provider]
        except KeyError as exc:
            raise ConfigurationError(f"Provider {route.provider!r} for runtime role {role!r} is not registered.") from exc
        if (route.provider == "openai" or getattr(provider, "name", None) == "openai") and route.model != LUNA_MODEL:
            raise ConfigurationError(f"OpenAI X Autopilot runtime requires model {LUNA_MODEL!r}.")
        attempts = route.retries + 1
        last_error: ProviderError | None = None
        for attempt in range(attempts):
            try:
                response = provider.generate(request, model=route.model, reasoning_effort=route.reasoning_effort, max_output_tokens=route.max_output_tokens, timeout_seconds=route.timeout_seconds)
                validate_structured_output(response.data, request.schema)
                return response
            except ProviderUnavailableError:
                raise
            except ProviderError as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(min(0.25 * (2**attempt), 1.0))
        assert last_error is not None
        raise last_error


def validate_structured_output(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Validate the JSON Schema subset used by versioned runtime outputs."""
    expected=schema.get("type")
    allowed=expected if isinstance(expected,list) else [expected] if expected else []
    matches = (
        (value is None and "null" in allowed)
        or (isinstance(value,bool) and "boolean" in allowed)
        or (isinstance(value,int) and not isinstance(value,bool) and "integer" in allowed)
        or (isinstance(value,(int,float)) and not isinstance(value,bool) and "number" in allowed)
        or (isinstance(value,str) and "string" in allowed)
        or (isinstance(value,list) and "array" in allowed)
        or (isinstance(value,dict) and "object" in allowed)
    )
    if allowed and not matches:
        raise StructuredOutputError(f"Structured output {path} has the wrong type; expected {allowed}.")
    if "enum" in schema and value not in schema["enum"]:
        raise StructuredOutputError(f"Structured output {path} is not an allowed value.")
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if "minimum" in schema and value < schema["minimum"]: raise StructuredOutputError(f"Structured output {path} is below minimum.")
        if "maximum" in schema and value > schema["maximum"]: raise StructuredOutputError(f"Structured output {path} is above maximum.")
    if isinstance(value,dict):
        for name in schema.get("required",[]):
            if name not in value: raise StructuredOutputError(f"Structured output {path} is missing {name!r}.")
        if schema.get("additionalProperties") is False:
            extra=set(value)-set(schema.get("properties",{}))
            if extra: raise StructuredOutputError(f"Structured output {path} has unexpected fields: {sorted(extra)}.")
        for name,child in value.items():
            if name in schema.get("properties",{}): validate_structured_output(child,schema["properties"][name],f"{path}.{name}")
    if isinstance(value,list) and "items" in schema:
        for index,child in enumerate(value): validate_structured_output(child,schema["items"],f"{path}[{index}]")
