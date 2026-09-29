#!/usr/bin/env python3
"""Repository configuration console, served only on loopback (Python 3.11+)."""
from __future__ import annotations
import argparse
import base64
import difflib
import hashlib
import importlib.util
import json
import re
import secrets
import sys
import tomllib
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import install as installer

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent / 'console'
STATE = Path('.codex/.bounded-orchestrator/console-restore.json')
SAFE_PATHS = sorted(installer.ALLOWED_MANIFEST_FILES | {Path('AGENTS.md'), installer.MANIFEST_RELATIVE}, key=str)
EFFORTS = installer.EFFORTS

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
    headers = table_headers(text)
    if section:
        header = next((h for h in headers if h[2] == section and not h[3]), None)
        if header is None:
            return text.rstrip() + '\n\n['+section+']\n' + ''.join(k+' = '+json.dumps(v)+'\n' for k,v in values.items())
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
            chunk = chunk[:a]+rendered+('\n' if line.endswith('\n') else '')+chunk[b:]
        else:
            chunk = chunk.rstrip()+'\n'+rendered+'\n'
    return text[:start]+chunk+text[end:]

class Console:
    def __init__(self, target, sessions):
        self.target = installer.validate_target(target, ROOT)
        self.sessions = sessions.expanduser().resolve()
        self.pending = None
        self.validate_paths()

    def validate_paths(self):
        for relative in [*SAFE_PATHS, STATE, installer.BACKUP_RELATIVE / "probe"]:
            path = self.target/relative
            for parent in (path, *path.parents):
                if parent == self.target:
                    break
                if parent.is_symlink():
                    raise ValueError('Symlink destination refused: '+str(relative))
            if path.exists() and not path.is_file():
                raise ValueError('File destination required: '+str(relative))

    def snapshot(self):
        self.validate_paths()
        return {str(p): contents(self.target/p) for p in SAFE_PATHS}

    def settings(self):
        self.validate_paths()
        config_path = self.target/installer.CONFIG_RELATIVE
        config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
        roles = {}
        for role in installer.ALL_ROLES:
            path = config_path if role == 'owner' else self.target/installer.ROLE_FILES[role]
            data = tomllib.loads(path.read_text()) if path.exists() else {}
            roles[role] = {'model': data.get('model', ''), 'effort': data.get('model_reasoning_effort', '')}
        return {'target': str(self.target), 'target_kind': 'project', 'user_target_supported': False, 'presets': {k: {r: {'model': m, 'effort': e} for r,(m,e) in v.items()} for k,v in installer.PRESETS.items()}, 'roles': roles, 'efforts': EFFORTS, 'concurrency': config.get('agents', {}).get('max_concurrent_threads_per_session', 4), 'installed': config_path.exists(), 'restore_available': (self.target/STATE).is_file(), 'limitations': 'Project configuration only. Model/effort availability must be verified in your Codex client. Custom GPT IDs accepted; no account capability discovery. Context/report preferences are soft instructions, not token limits.'}

    def preview(self, payload):
        if set(payload) - {'preset', 'roles', 'concurrency'}:
            raise ValueError('Unknown setting')
        preset = payload.get('preset', 'focused')
        if preset not in installer.PRESETS:
            raise ValueError('Unknown preset')
        overrides = payload.get('roles', {})
        if not isinstance(overrides, dict) or set(overrides)-set(installer.ALL_ROLES):
            raise ValueError('Unknown role')
        models, efforts = [], []
        for role, value in overrides.items():
            if not isinstance(value, dict) or set(value) != {'model', 'effort'} or not all(isinstance(v,str) for v in value.values()):
                raise ValueError('Invalid role selection')
            models.append(role+'='+value['model'])
            efforts.append(role+'='+value['effort'])
        settings = installer.resolve_profile(preset, None, models, efforts)
        for model, effort in settings.values():
            if model == 'gpt-6-astra' and effort in ('none', 'minimal'):
                raise ValueError('GPT-6 Astra requires low or higher reasoning')
        cap = payload.get('concurrency', 4)
        if type(cap) is not int or not 1 <= cap <= 10:
            raise ValueError('Concurrency must be 1–10; runtime/account limits still apply')
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
        old = before[str(installer.CONFIG_RELATIVE)]
        if old is None:
            text = installer.render_root_config(ROOT, self.target, settings, 'none', '', '')
        else:
            text = old.decode()
        tomllib.loads(text)
        text = patch_values(text, '', {'model': settings['owner'][0], 'model_reasoning_effort': settings['owner'][1], 'review_model': settings['reviewer'][0]})
        text = patch_values(text, 'agents', {'enabled': True, 'max_depth': 1, 'max_concurrent_threads_per_session': cap, 'default_subagent_model': settings['explorer'][0], 'default_subagent_reasoning_effort': settings['explorer'][1]})
        for role, path in installer.ROLE_FILES.items():
            text = patch_values(text, 'agents.'+role, {'config_file': './agents/'+path.name})
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
            # Zero context prevents unrelated configuration/credentials being exposed.
            if name in {str(installer.CONFIG_RELATIVE), *map(str, installer.ROLE_FILES.values())}:
                diff = ''.join(difflib.unified_diff((old or b'').decode().splitlines(True), data.decode().splitlines(True), fromfile=name, tofile=name, n=0))
            else:
                diff = 'Managed asset '+('update' if old else 'install')
            changes.append({'path': name, 'diff': diff})
        preview_id = secrets.token_urlsafe(24)
        self.pending = (preview_id, before, desired, settings, preset, conflicts)
        return {'preview_id': preview_id, 'changes': changes, 'conflicts': conflicts, 'can_save': not conflicts, 'notice': 'Save backs up existing configuration. Unrelated assignments are preserved. Modified or unowned managed assets must be reconciled using the CLI installer first.'}

    def save(self, payload):
        if set(payload) != {'preview_id'} or not self.pending or payload['preview_id'] != self.pending[0]:
            raise ValueError('Preview required before Save')
        _, before, desired, settings, preset, conflicts = self.pending
        if conflicts:
            raise ValueError('Managed file conflict: '+', '.join(conflicts))
        if self.snapshot() != before:
            self.pending = None
            raise ValueError('Files changed since preview; preview again')
        manifest = installer.load_manifest(self.target)
        messages = []
        # Runtime ignore comes first so backups and snapshots stay local.
        ordered = [str(Path('.codex/.bounded-orchestrator/.gitignore'))] + [p for p in desired if p != '.codex/.bounded-orchestrator/.gitignore']
        try:
            for name in ordered:
                path, text = Path(name), desired[name].decode()
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
            installer.write_manifest(root=ROOT, target=self.target, preset=preset, settings=settings, external_provider=manifest.get('external_provider', 'none'), external_model=manifest.get('external_model') or '', external_effort=manifest.get('external_effort') or '', manifest=manifest, dry_run=False)
            after = self.snapshot()
            changed = {p: {'before': base64.b64encode(before[p]).decode() if before[p] is not None else None, 'after': digest(after[p])} for p in before if before[p] != after[p]}
            installer.atomic_write_text(self.target/STATE, json.dumps({'schema': 1, 'files': changed}), False)
        except Exception:
            for name, data in before.items():
                if contents(self.target/name) != data:
                    self.restore_bytes(name, data)
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
        for name, value in decoded.items():
            self.restore_bytes(name, value)
        path.unlink()
        self.pending = None
        return {'status': 'restored', 'restart_required': True}

    def report(self, query):
        allowed = {'date_from', 'date_to', 'project', 'thread'}
        if set(query)-allowed or any(len(v) != 1 or len(v[0]) > 4096 for v in query.values()):
            raise ValueError('Invalid usage filter')
        filters = {k: v[0] for k,v in query.items()}
        for name in ('date_from', 'date_to'):
            if filters.get(name) and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', filters[name]):
                raise ValueError('Invalid date')
        return usage.scan(self.sessions, **filters)

class Server(HTTPServer):
    def __init__(self, address, console):
        super().__init__(address, Handler)
        self.console = console
        self.token = secrets.token_urlsafe(32)
        self.origin = 'http://127.0.0.1:'+str(self.server_port)

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
            if parsed.path == '/api/settings':
                return self.respond(200, {**self.server.console.settings(), 'csrf_token': self.server.token})
            if parsed.path == '/api/usage':
                return self.respond(200, self.server.console.report(parse_qs(parsed.query, keep_blank_values=True)))
            names = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
            if parsed.path not in names:
                return self.respond(404, {'error': 'Not found'})
            kinds = {'/': 'text/html', '/app.js': 'text/javascript', '/style.css': 'text/css'}
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
            actions = {'/api/preview': self.server.console.preview, '/api/save': self.server.console.save, '/api/restore': self.server.console.restore}
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
