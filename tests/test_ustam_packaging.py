"""Focused package integrity, native launcher, and frozen worker smoke checks."""
import importlib.util
import json
import queue
import signal
import socket
import time
import threading
import urllib.request
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

builder = load('ustam_builder', 'scripts/build_ustam_app.py')
launcher = load('ustam_launcher', 'launchers/launch_ustam.py')
syncer = load('ustam_syncer', 'scripts/sync_ustam_distribution.py')


class PackagingTests(unittest.TestCase):
    def test_manifest_closure_hash_and_ui_assets(self):
        manifest = builder.verify_assets()
        self.assertEqual(set(manifest['engines']), {'codex', 'claude', 'opencode'})
        for record in manifest['engines'].values():
            self.assertRegex(record['commit'], r'^[a-f0-9]{40}$')
            self.assertTrue(record['files'])

    def test_manifest_rejects_added_or_tampered_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'ustam').mkdir()
            manifest = {'schema': 1, 'engines': {}}
            import hashlib
            for provider in ('codex', 'claude', 'opencode'):
                base = root / 'ustam/engines' / provider
                base.mkdir(parents=True)
                (base / 'VERSION').write_text('1')
                manifest['engines'][provider] = {'commit': 'a'*40, 'files': {'VERSION': hashlib.sha256(b'1').hexdigest()}}
            (root / 'ustam/engine-manifest.json').write_text(json.dumps(manifest))
            (root / 'ustam/ui').mkdir()
            for name in ('index.html','app.js','style.css'):
                (root / 'ustam/ui' / name).write_text('')
            builder.verify_assets(root)
            (root / 'ustam/engines/codex/extra').write_text('')
            with self.assertRaisesRegex(ValueError, 'closure'):
                builder.verify_assets(root)
            (root / 'ustam/engines/codex/extra').unlink()
            (root / 'ustam/engines/codex/VERSION').write_text('2')
            with self.assertRaisesRegex(ValueError, 'hash'):
                builder.verify_assets(root)

    def test_generated_sync_preserves_unowned_and_locally_edited_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory)/'source', Path(directory)/'target'
            source.mkdir(); target.mkdir(); (target/'.git').mkdir()
            (source/'ustam').mkdir(); (source/'ustam/shared.py').write_text('first')
            legacy = target/'legacy.py'; legacy.write_text('provider-specific')
            with patch.object(syncer, 'FILES', ()):
                syncer.sync(target, True, source)
                self.assertEqual(legacy.read_text(), 'provider-specific')
                (source/'ustam/shared.py').write_text('next')
                (target/'ustam/shared.py').write_text('local edit')
                with self.assertRaisesRegex(ValueError, 'locally edited'):
                    syncer.sync(target, True, source)
                self.assertEqual((target/'ustam/shared.py').read_text(), 'local edit')
                (target/'ustam/shared.py').write_text('first')
                syncer.sync(target, True, source)
                self.assertEqual((target/'ustam/shared.py').read_text(), 'next')
                self.assertEqual(syncer.sync(target, False, source), [])
                manifest_path = target/syncer.MANIFEST
                manifest = json.loads(manifest_path.read_text())
                manifest['files']['legacy.py'] = syncer.digest(legacy)
                manifest_path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'unowned path'):
                    syncer.sync(target, True, source)
                self.assertEqual(legacy.read_text(), 'provider-specific')

    @unittest.skipUnless(os.environ.get('USTAM_NATIVE_LAUNCHER') and os.sys.platform == 'darwin', 'Mac native app self-contained check')
    def test_mac_app_runs_on_its_own_outside_package(self):
        import shutil
        executable = Path(os.environ['USTAM_NATIVE_LAUNCHER']).resolve()
        app = next(parent for parent in executable.parents if parent.name.endswith('.app'))
        import plistlib
        bundle_metadata = plistlib.loads((app/'Contents/Info.plist').read_bytes())
        self.assertEqual(bundle_metadata['UstamVersion'], (ROOT/'ustam/VERSION').read_text().strip())
        with tempfile.TemporaryDirectory() as directory:
            moved = Path(directory)/'standalone'/app.name
            shutil.copytree(app, moved, symlinks=True)
            with patch.dict(os.environ, {'USTAM_NATIVE_LAUNCHER':str(moved/'Contents/MacOS/Ustam'),
                                        'USTAM_FROZEN_WORKER':str(moved/'Contents/Resources/worker/UstamWorker')}):
                self.test_native_app_launches_hub_without_picker()
                self.test_frozen_clean_first_launch_and_provider_install()
                self.test_frozen_adapter_stdio_all_providers()

    def test_source_pythonw_uses_console_worker_interpreter(self):
        self.assertEqual(launcher.console_python('/runtime/pythonw.exe'), str(Path('/runtime/python.exe')))
        self.assertEqual(launcher.console_python('/runtime/python3'), str(Path('/runtime/python3')))

    def test_mac_app_worker_is_inside_bundle(self):
        with patch.object(launcher.sys, 'platform', 'darwin'):
            executable = Path.cwd() / 'Applications/Ustam.app/Contents/MacOS/Ustam'
            self.assertEqual(launcher.worker_path(executable), executable.parent.parent / 'Resources/worker/UstamWorker')

    def test_native_launcher_no_project_picker_or_python_dependency(self):
        with patch.object(launcher.sys, 'frozen', True, create=True), patch.object(launcher, 'worker_path', return_value=Path(__file__)), patch.object(launcher.subprocess, 'Popen') as popen:
            popen.return_value.wait.return_value = 0
            self.assertEqual(launcher.main([]), 0)
            self.assertEqual(popen.call_args.args[0], [str(Path(__file__))])
            self.assertEqual(popen.call_args.kwargs['stdin'], subprocess.DEVNULL)

    @unittest.skipUnless(os.environ.get('USTAM_FROZEN_WORKER'), 'Set USTAM_FROZEN_WORKER after building a native package')
    def test_frozen_adapter_stdio_all_providers(self):
        worker = os.environ['USTAM_FROZEN_WORKER']
        with tempfile.TemporaryDirectory() as directory:
            for provider in ('codex', 'claude', 'opencode'):
                project = Path(directory) / provider
                project.mkdir()
                request = {'reqid': uuid.uuid4().hex, 'method': 'inspect', 'target': str(project), 'params': {}}
                result = subprocess.run([worker, '--adapter', provider], input=json.dumps(request)+'\n',
                                        capture_output=True, text=True, timeout=30,
                                        env={**os.environ, 'PATH': '', 'HOME': directory, 'USERPROFILE': directory, 'LOCALAPPDATA': directory, 'APPDATA': directory, 'PYTHONPATH': '', 'PYTHONHOME': '', 'PYTHONDONTWRITEBYTECODE': '1'})
                self.assertEqual(result.returncode, 0, result.stderr)
                response = json.loads(result.stdout)
                self.assertEqual(response['reqid'], request['reqid'])
                self.assertTrue(response['ok'], response)

    @unittest.skipUnless(os.environ.get('USTAM_FROZEN_WORKER'), 'Set USTAM_FROZEN_WORKER after building a native package')
    def test_frozen_clean_first_launch_and_provider_install(self):
        worker = os.environ['USTAM_FROZEN_WORKER']
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state'
            env = {**os.environ, 'PATH': '', 'HOME': directory, 'USERPROFILE': directory, 'LOCALAPPDATA': directory, 'APPDATA': directory, 'PYTHONPATH': '', 'PYTHONHOME': ''}
            process = subprocess.Popen([worker, '--no-browser', '--state-dir', str(state)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd='/' if os.name != 'nt' else directory)
            try:
                ready = queue.Queue()
                threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
                origin = ready.get(timeout=20).strip()
                self.assertRegex(origin, r'^http://127\.0\.0\.1:\d+$')
                def request(route, body=None, csrf=None):
                    headers = {'Origin': origin}
                    if csrf:
                        headers['X-Ustam-CSRF'] = csrf
                    data = None if body is None else json.dumps(body).encode()
                    if data:
                        headers['Content-Type'] = 'application/json'
                    with urllib.request.urlopen(urllib.request.Request(origin+route, data, headers), timeout=30) as response:
                        return json.load(response)
                bootstrap = request('/api/bootstrap')
                self.assertEqual(bootstrap['projects'], [])
                self.assertEqual(set(bootstrap['providers']), {'codex', 'claude', 'opencode'})
                for asset in ('/', '/app.js', '/style.css'):
                    with urllib.request.urlopen(origin+asset, timeout=5) as response:
                        self.assertEqual(response.status, 200)
                csrf = bootstrap['csrf']
                for provider in ('codex', 'claude', 'opencode'):
                    project = Path(directory) / provider
                    project.mkdir()
                    request('/api/projects', {'action':'add', 'path':str(project)}, csrf)
                    registered = request('/api/bootstrap')['projects']
                    ident = next(p['id'] for p in registered if p['path'] == str(project.resolve()))
                    model = {'codex':'gpt-6.1-sol', 'claude':'sonnet', 'opencode':'openai/gpt-6.1-sol'}[provider]
                    payload = {'name': 'Offline package check', 'provider': provider, 'chief': {'model': model, 'effort': '' if provider == 'opencode' else 'medium'},
                               'helpers': [{'id':'one', 'role':'implementer', 'name':'Implementation', 'model':model, 'effort': '' if provider == 'opencode' else 'medium'}],
                               'concurrency':1, 'profile':'balanced'}
                    preview = request('/api/preview', {'project_ids':[ident], 'provider':provider, 'payload':payload}, csrf)['results'][0]
                    self.assertTrue(preview['ok'], preview)
                    applied = request('/api/apply', {'preview_ids':[preview['preview_id']]}, csrf)['results'][0]
                    self.assertTrue(applied['ok'], applied)
                    self.assertTrue(any(project.iterdir()))
            finally:
                process.terminate()
                process.communicate(timeout=10)

    @unittest.skipUnless(os.environ.get('USTAM_NATIVE_LAUNCHER'), 'Set USTAM_NATIVE_LAUNCHER for native launch smoke')
    def test_native_app_launches_hub_without_picker(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            env = {**os.environ, 'PATH': '', 'HOME': directory, 'PYTHONHOME':'', 'PYTHONPATH':''}
            process = subprocess.Popen([os.environ['USTAM_NATIVE_LAUNCHER'], '--no-browser', '--port', str(port), '--state-dir', str(Path(directory)/'state')],
                                       start_new_session=os.name != 'nt', env=env, cwd='/' if os.name != 'nt' else directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic()+20
                while time.monotonic() < deadline:
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/bootstrap', timeout=1) as response:
                            bootstrap = json.load(response)
                            self.assertEqual(bootstrap['projects'], [])
                            break
                    except OSError:
                        if process.poll() is not None:
                            self.fail('Native launcher exited before hub readiness')
                        time.sleep(.1)
                else:
                    self.fail('Native launcher never opened hub')
            finally:
                if os.name == 'nt':
                    taskkill = Path(os.environ.get('SystemRoot', 'C:/Windows'))/'System32/taskkill.exe'
                    subprocess.run([str(taskkill), '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10, check=False)
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                process.communicate(timeout=10)

if __name__ == '__main__':
    unittest.main()
