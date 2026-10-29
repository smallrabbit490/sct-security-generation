"""Resume existing Q and FFS segments through the same verified endpoint."""
import argparse
import json
import runpy
import socket
import ssl
import subprocess
import sys
from pathlib import Path

from configs.cle_v41_relation_20261026.wiring import SETTINGS
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
from .transport import verified_proxy_transport

ROOT = Path(__file__).resolve().parents[2]
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')


def proxy_ready():
    with socket.create_connection(('127.0.0.1', 7897), timeout=5) as sock:
        sock.sendall(b'CONNECT api.chatanywhere.org:443 HTTP/1.1\r\nHost: api.chatanywhere.org:443\r\n\r\n')
        reply = b''
        while b'\r\n\r\n' not in reply and len(reply) < 4096:
            data = sock.recv(1024)
            if not data:
                break
            reply += data
        if b' 200 ' not in reply.split(b'\r\n', 1)[0]:
            return False
        with ssl.create_default_context().wrap_socket(sock, server_hostname='api.chatanywhere.org'):
            return True


def helper(kind):
    folder = 'FQ_LEARN' if kind == 'q' else 'FFS'
    return runpy.run_path(str(RUN / folder / 'transport_resume_stream_20261027.py'))


def active(kind):
    command = 'Get-CimInstance Win32_Process -Filter "Name=\'python.exe\'" | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress'
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, text=True, check=True)
    values = json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(values, dict):
        values = [values]
    folder = 'FQ_LEARN' if kind == 'q' else 'FFS'
    for item in values:
        line = item.get('CommandLine') or ''
        if ' run' not in line and ' resume' not in line:
            continue
        if ('cle_weekly_proxy_recovery_20261027.runner' in line and '--kind ' + kind in line
                or folder in line and ('transport_resume' in line or 'recovery_1020' in line)
                or kind == 'q' and ('cle_weekly_full_20261027.learn' in line or 'cle_weekly_recovery_20261027.recover' in line)
                or kind == 'ffs' and ('cle_weekly_fs_20261027.evaluate' in line or 'recover_utf8_20261027.py' in line)):
            return True
    return False


def launch(kind):
    ensure_model_call_allowed(SETTINGS['model'])
    if active(kind):
        return {'status': 'already_running', 'kind': kind}
    if not proxy_ready():
        return {'status': 'proxy_unavailable', 'kind': kind}
    checked = helper(kind)['probe']()
    if checked.get('status') != 'passed':
        return {'status': 'probe_not_passed', 'kind': kind}
    logs = RUN / ('FQ_LEARN' if kind == 'q' else 'FFS')
    with (logs / 'proxy_recovery.stdout.log').open('a', encoding='utf-8') as stdout, (logs / 'proxy_recovery.stderr.log').open('a', encoding='utf-8') as stderr:
        process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
            'configs.cle_weekly_proxy_recovery_20261027.runner', 'run', '--kind', kind],
            cwd=ROOT, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    return {'status': 'launched', 'kind': kind, 'pid': process.pid, 'probe': checked}


def run(kind):
    h = helper(kind)
    checked = h['probe']()
    if checked.get('status') != 'passed':
        raise RuntimeError('saved_prefix_probe_not_passed')
    with verified_proxy_transport():
        if kind == 'q':
            with h['runtime']():
                h['learn'].coordinate(resume_stage=checked['stage'])
        else:
            sys.argv = ['configs.cle_weekly_fs_20261027.evaluate', 'resume', '--workers', '3']
            h['evaluate'].main()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['launch', 'run'])
    parser.add_argument('--kind', choices=['q', 'ffs'], required=True)
    args = parser.parse_args()
    if args.action == 'launch':
        print(json.dumps(launch(args.kind), ensure_ascii=False))
    else:
        run(args.kind)


if __name__ == '__main__':
    main()
