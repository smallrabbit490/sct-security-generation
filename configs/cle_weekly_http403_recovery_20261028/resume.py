"""仅接续已核实的两条403逻辑请求；先精确零API重放，再沿原生流程运行。"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import urllib.error

from tools.cle_live_workbench.time_policy import install, child_environment
install()
from tools.cle_live_workbench import app
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

RUN = app.RUN
EVIDENCE = RUN/'workbench_monitor/maintenance_20261028_provider403'
AUTH = EVIDENCE/'confirmed_rejected_request_recovery.json'
MODULE = 'configs.cle_weekly_http403_recovery_20261028.resume'
TARGETS = {'q': ('K2_861', 'a9b9aae6ff6118e6147853da8258aafdafb2db9f6148c4b4be3c1366914a5789-000001'),
           'ffs': ('1086_r2_BM', '9f58795c1454fcf5ae75f599501c0efb83d70e7ed2fa8b11f82aa6e6dc456c39-000001')}


def helper(kind):
    evidence = app.read_json(EVIDENCE/'single_token_model_access.json', {})
    if evidence.get('http_status') != 200 or evidence.get('model') != 'deepseek-v4.1-flash-1017':
        raise ReplayStop('same_model_access_not_confirmed')
    authorization = app.read_json(AUTH, {})
    if authorization.get('targets') != {k: list(v) for k, v in TARGETS.items()}:
        raise ReplayStop('current_rejected_requests_not_registered')
    if authorization.get('retry_enabled') is False:
        raise ReplayStop('confirmed_provider_balance_block_requires_restored_credit')
    folder = 'FQ_LEARN' if kind == 'q' else 'FFS'
    h = runpy.run_path(str(RUN/folder/'transport_resume_stream_20261027.py'))
    original = h['classify']

    def classify(sources):
        pending, rejected = original(sources)
        remaining = []
        for text in rejected:
            path = Path(text)
            record = app.read_json(path)
            cell = path.parent.parent.name
            if (cell, record.get('identity')) != TARGETS[kind]:
                remaining.append(text)
                continue
            diagnostics = record.get('diagnostics') or []
            if (record.get('status') != 'failed_or_unresolved' or not diagnostics or
                    any(d.get('category') != 'http_error' or d.get('http_status') != 403 for d in diagnostics)):
                raise ReplayStop('expected_exact_known_HTTP403_rejection')
            segment = path.parents[3]
            matches = []
            for request in (segment/'wire').glob('*.request.json'):
                body = app.read_json(request).get('body', {})
                if (body.get('model') != record['settings']['model'] or
                        body.get('messages') != [{'role': 'user', 'content': record['prompt']}]):
                    continue
                status = app.read_json(request.with_name(request.name.replace('.request.json', '.status.json')), {})
                response = request.with_name(request.name.replace('.request.json', '.response.raw'))
                matches.append(status.get('http_status') == 403 and not response.exists())
            if not matches or not all(matches):
                raise ReplayStop('rejection_wire_not_exact_or_saved_response_exists')
            pending.setdefault(TARGETS[kind], []).append({'path': text,
                **{k: record[k] for k in ('settings', 'prompt', 'selector')}})
        return pending, remaining

    h['probe'].__globals__['classify'] = classify
    h['probe'].__globals__['AUTH'] = AUTH
    if kind == 'q':
        h['probe'].__globals__['R'] = EVIDENCE/'q_prefix'
    return h


def probe(kind):
    h = helper(kind)
    result = h['probe']() if kind == 'q' else h['probe'](label='confirmed_http403_20261028')
    if result.get('status') != 'passed' or result.get('new_HTTP') != 0:
        raise ReplayStop('rejected_request_prefix_not_exact')
    write_json(EVIDENCE/(kind+'_prefix_check.json'), result)
    return result


@contextmanager
def capture_rejection():
    from configs.cle_v41_relation_20261026.execution import StudyExecution
    original = StudyExecution.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        if not kwargs.get('live'):
            return
        self.save('confirmed_http403_recovery', {'authorization': str(AUTH),
            'classification': 'known_HTTP403_rejection_after_same_model_access_200',
            'not_a_TLS_exception': True, 'old_failures_and_unknown_usage_retained': True})
        target = self.root/'source_bundle_external'
        target.mkdir(exist_ok=True)
        shutil.copy2(Path(__file__), target/'confirmed_http403_resume.py')
        shutil.copy2(AUTH, target/AUTH.name)
        transport = self.physical_open
        counter = [0]

        def opened(request, *a, **kw):
            try:
                return transport(request, *a, **kw)
            except urllib.error.HTTPError as exc:
                raw = exc.read(16000)
                try:
                    error = json.loads(raw).get('error', {})
                    detail = {k: error[k] for k in ('message', 'type', 'code') if k in error}
                except (ValueError, TypeError):
                    detail = {'body_excerpt': raw.decode('utf-8', 'replace')[:1200]}
                clean = re.sub(r'(ApiKey\s*[:：]\s*)[^)\n]+', r'\1[redacted]',
                               json.dumps(detail, ensure_ascii=False), flags=re.I)
                clean = re.sub(r'sk-[A-Za-z0-9_.*-]+', '[redacted]', clean)
                counter[0] += 1
                self.save('provider_http_error_%04d' % counter[0],
                          {'http_status': exc.code, 'error': json.loads(clean), 'headers_recorded': False})
                raise
        self.physical_open = opened

    StudyExecution.__init__ = initialize
    try:
        yield
    finally:
        StudyExecution.__init__ = original


def launch(kind):
    snapshot = app.Collector(RUN).collect(app.process_inventory())
    package = 'FQ_LEARN' if kind == 'q' else 'FFS'
    if any(p['package'] == package for p in snapshot['processes']):
        return {'status': 'already_running'}
    slots = 1 if kind == 'q' else 3
    if snapshot['workers'] + slots > 4 or kind == 'ffs' and any(
            p['package'] != 'FQ_LEARN' for p in snapshot['processes']):
        raise ReplayStop('required_worker_slots_not_available')
    checked = probe(kind)
    command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, 'run', '--kind', kind]
    with (EVIDENCE/(kind+'_stdout.log')).open('ab') as stdout, (EVIDENCE/(kind+'_stderr.log')).open('ab') as stderr:
        process = subprocess.Popen(command, cwd=app.ROOT, env=child_environment(__import__('os').environ),
            stdout=stdout, stderr=stderr, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    registry = RUN/'workbench_monitor/autonomy/registered_workers.json'
    entries = app.read_json(registry, [])
    entries.append({'pid': process.pid, 'package': package, 'workers': slots,
                    'command_marker': MODULE+' run --kind '+kind})
    write_json(registry, entries)
    result = {'status': 'launched', 'pid': process.pid, 'workers': slots,
              'prefix_check': str(EVIDENCE/(kind+'_prefix_check.json')), 'command': command}
    write_json(EVIDENCE/(kind+'_launch.json'), result)
    return result


def run(kind):
    probe(kind)
    h = helper(kind)
    from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
    with verified_proxy_transport(), capture_rejection():
        if kind == 'q':
            with h['runtime']():
                h['learn'].coordinate(resume_stage=app.read_json(EVIDENCE/'q_prefix_check.json')['stage'])
        else:
            sys.argv = ['configs.cle_weekly_fs_20261027.evaluate', 'resume', '--workers', '3']
            h['evaluate'].main()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    parser.add_argument('--kind', choices=['q', 'ffs'], required=True)
    args = parser.parse_args()
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action](args.kind)
    if result is not None:
        # 输出不含prompt、HTTP头或凭据。
        print(json.dumps({k: v for k, v in result.items() if k != 'targets'}, ensure_ascii=False))
