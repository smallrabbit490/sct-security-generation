"""接续K3题1344已结束进程的硬超时；旧请求、未知用量和冻结流程保持。"""
import argparse
import json
from pathlib import Path
import shutil

from configs.cle_weekly_http403_recovery_20261028 import resume as original
from configs.cle_weekly_proxy_recovery_20261027 import transport
from configs.cle_weekly_q_tls12_20261028.resume import tls12_transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

MODULE = 'configs.cle_weekly_q_timeout_1344_20261028.resume'
EVIDENCE = original.RUN / 'workbench_monitor/autonomy/repair_evidence/Q.run_20261028T161800_attempt26'
CELL = 'K3_1344'
IDENTITY = 'cb5c96ef3d6fb0bc73c4d5f536ff0f2f99d203ebfe993c723d59247cc8683423-000001'
SEGMENT = original.RUN / 'FQ_LEARN/K3/segment_009'
TARGET = SEGMENT / 'journals' / CELL / 'requests' / (IDENTITY + '.json')
native_helper = original.helper


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def inspect_timeout(sources):
    """仅准入本次无响应的TimeoutError；认证、额度或已有成功响应均不豁免。"""
    if SEGMENT not in list(map(Path, sources)):
        raise ReplayStop('hard_timeout_source_prefix_changed')
    record = read(TARGET)
    from configs.cle_v41_relation_20261026.wiring import SETTINGS
    diagnostics = record.get('diagnostics') or []
    if (record.get('identity') != IDENTITY or record.get('status') != 'failed_or_unresolved'
            or record.get('settings') != SETTINGS or record.get('selector') is not True
            or record.get('error_type') != 'TimeoutError' or len(diagnostics) != 1
            or diagnostics[0].get('category') != 'hard_timeout'
            or diagnostics[0].get('attempt') != 1
            or diagnostics[0].get('elapsed_s', 0) < 120):
        raise ReplayStop('not_the_observed_hard_timeout')
    matches = []
    for source in map(Path, sources):
        saved = source / 'journals' / CELL / 'requests' / (IDENTITY + '.json')
        if saved.exists() and read(saved).get('status') == 'completed':
            raise ReplayStop('saved_success_must_be_reused')
        for request in (source / 'wire').glob('*.request.json'):
            body = read(request).get('body', {})
            if (body.get('model') != SETTINGS['model'] or body.get('messages') != [
                    {'role': 'user', 'content': record['prompt']}]):
                continue
            status = request.with_name(request.name.replace('.request.json', '.status.json'))
            raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
            # 更早的同题TLS失败由既有分类器负责；本入口只核对第9段缺失的物理终态。
            if source == SEGMENT:
                if (status.exists() or raw.exists() or body.get('temperature') != 0
                        or body.get('thinking') != {'type': 'disabled'}
                        or body.get('max_tokens') != 256 or body.get('stream') is not True):
                    raise ReplayStop('hard_timeout_wire_or_saved_raw_changed')
                matches.append(str(request))
            elif raw.exists():
                raise ReplayStop('matching_saved_raw_requires_separate_review')
    if len(matches) != 1:
        raise ReplayStop('hard_timeout_physical_boundary_not_unique')
    budget = read(Path(sources[-1]) / 'budget.json')
    cap = read(original.RUN / 'budget.json')['stages']['K3']
    physical = sum(len(list((Path(p) / 'wire').glob('*.request.json'))) for p in sources)
    if (budget['cap_tokens'] != cap['tokens'] or budget['cap_HTTP'] != cap['HTTP']
            or budget['cap_embedding_HTTP'] != cap['embedding_HTTP']
            or physical != budget['transport_attempts_including_prior']
            or physical >= budget['cap_HTTP']
            or budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']):
        raise ReplayStop('hard_timeout_budget_mismatch_or_exhausted')
    write_json(EVIDENCE / ('hard_timeout_audit_after_segment_%03d.json' % len(sources)), {
        'classification': 'physical_request_hard_timeout_execution_and_cost_unknown',
        'cell': CELL, 'identity': IDENTITY, 'journal': str(TARGET),
        'diagnostics': diagnostics, 'settings': record['settings'], 'selector': True,
        'native_selector_physical_max_tokens': 256, 'wire': matches,
        'status_exists': False, 'raw_exists': False, 'reusable_success': False,
        'budget': {k: v for k, v in budget.items() if k != 'entries'},
        'physical_HTTP_checked': physical, 'old_unknown_usage_retained': True})
    return record


def helper(kind):
    """只在内存中增加这一条恢复分类，沿用原生身份核对、前缀复用与Q重建。"""
    if kind != 'q':
        raise ReplayStop('this_entry_only_handles_Q_run')
    h = native_helper(kind)
    classify_previous = h['probe'].__globals__['classify']

    def classify(sources):
        pending, rejected = classify_previous(sources)
        if str(TARGET) in rejected:
            record = inspect_timeout(sources)
            rejected = [p for p in rejected if p != str(TARGET)]
            pending.setdefault((CELL, IDENTITY), []).append({
                'path': str(TARGET),
                **{k: record[k] for k in ('settings', 'prompt', 'selector')}})
        return pending, rejected

    h['probe'].__globals__['classify'] = classify
    h['probe'].__globals__['R'] = EVIDENCE / 'prefix'
    return h


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    parser.add_argument('--kind', choices=['q'], default='q')
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    original.helper = helper
    original.MODULE = MODULE
    if args.action == 'run':
        # 默认TLS的新段已实测SSLEOFError；仅换用同端点、证书校验保留的TLS1.2。
        previous_transport = transport.verified_proxy_transport
        transport.verified_proxy_transport = tls12_transport
        try:
            result = original.run('q')
        finally:
            transport.verified_proxy_transport = previous_transport
    else:
        result = {'probe': original.probe, 'launch': original.launch}[args.action]('q')
    if result is not None:
        write_json(EVIDENCE / (args.action + '.json'), result)
        print(json.dumps({k: v for k, v in result.items() if k != 'targets'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
