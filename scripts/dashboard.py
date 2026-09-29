#!/usr/bin/env python3
"""Repository configuration console, served only on loopback (Python 3.11+)."""
from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.util
import json
import re
import secrets
import sys
import threading
import tomllib
import webbrowser
from collections import defaultdict
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import install as installer
import model_catalog

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent / 'console'
STATE = Path('.codex/.bounded-orchestrator/console-restore.json')
HISTORY = Path('.codex/.bounded-orchestrator/console-style-history.json')
SAFE_PATHS = sorted(installer.ALLOWED_MANIFEST_FILES | {Path('AGENTS.md'), installer.MANIFEST_RELATIVE}, key=str)
EFFORTS = installer.EFFORTS
TEAM_SLOTS = installer.TEAM_SLOT_FILES

def load_usage():
    spec = importlib.util.spec_from_file_location('console_usage', ROOT/'.codex/tools/usage_report.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

usage = load_usage()

def contents(path):
    return path.read_bytes() if path.exists() else None

def digest(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None

def instant(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.timestamp() if parsed.tzinfo else None
    except ValueError:
        return None

def usage_breakdowns(report, history, project):
    """Group observed totals; style is an explicitly labelled timeline estimate."""
    models, styles = defaultdict(int), defaultdict(int)
    events = sorted(((instant(event.get('at')), event) for event in history if isinstance(event, dict)), key=lambda row: row[0] if row[0] is not None else -1)
    events = [(when, event) for when, event in events if when is not None]
    for record in report['records']:
        amount = record['usage'].get('total_tokens', 0)
        if type(amount) is not int or amount < 0:
            continue
        model = record['model'] if record['model'] != 'unknown' else 'unknown'
        models[model] += amount
        style = 'unknown'
        start, end = instant(record.get('turn_start')), instant(record.get('turn_end'))
        same_project = record['project'] != 'unknown' and Path(record['project']).resolve() == Path(project).resolve()
        if start is not None and end is not None and end >= start and same_project:
            earlier = [(index, event) for index, (when, event) in enumerate(events) if when < start]
            if earlier:
                index, event = earlier[-1]
                next_at = events[index + 1][0] if index + 1 < len(events) else None
                if event.get('action') == 'save' and (next_at is None or end < next_at):
                    style = event.get('preset', 'unknown')
        styles[style] += amount
    def rows(values):
        return [{'id': key, 'total_tokens': value} for key, value in sorted(values.items(), key=lambda pair: (-pair[1], pair[0]))]
    return {'model': {'basis': 'observed_turn_context', 'rows': rows(models)},
            'style': {'basis': 'estimated_from_console_save_history', 'rows': rows(styles)},
            'total_tokens': report['totals'].get('total_tokens', 0)}

def orchestra_view(report, selected_root='', filters=None):
    """Attribute each observed record once through explicit session identities."""
    nodes = {item['id']: item for item in report.get('agents', []) if isinstance(item, dict) and isinstance(item.get('id'), str)}
    filters = filters or {}
    def metadata_visible(node):
        stamp = node.get('observed_at', 'unknown')
        day = stamp[:10] if stamp != 'unknown' else ''
        if (filters.get('date_from') and (not day or day < filters['date_from'])) or (filters.get('date_to') and (not day or day > filters['date_to'])):
            return False
        if filters.get('project') and node.get('project') != filters['project']:
            return False
        if filters.get('thread') and node.get('id') != filters['thread']:
            return False
        return True
    def root_of(agent_id):
        seen = set()
        current = agent_id
        while current in nodes and current not in seen:
            seen.add(current)
            node = nodes[current]
            if node.get('ambiguous'):
                return None
            parent = node.get('parent')
            if not parent:
                return current if node.get('source') == 'root' else None
            if node.get('source') != 'subagent':
                return None
            current = parent
        return None
    def family(record):
        root = root_of(record['thread'])
        linked = record.get('session_id')
        if root and linked not in (None, '', 'unknown', root):
            return None
        if root:
            return root
        return linked if linked in nodes and root_of(linked) == linked else None
    roots = {}
    for record in report['records']:
        root = family(record)
        if root:
            item = roots.setdefault(root, {'id': root, 'project': nodes[root].get('project', 'unknown'), 'last_seen': '', 'total_tokens': 0})
            item['last_seen'] = max(item['last_seen'], record['timestamp'] if record['timestamp'] != 'unknown' else '')
            item['total_tokens'] += record['usage'].get('total_tokens', 0)
    for agent_id in nodes:
        root = root_of(agent_id)
        if root:
            roots.setdefault(root, {'id': root, 'project': nodes[root].get('project', 'unknown'), 'last_seen': '', 'total_tokens': 0})
    scopes = sorted(roots.values(), key=lambda item: (item['last_seen'], item['id']), reverse=True)
    if selected_root and (selected_root not in nodes or root_of(selected_root) != selected_root):
        raise ValueError('Unknown work selection')
    chosen = [record for record in report['records'] if not selected_root or family(record) == selected_root]
    actors = {}
    unassigned = 0
    for record in chosen:
        amount = record['usage'].get('total_tokens', 0)
        actor_id = record['thread']
        node = nodes.get(actor_id)
        if not node or root_of(actor_id) != family(record):
            unassigned += amount
            continue
        actor = actors.setdefault(actor_id, {'id': actor_id, 'name': node.get('name') or '', 'role': node.get('role') or '',
                                             'kind': 'conductor' if actor_id == family(record) else 'helper',
                                             'source': 'session_meta', 'total_tokens': 0, 'input_tokens': 0,
                                             'cached_input_tokens': 0, 'output_tokens': 0, 'models': {}, 'efforts': {}, 'model_efforts': {}})
        actor['total_tokens'] += amount
        for key in ('input_tokens', 'cached_input_tokens', 'output_tokens'):
            actor[key] += record['usage'].get(key, 0)
        model = record['model']
        actor['models'][model] = actor['models'].get(model, 0) + amount
        effort = record.get('effort', 'unknown')
        actor['efforts'][effort] = actor['efforts'].get(effort, 0) + amount
        pair = (model, effort)
        actor['model_efforts'][pair] = actor['model_efforts'].get(pair, 0) + amount
    if selected_root:
        for agent_id, node in nodes.items():
            if root_of(agent_id) != selected_root or agent_id in actors or (agent_id != selected_root and not metadata_visible(node)):
                continue
            actors[agent_id] = {'id': agent_id, 'name': node.get('name') or '', 'role': node.get('role') or '',
                                'kind': 'conductor' if agent_id == selected_root else 'helper', 'source': 'session_meta',
                                'total_tokens': None, 'input_tokens': None, 'cached_input_tokens': None,
                                'output_tokens': None, 'models': {}, 'efforts': {}, 'model_efforts': {}, 'usage_observed': False}
    actor_rows = []
    for actor in actors.values():
        actor['models'] = [{'id': model, 'total_tokens': tokens} for model, tokens in sorted(actor['models'].items(), key=lambda item: (-item[1], item[0]))]
        actor['efforts'] = [{'id': effort, 'total_tokens': tokens} for effort, tokens in sorted(actor['efforts'].items(), key=lambda item: (-item[1], item[0]))]
        actor['model_efforts'] = [{'model': model, 'effort': effort, 'total_tokens': tokens} for (model, effort), tokens in sorted(actor['model_efforts'].items(), key=lambda item: (-item[1], item[0]))]
        actor_rows.append(actor)
    actor_rows.sort(key=lambda item: (item['kind'] != 'conductor', -(item['total_tokens'] or 0), item['id']))
    total = sum(record['usage'].get('total_tokens', 0) for record in chosen)
    conductor = sum(item['total_tokens'] or 0 for item in actor_rows if item['kind'] == 'conductor')
    helpers = sum(item['total_tokens'] or 0 for item in actor_rows if item['kind'] == 'helper')
    return {'scopes': scopes, 'selected_root': selected_root or None, 'actors': actor_rows, '_records': chosen,
            'total_tokens': total, 'conductor_tokens': conductor, 'helper_tokens': helpers,
            'unassigned_tokens': unassigned, 'helper_count': sum(item['kind'] == 'helper' for item in actor_rows),
            'basis': 'session_meta_id_parent_thread_id_and_request_thread_id'}

def filter_report_records(report, records):
    report['records'] = records
    report['records_observed'] = len(records)
    report['status'] = 'available' if records else 'unavailable'
    grouped, grand = defaultdict(lambda: defaultdict(int)), defaultdict(int)
    for record in records:
        key = tuple(record[name] for name in ('model', 'role', 'thread', 'project'))
        for name, value in record['usage'].items():
            grouped[key][name] += value
            grand[name] += value
    report['groups'] = [dict(zip(('model', 'role', 'thread', 'project'), key), usage=dict(usage)) for key, usage in sorted(grouped.items())]
    report['totals'] = dict(grand)
    return report

def visible_lines(text):
    """Locate structural lines outside multiline strings."""
    lines = []
    offset = 0
    multiline = None
    for line in text.splitlines(keepends=True):
        if multiline is None:
            lines.append((offset, offset + len(line), line))
        i = 0
        quote = None
        while i < len(line):
            if multiline:
                if line.startswith(multiline, i):
                    i += 3
                    multiline = None
                elif multiline == '"""' and line[i] == '\\':
                    i += 2
                else:
                    i += 1
            elif quote:
                if quote == '"' and line[i] == '\\':
                    i += 2
                elif line[i] == quote:
                    quote = None
                    i += 1
                else:
                    i += 1
            elif line[i] == '#':
                break
            elif line.startswith('"""', i) or line.startswith("'" * 3, i):
                multiline = line[i:i+3]
                i += 3
            elif line[i] in ('"', "'"):
                quote = line[i]
                i += 1
            else:
                i += 1
        offset += len(line)
    return lines

def table_headers(text):
    """Find both regular and array-table boundaries outside strings."""
    headers = []
    for start, end, line in visible_lines(text):
        match = re.fullmatch(r'\s*(\[\[?)(.+?)(\]\]?)\s*(?:#.*)?(?:\n)?', line)
        if match and len(match[1]) == len(match[3]):
            headers.append((start, end - len(line) + len(line.rstrip('\r\n')), match[2], len(match[1]) == 2))
    return headers

def patch_values(text, section, values):
    """Edit only named assignments in one TOML section, retaining other bytes."""
    newline = '\r\n' if '\r\n' in text and '\n' not in text.replace('\r\n', '') else '\n'
    headers = table_headers(text)
    if section:
        header = next((h for h in headers if h[2] == section and not h[3]), None)
        if header is None:
            separator = '' if not text or text.endswith(('\n', '\r')) else newline
            return text + separator + newline + '['+section+']'+newline + ''.join(k+' = '+json.dumps(v)+newline for k,v in values.items())
        start = header[1]
        end = next((h[0] for h in headers if h[0] > header[0]), len(text))
    else:
        start, end = 0, headers[0][0] if headers else len(text)
    chunk = text[start:end]
    for key, value in values.items():
        assignment = r'^\s*'+re.escape(key)+r'\s*='
        existing = next((item for item in visible_lines(chunk) if re.match(assignment, item[2])), None)
        rendered = key+' = '+json.dumps(value)
        if existing:
            if '"""' in existing[2] or "'" * 3 in existing[2]:
                raise ValueError('Multiline selected setting requires manual reconciliation: '+key)
            a, b, line = existing
            ending = '\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''
            chunk = chunk[:a]+rendered+ending+chunk[b:]
        else:
            if chunk and not chunk.endswith(('\n', '\r')):
                chunk += newline
            chunk += rendered+newline
    return text[:start]+chunk+text[end:]

def managed_preview_diff(name, old, new):
    """Show only managed TOML settings, never surrounding user configuration."""
    if name == str(installer.CONFIG_RELATIVE):
        paths = [('model',), ('model_reasoning_effort',), ('review_model',)]
        paths += [('agents', key) for key in ('enabled', 'max_depth', 'max_concurrent_threads_per_session',
                                               'default_subagent_model', 'default_subagent_reasoning_effort')]
        paths += [('agents', role, 'config_file') for role in installer.ROLE_FILES]
        paths += [('agents', slot, key) for slot in TEAM_SLOTS for key in ('description', 'config_file')]
    elif name in {str(path) for path in TEAM_SLOTS.values()}:
        paths = [(key,) for key in ('name', 'description', 'model', 'model_reasoning_effort')]
    else:
        paths = [('model',), ('model_reasoning_effort',)]
    before = tomllib.loads(old.decode()) if old is not None else {}
    after = tomllib.loads(new.decode()) if new is not None else {}
    missing = object()
    def value(document, path):
        for part in path:
            if not isinstance(document, dict) or part not in document:
                return missing
            document = document[part]
        return document
    def describe(item):
        return '(unset)' if item is missing else json.dumps(item, ensure_ascii=False)
    lines = []
    for path in paths:
        earlier, later = value(before, path), value(after, path)
        if earlier != later:
            lines.append('.'.join(path)+': '+describe(earlier)+' → '+describe(later))
    return '\n'.join(lines) if lines else 'Managed settings update'

def without_team_tables(text):
    """Remove only console-reserved slot tables, retaining unrelated TOML bytes."""
    headers = table_headers(text)
    cuts = []
    for index, (start, _, name, array) in enumerate(headers):
        parts = name.split('.')
        if len(parts) >= 2 and parts[0] == 'agents' and parts[1] in TEAM_SLOTS:
            end = headers[index + 1][0] if index + 1 < len(headers) else len(text)
            cuts.append((start, end))
    for start, end in reversed(cuts):
        text = text[:start] + text[end:]
    return text

def render_team_slot(slot, duty, model, effort, title):
    text = installer.render_role_config(ROOT, duty, model, effort)
    description = f"Team helper {slot[-2:]} · {duty}" + (f" · {title}" if title else '')
    text = patch_values(text, '', {'name': slot, 'description': description})
    tomllib.loads(text)
    return text

class Console:
    def __init__(self, target, sessions):
        self.target = installer.validate_target(target, ROOT)
        self.sessions = sessions.expanduser().resolve()
        self.pending = None
        self._catalog = None
        self.validate_paths()

    def validate_paths(self):
        for relative in [*SAFE_PATHS, STATE, HISTORY, installer.BACKUP_RELATIVE / "probe"]:
            path = self.target/relative
            for parent in (path, *path.parents):
                if parent == self.target:
                    break
                if parent.is_symlink():
                    raise ValueError('Symlink destination refused: '+str(relative))
            if path.exists() and not path.is_file():
                raise ValueError('File destination required: '+str(relative))
        backup_root = self.target / installer.BACKUP_RELATIVE
        if backup_root.exists():
            for path in backup_root.rglob('*'):
                if path.is_symlink():
                    raise ValueError('Symlink backup path refused')

    def snapshot(self):
        self.validate_paths()
        return {str(p): contents(self.target/p) for p in SAFE_PATHS}

    def style_history(self):
        self.validate_paths()
        path = self.target/HISTORY
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        if data.get('schema') != 1 or not isinstance(data.get('events'), list) or len(data['events']) > 1000:
            raise ValueError('Invalid style history')
        return data['events']

    def append_style_history(self, action, preset=None, settings=None):
        events = self.style_history()
        event = {'at': datetime.now(timezone.utc).isoformat(), 'action': action}
        if action == 'save':
            event.update(preset=preset, roles={role: {'model': model, 'effort': effort} for role, (model, effort) in settings.items()})
        events.append(event)
        installer.atomic_write_text(self.target/HISTORY, json.dumps({'schema': 1, 'events': events[-1000:]}, separators=(',', ':')), False)

    def models(self, refresh=False):
        if self._catalog is None or refresh:
            self._catalog = model_catalog.catalog()
        return self._catalog

    def refresh_models(self, payload):
        if payload:
            raise ValueError('Model refresh takes no fields')
        return self.models(refresh=True)

    def settings(self):
        self.validate_paths()
        config_path = self.target/installer.CONFIG_RELATIVE
        config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
        manifest = installer.load_manifest(self.target)
        roles = {}
        for role in installer.ALL_ROLES:
            path = config_path if role == 'owner' else self.target/installer.ROLE_FILES[role]
            data = tomllib.loads(path.read_text()) if path.exists() else {}
            roles[role] = {'model': data.get('model', ''), 'effort': data.get('model_reasoning_effort', '')}
        team = []
        for item in manifest.get('team_slots', []):
            if isinstance(item, dict) and item.get('slot') in TEAM_SLOTS:
                path = self.target/TEAM_SLOTS[item['slot']]
                if path.is_file():
                    data = tomllib.loads(path.read_text())
                    team.append({'slot': item['slot'], 'duty': item.get('duty', ''), 'model': data.get('model', ''), 'effort': data.get('model_reasoning_effort', ''), 'title': item.get('title', '')})
        return {'target': str(self.target), 'target_kind': 'project', 'user_target_supported': False, 'presets': {k: {r: {'model': m, 'effort': e} for r,(m,e) in v.items()} for k,v in installer.PRESETS.items()}, 'roles': roles, 'team': team, 'team_duties': list(installer.ROLE_FILES), 'efforts': EFFORTS, 'concurrency': config.get('agents', {}).get('max_concurrent_threads_per_session', 4), 'installed': config_path.exists(), 'restore_available': (self.target/STATE).is_file(), 'limitations': 'Project configuration only. Model/effort availability must be verified in your Codex client. Custom GPT IDs accepted; no account capability discovery. Context/report preferences are soft instructions, not token limits.'}

    def preview(self, payload):
        if set(payload) - {'preset', 'roles', 'concurrency', 'team'}:
            raise ValueError('Unknown setting')
        preset = payload.get('preset', 'focused')
        if preset not in installer.PRESETS:
            raise ValueError('Unknown preset')
        overrides = payload.get('roles', {})
        if not isinstance(overrides, dict) or set(overrides)-set(installer.ALL_ROLES):
            raise ValueError('Unknown role')
        models, efforts = [], []
        known_models = {item['id']: item for item in self.models()['models']}
        saved_state = self.settings()
        saved_models = saved_state['roles']
        for role, value in overrides.items():
            if not isinstance(value, dict) or set(value) != {'model', 'effort'} or not all(isinstance(v,str) for v in value.values()):
                raise ValueError('Invalid role selection')
            if value['model'] not in known_models and value['model'] != saved_models[role]['model']:
                raise ValueError('Selected model is no longer in the model list: '+role)
            models.append(role+'='+value['model'])
            efforts.append(role+'='+value['effort'])
        settings = installer.resolve_profile(preset, None, models, efforts)
        for role, (model, effort) in settings.items():
            saved = saved_models[role]
            if (model, effort) != (saved['model'], saved['effort']):
                entry = known_models.get(model)
                if entry is None:
                    raise ValueError('Selected model is no longer in the model list: '+role)
                if entry['efforts'] and effort not in entry['efforts']:
                    raise ValueError('Selected reasoning effort is not supported by the model: '+role)
            if model == 'gpt-6-astra' and effort in ('none', 'minimal') and (model, effort) != (saved['model'], saved['effort']):
                raise ValueError('GPT-6 Astra requires low or higher reasoning')
        cap = payload.get('concurrency', 4)
        if type(cap) is not int or not 1 <= cap <= 10:
            raise ValueError('Concurrency must be 1–10; runtime/account limits still apply')
        team = payload.get('team', saved_state['team'])
        if not isinstance(team, list) or len(team) > 10 or ('team' in payload and len(team) != cap):
            raise ValueError('Team must have one helper per selected slot')
        saved_team = {item['slot']: item for item in saved_state['team']}
        clean_team = []
        for index, item in enumerate(team, 1):
            slot = f'team_slot_{index:02d}'
            if not isinstance(item, dict) or set(item) != {'slot', 'duty', 'model', 'effort', 'title'} or item['slot'] != slot:
                raise ValueError('Invalid team slot')
            duty, model, effort, title = (item[key] for key in ('duty', 'model', 'effort', 'title'))
            if duty not in installer.ROLE_FILES or not all(isinstance(value, str) for value in (model, effort, title)) or len(title) > 48 or any(ord(ch) < 32 for ch in title):
                raise ValueError('Invalid team choice')
            installer.validate_native_model(model, slot+' model')
            if effort not in EFFORTS:
                raise ValueError('Invalid team reasoning')
            previous = saved_team.get(slot)
            if model not in known_models and (not previous or (model, effort) != (previous['model'], previous['effort'])):
                raise ValueError('Selected team model is no longer in the model list: '+slot)
            entry = known_models.get(model)
            if entry and entry['efforts'] and effort not in entry['efforts'] and (not previous or (model, effort) != (previous['model'], previous['effort'])):
                raise ValueError('Selected team reasoning is not supported by the model: '+slot)
            clean_team.append({'slot': slot, 'duty': duty, 'model': model, 'effort': effort, 'title': title})
        before = self.snapshot()
        desired = {str(p): (ROOT/p).read_bytes() for p in installer.MANAGED_RELATIVE_FILES}
        for role, relative in installer.ROLE_FILES.items():
            old = before[str(relative)]
            text = old.decode() if old is not None else (ROOT/relative).read_text()
            tomllib.loads(text)
            model, effort = settings[role]
            text = patch_values(text, '', {'model': model, 'model_reasoning_effort': effort})
            tomllib.loads(text)
            desired[str(relative)] = text.encode()
        for slot, relative in TEAM_SLOTS.items():
            item = next((item for item in clean_team if item['slot'] == slot), None)
            desired[str(relative)] = render_team_slot(slot, item['duty'], item['model'], item['effort'], item['title']).encode() if item else None
        old = before[str(installer.CONFIG_RELATIVE)]
        if old is None:
            text = installer.render_root_config(ROOT, self.target, settings, 'none', '', '')
        else:
            text = old.decode()
        tomllib.loads(text)
        existing_slots = {parts[1] for _, _, name, _ in table_headers(text) if (parts := name.split('.')) and len(parts) >= 2 and parts[0] == 'agents' and parts[1] in TEAM_SLOTS}
        if existing_slots - set(saved_team):
            raise ValueError('Existing team slot table is not console-managed')
        text = without_team_tables(text)
        text = patch_values(text, '', {'model': settings['owner'][0], 'model_reasoning_effort': settings['owner'][1], 'review_model': settings['reviewer'][0]})
        text = patch_values(text, 'agents', {'enabled': True, 'max_depth': 1, 'max_concurrent_threads_per_session': cap, 'default_subagent_model': settings['explorer'][0], 'default_subagent_reasoning_effort': settings['explorer'][1]})
        for role, path in installer.ROLE_FILES.items():
            text = patch_values(text, 'agents.'+role, {'config_file': './agents/'+path.name})
        for item in clean_team:
            path = TEAM_SLOTS[item['slot']]
            text = patch_values(text, 'agents.'+item['slot'], {'description': f"Team helper {item['slot'][-2:]} · {item['duty']}" + (f" · {item['title']}" if item['title'] else ''), 'config_file': './agents/'+path.name})
        tomllib.loads(text)
        desired[str(installer.CONFIG_RELATIVE)] = text.encode()
        desired['AGENTS.md'] = installer.merge_agents_text((before['AGENTS.md'] or b'').decode(), (ROOT/'templates/AGENTS.block.md').read_text()).encode()
        manifest = installer.load_manifest(self.target)
        conflicts = []
        changes = []
        for name, data in desired.items():
            old = before[name]
            if old == data:
                continue
            if old is not None and name not in ('AGENTS.md', str(installer.CONFIG_RELATIVE)) and not installer.unchanged_owned(manifest, Path(name), self.target/name):
                conflicts.append(name)
            # Preview only explicitly managed settings; even a zero-context file diff
            # can expose unrelated values when line endings or nearby tables change.
            if name in {str(installer.CONFIG_RELATIVE), *map(str, installer.ROLE_FILES.values()), *map(str, TEAM_SLOTS.values())}:
                diff = managed_preview_diff(name, old, data)
            else:
                diff = 'Managed asset '+('update' if old else 'install')
            changes.append({'path': name, 'diff': diff})
        preview_id = secrets.token_urlsafe(24)
        self.pending = (preview_id, before, desired, settings, preset, clean_team, conflicts)
        return {'preview_id': preview_id, 'changes': changes, 'conflicts': conflicts, 'can_save': not conflicts, 'notice': 'Save backs up existing configuration. Unrelated assignments are preserved. Modified or unowned managed assets must be reconciled using the CLI installer first.'}

    def save(self, payload):
        if set(payload) != {'preview_id'} or not self.pending or payload['preview_id'] != self.pending[0]:
            raise ValueError('Preview required before Save')
        _, before, desired, settings, preset, team, conflicts = self.pending
        if conflicts:
            raise ValueError('Managed file conflict: '+', '.join(conflicts))
        if self.snapshot() != before:
            self.pending = None
            raise ValueError('Files changed since preview; preview again')
        manifest = installer.load_manifest(self.target)
        messages = []
        old_state, old_history = contents(self.target/STATE), contents(self.target/HISTORY)
        # Runtime ignore comes first so backups and snapshots stay local.
        ordered = [str(Path('.codex/.bounded-orchestrator/.gitignore'))] + [p for p in desired if p != '.codex/.bounded-orchestrator/.gitignore']
        try:
            for name in ordered:
                path = Path(name)
                if desired[name] is None:
                    if before[name] is not None:
                        if not installer.unchanged_owned(manifest, path, self.target/path):
                            raise ValueError('Team file changed since preview: '+name)
                        (self.target/path).unlink()
                        manifest.get('files', {}).pop(name, None)
                    continue
                text = desired[name].decode()
                if name == str(installer.CONFIG_RELATIVE):
                    installer.backup_file(self.target, self.target/path, False) if before[name] is not None else None
                    installer.install_config(target=self.target, config_text=text, preset=preset, manifest=manifest, force_config=True, dry_run=False, messages=messages)
                elif name == 'AGENTS.md':
                    if before[name] is not None and before[name] != desired[name]:
                        installer.backup_file(self.target, self.target/path, False)
                    installer.atomic_write_text(self.target/path, text, False)
                    manifest['agents_block'] = True
                else:
                    installer.install_text_file(target=self.target, relative=path, text=text, manifest=manifest, force=before[name] is not None, dry_run=False, messages=messages)
            manifest['team_slots'] = team
            installer.write_manifest(root=ROOT, target=self.target, preset=preset, settings=settings, external_provider=manifest.get('external_provider', 'none'), external_model=manifest.get('external_model') or '', external_effort=manifest.get('external_effort') or '', manifest=manifest, dry_run=False)
            after = self.snapshot()
            changed = {p: {'before': base64.b64encode(before[p]).decode() if before[p] is not None else None, 'after': digest(after[p])} for p in before if before[p] != after[p]}
            installer.atomic_write_text(self.target/STATE, json.dumps({'schema': 1, 'files': changed}), False)
            self.append_style_history('save', preset, settings)
        except Exception:
            for name, data in before.items():
                if contents(self.target/name) != data:
                    self.restore_bytes(name, data)
            self.restore_bytes(str(STATE), old_state)
            self.restore_bytes(str(HISTORY), old_history)
            raise
        self.pending = None
        return {'status': 'saved', 'changed_files': list(changed), 'restart_required': True}

    def restore_bytes(self, name, data):
        path = self.target/name
        if data is None:
            # Preserve privacy after undoing a first installation: installer
            # backups remain local and must never become visible to Git.
            runtime_ignore = Path('.codex/.bounded-orchestrator/.gitignore')
            if Path(name) == runtime_ignore and (self.target/installer.BACKUP_RELATIVE).exists():
                if not path.exists():
                    installer.atomic_write_text(path, (ROOT/runtime_ignore).read_text(), False)
                return
            path.unlink(missing_ok=True)
        else:
            installer.atomic_write_text(path, data.decode(), False)

    def restore(self, payload):
        if payload:
            raise ValueError('Restore takes no fields')
        self.validate_paths()
        path = self.target/STATE
        data = json.loads(path.read_text())
        if data.get('schema') != 1 or not isinstance(data.get('files'), dict) or set(data['files']) - {str(p) for p in SAFE_PATHS}:
            raise ValueError('Invalid restore snapshot')
        snapshot = self.snapshot()
        for name, entry in data['files'].items():
            if digest(snapshot[name]) != entry['after']:
                raise ValueError('File changed after Save; restore refused: '+name)
        decoded = {name: base64.b64decode(entry['before'], validate=True) if entry['before'] is not None else None for name,entry in data['files'].items()}
        # Record the transition before changing settings; a failed restore then
        # leaves future attribution unknown rather than falsely assigning a style.
        self.append_style_history('restore')
        for name, value in decoded.items():
            self.restore_bytes(name, value)
        path.unlink()
        self.pending = None
        return {'status': 'restored', 'restart_required': True}

    def report(self, query):
        allowed = {'date_from', 'date_to', 'project', 'thread', 'root'}
        if set(query)-allowed or any(len(v) != 1 or len(v[0]) > 4096 for v in query.values()):
            raise ValueError('Invalid usage filter')
        filters = {k: v[0] for k,v in query.items()}
        selected_root = filters.pop('root', '')
        for name in ('date_from', 'date_to'):
            if filters.get(name) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', filters[name]):
                raise ValueError('Invalid date')
        result = usage.scan(self.sessions, **filters)
        orchestra = orchestra_view(result, selected_root, filters)
        if selected_root:
            filter_report_records(result, orchestra.pop('_records'))
        else:
            orchestra.pop('_records')
        result['orchestra'] = orchestra
        result['sample_data'] = self.sessions == (ROOT/'tests/fixtures/usage-sanitized').resolve()
        result['source_path'] = str(self.sessions)
        if result['sample_data']:
            history = json.loads((ROOT/'tests/fixtures/usage-sanitized/style-history.json').read_text())['events']
            project = '/sample/project'
        else:
            history = self.style_history()
            project = str(self.target)
        result['breakdowns'] = usage_breakdowns(result, history, project)
        return result

class Server(HTTPServer):
    def __init__(self, address, console):
        super().__init__(address, Handler)
        self.console = console
        self.token = secrets.token_urlsafe(32)
        self.origin = 'http://127.0.0.1:'+str(self.server_port)

    def get_request(self):
        connection, address = super().get_request()
        # Browsers may open an idle preconnect socket. Keep this single-threaded
        # server responsive without allowing concurrent settings writes.
        connection.settimeout(1.0)
        return connection, address

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, status, body, kind='application/json'):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', kind+'; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') == '127.0.0.1:'+str(self.server.server_port)

    def do_GET(self):
        if not self.valid_host():
            return self.respond(403, {'error': 'Invalid Host'})
        parsed = urlsplit(self.path)
        try:
            if parsed.path == '/api/models':
                return self.respond(200, self.server.console.models())
            if parsed.path == '/api/settings':
                return self.respond(200, {**self.server.console.settings(), 'csrf_token': self.server.token})
            if parsed.path == '/api/usage':
                return self.respond(200, self.server.console.report(parse_qs(parsed.query, keep_blank_values=True)))
            names = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css', '/orchestra.svg': 'orchestra.svg'}
            if parsed.path not in names:
                return self.respond(404, {'error': 'Not found'})
            kinds = {'/': 'text/html', '/app.js': 'text/javascript', '/style.css': 'text/css', '/orchestra.svg': 'image/svg+xml'}
            return self.respond(200, (ASSETS/names[parsed.path]).read_bytes(), kinds[parsed.path])
        except (ValueError, OSError, installer.InstallError) as exc:
            return self.respond(400, {'error': str(exc)})

    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin') != self.server.origin or not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), self.server.token):
            return self.respond(403, {'error': 'Invalid request origin/token'})
        try:
            if self.headers.get('Content-Type') != 'application/json':
                raise ValueError('JSON required')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 32768:
                raise ValueError('Invalid body size')
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError('Object required')
            if self.path == '/api/quit':
                if payload:
                    raise ValueError('Quit takes no fields')
                self.respond(200, {'status': 'closing'})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            actions = {'/api/preview': self.server.console.preview, '/api/save': self.server.console.save, '/api/restore': self.server.console.restore, '/api/models/refresh': self.server.console.refresh_models}
            if self.path not in actions:
                return self.respond(404, {'error': 'Not found'})
            return self.respond(200, actions[self.path](payload))
        except (ValueError, OSError, installer.InstallError, KeyError, TypeError) as exc:
            return self.respond(400, {'error': str(exc)})

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=Path, help='Existing target Git repository (project settings only)')
    parser.add_argument('--sessions', type=Path, default=Path.home()/'.codex/sessions')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('Port must be 0–65535')
    try:
        server = Server(('127.0.0.1', args.port), Console(args.target, args.sessions))
    except (ValueError, OSError, installer.InstallError) as exc:
        parser.error(str(exc))
    print('Codex yerel konsol: '+server.origin, flush=True)
    if not args.no_browser:
        webbrowser.open(server.origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
