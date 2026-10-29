"""Resume FFS after an explicitly authorized and replayed embedding interruption."""
import json
import runpy
import subprocess
import sys
from pathlib import Path

from configs.cle_weekly_embedding_recovery_20261027.probe import inspect, probe, ROOT
from configs.cle_weekly_proxy_recovery_20261027.runner import active, proxy_ready
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from configs.cle_v41_relation_20261026.wiring import SETTINGS
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
from methods.sct_trajectory.replay_journal import ReplayStop, write_json


def run(focus):
    info = inspect()
    checked = probe(focus)
    if checked['status'] != 'passed' or checked['pending_identity'] != info['pending_identity']:
        raise ReplayStop('embedding_prefix_not_verified')
    utf = runpy.run_path(str(ROOT / 'recover_utf8_20261027.py'))
    evaluate = utf['evaluate']
    evaluate.base.unresolved_requests = lambda sources: []
    original_init = evaluate.FrozenFS.__init__

    def guarded_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        original = self.io.embedding
        expected = json.loads(info['pending_public']['prompt'])
        pending = True
        def embedding(texts, call):
            nonlocal pending
            if pending:
                if texts != expected:
                    raise ReplayStop('different_embedding_before_verified_pending')
                self.io.save('authorized_embedding_boundary', {
                    'identity': info['pending_identity'], 'probe': checked,
                    'previous_execution_and_cost_unknown': True})
                result = original(texts, call)
                pending = False
                return result
            return original(texts, call)
        self.io.embedding = embedding

    evaluate.FrozenFS.__init__ = guarded_init
    with verified_proxy_transport():
        sys.argv = ['configs.cle_weekly_fs_20261027.evaluate', 'resume', '--workers', '3']
        evaluate.main()


def launch(focus):
    ensure_model_call_allowed(SETTINGS['model'])
    command = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'configs.cle_weekly_embedding_recovery_20261027.resume run|configs.cle_weekly_fs_20261027.embedding_resume run' } | Select-Object -ExpandProperty ProcessId"
    existing = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                              capture_output=True, text=True, check=True)
    if active('ffs') or existing.stdout.strip():
        return {'status': 'already_running'}
    if not proxy_ready():
        return {'status': 'proxy_unavailable'}
    checked = probe(focus)
    if checked['status'] != 'passed':
        return {'status': 'probe_failed', 'probe': checked}
    with (ROOT / 'embedding_resume.stdout.log').open('a', encoding='utf-8') as out, \
         (ROOT / 'embedding_resume.stderr.log').open('a', encoding='utf-8') as err:
        process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
            'configs.cle_weekly_embedding_recovery_20261027.resume', 'run', focus], cwd=evaluate_root(),
            stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
    result = {'status': 'launched', 'pid': process.pid, 'probe': checked}
    write_json(ROOT / 'embedding_resume_launch.json', result)
    return result


def evaluate_root():
    return Path(__file__).resolve().parents[2]


if __name__ == '__main__':
    if sys.argv[1] == 'launch':
        print(json.dumps(launch(sys.argv[2]), ensure_ascii=False))
    elif sys.argv[1] == 'run':
        run(sys.argv[2])
    else:
        raise ValueError('expected launch or run')
