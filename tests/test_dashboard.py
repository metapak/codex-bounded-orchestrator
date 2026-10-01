from __future__ import annotations
import http.client
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import dashboard

class ConsoleTests(unittest.TestCase):
    def test_managed_write_order_never_duplicates_windows_style_path(self):
        runtime = '.codex\\.bounded-orchestrator\\.gitignore'
        desired = {runtime: b'private', '.codex\\config.toml': b'config'}
        self.assertEqual(dashboard.ordered_managed_paths(desired, runtime),
                         [runtime, '.codex\\config.toml'])

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

    def test_crlf_preview_hides_unrelated_secret_and_save_preserves_bytes(self):
        config = self.target/'.codex/config.toml'
        config.parent.mkdir()
        unrelated = b'secret = "PRIVATE_VALUE"\r\n\r\n[unrelated]\r\nnote = "keep"\r\n'
        original = b'model = "gpt-user"\r\n' + unrelated
        config.write_bytes(original)
        preview = self.console.preview({'preset': 'focused'})
        self.assertTrue(preview['can_save'])
        self.assertNotIn('PRIVATE_VALUE', json.dumps(preview))
        self.assertIn('model:', json.dumps(preview))
        self.assertEqual(config.read_bytes(), original)
        self.console.save({'preview_id': preview['preview_id']})
        saved = config.read_bytes()
        self.assertIn(b'secret = "PRIVATE_VALUE"\r\n', saved)
        self.assertIn(b'[unrelated]\r\nnote = "keep"\r\n', saved)
        self.assertNotIn(b'\n', saved.replace(b'\r\n', b''))
        self.console.restore({})
        self.assertEqual(config.read_bytes(), original)

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
        self.assertEqual(current['model'], 'gpt-6-sol')
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
        self.assertIn('.codex/agents/explorer.toml', [path.replace('\\', '/') for path in plan['conflicts']])
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

    def test_usage_identifies_sanitized_sample_and_selected_source(self):
        sample = ROOT/'tests/fixtures/usage-sanitized'
        console = dashboard.Console(self.target, sample)
        report = console.report({})
        self.assertTrue(report['sample_data'])
        self.assertEqual(report['source_path'], str(sample.resolve()))
        self.assertEqual(report['totals']['total_tokens'], 88194)
        self.assertEqual({row['id']:row['total_tokens'] for row in report['breakdowns']['model']['rows']}, {'gpt-6-sol':35268, 'gpt-6-astra':32426, 'gpt-6-luna':12000, 'gpt-5.6-sol':8000, 'unknown':500})
        self.assertEqual({row['id']:row['total_tokens'] for row in report['breakdowns']['style']['rows']}, {'focused':29268, 'quality':58426, 'unknown':500})
        self.assertEqual(report['orchestra']['conductor_tokens'],61694)
        self.assertEqual(report['orchestra']['helper_tokens'],26000)
        self.assertEqual(report['orchestra']['unassigned_tokens'],500)
        self.assertEqual(report['orchestra']['helper_count'],3)
        scoped = console.report({'root':['demo-root']})
        self.assertEqual(scoped['orchestra']['helper_count'],4)
        self.assertIsNone(next(actor['total_tokens'] for actor in scoped['orchestra']['actors'] if actor['id']=='demo-helper-four'))
        self.assertEqual(sum(scoped['orchestra'][key] for key in ('conductor_tokens','helper_tokens','unassigned_tokens')),scoped['orchestra']['total_tokens'])
        filtered = console.report({'date_from':['2026-09-02'], 'date_to':['2026-09-02'], 'thread':['demo-root'], 'root':['demo-root']})
        self.assertEqual(filtered['breakdowns']['total_tokens'], 32426)
        self.assertEqual(filtered['breakdowns']['model']['rows'], [{'id':'gpt-6-astra','total_tokens':32426}])
        self.assertEqual(filtered['breakdowns']['style']['rows'], [{'id':'quality','total_tokens':32426}])
        self.assertEqual(filtered['orchestra']['helper_count'],0)
        self.assertFalse(self.console.report({})['sample_data'])

    def test_time_strip_uses_deduped_cumulative_deltas_and_keeps_unknown_time(self):
        rows = [{'timestamp':'2026-09-01T09:00:00Z','type':'session_meta','payload':{'id':'legacy-thread','cwd':str(self.target),'source':'cli'}}]
        rows += [{'timestamp':stamp,'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'total_tokens':total}}}}
                 for stamp,total in [('2026-09-01T10:00:00Z',12),('2026-09-02T10:00:00Z',19),
                                     ('2026-09-02T11:00:00Z',4),('2026-09-02T12:00:00Z',9)]]
        for name in ('a.jsonl','duplicate.jsonl'):
            (self.sessions/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
        (self.sessions/'unknown.jsonl').write_text(json.dumps({'type':'token_usage_record','thread_id':'other-thread','usage':{'total_tokens':3}})+'\n')
        report = self.console.report({})
        timeline = report['time_breakdown']
        self.assertEqual(report['totals']['total_tokens'],31)
        self.assertEqual(report['counter_resets'],1)
        self.assertEqual(timeline['days'],[{'day':'2026-09-01','total_tokens':12},{'day':'2026-09-02','total_tokens':16}])
        self.assertEqual(timeline['unknown_time_tokens'],3)
        self.assertEqual(sum(row['total_tokens'] for row in timeline['days'])+timeline['unknown_time_tokens'],timeline['total_tokens'])
        filtered = self.console.report({'date_from':['2026-09-02']})['time_breakdown']
        self.assertEqual(filtered['days'],[{'day':'2026-09-02','total_tokens':16}])
        self.assertEqual(filtered['unknown_time_tokens'],0)

    def test_style_attribution_requires_bounded_turn_and_exact_project(self):
        rows = [
            {'model':'gpt-one','project':str(self.target),'turn_start':'2026-09-01T10:00:00Z','turn_end':'2026-09-01T10:01:00Z','usage':{'input_tokens':15,'cached_input_tokens':10,'output_tokens':5,'total_tokens':20}},
            {'model':'unknown','project':str(self.target),'turn_start':'2026-09-01T10:30:00Z','turn_end':'2026-09-01T11:01:00Z','usage':{'total_tokens':10}},
            {'model':'gpt-two','project':str(self.target),'turn_start':'unknown','turn_end':'2026-09-01T12:00:00Z','usage':{'total_tokens':5}},
            {'model':'gpt-two','project':'/other/project','turn_start':'2026-09-01T12:00:00Z','turn_end':'2026-09-01T12:01:00Z','usage':{'total_tokens':15}},
        ]
        events = [{'at':'2026-09-01T09:00:00Z','action':'save','preset':'focused'}, {'at':'2026-09-01T11:00:00Z','action':'restore'}]
        result = dashboard.usage_breakdowns({'records':rows,'totals':{'total_tokens':50}},events,str(self.target))
        self.assertEqual(sum(row['total_tokens'] for row in result['model']['rows']),50)
        self.assertEqual(sum(row['total_tokens'] for row in result['style']['rows']),50)
        self.assertEqual({row['id']:row['total_tokens'] for row in result['style']['rows']},{'focused':20,'unknown':30})
        self.assertEqual(next(row['total_tokens'] for row in result['model']['rows'] if row['id']=='unknown'),10)

    def test_save_restore_writes_private_style_transitions(self):
        plan = self.console.preview({'preset':'quality'})
        self.console.save({'preview_id':plan['preview_id']})
        history = self.console.style_history()
        self.assertEqual(history[-1]['action'],'save')
        self.assertEqual(history[-1]['preset'],'quality')
        self.assertEqual(history[-1]['roles']['owner']['model'],'gpt-6-astra')
        ignored = subprocess.run(['git','check-ignore',str(self.target/dashboard.HISTORY)],cwd=self.target,capture_output=True)
        self.assertEqual(ignored.returncode,0)
        self.console.restore({})
        self.assertEqual(self.console.style_history()[-1]['action'],'restore')

    def test_unfinished_turn_is_unknown_until_matching_task_complete_marker(self):
        history = self.target/dashboard.HISTORY
        history.parent.mkdir(parents=True)
        history.write_text(json.dumps({'schema':1,'events':[{'at':'2026-09-01T09:00:00Z','action':'save','preset':'focused'}]}))
        log = self.sessions/'rollout.jsonl'
        rows = [
            {'timestamp':'2026-09-01T10:00:00Z','type':'session_meta','payload':{'id':'session-one','cwd':str(self.target)}},
            {'timestamp':'2026-09-01T10:01:00Z','type':'turn_context','payload':{'turn_id':'turn-one','model':'gpt-6-sol'}},
            {'timestamp':'2026-09-01T10:02:00Z','type':'token_usage_record','payload':{'turn_id':'turn-one','usage':{'total_tokens':25}}},
        ]
        log.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        self.assertEqual(self.console.report({})['breakdowns']['style']['rows'],[{'id':'unknown','total_tokens':25}])
        rows.append({'timestamp':'2026-09-01T10:03:00Z','type':'event_msg','payload':{'type':'task_complete','turn_id':'turn-one'}})
        log.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        self.assertEqual(self.console.report({})['breakdowns']['style']['rows'],[{'id':'focused','total_tokens':25}])

    def test_same_session_turns_split_across_saves_and_ambiguous_turns_unknown(self):
        history = self.target/dashboard.HISTORY
        history.parent.mkdir(parents=True)
        history.write_text(json.dumps({'schema':1,'events':[
            {'at':'2026-09-01T09:00:00Z','action':'save','preset':'focused'},
            {'at':'2026-09-01T11:00:00Z','action':'save','preset':'quality'},
        ]}))
        rows = [{'timestamp':'2026-09-01T08:00:00Z','type':'session_meta','payload':{'id':'shared-session','cwd':str(self.target)}}]
        def turn(turn_id, start, usage_at, end, model, tokens):
            rows.extend([
                {'timestamp':start,'type':'turn_context','payload':{'turn_id':turn_id,'model':model}},
                {'timestamp':usage_at,'type':'token_usage_record','payload':{'turn_id':turn_id,'usage':{'input_tokens':tokens-1,'cached_input_tokens':1,'output_tokens':1,'total_tokens':tokens}}},
            ])
            if end:
                rows.append({'timestamp':end,'type':'event_msg','payload':{'type':'task_complete','turn_id':turn_id}})
        turn('turn-focused','2026-09-01T10:00:00Z','2026-09-01T10:01:00Z','2026-09-01T10:05:00Z','gpt-6-sol',10)
        turn('turn-crossing','2026-09-01T10:59:00Z','2026-09-01T11:00:00Z','2026-09-01T11:01:00Z','gpt-6-sol',7)
        turn('turn-quality','2026-09-01T11:10:00Z','2026-09-01T11:11:00Z','2026-09-01T11:15:00Z','gpt-6-astra',20)
        turn('turn-open','2026-09-01T11:20:00Z','2026-09-01T11:21:00Z',None,'gpt-6-astra',5)
        (self.sessions/'rollout.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        report = self.console.report({})
        self.assertEqual(report['totals']['total_tokens'],42)
        self.assertEqual({row['id']:row['total_tokens'] for row in report['breakdowns']['style']['rows']},{'focused':10,'quality':20,'unknown':12})
        self.assertEqual(sum(row['total_tokens'] for row in report['breakdowns']['model']['rows']),42)

    def test_agent_hierarchy_nested_orphan_cycle_and_multiple_models(self):
        agents = [
            {'id':'root','parent':None,'source':'root','name':'','role':'owner','project':'/project'},
            {'id':'child','parent':'root','source':'subagent','name':'<script>not markup</script>','role':'researcher','project':'/project'},
            {'id':'grandchild','parent':'child','source':'subagent','name':'','role':'reviewer','project':'/project'},
            {'id':'orphan','parent':'missing','source':'subagent','name':'','role':'worker','project':'/project'},
            {'id':'bad-source','parent':'root','source':'root','name':'','role':'worker','project':'/project'},
            {'id':'cycle-a','parent':'cycle-b','source':'subagent','name':'','role':'worker','project':'/project'},
            {'id':'cycle-b','parent':'cycle-a','source':'subagent','name':'','role':'worker','project':'/project'},
        ]
        records = [
            {'thread':'root','session_id':'root','model':'gpt-root','timestamp':'2026-09-01T10:00:00Z','usage':{'total_tokens':10}},
            {'thread':'child','session_id':'root','model':'gpt-one','timestamp':'2026-09-01T10:01:00Z','usage':{'total_tokens':20}},
            {'thread':'child','session_id':'root','model':'gpt-two','timestamp':'2026-09-01T10:02:00Z','usage':{'total_tokens':30}},
            {'thread':'grandchild','session_id':'root','model':'gpt-two','timestamp':'2026-09-01T10:03:00Z','usage':{'total_tokens':5}},
            {'thread':'orphan','session_id':'root','model':'gpt-one','timestamp':'2026-09-01T10:04:00Z','usage':{'total_tokens':7}},
            {'thread':'bad-source','session_id':'root','model':'gpt-one','timestamp':'2026-09-01T10:04:01Z','usage':{'total_tokens':9}},
            {'thread':'cycle-a','session_id':'root','model':'gpt-one','timestamp':'2026-09-01T10:05:00Z','usage':{'total_tokens':3}},
        ]
        result = dashboard.orchestra_view({'agents':agents,'records':records},'root')
        self.assertEqual((result['total_tokens'],result['conductor_tokens'],result['helper_tokens'],result['unassigned_tokens']),(84,10,55,19))
        self.assertEqual(result['helper_count'],2)
        child = next(actor for actor in result['actors'] if actor['id']=='child')
        self.assertEqual(child['name'],'<script>not markup</script>')
        self.assertEqual(child['models'],[{'id':'gpt-two','total_tokens':30},{'id':'gpt-one','total_tokens':20}])

    def test_conflicting_agent_metadata_across_files_remains_unassigned(self):
        root_one = {'type':'session_meta','payload':{'id':'root-one','source':'cli','cwd':'/project'}}
        root_two = {'type':'session_meta','payload':{'id':'root-two','source':'cli','cwd':'/project'}}
        first = {'type':'session_meta','payload':{'id':'same-helper','parent_thread_id':'root-one','source':{'subagent':{}},'agent_role':'reviewer','cwd':'/project'}}
        second = {'type':'session_meta','payload':{'id':'same-helper','parent_thread_id':'root-two','source':{'subagent':{}},'agent_role':'reviewer','cwd':'/project'}}
        usage_row = {'timestamp':'2026-09-01T10:00:00Z','type':'token_usage_record','payload':{'thread_id':'same-helper','session_id':'root-one','usage':{'total_tokens':9}}}
        for filename, rows in [('a.jsonl',[root_one,first,usage_row]),('b.jsonl',[root_two,second])]:
            (self.sessions/filename).write_text(''.join(json.dumps(row)+'\n' for row in rows))
        report = dashboard.usage.scan(self.sessions)
        self.assertTrue(next(agent for agent in report['agents'] if agent['id']=='same-helper')['ambiguous'])
        result = dashboard.orchestra_view(report,'root-one')
        self.assertEqual((result['helper_count'],result['helper_tokens'],result['unassigned_tokens']),(0,0,9))

    def test_model_catalog_merges_runtime_and_offline_documentation(self):
        import model_catalog
        with mock.patch.object(model_catalog, 'discover_cli', return_value=[{'id':'gpt-6-astra','label':'GPT-6 Astra','efforts':['low','medium'],'origin':'local_cli'}]):
            catalog = model_catalog.catalog()
        entries = {item['id']:item for item in catalog['models']}
        self.assertEqual(catalog['discovery'], 'local_cli')
        self.assertEqual(entries['gpt-6-astra']['origin'], 'local_cli')
        self.assertEqual(entries['gpt-6.1-sol']['origin'], 'documentation')
        self.assertEqual(entries['gpt-6.1-sol']['efforts'], ['low','medium','high','xhigh','max','ultra'])
        self.assertFalse(catalog['account_access_verified'])
        with mock.patch.object(model_catalog, 'discover_cli', return_value=None):
            fallback = model_catalog.catalog()
        self.assertEqual(fallback['discovery'], 'documentation_fallback')
        self.assertTrue(fallback['documentation_reviewed_at'])
        self.assertIn('gpt-6-luna', {item['id'] for item in fallback['models']})
        self.assertIn('ultra', next(item for item in fallback['models'] if item['id']=='gpt-6.1-sol')['efforts'])

    def test_local_gpt_6_1_efforts_override_documentation_fallback(self):
        import model_catalog
        local = [{'id':'gpt-6.1-sol','label':'GPT-6.1 Sol','efforts':['low','medium','high','xhigh','max'],'origin':'local_cli'}]
        with mock.patch.object(model_catalog, 'discover_cli', return_value=local):
            self.console._catalog = model_catalog.catalog()
        entry = next(item for item in self.console._catalog['models'] if item['id']=='gpt-6.1-sol')
        self.assertEqual(entry['origin'], 'local_cli')
        self.assertNotIn('ultra', entry['efforts'])
        with self.assertRaisesRegex(ValueError, 'reasoning effort is not supported'):
            self.console.preview({'preset':'balanced', 'roles':{'owner':{'model':'gpt-6.1-sol','effort':'ultra'}}})
        self.assertTrue(self.console.preview({'preset':'balanced', 'roles':{'owner':{'model':'gpt-6.1-sol','effort':'max'}}})['can_save'])

    def test_saved_unlisted_model_is_preserved_but_new_unlisted_rejected(self):
        config = self.target/'.codex/config.toml'
        config.parent.mkdir()
        config.write_text('model = "gpt-private-legacy"\nmodel_reasoning_effort = "medium"\n')
        saved = self.console.settings()['roles']['owner']
        self.assertEqual(saved['model'], 'gpt-private-legacy')
        plan = self.console.preview({'preset':'balanced', 'roles':{'owner':saved}})
        self.assertTrue(plan['can_save'])
        self.console.save({'preview_id':plan['preview_id']})
        self.assertEqual(self.console.settings()['roles']['owner']['model'], 'gpt-private-legacy')
        with self.assertRaisesRegex(ValueError, 'no longer in the model list'):
            self.console.preview({'preset':'balanced', 'roles':{'owner':{'model':'gpt-unlisted-new','effort':'medium'}}})

    def test_team_slots_allow_duplicate_duties_and_restore_safe_changes(self):
        config = self.target/'.codex/config.toml'
        config.parent.mkdir()
        config.write_text('private_setting = "keep"\n[unrelated]\nvalue = 7\n')
        team = [
            {'slot':'team_slot_01','duty':'researcher','model':'gpt-6-sol','effort':'medium','title':'Sources'},
            {'slot':'team_slot_02','duty':'researcher','model':'gpt-6-luna','effort':'high','title':'Facts'},
        ]
        plan = self.console.preview({'preset':'focused','concurrency':2,'team':team})
        self.assertTrue(plan['can_save'],plan['conflicts'])
        self.console.save({'preview_id':plan['preview_id']})
        saved = self.console.settings()
        self.assertEqual(saved['team'],team)
        self.assertEqual(saved['concurrency'],2)
        self.assertEqual(dashboard.tomllib.loads(config.read_text())['private_setting'],'keep')
        self.assertEqual(dashboard.tomllib.loads(config.read_text())['agents']['team_slot_02']['config_file'],'./agents/team-slot-02.toml')
        first = self.target/dashboard.TEAM_SLOTS['team_slot_01']
        second = self.target/dashboard.TEAM_SLOTS['team_slot_02']
        self.assertEqual(dashboard.tomllib.loads(first.read_text())['name'],'team_slot_01')
        self.assertEqual(dashboard.tomllib.loads(second.read_text())['name'],'team_slot_02')
        self.assertTrue(dashboard.installer.unchanged_owned(dashboard.installer.load_manifest(self.target),dashboard.TEAM_SLOTS['team_slot_02'],second))
        config.write_text(config.read_text()+'\n[agents.team_slot_02.env]\nNOTE = "keep"\n')
        reduced = self.console.preview({'preset':'focused','concurrency':1,'team':team[:1]})
        self.assertTrue(reduced['can_save'],reduced['conflicts'])
        self.console.save({'preview_id':reduced['preview_id']})
        self.assertFalse(second.exists())
        self.assertNotIn('team_slot_02',dashboard.tomllib.loads(config.read_text())['agents'])
        self.console.restore({})
        self.assertTrue(second.exists())
        self.assertEqual(self.console.settings()['team'],team)
        self.assertEqual(dashboard.tomllib.loads(config.read_text())['agents']['team_slot_02']['env']['NOTE'],'keep')
        second.write_text(second.read_text()+'\n# personal edit\n')
        conflict = self.console.preview({'preset':'focused','concurrency':1,'team':team[:1]})
        self.assertIn(str(dashboard.TEAM_SLOTS['team_slot_02']),conflict['conflicts'])

    def test_fifty_planned_slots_are_separate_from_concurrency_and_restore(self):
        duties = list(dashboard.installer.ROLE_FILES)
        team = [{'slot':f'team_slot_{index:02d}', 'duty':duties[(index-1)%len(duties)],
                 'model':'gpt-6-sol', 'effort':'medium', 'title':f'Part {index}'} for index in range(1,51)]
        plan = self.console.preview({'preset':'focused','concurrency':4,'team_count':50,'team':team})
        self.assertTrue(plan['can_save'], plan['conflicts'])
        self.console.save({'preview_id':plan['preview_id']})
        saved = self.console.settings()
        self.assertEqual((saved['team_count'],saved['concurrency'],len(saved['team'])),(50,4,50))
        self.assertEqual(saved['saved_preset'],'focused')
        last = self.target/dashboard.TEAM_SLOTS['team_slot_50']
        self.assertTrue(last.is_file())
        self.assertEqual(dashboard.tomllib.loads((self.target/'.codex/config.toml').read_text())['agents']['max_concurrent_threads_per_session'],4)
        smaller = self.console.preview({'preset':'focused','concurrency':2,'team_count':7,'team':team[:7]})
        self.assertTrue(smaller['can_save'], smaller['conflicts'])
        self.console.save({'preview_id':smaller['preview_id']})
        self.assertFalse(last.exists())
        self.assertEqual(self.console.settings()['team_count'],7)
        self.assertNotIn(dashboard.TEAM_SLOTS['team_slot_50'].as_posix(),
                         dashboard.installer.load_manifest(self.target)['files'])
        self.console.restore({})
        self.assertTrue(last.exists())
        self.assertEqual(self.console.settings()['team_count'],50)
        self.assertEqual(dashboard.installer.uninstall(self.target, False),0)
        self.assertFalse(last.exists())

    def test_fifty_slot_preflight_and_mid_save_rollback(self):
        team = [{'slot':f'team_slot_{index:02d}', 'duty':'researcher','model':'gpt-6-sol','effort':'medium','title':''}
                for index in range(1,51)]
        payload = {'preset':'focused','concurrency':4,'team_count':50,'team':team}
        for count in (0,51,True):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError,'Planned team size'):
                self.console.preview({**payload,'team_count':count})
        with self.assertRaisesRegex(ValueError,'one helper per selected slot'):
            self.console.preview({**payload,'team_count':49})
        outside = Path(self.tmp.name)/'outside.toml'
        leaf = self.target/dashboard.TEAM_SLOTS['team_slot_50']
        leaf.parent.mkdir(parents=True)
        leaf.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'Symlink destination refused'):
            self.console.preview(payload)
        self.assertFalse(outside.exists())
        leaf.unlink()
        plan = self.console.preview(payload)
        before = self.console.snapshot()
        original = dashboard.installer.install_text_file
        def fail_on_thirtieth(**kwargs):
            if kwargs.get('relative') == dashboard.TEAM_SLOTS['team_slot_30']:
                raise OSError('injected write failure')
            return original(**kwargs)
        with mock.patch.object(dashboard.installer,'install_text_file',side_effect=fail_on_thirtieth):
            with self.assertRaisesRegex(OSError,'injected write failure'):
                self.console.save({'preview_id':plan['preview_id']})
        self.assertEqual(self.console.snapshot(),before)
        self.assertFalse((self.target/dashboard.installer.MANIFEST_RELATIVE).exists())

    def test_new_slot_created_during_save_is_never_replaced_or_rolled_back(self):
        team = [{'slot':f'team_slot_{index:02d}', 'duty':'researcher','model':'gpt-6-sol','effort':'medium','title':''}
                for index in range(1,51)]
        plan = self.console.preview({'preset':'focused','concurrency':4,'team_count':50,'team':team})
        leaf = self.target/dashboard.TEAM_SLOTS['team_slot_25']
        original = dashboard.installer.install_text_file
        def create_racing_file(**kwargs):
            if kwargs.get('relative') == dashboard.TEAM_SLOTS['team_slot_25']:
                leaf.write_text('OWNER_NEW_FILE = "keep"\n')
            return original(**kwargs)
        with mock.patch.object(dashboard.installer,'install_text_file',side_effect=create_racing_file):
            with self.assertRaises((FileExistsError,dashboard.installer.InstallError)):
                self.console.save({'preview_id':plan['preview_id']})
        self.assertEqual(leaf.read_text(),'OWNER_NEW_FILE = "keep"\n')
        self.assertFalse((self.target/dashboard.TEAM_SLOTS['team_slot_24']).exists())
        self.assertFalse((self.target/dashboard.installer.MANIFEST_RELATIVE).exists())

    def test_existing_managed_file_changed_during_save_is_preserved(self):
        initial = self.console.preview({'preset':'focused'})
        self.console.save({'preview_id':initial['preview_id']})
        explorer = self.target/dashboard.installer.ROLE_FILES['explorer']
        manifest = self.target/dashboard.installer.MANIFEST_RELATIVE
        old_manifest = manifest.read_bytes()
        plan = self.console.preview({'preset':'quality'})
        original = dashboard.installer.install_text_file
        def edit_after_precheck(**kwargs):
            if kwargs.get('relative') == dashboard.installer.ROLE_FILES['explorer']:
                explorer.write_bytes(explorer.read_bytes()+b'\n# OWNER CONCURRENT EDIT\n')
            return original(**kwargs)
        with mock.patch.object(dashboard.installer,'install_text_file',side_effect=edit_after_precheck):
            with self.assertRaisesRegex(dashboard.installer.InstallError,'changed during installation'):
                self.console.save({'preview_id':plan['preview_id']})
        self.assertIn(b'OWNER CONCURRENT EDIT', explorer.read_bytes())
        self.assertEqual(manifest.read_bytes(), old_manifest)
        self.assertEqual(self.console.settings()['roles']['owner']['model'], 'gpt-6-sol')

    def test_existing_crlf_config_and_agent_keep_raw_snapshot_through_restore(self):
        first = self.console.preview({'preset':'focused'})
        self.console.save({'preview_id':first['preview_id']})
        config = self.target/dashboard.installer.CONFIG_RELATIVE
        role = dashboard.installer.ROLE_FILES['explorer']
        agent = self.target/role
        manifest_path = self.target/dashboard.installer.MANIFEST_RELATIVE
        config.write_bytes(config.read_bytes().replace(b'\n', b'\r\n'))
        agent.write_bytes(agent.read_bytes().replace(b'\n', b'\r\n'))
        manifest = dashboard.installer.load_manifest(self.target)
        manifest['files'][str(role)]['sha256'] = dashboard.installer.sha256_path(agent)
        manifest_path.write_text(json.dumps(manifest))
        before = self.console.snapshot()
        change = self.console.preview({'preset':'quality'})
        self.assertTrue(change['can_save'], change['conflicts'])
        self.console.save({'preview_id':change['preview_id']})
        self.console.restore({})
        self.assertEqual(self.console.snapshot(), before)
        self.assertIn(b'\r\n', config.read_bytes())
        self.assertIn(b'\r\n', agent.read_bytes())

    def test_fifty_slot_restore_failure_rolls_back_and_can_retry(self):
        team = [{'slot':f'team_slot_{index:02d}', 'duty':'researcher','model':'gpt-6-sol','effort':'medium','title':''}
                for index in range(1,51)]
        full = self.console.preview({'preset':'focused','concurrency':4,'team_count':50,'team':team})
        self.console.save({'preview_id':full['preview_id']})
        smaller = self.console.preview({'preset':'focused','concurrency':4,'team_count':3,'team':team[:3]})
        self.console.save({'preview_id':smaller['preview_id']})
        before = self.console.snapshot()
        history = (self.target/dashboard.HISTORY).read_bytes()
        state = (self.target/dashboard.STATE).read_bytes()
        original = self.console.restore_bytes
        injected = False
        def fail_after_twenty_fifth(name, data, **kwargs):
            nonlocal injected
            original(name, data, **kwargs)
            if name == str(dashboard.TEAM_SLOTS['team_slot_25']) and not injected:
                injected = True
                raise OSError('injected restore failure')
        with mock.patch.object(self.console,'restore_bytes',side_effect=fail_after_twenty_fifth):
            with self.assertRaisesRegex(OSError,'injected restore failure'):
                self.console.restore({})
        self.assertEqual(self.console.snapshot(),before)
        self.assertEqual((self.target/dashboard.HISTORY).read_bytes(),history)
        self.assertEqual((self.target/dashboard.STATE).read_bytes(),state)
        self.console.restore({})
        self.assertEqual(self.console.settings()['team_count'],50)

    def test_manifest_dangling_symlink_inserted_during_save_is_not_replaced(self):
        plan = self.console.preview({'preset':'focused'})
        manifest = self.target/dashboard.installer.MANIFEST_RELATIVE
        outside = Path(self.tmp.name)/'outside.json'
        original = dashboard.installer.write_manifest
        def create_racing_symlink(**kwargs):
            manifest.symlink_to(outside)
            return original(**kwargs)
        with mock.patch.object(dashboard.installer,'write_manifest',side_effect=create_racing_symlink):
            with self.assertRaises((FileExistsError,dashboard.installer.InstallError)):
                self.console.save({'preview_id':plan['preview_id']})
        self.assertTrue(manifest.is_symlink())
        self.assertFalse(outside.exists())
        self.assertFalse((self.target/'.codex/agents/researcher.toml').exists())

    def test_fifty_slot_conflict_and_changed_preview_refuse_write(self):
        team = [{'slot':f'team_slot_{index:02d}', 'duty':'researcher','model':'gpt-6-sol','effort':'medium','title':''}
                for index in range(1,51)]
        plan = self.console.preview({'preset':'focused','concurrency':4,'team_count':50,'team':team})
        self.console.save({'preview_id':plan['preview_id']})
        last = self.target/dashboard.TEAM_SLOTS['team_slot_50']
        original = last.read_bytes()
        last.write_text(last.read_text()+'\n# owner edit\n')
        before = last.read_bytes()
        smaller = self.console.preview({'preset':'focused','concurrency':4,'team_count':3,'team':team[:3]})
        self.assertIn(str(dashboard.TEAM_SLOTS['team_slot_50']),smaller['conflicts'])
        with self.assertRaisesRegex(ValueError,'Managed file conflict'):
            self.console.save({'preview_id':smaller['preview_id']})
        self.assertEqual(last.read_bytes(),before)
        last.write_bytes(original)
        clean = self.console.preview({'preset':'focused','concurrency':4,'team_count':3,'team':team[:3]})
        self.assertTrue(clean['can_save'])
        last.write_bytes(original+b'\n# newer owner edit\n')
        with self.assertRaisesRegex(ValueError,'since preview'):
            self.console.save({'preview_id':clean['preview_id']})

    def test_team_rejects_invalid_slot_or_effort(self):
        team = [{'slot':'team_slot_01','duty':'researcher','model':'gpt-6-luna','effort':'ultra','title':''}]
        with self.assertRaisesRegex(ValueError, 'not supported'):
            self.console.preview({'preset':'focused','concurrency':1,'team':team})
        team[0]['effort']='high'
        team[0]['slot']='other'
        with self.assertRaisesRegex(ValueError, 'Invalid team slot'):
            self.console.preview({'preset':'focused','concurrency':1,'team':team})

    def test_backup_symlink_ancestor_refused_before_save(self):
        config=self.target/'.codex/config.toml'
        config.parent.mkdir()
        config.write_text('secret = "keep"\n')
        backup_root=self.target/dashboard.installer.BACKUP_RELATIVE
        backup_root.mkdir(parents=True)
        escape=Path(self.tmp.name)/'escape'
        escape.mkdir()
        with mock.patch.object(dashboard.installer,'timestamp_for_path',return_value='20260101T000000Z'):
            (backup_root/'20260101T000000Z').symlink_to(escape, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'Symlink backup path refused'):
                self.console.preview({'preset':'focused'})
        self.assertEqual(config.read_text(),'secret = "keep"\n')
        self.assertEqual(list(escape.iterdir()),[])

    def test_dangling_backup_leaf_symlink_refused_before_save(self):
        config=self.target/'.codex/config.toml'
        config.parent.mkdir()
        config.write_text('secret = "keep"\n')
        backup_root=self.target/dashboard.installer.BACKUP_RELATIVE
        leaf=backup_root/'20260101T000000Z'/'.codex/config.toml'
        leaf.parent.mkdir(parents=True)
        outside=Path(self.tmp.name)/'stolen.toml'
        leaf.symlink_to(outside)
        before=config.read_bytes()
        with mock.patch.object(dashboard.installer,'timestamp_for_path',return_value='20260101T000000Z'):
            with self.assertRaisesRegex(ValueError, 'Symlink backup path refused'):
                self.console.preview({'preset':'focused'})
        self.assertEqual(config.read_bytes(),before)
        self.assertFalse(outside.exists())

    def test_model_effort_pair_and_existing_legacy_pair(self):
        import model_catalog
        with mock.patch.object(model_catalog, 'discover_cli', return_value=None):
            self.console._catalog = model_catalog.catalog()
        with self.assertRaisesRegex(ValueError, 'reasoning effort is not supported'):
            self.console.preview({'preset':'balanced', 'roles':{'explorer':{'model':'gpt-6-luna','effort':'ultra'}}})
        self.assertTrue(self.console.preview({'preset':'balanced', 'roles':{'owner':{'model':'gpt-6.1-sol','effort':'ultra'}}})['can_save'])
        self.assertTrue(self.console.preview({'preset':'balanced', 'roles':{'owner':{'model':'gpt-6.1-sol','effort':'max'}}})['can_save'])
        self.assertTrue(self.console.preview({'preset':'balanced', 'roles':{'owner':{'model':'gpt-6-astra','effort':'ultra'}}})['can_save'])
        role = self.target/'.codex/agents/explorer.toml'
        role.parent.mkdir(parents=True)
        role.write_text('model="gpt-6-luna"\nmodel_reasoning_effort="ultra"\n')
        self.console.preview({'preset':'balanced', 'roles':{'explorer':{'model':'gpt-6-luna','effort':'ultra'}}})
        with self.assertRaisesRegex(ValueError, 'reasoning effort is not supported'):
            self.console.preview({'preset':'balanced', 'roles':{'explorer':{'model':'gpt-6-luna','effort':'minimal'}}})

    def test_every_builtin_preset_uses_catalog_supported_efforts(self):
        import model_catalog
        self.console._catalog = model_catalog.catalog()
        for preset in dashboard.installer.PRESETS:
            with self.subTest(preset=preset):
                self.assertTrue(self.console.preview({'preset':preset})['can_save'])
        self.assertTrue(all('astra' not in model for model, _ in dashboard.installer.PRESETS['focused'].values()))

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
            conn.request('GET','/api/models')
            result=conn.getresponse();self.assertEqual(result.status,200)
            models=json.loads(result.read())
            self.assertIn('gpt-6.1-sol',{item['id'] for item in models['models']})
            conn.request('GET','/api/usage')
            result=conn.getresponse()
            self.assertEqual(json.loads(result.read())['status'],'unavailable')
            conn.request('POST','/api/save', '{}', {'Content-Type':'application/json'})
            result=conn.getresponse(); self.assertEqual(result.status,403);result.read()
            headers={'Content-Type':'application/json','Origin':server.origin,'X-CSRF-Token':token}
            conn.request('POST','/api/models/refresh','{}',headers)
            result=conn.getresponse();self.assertEqual(result.status,200);result.read()
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

    def test_idle_browser_connection_does_not_block_other_requests(self):
        server = dashboard.Server(('127.0.0.1', 0), self.console)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        idle = socket.create_connection(('127.0.0.1', server.server_port), timeout=3)
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            conn.request('GET', '/')
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn(b'Codex', response.read())
        finally:
            idle.close();conn.close();server.shutdown();server.server_close();worker.join()

if __name__ == '__main__':
    unittest.main()
