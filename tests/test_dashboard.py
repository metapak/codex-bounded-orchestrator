from __future__ import annotations
import http.client
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import dashboard

class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name)/'repo'
        self.target.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.target)], check=True)
        self.sessions = Path(self.tmp.name)/'sessions'
        self.sessions.mkdir()
        self.console = dashboard.Console(self.target, self.sessions)

    def tearDown(self):
        self.tmp.cleanup()

    def test_preview_save_restore_preserves_other_config_and_files(self):
        config = self.target/'.codex/config.toml'
        config.parent.mkdir()
        original = '# User comment\nmodel = "gpt-user"\nsecret = "PRIVATE_VALUE"\n\n[unrelated]\nvalue = 3\n'
        config.write_text(original)
        agents = self.target/'AGENTS.md'
        agents.write_text('Personal instruction\n')
        preview = self.console.preview({'preset': 'economy', 'concurrency': 2})
        self.assertTrue(preview['can_save'])
        self.assertEqual(config.read_text(), original)
        self.assertNotIn('PRIVATE_VALUE', json.dumps(preview))
        self.console.save({'preview_id': preview['preview_id']})
        current = config.read_text()
        self.assertIn('secret = "PRIVATE_VALUE"', current)
        self.assertIn('[unrelated]\nvalue = 3', current)
        self.assertEqual(dashboard.tomllib.loads(current)['agents']['max_concurrent_threads_per_session'], 2)
        self.assertNotIn('PRIVATE_VALUE', json.dumps(self.console.settings()))
        self.console.restore({})
        self.assertEqual(config.read_text(), original)
        self.assertEqual(agents.read_text(), 'Personal instruction\n')
        self.assertFalse((self.target/'.codex/tools/usage_report.py').exists())

    def test_array_tables_and_multiline_strings_preserve_unrelated_fields(self):
        config = self.target/'.codex/config.toml'
        config.parent.mkdir()
        triple = '"' * 3
        original = ('note = '+triple+'\nmodel = "string-data"\n[agents]\nmax_depth = 999\n'+triple+'\n'
                    '[[unrelated]]\nmodel = "private-provider"\nsecret = "keep"\n'
                    '  ["quoted]table"]\nmodel = "other-provider"\n')
        config.write_text(original)
        before = dashboard.tomllib.loads(original)
        preview = self.console.preview({'preset': 'focused'})
        self.assertTrue(preview['can_save'])
        self.console.save({'preview_id':preview['preview_id']})
        current = dashboard.tomllib.loads(config.read_text())
        self.assertEqual(current['unrelated'], before['unrelated'])
        self.assertEqual(current['quoted]table'], before['quoted]table'])
        self.assertEqual(current['note'], before['note'])
        self.assertEqual(current['model'], 'gpt-6-astra')
        self.assertEqual(current['agents']['max_depth'], 1)
        self.console.restore({})
        self.assertEqual(config.read_text(), original)

    def test_malformed_toml_refused_before_patching_selected_keys(self):
        config = self.target/'.codex/config.toml'
        config.parent.mkdir()
        config.write_text('model = invalid\n')
        with self.assertRaises(dashboard.tomllib.TOMLDecodeError):
            self.console.preview({})
        self.assertEqual(config.read_text(), 'model = invalid\n')

    def test_first_install_restore_keeps_backups_ignored_and_unstaged(self):
        config = self.target/'.codex/config.toml'
        config.parent.mkdir()
        original = 'model="gpt-personal"\nprivate_fixture="SECRET_LIKE_TEST_VALUE"\n'
        config.write_text(original)
        plan = self.console.preview({'preset':'focused'})
        self.console.save({'preview_id':plan['preview_id']})
        backups = list((self.target/dashboard.installer.BACKUP_RELATIVE).rglob('config.toml'))
        self.assertTrue(backups)
        self.console.restore({})
        self.assertEqual(config.read_text(), original)
        ignore = self.target/'.codex/.bounded-orchestrator/.gitignore'
        self.assertEqual(ignore.read_text(), '*\n!.gitignore\n')
        for backup in backups:
            checked = subprocess.run(['git','check-ignore',str(backup)],cwd=self.target,capture_output=True)
            self.assertEqual(checked.returncode,0)
            self.assertIn('SECRET_LIKE_TEST_VALUE',backup.read_text())
        subprocess.run(['git','add','-A'],cwd=self.target,check=True)
        staged = subprocess.check_output(['git','ls-files','--','.codex/.bounded-orchestrator/backups'],cwd=self.target)
        self.assertEqual(staged,b'')

    def test_preview_conflict_and_stale_save(self):
        role = self.target/'.codex/agents/explorer.toml'
        role.parent.mkdir(parents=True)
        role.write_text('model="gpt-personal"\nmodel_reasoning_effort="low"\n')
        plan = self.console.preview({'preset': 'balanced'})
        self.assertIn('.codex/agents/explorer.toml', plan['conflicts'])
        with self.assertRaises(ValueError):
            self.console.save({'preview_id': plan['preview_id']})
        role.unlink()
        plan = self.console.preview({})
        (self.target/'AGENTS.md').write_text('Changed concurrently\n')
        with self.assertRaisesRegex(ValueError, 'since preview'):
            self.console.save({'preview_id': plan['preview_id']})

    def test_restore_refuses_modified_saved_files(self):
        preview = self.console.preview({})
        self.console.save({'preview_id': preview['preview_id']})
        (self.target/'.codex/config.toml').write_text('model="gpt-other"\n')
        with self.assertRaisesRegex(ValueError, 'changed after Save'):
            self.console.restore({})

    def test_validation_and_symlink(self):
        for payload in ({'concurrency': 0}, {'concurrency': True}, {'preset':'missing'}, {'roles':{'unknown':{}}}, {'roles':{'owner':{'model':'claude-5','effort':'low'}}}, {'roles':{'owner':{'model':'gpt-6-astra','effort':'none'}}}):
            with self.assertRaises((ValueError, dashboard.installer.InstallError)):
                self.console.preview(payload)
        (self.target/'.codex').symlink_to(self.sessions, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.console.preview({})

    def test_http_security_api_and_assets(self):
        server = dashboard.Server(('127.0.0.1',0), self.console)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
        try:
            conn.request('GET','/api/settings')
            result = conn.getresponse()
            self.assertEqual(result.status, 200)
            token=json.loads(result.read())['csrf_token']
            conn.request('GET','/api/usage')
            result=conn.getresponse()
            self.assertEqual(json.loads(result.read())['status'],'unavailable')
            conn.request('POST','/api/save', '{}', {'Content-Type':'application/json'})
            result=conn.getresponse(); self.assertEqual(result.status,403);result.read()
            headers={'Content-Type':'application/json','Origin':server.origin,'X-CSRF-Token':token}
            conn.request('POST','/api/preview', '{}', headers)
            result=conn.getresponse();self.assertEqual(result.status,200);plan=json.loads(result.read())
            conn.request('POST','/api/save', json.dumps({'preview_id':plan['preview_id']}),headers)
            result=conn.getresponse();self.assertEqual(result.status,200);result.read()
            conn.request('POST','/api/restore', '{}', headers)
            result=conn.getresponse();self.assertEqual(result.status,200);result.read()
            conn.request('GET','/api/usage?date_from=bad')
            result=conn.getresponse();self.assertEqual(result.status,400);result.read()
            conn.request('GET','/../../config.toml')
            result=conn.getresponse();self.assertEqual(result.status,404);result.read()
            conn.request('GET','/',headers={'Host':'evil.example'})
            result=conn.getresponse();self.assertEqual(result.status,403);result.read()
            for route in ('/','/style.css','/app.js'):
                conn.request('GET',route)
                result=conn.getresponse();self.assertEqual(result.status,200);self.assertTrue(result.read())
        finally:
            conn.close();server.shutdown();server.server_close();worker.join()

if __name__ == '__main__':
    unittest.main()
