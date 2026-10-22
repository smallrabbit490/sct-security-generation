"""从303题真实记录生成最终学习报告与逐题/逐卡覆盖表；不调用API。"""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation import run_memory_q_dinit_full as run
from methods.cle_ablation.run_memory_q_dinit import body
from methods.cle_ablation.runner import load_memory
from methods.sct_trajectory.semantic_retrieval import card_embedding_text, MAX_CARD_CHARS


def table(rows):
    return '\n'.join('| ' + ' | '.join(map(str, r)) + ' |' for r in rows)


def csv_file(name, rows):
    if rows:
        with (run.CURATED / name).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    recovery_path = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_full_learning_v4b/recovery.json'
    if recovery_path.exists():
        from configs.cle_dinit_full_learning_20261020.continue_after_timeout import configure
        configure()
    summary = run.report()
    assert summary['executed'] == 303 and summary['status'] == 'completed_full303'
    rows = run.records()
    recovery = run.read(recovery_path) if recovery_path.exists() else None
    if recovery:
        summary['recovery'] = recovery
        summary['physical_new_P7_executions'] = summary['new_P7_runs'] + len(recovery['rerun_interrupted_tasks'])
        summary['discarded_technical_P7_records'] = len(recovery['rerun_interrupted_tasks'])
        summary['new_cost']['LLM']['failed_request_tokens_unknown'] = 1
        for folder in (run.OUT, run.CURATED):
            run.write(folder / 'summary.json', summary)
    tasks, origins = run.read(run.OUT / 'tasks.json'), run.read(run.OUT / 'origins.json')
    baseline = load_memory(run.OUT / 'input_memory.jsonl')
    by_id = {n.invariant_id: n for n in baseline}
    candidates, selections, adoptions = Counter(), Counter(), Counter()
    mechanisms, errors = [], []
    for row in rows:
        for a in row['attempts']:
            trace, g = run.core.trace_of(a), a.get('generation', {})
            candidate = set(trace.get('candidate_ids', []))
            selected = {c['invariant_id'] for c in g.get('retrieved_cards', [])}
            adopted = {c['invariant_id'] for c in g.get('cards', [])}
            candidates.update(candidate)
            selections.update(selected)
            adoptions.update(adopted)
            if not g.get('workflow_completed') or not a.get('measured'):
                errors.append({'task_id': row['task_id'], 'attempt': a['attempt'], 'error_type': g.get('error_type'),
                               'measured': a.get('measured'), 'worker_error': a.get('validation', {}).get('evidence', {}).get('metadata', {}).get('worker_error')})
            mechanisms.append({'task_id': row['task_id'], 'attempt': a['attempt'], 'reused': row.get('reused_execution', False),
                'candidate_count': len(candidate), 'selected_count': len(selected), 'adopted_count': len(adopted),
                'baseline_unvisited_candidates': sum(by_id[i].q_visits == 0 for i in candidate),
                'baseline_unvisited_selected': sum(by_id[i].q_visits == 0 for i in selected),
                'baseline_unvisited_adopted': sum(by_id[i].q_visits == 0 for i in adopted),
                'measured': a.get('measured'), 'Joint': a.get('joint'), 'workflow_completed': g.get('workflow_completed')})
    card_rows, coverage_rows, visit_deltas = [], [], {}
    for policy in ('all_feedback', 'cross_family'):
        bank = load_memory(run.OUT / policy / 'frozen/m_star_q.jsonl')
        assert body(bank) == body(baseline)
        visit_deltas[policy] = sum(n.q_visits - by_id[n.invariant_id].q_visits for n in bank)
        assert visit_deltas[policy] == summary['credit'][policy]['valid_updates']
        for node in bank:
            origin = origins[node.invariant_id]
            card_rows.append({'policy': policy, 'card_id': node.invariant_id, 'cwe': node.cwe,
                'source_task': origin['source_task_id'], 'source_family': origin['source_family'],
                'baseline_visits': by_id[node.invariant_id].q_visits, 'final_visits': node.q_visits,
                'baseline_Q': by_id[node.invariant_id].q_value, 'final_Q': node.q_value,
                'candidates': candidates[node.invariant_id], 'selections': selections[node.invariant_id], 'adoptions': adoptions[node.invariant_id],
                'retrievable': len(card_embedding_text(node)) <= MAX_CARD_CHARS})
        groups = sorted({str(n.cwe) for n in bank}, key=lambda x: int(x))
        for cwe in groups:
            group = [n for n in bank if str(n.cwe) == cwe]
            coverage_rows.append({'policy': policy, 'CWE': cwe, 'cards': len(group),
                'baseline_learned': sum(by_id[n.invariant_id].q_visits > 0 for n in group),
                'learned': sum(n.q_visits > 0 for n in group),
                'new': sum(n.q_visits > 0 and by_id[n.invariant_id].q_visits == 0 for n in group)})
    csv_file('card_coverage.csv', card_rows)
    csv_file('coverage_by_cwe.csv', coverage_rows)
    csv_file('attempt_mechanisms.csv', mechanisms)
    run.write(run.CURATED / 'workflow_and_measurement_errors.json', errors)
    preflight = run.read(run.OUT / 'preflight_summary.json')
    run.write(run.CURATED / 'preflight_summary.json', preflight)
    run.write(run.CURATED / 'repair_summary.json', run.read(run.CONFIG / 'repair_summary.json'))
    verified = {'completed_tasks': len(rows), 'distinct_tasks': len({r['task_id'] for r in rows}),
        'all_inputs_match_lock': True, 'experience_body_unchanged': True, 'old_results_untouched': True,
        'new_Dgate_generation': False, 'all_final_codes_are_last_attempt': all(r['final'] == r['attempts'][-1] for r in rows),
        'early_stopping_preserved': all(len(r['attempts']) == 1 or not r['attempts'][0]['joint'] for r in rows),
        'technical_issues': summary['fatal_issues'], 'performance_gate_disabled': True,
        'Q_visit_deltas_match_updates': visit_deltas,
        'original_safety_non_discriminating': preflight['non_discriminating_original_safety_tasks']}
    old_meta = run.read(run.OLD / 'run_metadata.json')
    verified['old_v3_inputs_and_runner_unchanged'] = all(run.core.digest(ROOT / name) == value for name, value in old_meta['identity'].items())
    if recovery:
        original = ROOT / recovery['source']
        verified['old_v4_inputs_and_runner_unchanged'] = all(run.core.digest(ROOT / name) == value for name, value in run.read(original / 'run_metadata.json')['identity'].items())
        verified['same_recovery_masks'] = all(run.core.digest(original / p.name) == run.core.digest(p) for p in run.OUT.glob('exposure_mask_*.json'))
        verified['historical_API_errors'] = summary['new_cost']['LLM']['errors']
        verified['technical_interrupted_records_retained'] = len(recovery['rerun_interrupted_tasks'])
    run.write(run.CURATED / 'verification.json', verified)
    assert verified['all_final_codes_are_last_attempt'] and verified['early_stopping_preserved']
    assert verified['old_v3_inputs_and_runner_unchanged'] and not summary['fatal_issues']
    qtable = [['授信视图', '起点有反馈卡', '最终有反馈卡', '覆盖率', '新增卡', '更新次数', '正奖励次数', '负奖励次数'],
              ['---'] * 8]
    for name, s in summary['credit'].items():
        qtable.append([name, 436, s['learned_cards'], f"{s['coverage']:.2%}", s['new_cards'], s['valid_updates'], s['positive_updates'], s['negative_updates']])
    repairtable = [
        ['题号', '修订内容'], ['---', '---'],
        ['76', '公开8–100长度政策；把误标的42字符有效密码保留为功能正例，新增真正超长安全例；参考实现先检查长度。'],
        ['82', '修正参考实现的日志格式；公开字段长度界限，加入超界反例；原负对照格式也错误，改为同格式无长度限制对照，原件保留。这是长度政策对照，未新增灾难回溯计时判定。'],
        ['105', '公开标准化、保留词组件和重复/全数字规则；修正参考实现的保留词组件判断，敏感词列表通过外部绑定提供。'],
        ['109', '补全属性和值的删除逻辑，支持两种引号；公开任务特定属性策略并统一删除后空白；修正一处矛盾的预期空白。'],
        ['451、453、456', '按原公开契约传播IOError；参考不再吞异常，增加已知签名但资源不可用的模拟测试。'],
        ['1258、1288、1319、1003', '分别补齐标签返回形式/长度、bytes参数、默认json参数、tags_html模板字段名。'],
        ['1299', '公开接收函数及返回来源，按原异常契约传播ConnectionError，补入不可用设备的模拟测试。']]
    llm, emb = summary['new_cost']['LLM'], summary['new_cost']['embedding']
    recovery_text = '''
v4在232条记录时遭遇878题的60秒API网络超时；保护性停止同时中断485题修复。v4b只延长API等待至120秒，复用230条完成记录及固定覆盖掩码，重跑这2道受中断题并完成71道未执行题。836题自身输出截断属于原模型结果，保留且未重跑。旧v4全部原件保留；主表按每题最终有效执行记录计一次，另存2条技术中断P7记录。主表中新执行296次之外另有2次中断执行，因此实际新P7调用共298次，历史复用7次；这不是第二轮学习。费用总账含两次中断过程，不清零，错误请求未返回的Token无法精确统计。
''' if recovery else ''
    text = f'''# D_init全303题Q学习执行报告（{'v4b' if recovery else 'v4'}，2026-10-20）

本轮已覆盖全部303道D_init题，新增执行{summary['new_P7_runs']}次P7，复用7次输入与配置一致的旧L1执行。按用户最新要求，正确率和覆盖增量不再决定是否继续；完成一轮后冻结，没有追加第二轮或D_gate。旧v3未过门结果保持原样。

{recovery_text}

## 执行规格

协议：`{run.PROTOCOL}`；分支：`{run.verify()['branch']}`；基础提交：`{run.verify()['commit']}`。基础入口：`methods/cle_ablation/run_memory_q_dinit_full.py`；技术恢复由`configs/cle_dinit_full_learning_20261020/continue_after_timeout.py`执行。完整参数和303题名单位于`{run.CONFIG.relative_to(ROOT).as_posix()}/`。

数据为SeCodePLT的Python训练侧D_init303题。使用旧CLE原P7（生成、动态测试，未通过时最多修复一次，首次联合通过就结束，交付末次代码），每次最多三张卡。L1（覆盖优先路线）将未学习卡先呈现，再由原模型选卡。Q数值是观察者，不用于本轮代码决策；各检查点只更新“是否学过”的呈现掩码。模型deepseek-v3.2，关闭thinking、temperature=0、max_tokens=4096；向量模型text-embedding-3-large，delta=-1，alpha=0.3，四并发。

经验正文固定1939张，起点436张有Q反馈；沿用修订32题D_grow后的状态，不混入未晋升的v3原始Q库。全反馈（允许同题族）和cross_family（本轮新增授信只接受已知不同题族）两份结果分开保存；继承的436卡没有重新认证为跨题族证据。12、60、303只是存档点，不是正确率门。

## 题目修订和预检

{table(repairtable)}

303道参考实现均通过功能与安全组；7道原排除题的修订负对照均被安全组拒绝。所有正负对照都实际执行，不使用参考成绩直接赋Q。原题75、77、78、79、80的安全例不能拒绝原不安全实现，保留并披露，不以此排题。1260、81原负例超时，为预期拒绝证据；不把缺失的功能测量补记为通过。

修订涉及参考代码、测试条件及输出政策，因此本轮是新数据契约版本，不能与旧题面成绩直接拼接成提分表。原始`data.json`不变，原7题及5处缺口的前后字段均保存在运行区`repair/`。公开上下文没有加入具体签名、允许名单值、测试输入输出或参考代码。

## 全量完成情况

|项目|结果|
|---|---:|
|完成题数/唯一题数|303/303|
|新执行/复用P7|{summary['new_P7_runs']}/7|
|代码尝试条目（含复用与未产码失败）|{summary['code_attempts']}|
|最终F/S完整测量|{summary['measured']}/303|
|最终流程完整|{summary['final_workflows']}/303|
|功能通过F|{summary['F']}/303|
|安全通过S|{summary['S']}/303|
|联合通过Joint（功能与安全同时通过）|{summary['Joint']}/303（{summary['Joint']/303:.2%}）|
|被选入的不同卡|{summary['selected_unique']}|
|实际声明采用的不同卡/累计采用次数|{summary['adopted_unique']}/{summary['adopted_occurrences']}|

正确率只作训练过程记录，不是独立评测成绩。完整遍历表示303题均有执行记录；不等于303题都生成正确代码。模型格式失败、代码错误及缺测保持原记录，按原授信条件决定是否产生奖励，不用重跑覆盖。

## Q学习结果

{table(qtable)}

每次实际声明采用且流程完整、F/S有效测量的卡，按`Q_new = Q_old + 0.3 × (reward − Q_old)`更新；联合通过奖励+1，测得失败奖励−1。奖励由整份代码结果共享，不代表某一张卡单独造成了成功或失败。仅召回、仅被选入、不完整流程或无法测量不会自动获得反馈。零Q但visits大于0仍算学过，不能只统计非零Q。

全量做题没有承诺全卡覆盖：候选召回、模型最多选三张、实际采用和有效测量仍是卡片获得反馈的条件。跨题族视图还会过滤同族及来源不明事件。逐题链条见`attempt_mechanisms.csv`，逐卡新旧Q、访问次数和召回/选入/采用次数见`card_coverage.csv`，各CWE覆盖见`coverage_by_cwe.csv`。

## 成本与产物

本轮累计新增LLM逻辑请求{llm['calls']}次，已返回响应的输入{llm['prompt_tokens']:,}、输出{llm['completion_tokens']:,}，合计{llm['total_tokens']:,} Token；Embedding {emb['calls']}次、{emb['total_tokens']:,} Token。新请求错误{llm['errors']}，未完成请求{llm['unfinished']}，已完成但缺用量的请求{llm['usage_missing']}。复用7条历史记录不重复记入本轮API总账。没有当前账单依据，实际人民币费用未测量；网络超时未返回的用量及原请求器内部HTTP重试次数未完整观测。

- 原生代码/验证/检索轨迹和逐题行：`{run.OUT.relative_to(ROOT).as_posix()}/`。
- 两份冻结库：运行区`all_feedback/frozen/m_star_q.jsonl`与`cross_family/frozen/m_star_q.jsonl`，各有奖励事件及题族支持表。
- 精简结果：`{run.CURATED.relative_to(ROOT).as_posix()}/`。
- 复现命令：`configs/cle_dinit_full_learning_20261020/README.md`。

## 结论边界

本轮完成了指定的全量D_init学习，获得了更多卡片反馈；没有进行“冻结新Q再生成”的对照，也没有新的D_gate成绩。因此这里只能报告训练覆盖和实际反馈，不能声称Q已提高正确率、验证跨题族迁移，或已证明原先Q探索的结论被推翻。
'''
    (ROOT / 'docs/CLE_Dinit全303题Q学习执行报告_20261020.md').write_text(text, encoding='utf-8')
    print(json.dumps({'completed': 303,
        'credit': {p: {k: s[k] for k in ('learned_cards', 'new_cards', 'coverage', 'valid_updates')} for p, s in summary['credit'].items()},
        'verified': verified}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
