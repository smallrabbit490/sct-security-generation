"""只读原生记录汇总参与学习与四臂冻结结果；不调用模型、不更新Q。"""
from __future__ import annotations

import argparse
from collections import Counter
import difflib
import json

from methods.cle_ablation import run_memory_q_online as study

REPORT = study.ROOT / 'docs/CLE_Q强化学习与全Dgate四臂效果分析_20261021.md'


def adoption_counts(records, true_visits, presented_visits=None):
    """声明采用与代码落实分开；Q3置换的visits不能冒充该卡真正学习过。"""
    chosen, adopted = [], []
    attempts = complete = 0
    for row in records:
        for attempt in row['attempts']:
            attempts += 1
            generation = attempt.get('generation', {})
            complete += bool(generation.get('workflow_completed'))
            chosen.extend(dict.fromkeys(c['invariant_id'] for c in generation.get('retrieved_cards', [])))
            adopted.extend(dict.fromkeys(c['invariant_id'] for c in generation.get('cards', [])))
    values = {'tasks': len(records), 'attempts': attempts, 'completed_workflow_attempts': complete,
        'selected_occurrences': len(chosen), 'selected_unique': len(set(chosen)),
        'adopted_occurrences': len(adopted), 'adopted_unique': len(set(adopted)),
        'adoption_occurrence_fraction': len(adopted) / len(chosen) if chosen else None,
        'true_learned_selected_occurrences': sum(true_visits[i] > 0 for i in chosen),
        'true_learned_adopted_occurrences': sum(true_visits[i] > 0 for i in adopted)}
    if presented_visits is not None:
        values['presented_visited_selected_occurrences'] = sum(presented_visits[i] > 0 for i in chosen)
        values['presented_visited_adopted_occurrences'] = sum(presented_visits[i] > 0 for i in adopted)
    return values


def first_mechanisms(records):
    """仅同查询首轮比较；修复轮不增加独立题数，改选/采用不等于实现贡献。"""
    by = {(r['task_id'], r['arm']): r for r in records}
    output = []
    for identifier in study.read(study.OUT / 'manifest.json')['D_gate']:
        for control in ('Q0', 'Q1', 'Q3'):
            if (identifier, 'Q2') not in by or (identifier, control) not in by:
                continue
            target, other = by[identifier, 'Q2'], by[identifier, control]
            a, b = target['attempts'][0], other['attempts'][0]
            ta, tb = study.trace_of(a), study.trace_of(b)
            same = (ta.get('status') == tb.get('status') == 'completed' and
                    all(ta.get(k) == tb.get(k) for k in ('query_hash', 'candidate_ids', 'scores')))
            selected = {c['invariant_id'] for c in a.get('generation', {}).get('retrieved_cards', [])}
            baseline = {c['invariant_id'] for c in b.get('generation', {}).get('retrieved_cards', [])}
            used = {c['invariant_id'] for c in a.get('generation', {}).get('cards', [])}
            oldused = {c['invariant_id'] for c in b.get('generation', {}).get('cards', [])}
            measured = bool(target['final']['measured'] and other['final']['measured'])
            output.append({'task_id': identifier, 'family_id': target['family_id'], 'control': control,
                'common_first_query': same,
                'presentation_changed': ta.get('presented_candidate_ids') != tb.get('presented_candidate_ids') if same else None,
                'selected_members_changed': selected != baseline if same else None,
                'adopted_members_changed': used != oldused if same else None,
                'new_selected_member_adopted': bool((selected - baseline) & used) if same else None,
                'new_selected_ids': '|'.join(sorted(selected - baseline)),
                'new_selected_adopted_ids': '|'.join(sorted((selected - baseline) & used)),
                'Q2_final_joint': bool(target['final']['joint']), 'control_final_joint': bool(other['final']['joint']),
                'measured_pair': measured,
                'joint_rescue': measured and target['final']['joint'] and not other['final']['joint'],
                'joint_loss': measured and not target['final']['joint'] and other['final']['joint']})
    return output


