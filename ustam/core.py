"""Hub operations and bound previews over provider adapters."""
import copy
from contextlib import contextmanager
import threading
import time
import uuid
from .storage import PROVIDERS, StateStore
from .discovery import canonical, discover, project, pick_directory

class Hub:
    def __init__(self, state_dir=None, adapters=None, jobs=None):
        self.store = StateStore(state_dir)
        if adapters is None:
            from .adapters import AdapterManager
            adapters = AdapterManager()
        self.adapters = adapters
        self.jobs = jobs
        self.previews = {}
        self.lock = threading.RLock()
        self.path_locks = {}
        self.picker_lock = threading.Lock()
    def close(self):
        if self.jobs and hasattr(self.jobs, 'close'):
            self.jobs.close()
        self.adapters.close()
    def bootstrap(self):
        data = self.store.read()
        data['providers'] = list(PROVIDERS)
        data['capabilities'] = {'native_picker': {'endpoint': '/api/projects/pick'}, 'jobs': self.jobs is not None, 'providers': {provider: {'max_concurrency': limit} for provider, limit in (('codex', 10), ('claude', 20), ('opencode', 1))}}
        return data
    def provider(self, value):
        if value not in PROVIDERS:
            raise ValueError('Unknown provider')
        return value
    def targets(self, ids, validate_paths=True):
        if not isinstance(ids, list) or not ids or len(ids) > 100 or any(not isinstance(x, str) for x in ids):
            raise ValueError('Select between 1 and 100 projects')
        registry = {p['id']: p for p in self.store.read()['projects']}
        result = []
        for ident in dict.fromkeys(ids):
            if ident not in registry:
                raise ValueError('Unknown registered project')
            entry = registry[ident]
            if validate_paths:
                try:
                    current = canonical(entry['path'])
                except OSError as error:
                    raise ValueError('Project folder is unavailable; refresh the registry') from error
                if current != entry['path']:
                    raise ValueError('Project path changed; refresh registry')
            result.append(entry)
        return result
    def pick_project_directory(self, body):
        if body not in ({}, {"kind": "directory"}):
            raise ValueError("Folder picker accepts only an empty object or directory kind")
        if not self.picker_lock.acquire(blocking=False):
            raise ValueError("A folder picker is already open")
        try:
            path = pick_directory()
            return {"path": path, "cancelled": path is None}
        finally:
            self.picker_lock.release()
    def projects(self, body):
        action = body.get('action')
        snapshot = self.store.read()
        if action == 'add':
            entry = project(body.get('path'))
            def change(data):
                data['projects'] = [p for p in data['projects'] if p['id'] != entry['id']] + [entry]
        elif action == 'refresh':
            roots = body.get('roots', snapshot['roots'])
            if not isinstance(roots, list) or len(roots) > 20:
                raise ValueError('Select at most 20 discovery roots')
            roots = list(dict.fromkeys(canonical(root) for root in roots))
            entries = discover(roots)
            def change(data):
                # Explicit manual additions remain registered across discovery refreshes.
                manual = [p for p in data['projects'] if p.get('manual')]
                combined = {p['id']: p for p in entries + manual}
                data['roots'], data['projects'] = roots, list(combined.values())
                data['selected_projects'] = [x for x in data['selected_projects'] if x in combined]
        elif action == 'remove':
            ident = body.get('id')
            self.targets([ident])
            def change(data):
                data['projects'] = [p for p in data['projects'] if p['id'] != ident]
                data['selected_projects'] = [x for x in data['selected_projects'] if x != ident]
                data['project_overrides'].pop(ident, None)
        elif action == 'selection':
            ids = body.get('ids', [])
            if ids:
                self.targets(ids)
            elif not isinstance(ids, list):
                raise ValueError('ids must be a list')
            selected = body.get('providers', snapshot['selected_providers'])
            self.validate_providers(selected)
            def change(data):
                data['selected_projects'] = list(dict.fromkeys(ids))
                data['selected_providers'] = selected
        else:
            raise ValueError('Unknown project action')
        if action == 'add':
            entry['manual'] = True
        return self.store.update(change, body.get('revision', snapshot['revision']))
    def validate_providers(self, values):
        if not isinstance(values, list) or not values:
            raise ValueError('Select at least one provider')
        for value in values:
            self.provider(value)
    def orchestra(self, value):
        if not isinstance(value, dict):
            raise ValueError('Orchestra must be an object')
        value = copy.deepcopy(value)
        value.setdefault('id', uuid.uuid4().hex)
        if value.get('version', value.get('schema', 1)) != 1:
            raise ValueError('Unsupported orchestra version')
        if 'profile' in value and not isinstance(value['profile'], str):
            raise ValueError('Profile must be a string')
        if not isinstance(value['id'], str) or not value['id'] or not isinstance(value.get('name'), str) or not value['name'].strip():
            raise ValueError('Orchestra id and name are required')
        self.provider(value.get('provider'))
        if not isinstance(value.get('chief'), dict) or not isinstance(value.get('helpers'), list):
            raise ValueError('Chief and helpers are required')
        concurrency = value.get('concurrency')
        if isinstance(concurrency, bool) or not isinstance(concurrency, int) or not 1 <= concurrency <= {'codex': 10, 'claude': 20, 'opencode': 1}[value['provider']]:
            raise ValueError('Concurrency is unsupported by the selected provider')
        helper_ids = set()
        for helper in value['helpers']:
            if not isinstance(helper, dict) or any(not isinstance(helper.get(key), str) or not helper[key] for key in ('id', 'role', 'name', 'model')):
                raise ValueError('Each helper needs id, role, name and model')
            if not isinstance(helper.get('effort'), str):
                raise ValueError('Each helper needs an explicit effort string')
            if helper['id'] in helper_ids:
                raise ValueError('Helper ids must be unique')
            helper_ids.add(helper['id'])
        if not isinstance(value['chief'].get('model'), str) or not value['chief']['model'] or not isinstance(value['chief'].get('effort'), str):
            raise ValueError('Chief needs model and effort')
        return value
    def orchestras(self, body):
        if body.get('action') == 'save':
            entry = self.orchestra(body.get('orchestra'))
            def change(data):
                data['orchestras'] = [p for p in data['orchestras'] if p['id'] != entry['id']] + [entry]
        elif body.get('action') == 'remove':
            ident = body.get('id')
            if not isinstance(ident, str):
                raise ValueError('Orchestra id is required')
            def change(data):
                data['orchestras'] = [p for p in data['orchestras'] if p['id'] != ident]
        else:
            raise ValueError('Unknown orchestra action')
        return self.store.update(change, body.get('revision'))
    def defaults(self, body):
        for key in ('defaults', 'override'):
            if key in body and not isinstance(body[key], dict):
                raise ValueError(key + ' must be an object')
        if 'selected_providers' in body:
            self.validate_providers(body['selected_providers'])
        if 'project_id' in body:
            self.targets([body['project_id']])
        def change(data):
            if 'defaults' in body:
                data['defaults'] = body['defaults']
            if 'selected_providers' in body:
                data['selected_providers'] = body['selected_providers']
            if 'project_id' in body:
                data['project_overrides'][body['project_id']] = body.get('override', {})
        return self.store.update(change, body.get('revision'))
    def payload(self, body):
        payload = body.get('payload', {})
        if not isinstance(payload, dict):
            raise ValueError('payload must be an object')
        if 'orchestra' in payload:
            payload = payload['orchestra']
        if any(key in payload for key in ('chief', 'helpers', 'provider')):
            payload = self.orchestra(payload)
            if payload['provider'] != body['provider']:
                raise ValueError('Cross-provider orchestra requires explicit remapping before preview')
        return copy.deepcopy(payload)
    def _path_lock(self, path):
        with self.lock:
            return self.path_locks.setdefault(path, threading.RLock())
    @contextmanager
    def mutation(self, path):
        # The jobs manager starts under this same lock, preventing a check/start race.
        guard = self.jobs.lock if self.jobs and hasattr(self.jobs, "lock") else self.lock
        with guard:
            if self.jobs and path in getattr(self.jobs, "active", {}):
                raise ValueError("A job is active for this project; stop it before changing configuration")
            yield
    def batch(self, action, body):
        provider = self.provider(body.get('provider'))
        targets = self.targets(body.get('project_ids'), validate_paths=False)
        payload = self.payload(body)
        results = []
        for target in targets:
            result = {'project_id': target['id'], 'ok': True}
            try:
                with self._path_lock(target['path']):
                    # Registered stale paths fail individually; unknown IDs fail the request.
                    self.targets([target['id']])
                    if action == 'preview':
                        revision = self.store.read()['revision']
                        output = self.adapters.preview(provider, target['path'], payload)
                        if not isinstance(output, dict) or not output.get('preview_id'):
                            raise ValueError('Adapter did not return a bound preview')
                        ident = uuid.uuid4().hex
                        with self.lock:
                            self.previews = {key: item for key, item in self.previews.items() if time.monotonic() - item['created'] <= 300}
                            if len(self.previews) >= 1000:
                                raise ValueError('Too many pending previews; apply or restart the hub')
                            self.previews[ident] = {'project': target, 'provider': provider, 'payload': payload, 'revision': revision, 'adapter_id': output['preview_id'], 'created': time.monotonic()}
                        result.update(preview_id=ident, preview=output)
                    else:
                        if action == 'restore':
                            with self.store.lock, self.mutation(target['path']):
                                self.targets([target['id']])
                                output = self.adapters.restore(provider, target['path'], payload)
                        else:
                            output = getattr(self.adapters, action)(provider, target['path'])
                        result['result'] = output
            except Exception as error:
                result.update(ok=False, error=str(error))
            results.append(result)
        return {'results': results}
    def apply(self, body):
        ids = body.get('preview_ids')
        if not isinstance(ids, list) or not ids or len(ids) > 100 or any(not isinstance(x, str) for x in ids):
            raise ValueError('Select valid preview ids')
        results = []
        for ident in ids:
            with self.lock:
                bound = self.previews.pop(ident, None)
            result = {'preview_id': ident, 'ok': True}
            try:
                if not bound:
                    raise ValueError('Unknown or already consumed preview')
                target = bound['project']
                result['project_id'] = target['id']
                with self._path_lock(target['path']), self.store.lock:
                    current = self.targets([target['id']])[0]
                    if current['path'] != target['path'] or bound['revision'] != self.store.read()['revision'] or time.monotonic() - bound['created'] > 300:
                        raise ValueError('Preview expired or metadata changed; preview again')
                    with self.mutation(target['path']):
                        result['result'] = self.adapters.apply(bound['provider'], target['path'], bound['adapter_id'])
            except Exception as error:
                result.update(ok=False, error=str(error))
            results.append(result)
        return {'results': results}
    def job_action(self, body):
        if not self.jobs:
            raise ValueError('Job manager unavailable')
        action = body.get('action')
        if action == 'plan':
            payload = copy.deepcopy(body)
            targets = self.targets(body.get('project_ids'))
            self.provider(body.get('provider'))
            payload['targets'] = [{'project_id': p['id'], 'path': p['path']} for p in targets]
            # Never pass caller-supplied paths through to jobs.
            for key in ('path', 'target', 'paths'):
                payload.pop(key, None)
            return {'job': self.jobs.plan(payload)}
        if action in ('start', 'cancel', 'resume'):
            ident = body.get('id', body.get('job_id'))
            if not isinstance(ident, str):
                raise ValueError('Job id required')
            if action in ('start', 'resume'):
                # Lock order is metadata then jobs, including Runtime.prepare.
                with self.store.lock:
                    job = self.jobs.get(ident)
                    registered = self.targets([job['project_id']])[0]
                    if registered['path'] != job['path']:
                        raise ValueError('Job project identity changed; create a new plan')
                    return {'job': getattr(self.jobs, action)(ident)}
            return {'job': self.jobs.cancel(ident)}
        raise ValueError('Unknown job action')
