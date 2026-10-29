"""只接续FFS第56段的精确Embedding HTTP552断点，不改活动源码或旧记录。"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import runpy
import shutil
import sys
from unittest.mock import patch

from configs.cle_weekly_embedding_recovery_20261027 import probe as native
from configs.cle_weekly_fs_embedding_timeout_20261028 import resume as prior
from configs.cle_weekly_fs_checkpoint_20261028.resume import checkpoint_replace_retry
from configs.cle_weekly_http403_recovery_20261028 import resume as launcher
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

RUN, FFS = prior.RUN, prior.FFS
MODULE = 'configs.cle_weekly_fs_embedding_552_20261028.resume'
EVIDENCE = RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_segment056_attempt33'
IDENTITY = '79c7df98f0e2a1e9e7221dde1dfd97ca327521e5708ccce838533c9c818761be-000001'
EXPECTED = 2250
read = prior.read


@lru_cache(maxsize=1)
def evaluate_module():
    """保留既有孤立代理项JSON转义修复；模型输入和解码值不变。"""
    return runpy.run_path(str(FFS / 'recover_utf8_20261027.py'))['evaluate']


def compare_completed(rows, sources):
    prior.EXPECTED = EXPECTED
    return prior.compare_completed(rows, sources)


@lru_cache(maxsize=1)
def probe():
    """实读所有未决及同输入wire，封网沿原P7定位断点；不发模型或向量请求。"""
    sources = list(map(Path, read(FFS / 'execution_index.json')['segments']))
    if len(sources) != 56:
        raise ReplayStop('source_segments_changed')
    pending = prior.unresolved(sources)
    if (len(pending) != 1 or pending[0][0].parent.parent.name != 'embedding'
            or pending[0][1]['identity'] != IDENTITY):
        raise ReplayStop('not_the_single_observed_embedding_552')
    path, failed = pending[0]
    if (failed['status'] != 'failed_or_unresolved' or failed['settings'] !=
            {'model': 'text-embedding-3-large', 'operation': 'embedding'}):
        raise ReplayStop('pending_status_or_settings_changed')
    # 该请求的精确域名带EO标识；552按官方EdgeOne定义为源站TCP建连超时。
    # 这是结合域名现场的分类推断；不把401/403/额度或其他HTTP码纳入例外。
    host = read(EVIDENCE / 'exact_embedding_host_connectivity.json')
    if (host['request'] != 'unauthenticated GET https://api.chatanywhere.tech/'
            or host['status'] != 200 or not host['headers'].get('EO-LOG-UUID')):
        raise ReplayStop('exact_host_edgeone_evidence_missing')
    texts = json.loads(failed['prompt'])
    matches, physical, embedding_http = [], 0, 0
    for source in sources:
        for request in (source / 'wire').glob('*.request.json'):
            physical += 1
            wire = read(request)
            body = wire.get('body', {})
            embedding_http += body.get('model') == 'text-embedding-3-large'
            if body.get('model') != 'text-embedding-3-large' or body.get('input') != texts:
                continue
            status_path = request.with_name(request.name.replace('.request.json', '.status.json'))
            raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
            status = read(status_path)
            if (wire['url'] != 'https://api.chatanywhere.tech/v1/embeddings'
                    or status.get('status') != 'transport_error' or status.get('error_type') != 'HTTPError'
                    or status.get('http_status') != 552 or raw.exists()):
                raise ReplayStop('saved_response_or_different_failure_for_same_input')
            matches.append({'request_path': str(request), 'status_path': str(status_path),
                            'status': status, 'raw_path': str(raw), 'raw_exists': False})
    budget = read(sources[-1] / 'budget.json')
    summary, state = read(sources[-1] / 'summary.json'), read(sources[-1] / 'state.json')
    if (len(matches) != 1 or physical != budget['transport_attempts_including_prior']
            or (budget['cap_tokens'], budget['cap_HTTP'], budget['cap_embedding_HTTP']) !=
            (640900000, 134712, 47680) or physical >= budget['cap_HTTP']
            or embedding_http >= budget['cap_embedding_HTTP']
            or budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']
            or summary['completed'] != EXPECTED or summary['planned'] != 2980
            or state['completed_P7'] != EXPECTED):
        raise ReplayStop('budget_or_completed_prefix_changed')
    audit = {'segments': list(map(str, sources)), 'records': [str(path)],
             'public': {k: failed[k] for k in ('settings', 'prompt', 'selector')},
             'matching_wire': matches, 'physical_requests': physical, 'embedding_HTTP': embedding_http,
             'budget': {k: v for k, v in budget.items() if k != 'entries'},
             'summary': summary, 'state': state,
             'classification': 'inferred_EdgeOne_HTTP552_origin_TCP_connect_timeout',
             'classification_source': 'https://intl.cloud.tencent.com/zh/document/product/1145/58009',
             'exact_host_evidence': str(EVIDENCE / 'exact_embedding_host_connectivity.json')}
    evaluate_module()
    checked_path = EVIDENCE / 'offline_checks.json'
    if checked_path.exists():
        checked = read(checked_path)
        if checked['audit'] != audit:
            raise ReplayStop('saved_prefix_sources_changed')
        return checked
    with (sources[-1] / 'rows.jsonl').open(encoding='utf-8') as stream:
        reused = compare_completed((json.loads(line) for line in stream), sources)
    write_json(EVIDENCE / 'completed_reuse_verification.json', reused)
    # 原分类器未支持HTTP552；只替换已实读核对的分类输入，回放仍走原入口。
    with patch.object(native, 'inspect', return_value={
            'segments': audit['segments'], 'pending_identity': IDENTITY}), \
            patch('socket.socket.connect', side_effect=ReplayStop('offline_network_forbidden')):
        prefix = native.probe()
    if prefix['status'] != 'passed' or prefix['new_HTTP'] != 0:
        raise ReplayStop('exact_embedding_prefix_not_verified')
    result = {'status': 'passed', 'new_HTTP': 0, 'audit': audit, 'native_prefix': prefix,
              'model_prefix': {'saved_rows': EXPECTED}, 'socket_network_blocked': True,
              'old_records_modified': False, 'scientific_protocol_changed': False}
    write_json(checked_path, result)
    return result


def run():
    """新段复用全部成功响应、原验证和三worker，累计预算中的未知用量不清零。"""
    checked = probe()
    evaluate = evaluate_module()
    allowed = set(checked['audit']['records'])
    evaluate.base.unresolved_requests = lambda sources: [str(p) for p, _ in prior.unresolved(sources)
                                                        if str(p) not in allowed]
    original = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        before = read(self.sources[-1] / 'budget.json')
        after = self.io.budget.snapshot()
        if (len(before['entries']) != len(after['entries']) or any(
                any(a[k] != b[k] for k in ('model', 'bound', 'usage'))
                for a, b in zip(before['entries'], after['entries'])) or any(
                before[k] != after[k] for k in ('cap_tokens', 'cap_HTTP', 'cap_embedding_HTTP',
                                               'charged_tokens_including_unknown_and_inflight_bounds'))):
            raise ReplayStop('cumulative_budget_or_unknown_usage_changed')
        budget_check = {'status': 'passed', 'retained_entries': len(before['entries']),
                        'model_bound_usage_unchanged': True, 'caps_unchanged': True,
                        'unknown_HTTP_retained': sum(x['usage'] is None for x in before['entries']),
                        'new_HTTP_before_verification': 0}
        write_json(EVIDENCE / 'budget_rollforward_check.json', budget_check)
        self.io.save('budget_rollforward_check', budget_check)
        reused = compare_completed(self.rows, self.sources)
        write_json(EVIDENCE / 'native_reuse_verification.json', reused)
        self.io.save('completed_reuse_verification', reused)
        self.io.save('authorized_embedding_552', {
            'identity': IDENTITY, 'evidence': str(EVIDENCE / 'offline_checks.json'),
            'classification': checked['audit']['classification'],
            'previous_execution_and_cost_unknown_retained': True})
        original_embedding, original_request = self.io.embedding, self.io.request_for

        def embedding(texts, call):
            if texts == json.loads(checked['audit']['public']['prompt']):
                self.io.save('authorized_embedding_boundary', {
                    'identity': IDENTITY, 'previous_execution_and_cost_unknown': True})
            return original_embedding(texts, call)

        def request_for(cell):
            request = original_request(cell)

            def tracked(prompt):
                response = request(prompt)
                journal = self.io.journal(cell)
                if journal.consumed:
                    self.io.save('recovery_reused_responses/' + cell, {
                        'cell': cell, 'identities': sorted(journal.consumed), 'new_HTTP_for_reuse': 0})
                return response
            return tracked

        self.io.embedding, self.io.request_for = embedding, request_for
        target = self.out / 'source_bundle_external/embedding_552_resume.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target)

    evaluate.FrozenFS.__init__ = initialize
    with checkpoint_replace_retry(FFS / 'segment_057'), verified_proxy_transport():
        sys.argv = [evaluate.__name__, 'resume', '--workers', '3']
        evaluate.main()


def launch():
    """沿用实际CIM容量检查、隐藏启动、PID登记和到期时段bootstrap。"""
    launcher.probe = lambda kind: probe()
    launcher.MODULE, launcher.EVIDENCE = MODULE, EVIDENCE
    return launcher.launch('ffs')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    parser.add_argument('--kind', choices=['ffs'], default='ffs')
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action]()
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'audit'}, ensure_ascii=False))