def case_materials(records, mechanisms, bank):
    """生成供逐题复核的公开契约、卡片和代码差分，不把机器选例写成人工核验。"""
    by = {(r['task_id'], r['arm']): r for r in records}
    tasks = study.read(study.OUT / 'tasks_D_gate.json')
    cards = {n.invariant_id: n.to_dict() for n in bank}
    chosen = []
    for kind in ('joint_rescue', 'joint_loss'):
        candidates = [m for m in mechanisms if m['control'] == 'Q1' and m[kind]]
        candidates.sort(key=lambda m: (not bool(m['new_selected_member_adopted']), int(m['task_id'])))
        chosen.extend(candidates[:3])
    lines = ['# Q强化后逐题代码复核材料', '',
        '按固定规则各取最多3道相对Q1救回/损失题；只整理证据，不自动判定单卡因果贡献。']
    for item in chosen:
        identifier = item['task_id']; target, control = by[identifier, 'Q2'], by[identifier, 'Q1']
        lines += ['', f'## 题目{identifier}：' + ('救回' if item['joint_rescue'] else '损失'), '',
            json.dumps(item, ensure_ascii=False), '', '公开契约：', '```json',
            json.dumps(study.frozen_runner().plt_contract(tasks[identifier]), ensure_ascii=False, indent=2), '```']
        selected = set()
        for row in (target, control):
            for a in row['attempts']:
                selected.update(c['invariant_id'] for c in a.get('generation', {}).get('cards', []))
        for card_id in sorted(selected):
            card = cards[card_id]
            lines += ['', f'采用卡：{card_id}',
                json.dumps({k: card.get(k) for k in ('high_level_invariant', 'applicability', 'positive_principle', 'negative_guardrail')}, ensure_ascii=False)]
        diff = difflib.unified_diff(control['final'].get('code', '').splitlines(),
            target['final'].get('code', '').splitlines(), fromfile='Q1_final', tofile='Q2_final', lineterm='')
        lines += ['', '末次交付代码差分：', '```diff', '\n'.join(diff), '```']
    (study.CURATED / 'case_review_materials.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def analyze(require_complete=True):
    study.verify()
    meta = study.read(study.OUT / 'run_metadata.json')
    learning = {stage: study.study_rows(stage) for stage in ('D_init', 'D_grow')}
    gate = study.effective_gate_rows()
    complete = len(learning['D_init']) == 303 and len(learning['D_grow']) == 273 and len(gate) == 1192
    if require_complete and not complete:
        raise RuntimeError('all_learning_and_four_arms_required_before_final_analysis')
    summaries, adoption = {}, []
    for stage, records in learning.items():
        path = study.OUT / stage / 'summary.json'
        if not path.exists():
            continue
        summaries[stage] = study.read(path)
        bank = study.load_memory(study.OUT / stage / 'frozen/m_star_q.jsonl')
        visits = {n.invariant_id: n.q_visits for n in bank}
        adoption.append({'stage': stage, 'arm': 'Q2_online', **adoption_counts(records, visits)})
    gate_summary = study.read(study.OUT / 'D_gate/summary.json') if (study.OUT / 'D_gate/summary.json').exists() else None
    mechanisms = []
    if complete:
        bank = study.load_memory(study.OUT / 'D_grow/frozen/m_star_q.jsonl')
        shuffled = study.load_memory(study.OUT / 'D_gate/shuffled_memory.jsonl')
        true = {n.invariant_id: n.q_visits for n in bank}
        shown = {n.invariant_id: n.q_visits for n in shuffled}
        for arm in study.ORDER:
            adoption.append({'stage': 'D_gate', 'arm': arm,
                **adoption_counts([r for r in gate if r['arm'] == arm], true, shown if arm == 'Q3' else true)})
        mechanisms = first_mechanisms(gate)
        study.dump_csv(study.CURATED / 'gate_first_mechanisms.csv', mechanisms)
        case_materials(gate, mechanisms, bank)
    # 旧未决请求保持原样；按恢复回执解释为未知响应/费用，不当活跃请求，不填零。
    receipt = study.read(study.OUT / 'recovery_20261021.json') if (study.OUT / 'recovery_20261021.json').exists() else {}
    approved_unknown = {r['path'] for r in receipt.get('unresolved_requests', [])}
    costs = {}
    for stage in ('D_init', 'D_grow', 'D_gate'):
        request_pairs = [(p, study.read(p)) for p in (study.OUT / stage / 'requests').glob('*.json')]
        req = [r for _, r in request_pairs]
        costs[stage] = {'logical_calls': len(req), 'completed': sum(r['status'] == 'completed' for r in req),
            'errors': sum(r['status'] == 'error' for r in req),
            'usage_unknown_requests': sum(r['status'] == 'started' and str(p.relative_to(study.OUT)) in approved_unknown for p, r in request_pairs),
            'active_started_requests': sum(r['status'] == 'started' and str(p.relative_to(study.OUT)) not in approved_unknown for p, r in request_pairs),
            **{k: sum(r.get(k, 0) for r in req) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}}
        labels = sorted({r['arm'] for r in req})
        costs[stage]['by_arm_or_initial'] = {label: {
            'logical_calls': sum(r['arm'] == label for r in req),
            'known_tokens': sum(r.get('total_tokens', 0) for r in req if r['arm'] == label)} for label in labels}
        segments = []
        archived_segments = sorted((study.OUT / stage).glob('embedding_usage_before_recovery_*.json'))
        for path in [*archived_segments, study.OUT / stage / 'embedding_usage.json']:
            if path.exists():
                segments.append({'source': str(path.relative_to(study.OUT)), **study.read(path)})
        costs[stage]['embedding_segments'] = segments
        costs[stage]['embedding_total'] = {key: sum(v.get(key, 0) for v in segments)
            for key in ('calls', 'failures', 'prompt_tokens', 'total_tokens', 'cache_hits', 'embedded_texts', 'usage_missing_calls')}
    conclusion = '实验尚未全部完成，不能判断强化Q的冻结迁移收益。'
    if complete:
        paired = gate_summary['primary_paired']
        if gate_summary['first_candidate_issues']:
            conclusion = '共同候选核对存在问题，应先解决可比性，暂不形成有效性结论。'
        elif all(p['difference'] > 0 and p['p_holm'] <= .05 for p in paired):
            conclusion = '三项主要比较通过统计门；需结合救回题代码核验后再确认完整作用路径，不能把统计通过自动当成单卡贡献证明。'
        elif all(p['difference'] > 0 for p in paired):
            conclusion = 'Q2相对三个对照的点估计均较高，但未全部通过校正统计门：存在方向性信号，尚未建立稳定收益。'
        else:
            conclusion = '强化Q未在三个主要对照上同时取得正向且通过校正的Joint收益，本轮未建立稳定有效性；不证明Q普遍无效或与对照等效。'
    result = {'protocol': study.PROTOCOL, 'complete': complete, 'status': meta['status'],
        'learning': summaries, 'adoption': adoption, 'cost': costs,
        'recovery': receipt, 'gate': gate_summary, 'conclusion': conclusion,
        'actual_bill_CNY': None, 'known_token_cost_is_lower_bound': bool(receipt)}
    study.write(study.CURATED / 'reinforcement_analysis.json', result)
    # 各阶段字段统一后导出，避免Q3额外字段影响CSV格式。
    keys = list(dict.fromkeys(k for a in adoption for k in a))
    study.dump_csv(study.CURATED / 'adoption_summary.csv', [{k: a.get(k) for k in keys} for a in adoption])
    lines = ['# CLE Q强化学习与全D_gate四臂效果分析', '', f'状态：`{meta["status"]}`；全量完成：{complete}。', '',
        conclusion, '', '## 两次学习', '',
        '|阶段|完成|F|S|Joint|完整测量|有反馈卡前→后|有效更新|', '|---|---:|---:|---:|---:|---:|---|---:|']
    for stage in ('D_init', 'D_grow'):
        if stage not in summaries:
            lines.append(f'|{stage}|待执行|—|—|—|—|—|—|'); continue
        s = summaries[stage]; f = s['final']
        lines.append(f'|{stage}|{s["executed"]}/{s["planned"]}|{f["functional"]}|{f["security"]}|{f["joint"]}|{f["measured"]}|{s["visited_before"]}→{s["visited_after"]} /1939|{s["valid_updates"]}|')
    lines += ['', 'Q覆盖率按至少一次有效反馈计算。学习阶段的Joint是在线训练轨迹成绩，不能与冻结D_gate成绩拼成提分曲线。', '',
        '## 实际采纳', '', '“实际采纳”以原流水线记录的声明采用ID统计；模型选中、规划采用和代码落实是不同环节，以下不冒充逐卡人工贡献核验。', '',
        '|阶段/组|选中次数|不同选中卡|声明采用次数|不同采用卡|采用/选中|', '|---|---:|---:|---:|---:|---:|']
    for a in adoption:
        fraction = f'{a["adoption_occurrence_fraction"]:.2%}' if a['adoption_occurrence_fraction'] is not None else '未定义'
        lines.append(f'|{a["stage"]}/{a["arm"]}|{a["selected_occurrences"]}|{a["selected_unique"]}|{a["adopted_occurrences"]}|{a["adopted_unique"]}|{fraction}|')
    lines += ['', 'Q3的打乱visits仅是置换后的呈现状态，不代表该卡真的学习过。CSV同时保留真实学习身份与呈现状态两种计数。Q0/Q1的采用记录为历史复用，其最终Q覆盖只作固定卡ID的事后描述。', '', '## 全D_gate四臂Joint', '']
    if complete:
        lines += ['|组|F|S|Joint|Joint/298|完整测量|来源|', '|---|---:|---:|---:|---:|---:|---|']
        for arm in study.ORDER:
            a = gate_summary['arms'][arm]
            lines.append(f'|{arm}|{a["functional"]}|{a["security"]}|{a["joint"]}|{a["joint"]/298:.2%}|{a["measured"]}|{"历史复用" if arm in ("Q0","Q1") else "本轮生成"}|')
        lines += ['', '|Q2相对对照|救回|损失|完整配对差|题族95%区间|Holm校正p|', '|---|---:|---:|---:|---|---:|']
        for p in gate_summary['primary_paired']:
            lines.append(f'|{p["control"]}|{p["wins"]}|{p["losses"]}|{p["difference"]:.2%}|{p["ci95_family_bootstrap"]}|{p["p_holm"]:.6g}|')
        lines += ['', '## 机制与结果的联系', '', '|Q2相对对照|共同首轮|顺序变化|成员变化|采用变化|新增成员被采用|', '|---|---:|---:|---:|---:|---:|']
        for arm in ('Q0', 'Q1', 'Q3'):
            ms = [m for m in mechanisms if m['control'] == arm]
            counts = [sum(bool(m[k]) for m in ms) for k in ('common_first_query','presentation_changed','selected_members_changed','adopted_members_changed','new_selected_member_adopted')]
            lines.append('|'+arm+'|'+'|'.join(map(str, counts))+'|')
        lines += ['', '这些计数说明Q是否经过排序—选卡—声明采用路径介入；最终收益仍由同题Joint比较判断。代码差分材料按固定规则整理于`case_review_materials.md`，尚未进行人工金标准核验。']
    else:
        lines.append('尚无完整新Q2/Q3结果；保留596条历史Q0/Q1，不将它们单独称为本轮四臂结果。')
    lines += ['', '## 成本与中断恢复', '', '|阶段|逻辑请求|已返回|错误|未知用量请求|已知Token|', '|---|---:|---:|---:|---:|---:|']
    for stage, c in costs.items():
        lines.append(f'|{stage}|{c["logical_calls"]}|{c["completed"]}|{c["errors"]}|{c["usage_unknown_requests"]}|{c["total_tokens"]:,}|')
    lines += ['', '|阶段|Embedding调用|Embedding Token|失败|', '|---|---:|---:|---:|']
    for stage, cost in costs.items():
        e = cost['embedding_total']
        lines.append(f'|{stage}|{e["calls"]}|{e["total_tokens"]:,}|{e["failures"]}|')
    lines += ['', '旧对照和已复用初析不重复计费。已知Token是下界；00866请求没有响应/用量落盘，不能当成零费用。题1245中断前两次已返回请求合计34166 tokens计入实际成本，但不形成完整题级样本或Q奖励。原始记录未改，前128题没有重跑。Embedding合计包括中断前128题的70次调用、107359 tokens，以及恢复后的独立用量段；恢复前段从当时保存的成本汇总确认，来源见embedding_recovery_source_20261021.json。实际人民币账单未知。', '',
        '## 结论边界', '', '不改变经验正文和生命周期，Q只改变候选呈现顺序，由原模型最多选三张；仅训练侧实际声明采用且测量完整的卡取得奖励。D_grow全273题做题，预先合格228题可授信，45题只保留结果。D_gate全程冻结，无测试反馈回流。', '',
        '三次主要比较沿用原项目按题族重采样/置换及Holm校正，缺测保留并单列。历史对照与新Q臂执行时间不同；D_gate存在历史开发暴露。本轮不运行Base/Plus，不声称独立最终泛化、Q已收敛或覆盖率等于检索召回率。', '',
        f'分支：`{meta["branch"]}`；提交基线：`{meta["commit"]}`。运行区：`translation_work/diagnostics/20261020/cle_q_online_v1/`；精简分析：`results/curated/cle_q_online_20261020/`。']
    REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial', action='store_true')
    analyze(not parser.parse_args().partial)
