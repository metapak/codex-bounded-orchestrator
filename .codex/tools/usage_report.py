#!/usr/bin/env python3
"""Report locally observed Codex token deltas without reading prompt content."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

COUNTERS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")


def scalar(obj: dict, *keys: str) -> str:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (str, int)) and str(value):
            return str(value)
    return "unknown"


def token_record(obj: dict) -> dict | None:
    """Return only allowed token-record metadata plus its usage object."""
    if obj.get("type") == "token_usage_record":
        payload = obj.get("payload")
        if isinstance(obj.get("usage"), dict):
            return obj
        if isinstance(payload, dict) and isinstance(payload.get("usage"), dict):
            # Real rollout records keep usage inside payload while the event type
            # stays on the outer object. Copy only accounting/grouping fields;
            # never retain prompt, message, source, or other event content.
            record = {"usage": payload["usage"]}
            for key in ("model", "model_id", "role", "agent_role", "thread_id", "session_id", "conversation_id"):
                value = payload.get(key, obj.get(key))
                if isinstance(value, (str, int)):
                    record[key] = value
            context = payload.get("context")
            if isinstance(context, dict):
                for key in ("model", "model_id", "role", "agent_role", "thread_id", "session_id", "conversation_id"):
                    value = context.get(key)
                    if key not in record and isinstance(value, (str, int)):
                        record[key] = value
            return record
    candidates = [obj]
    for key in ("payload", "event", "data"):
        if isinstance(obj.get(key), dict):
            candidates.append(obj[key])
    for item in candidates:
        if item.get("type") == "token_usage_record" and isinstance(item.get("usage"), dict):
            return item
    return None


def scan(root: Path) -> dict:
    totals = defaultdict(lambda: defaultdict(int))
    files = records = malformed = 0
    for path in sorted(root.rglob("*.jsonl")) if root.exists() else []:
        files += 1
        previous: dict[tuple[str, str, str], dict[str, int]] = {}
        try:
            lines = path.open("r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with lines:
            for line in lines:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    malformed += 1
                    continue
                if not isinstance(obj, dict):
                    continue
                record = token_record(obj)
                if record is None:
                    continue
                usage = record["usage"]
                model = scalar(record, "model", "model_id")
                role = scalar(record, "role", "agent_role")
                thread = scalar(record, "thread_id", "session_id", "conversation_id")
                key = (model, role, thread)
                current = {name: value for name in COUNTERS
                           if isinstance((value := usage.get(name)), int) and value >= 0}
                if not current:
                    continue
                before = previous.get(key, {})
                for name, value in current.items():
                    delta = value - before.get(name, 0)
                    totals[key][name] += delta if delta >= 0 else value
                previous[key] = current
                records += 1
    groups = []
    grand = defaultdict(int)
    for (model, role, thread), usage in sorted(totals.items()):
        for name, value in usage.items():
            grand[name] += value
        groups.append({"model": model, "role": role, "thread": thread, "usage": dict(sorted(usage.items()))})
    return {"status": "available" if records else "unavailable", "source": "local Codex session token_usage_record.usage deltas",
            "files_scanned": files, "records_observed": records, "malformed_lines_skipped": malformed,
            "totals": dict(sorted(grand.items())), "groups": groups,
            "limitations": "Observed local token counters are not quota percentages, billing totals, or cost estimates."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=Path, default=Path.home() / ".codex/sessions")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = scan(args.sessions.expanduser())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Codex local usage report")
        print(f"Status: {report['status']}; records: {report['records_observed']}; files: {report['files_scanned']}")
        for group in report["groups"]:
            values = ", ".join(f"{k}={v}" for k, v in group["usage"].items())
            print(f"- model={group['model']} role={group['role']} thread={group['thread']}: {values}")
        print(report["limitations"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
