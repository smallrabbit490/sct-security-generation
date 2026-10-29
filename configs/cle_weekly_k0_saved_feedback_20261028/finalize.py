"""证书通过后复算完整统计、保存实际案例分析并登记；历史成绩与动态差异不改。"""
import argparse
import csv
import io
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from configs.cle_memory_q_full_gate_cap3_20261019.analyze import paired
from configs.cle_weekly_analysis_20261027 import analysis
from configs.cle_weekly_full_20261027 import learn
from configs.cle_weekly_k0_analysis_recovery_20261028.finalize import REVIEWS
from .certificate import RELATIVE, accepted


def run():
    root = learn.RUN
    if not accepted(root):
        raise RuntimeError('independent_K0_replay_not_verified')
    out = root / 'analysis/K0'
    old = analysis.read(out / 'reconciliation_20261028/before_summary.json')
    summary = analysis.run('K0')
    ids = analysis.read(root / 'manifest.json')['pools']['D_init']
    rows, paths, _ = analysis.collect_rows(summary['source_segments'], ids)
    tasks = analysis.read(root / 'shared_inputs/tasks_D_init.json')
    queue = analysis.read(out / 'case_review_queue.json')
    if {c['task_id'] for c in queue} != set(REVIEWS):
        raise RuntimeError('representative_queue_changed_requires_actual_review')
    cases = []
    for key, review in REVIEWS.items():
        evidence = analysis.read(out / 'case_evidence' / (key + '.json'))
        row = next(r for r in rows if r['task_id'] == key)
        if evidence['public_task'] != tasks[key]['task_description']:
            raise RuntimeError('case_public_task_differs:' + key)
        for stored, native in zip(evidence['attempts'], row['attempts']):
            if (stored['code'] != native['code'] or stored['validation'] != native['validation']
                    or stored['plan'] != native['generation']['plan_parsed']):
                raise RuntimeError('case_evidence_differs:' + key)
        cases.append({'task_id': key, 'analysis': review,
            'categories': [c['category'] for c in queue if c['task_id'] == key],
            'evidence': [str(out / 'case_evidence' / (key + '.json')), paths[key],
                str(root / 'shared_inputs/tasks_D_init.json'), str(root / 'shared_inputs/memory1939_q0.jsonl')],
            'rechecked_in_current_task': True})
    analysis.write(out / 'agent_case_review.json', {'status': 'completed', 'cases': cases,
        'reviewed_queue_entries': len(queue), 'unique_queue_tasks': len(cases), 'reviewed_utc': learn.now(),
        'new_model_HTTP': 0, 'new_embedding_HTTP': 0,
        'scope': 'actual representative cases; saved-feedback replay verified, dynamic divergence retained'})
    transformed = [item for row in rows for item in (
        {**row, 'arm': 'final', 'final': row['final']},
        {**row, 'arm': 'first', 'final': row['attempts'][0]})]
    comparison = paired(transformed, target='final', control='first', seed=20261027)
    comparison['scope'] = 'descriptive repair contrast within learning, not an independent Q-effect test'
    grouped = defaultdict(lambda: [0, 0, 0])
    for row in rows:
        value = grouped[row['family_id']]
        value[0] += int(row['final']['joint'])
        value[1] += 1
        value[2] += int(row['final']['measured'])
    values = np.asarray(list(grouped.values()), dtype=float)
    rng = np.random.default_rng(20261027)
    totals = values[rng.integers(0, len(values), size=(10000, len(values)))].sum(axis=1)
    intervals = {'families': len(grouped), 'bootstrap_samples': 10000, 'seed': 20261027,
        'unit': 'genuine family clusters, task-weighted rate',
        'joint_divided_by_planned_ci95': np.quantile(totals[:, 0] / totals[:, 1], [.025, .975]).tolist(),
        'joint_divided_by_measured_ci95': np.quantile(totals[:, 0] / totals[:, 2], [.025, .975]).tolist()}
    for key in ('first', 'final', 'memory', 'adoption', 'mechanism'):
        if old[key] != summary[key]:
            raise RuntimeError('recomputed_statistics_changed:' + key)
    certificate = analysis.read(root / RELATIVE / 'certificate.json')
    summary.update(first_final_paired=comparison, family_intervals=intervals,
        any_candidate_upper_bound=analysis.metrics([next((a for a in r['attempts'] if a.get('joint')), r['final'])
                                                  for r in rows], 303),
        repeat_variability={'planned_repeats': 1, 'status': 'not_estimable_single_learning_pass',
                            'independent_repeated_tasks': 0, 'joint_discordance': None},
        Q_primary_comparisons=old['Q_primary_comparisons'], unmeasured_tasks=old['unmeasured_tasks'],
        actual_case_review={'status': 'completed', 'unique_tasks': len(cases),
                            'path': str(out / 'agent_case_review.json')},
        full_response_replay={'status': certificate['status'], 'mode': certificate['mode'], 'completed': 303,
            'model_requests_consumed': certificate['model_requests_consumed'],
            'historical_feedback_calls': certificate['historical_feedback_calls'], 'new_HTTP': 0,
            'certificate': str(root / RELATIVE / 'certificate.json'),
            'dynamic_validation_all_consistent': False,
            'native_dynamic_replay': old['full_response_replay']},
        analysis_completion_status='completed_with_explicit_saved_feedback_replay_and_retained_dynamic_divergence')
    budget = analysis.read(Path(summary['source_segments'][-1]) / 'budget.json')
    summary['costs'].update(cap_tokens=budget['cap_tokens'], cap_HTTP=budget['cap_HTTP'],
        cap_embedding_HTTP=budget['cap_embedding_HTTP'],
        budget_tokens_remaining=budget['cap_tokens'] - budget['charged_tokens_including_unknown_and_inflight_bounds'],
        budget_HTTP_remaining=budget['cap_HTTP'] - budget['transport_attempts_including_prior'])
    analysis.write(out / 'summary.json', summary)
    # 原报告的完整统计、逐题正文仍适用；只替换已经实际解决的回放结论及所需决定。
    report = (out / 'reconciliation_20261028/before_analysis.md').read_text(encoding='utf-8')
    first_paragraph = report.split('\n\n')[1]
    report = report.replace(first_paragraph,
        f"K0已完成303/303题；保存响应加当时验证反馈的独立回放已核对全部303题、"
        f"{certificate['model_requests_consumed']}条模型请求及{certificate['historical_feedback_calls']}次反馈，"
        "除耗时外的原生逐题字段、Q事件和1939张冻结卡全部一致。12个代表题已重新实际审阅，"
        "本次新增模型及Embedding请求0。原动态回放仍保留1107同代码结果变化及随后1111提示分歧；"
        "本证书不表示动态验证全部一致。")
    start = report.index('所需决定是：')
    report = report[:start] + f'''本次按2026年10月28日明确授权独立核对全部303题。每个请求使用原生身份、同一模型参数和原保存响应；每次验证先匹配原题、原代码及尝试顺序，再输入当时反馈。实际消耗全部{certificate['model_requests_consumed']}条保存模型请求、{certificate['historical_feedback_calls']}次历史反馈，复算所有选卡/计划/代码/验证/Q字段（仅耗时除外），最终Q、visits与全部卡正文均与原冻结库一致。旧失败请求的{certificate['resolved_old_failures']}个精确成功后继已逐项登记，旧失败和未知用量保留。全部原始题行、journal、预算、状态和旧失败回放经前后核对未变。

证书：[保存响应与历史反馈回放](../../{RELATIVE}/certificate.json)；逐题核对：[303题清单](../../{RELATIVE}/per_task_audit.json)；历史反馈：[逐次记录](../../{RELATIVE}/feedback_audit.json)。本次未执行303题新的动态复验，当前原验证器的1107复验单列于[环境差异记录](reconciliation_20261028/current_validator_1107.json)，不能宣称动态验证全部一致。原记录未保存当时逐断言及DNS值，不能确认唯一原因。

工作台仅对Q.K0.analysis接纳这一明确口径的独立证书。后续冻结回测通过独立continuation入口消费相同证书，只消除K0回放这一项依赖，K1至K3、原固定范围/重复、并发、窗口、累计预算和原验证器要求保持。普通原生入口仍报告K0_native_replay_pending，避免把历史反馈证书改名为原生动态通过。本CLI只完成K0分析，不启动其他节点；Q效果仍等待预定2730格同题回测及2384格迁移比较。
'''
    (out / 'analysis.md').write_text(report, encoding='utf-8')
    registry = learn.ROOT / 'docs/research/registers/experiments.csv'
    with registry.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        fields, entries = reader.fieldnames, list(reader)
    for entry in entries:
        if entry[fields[0]] == 'CLE-EXP-20261027-Q-05':
            entry['status'] = 'K0_saved_feedback_replay_analyzed_K1_native_replayed'
            entry['as_of'] = learn.now()
            index = analysis.read(root / 'execution_index.json')
            entry['completed_snapshot'] = str(sum(analysis.read(Path(segments[-1]) / 'summary.json')['completed']
                                                  for segments in index.values()))
            entry['evidence'] = str(out / 'summary.json')
            entry['interpretation'] = 'K0完整303题历史响应及当时反馈独立回放一致，Joint148/303，可测301；12代表题实际复核；1107动态差异和原失败保留，不称动态验证全一致。K1原生回放已完成；其他学习状态见原生摘要，本次未操作其他节点。'
            buffer = io.StringIO(newline='')
            csv.DictWriter(buffer, fieldnames=fields, lineterminator='\n').writerow(entry)
            # 只替换这一行，保留登记表其他条目、编码及换行。
            with registry.open(encoding='utf-8-sig', newline='') as handle:
                lines = handle.readlines()
            for i, line in enumerate(lines):
                if line.startswith('CLE-EXP-20261027-Q-05,'):
                    lines[i] = buffer.getvalue().rstrip('\n') + ('\r\n' if line.endswith('\r\n') else '\n')
                    break
            with registry.open('w', encoding='utf-8-sig', newline='') as handle:
                handle.writelines(lines)
    print(json.dumps({'status': 'completed', 'completed': 303, 'reviewed': len(cases), 'new_HTTP': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    run()
