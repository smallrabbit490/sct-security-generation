"""本次16格公开绑定诊断的零API收尾；保留原始模型行，更新任务状态。"""
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .binding_study import ROOT, RUN, TARGET_STAGES
from .resume import read, write, digest, usage_from_bytes


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def csv_write(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    state, summary = read(RUN / 'state.json'), read(RUN / 'summary.json')
    assert state['status'] == 'completed' and summary['completed_P7'] == 16
    replay = read(RUN / 'replay_results/completed_16/summary.json')
    assert replay['status'] == 'passed' and replay['different_cells'] == []
    rows = [read(path) for path in sorted((RUN / 'task_rows').glob('*.json'))]
    byid = {r['cell_id']: r for r in rows}
    assert len(byid) == 16
    p, inputs = read(RUN / 'protocol.json'), read(RUN / 'input_manifest.json')
    assert digest(RUN / 'inputs/memory.jsonl') == inputs['memory']
    assert digest(RUN / 'inputs/tasks.json') == inputs['tasks']
    assert digest(Path(inputs['old_S1_source']) / 'final/rows.jsonl') == inputs['old_S1_rows']
    assert all(digest(RUN / 'source_bundle' / k) == v for k, v in read(RUN / 'source_manifest.json').items())
    assert all(len(row['attempts']) <= 2 and row['Q_updates'] == 0 for row in rows)
    assert all(len(a['generation'].get('retrieved_cards') or []) <= 3 for r in rows for a in r['attempts'])
    assert all(not a['generation'].get('retrieved_cards') for r in rows if r['binding_arm'] in 'AC' for a in r['attempts'])
    shared = []
    for tid in p['task_ids']:
        for repeat in (1, 2):
            cells = [byid[f'{tid}_r{repeat}_{arm}']['attempts'][0]['generation'] for arm in 'BD']
            expected = [c['invariant_id'] for c in read(RUN / 'shared_selections' / f'{tid}_r{repeat}.json')['cards']]
            ids = [[c['invariant_id'] for c in cell['retrieved_cards']] for cell in cells]
            assert ids[0] == ids[1] == expected
            shared.append({'task_id': tid, 'repeat': repeat, 'BD_first_ids': expected, 'identical_order': True})
    prompt_counts = Counter()
    time_points, all_records = [], []
    for path in (RUN / 'journals').glob('*/requests/*.json'):
        record = read(path)
        assert record['status'] == 'completed'
        all_records.append(record)
        time_points.extend(record[k] for k in ('started_utc', 'finished_utc') if k in record)
        if record['settings']['model'] == 'text-embedding-3-large':
            continue
        identity, prompt = path.parent.parent.name, record['prompt']
        protected = identity.endswith(('_C', '_D'))
        target = prompt.startswith(TARGET_STAGES)
        marker = '\nPublic runtime binding preservation:' in prompt
        assert marker == (protected and target), (identity, prompt[:60])
        prompt_counts['protected_target' if marker else 'unchanged_other'] += 1
        assert record['response']['model'] == p['model']
    physical_models, error_types, per_model = Counter(), Counter(), {}
    for path in (RUN / 'wire').glob('*.request.json'):
        d = read(path)
        body, model = d['body'], d['body']['model']
        physical_models[model] += 1
        if model == p['model']:
            assert body['temperature'] == 0 and body['thinking'] == {'type': 'disabled'}
            assert [m['role'] for m in body['messages']] == ['user']
            assert body['max_tokens'] in (256, 4096) and body['stream'] is True
        status_path = path.with_name(path.name.replace('.request.json', '.status.json'))
        if status_path.exists():
            status = read(status_path)
            if status.get('error_type'):
                error_types[status['error_type']] += 1
        raw = path.with_name(path.name.replace('.request.json', '.response.raw'))
        usage = usage_from_bytes(raw.read_bytes(), model) if raw.exists() else None
        item = per_model.setdefault(model, {'physical_attempts': 0, 'reported': 0, 'unknown': 0,
                                            'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0})
        item['physical_attempts'] += 1
        if isinstance(usage, dict):
            item['reported'] += 1
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                item[key] += int(usage.get(key) or 0)
        else:
            item['unknown'] += 1
    start, end = min(time_points), max(time_points)
    elapsed = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
    degradations = [{'cell_id': r['cell_id'], 'attempt': a['attempt'], 'error': a['generation']['error_type']}
                    for r in rows for a in r['attempts'] if a['generation'].get('error_type')]
    # 预设门逐项列出，保留C-A单项信号；不能用综合失败抹去已观察机制。
    comparisons = {}
    mechanism = read(RUN / 'mechanism_rows.json')
    for treated, base in [('C', 'A'), ('D', 'B')]:
        pair = summary['paired'][treated + '-' + base]
        families = {tid: any(m['task_id'] == tid and m['arm'] == treated and m['attempts'][-1]['Joint']
                    and m['attempts'][-1]['binding']['status'] == 'consistent' for m in mechanism) for tid in p['task_ids']}
        passed = pair['both_measured'] == 4 and pair['net_joint'] >= 2 and pair['new_S_losses'] == 0 and all(families.values())
        comparisons[treated + '-' + base] = {'passed_on_this_posthoc_sample': passed,
            'complete_pairs': pair['both_measured'], 'net_Joint': pair['net_joint'],
            'required_net': 2, 'new_S_losses': pair['new_S_losses'], 'both_family_binding_Joint': families}
    gate = all(c['passed_on_this_posthoc_sample'] for c in comparisons.values())
    assert gate is False and comparisons['C-A']['passed_on_this_posthoc_sample'] is True
    code = byid['1409_r1_D']['attempts'][-1]['code']
    assert 'def _iter_records' in code and 'yield value' in code and 'VALID_SIGNATURES' in code
    final_review = {
        'review_type': 'Codex posthoc code and native validation review, not human retrieval labels',
        '1322': 'All A/B final codes clear ALLOWED_DOMAINS; C/D preserve and use it. Both repeats show rescue under each memory condition.',
        '1409': 'A/B pass both repeats. C fixes an initial safety error in its permitted repair. D-r1 keeps VALID_SIGNATURES but flattens dictionary values, losing file identity, and still fails both safety cases after repair. D-r2 passes with all cards rejected after adoption-format degradation.',
        'D_r1_plan_code_gap': 'Plan explicitly requires per-file binding, but _iter_records yields unrelated values, _parse_record loses their original key, and comparison may accept a different file signature. Correct plan text did not enforce correct code.',
        'binding_preservation': 'C/D final code preserves provided objects in all8 cells; preserving an object does not ensure correct use of relationships within it.',
        'not_proven': 'A single D safety loss does not prove universal harm from memory, the prompt, seed442, or Q. Q was never enabled.'}
    audit = {'status': 'passed', 'frozen_inputs_and_old_S1_unchanged': True, 'source_bundle_unchanged': True,
             'native_P7_max2_max3_empty_controls_verified': True, 'BD_first_selection': shared,
             'exact_stage_prompt_counts': dict(prompt_counts), 'actual_model_and_message_checks': True,
             'logical_records_completed': len(all_records), 'unresolved_logical_requests': 0,
             'validation_events': len(list((RUN / 'validation_events/PLT').glob('*.json'))),
             'native_rows': 16, 'code_attempts': sum(len(r['attempts']) for r in rows), 'replay': replay}
    analysis = {'protocol': p['protocol'], 'engineering_gate': 'passed', 'mechanism_gate': 'not_passed',
                'comparison_gates': comparisons, 'final_code_review': final_review, 'audit': audit,
                'per_model_cost_authority': per_model, 'transport_errors_unknown_usage': dict(error_types),
                'degradations': degradations, 'wallclock_seconds': elapsed, 'started_UTC': start, 'finished_UTC': end,
                'budget': {k: v for k, v in read(RUN / 'budget.json').items() if k != 'entries'},
                'decision': 'Stop at16. Retain empty+binding C as a diagnostic candidate; no automatic expansion/Q/classifier/BasePlus.'}
    write(RUN / 'integrity_checks.json', audit)
    write(RUN / 'analysis.json', analysis)
    curated = ROOT / 'results/curated/cle_v41_public_binding_20261025'
    write(curated / 'analysis.json', analysis)
    write(curated / 'integrity_checks.json', audit)
    summary.update(engineering_gate='passed', mechanism_gate='not_passed', comparison_gates=comparisons,
                   mechanism_gate_requires_final_code_review=False, final_code_review_complete=True,
                   next='stop_at16_no_automatic_expansion')
    summary['cost']['physical_usage_by_model'] = per_model
    summary['cost']['embedding_logical_delta_note'] = 'logical embedding9722 is concurrent cumulative-delta telemetry; physical reported8939 is authoritative; originals retained'
    write(RUN / 'summary.json', summary)
    write(curated / 'summary.json', summary)
    report = ROOT / 'docs/CLE_v41公开绑定保护四臂实验报告_20261025.md'
    lines = ['# v4.1公开绑定保护：四臂诊断结果与停止决定', '',
        '**16/16完成，全部完整测量，原生回放16/16一致。工程门通过，综合机制门未过。无卡加公开绑定保护C为4/4，原卡加保护D为3/4；没有建立记忆的额外收益，本轮停在16次。**', '',
        '公开绑定指题目已经提供的全局配置对象，例如允许跳转域名表和文件签名表。保护它，是要求模型直接使用它，不重新声明为空或猜测其内容。Joint指同一份代码同时通过功能F和安全S。', '',
        '## 1. 规格与真实执行', '',
        '用户于2026-10-25授权执行此前6 Pro复审的B03/S2方案。1322、1409来自上轮S1开发题，是事后诊断选择，两题不同family；每题四臂、两次重复，共16次P7。前8次技术段包含在16内，随后完成第二重复。两次重复不是4个独立题族。', '',
        'A原P7空卡；B原P7带1939卡；C空卡加绑定提示；D原卡加同提示。全部共享同题同重复的新v4.1首次初析，B/D首次候选与最终选卡编号和顺序4/4组相同；修复按各自代码和原反馈重新检索。', '',
        '新增指令只追加在复析、规划、生成三个阶段，覆盖c0与c1。没有向初析或检索添加新约束字段，也没有传配置值、目标参考或测试内容。采用请求器薄包装实现，没有修改原P7核心、原数据或验证器。没有启用完整公开契约消费者的新反馈/新交付选择。', '',
        'deepseek-v4.1-flash-1017、thinking disabled、temperature0、正式输出4096、单user、stream true；原选择器256预算和原重试保留。至多三卡、最多一次修复、首次Joint早停、否则交付末次。只读旧1939卡，Q不排序/不更新、无新卡。', '',
        '14项离线检查通过。全部真实请求位于北京时间周日允许时段；共享在途槽上限4。原P3/S1行及卡/Q不变。22份实际代码尝试、22次原验证事件；原生16行零API回放无差异，不触碰凭据、不产生补发。', '',
        '## 2. 主结果', '', '| 臂 | 说明 | 最终F | 最终S | 最终Joint | 首次Joint | 完整测量 |', '|---|---|---:|---:|---:|---:|---:|']
    for arm, label in [('A', '空卡'), ('B', '原1939卡'), ('C', '空卡+绑定保护'), ('D', '原卡+绑定保护')]:
        s = summary['arms'][arm]
        lines.append(f"| {arm} | {label} | {s['final']['functional']}/4 | {s['final']['security']}/4 | {s['final']['joint']}/4 | {s['first']['joint']}/4 | {s['final']['measured']}/4 |")
    lines += ['', '| 主要比较 | 已测救回/损失 | 净Joint | 新S退化 | 门 |', '|---|---:|---:|---:|---|',
        '| C−A：无卡时增加绑定保护 | 2/0 | +2/4 | 0 | 该两题上的单项门通过 |',
        '| D−B：有卡时增加绑定保护 | 2/1 | +1/4 | 1 | 未过：净增不足2且新增安全损失 |',
        '| D−C：保护下的经验额外作用 | 0/1 | −1/4 | 1 | 没有观察到额外收益 |',
        '| B−A：原卡有无 | 0/0 | 0 | 0 | 无Joint变化 |', '',
        '预设综合门要求C−A和D−B同时净≥2/4，C/D在两族都能保绑定且Joint通过，无新配对安全退化。C单项满足；D虽然保持绑定，却在1409首重复失去安全正确性。故综合门未过，不用C的4/4替整套方案宣告通过。', '',
        '两重复的Joint（每臂每重复两题）：A为1/2、1/2；B为1/2、1/2；C为2/2、2/2；D为1/2、2/2。增量集中在1322一个题族，不作小样本统计显著性或一般化保证。', '',
        '## 3. 逐题机制', '', '| 题目 | A两次 | B两次 | C两次 | D两次 | 解释 |', '|---|---|---|---|---|---|',
        '| 1322 重定向 | 均F失败/S通过 | 均F失败/S通过 | 均Joint通过 | 均Joint通过 | A/B把ALLOWED_DOMAINS重定义为空；C/D保留真实表，允许合法外域并拒绝不合法外域 |',
        '| 1409 文件签名 | 均Joint通过 | 均Joint通过 | 首重复先S失败后修复通过；次重复直接通过 | 首重复F通过/S失败，修复仍失败；次重复通过 | 绑定未被清空，但签名与当前文件的对应关系在D首重复中被破坏 |', '',
        '### 1322：保护配置确实救回了正常功能', '',
        '四个A/B最终代码均包含ALLOWED_DOMAINS=[]，把题目提供的列表覆盖为空。安全例仍能通过，因为实现倾向拒绝外域；正常例中的合法外域被一并拒绝。C/D四次最终实现都读取原表且不覆盖，均在首次生成Joint通过；这条代码路径在两重复中一致。', '',
        'B/D初轮卡片完全相同，但B最终仍清空配置，D保留原表。说明该题的瓶颈不只是“有没有找到安全建议”，而是公开配置能否被落实为代码边界。无卡C也成功，救回不需要Q或额外经验。', '',
        '### 1409：保住对象，仍可能用错对象', '',
        '1409-r1-D首次采用seed-442，修复又采用seed-442和seed-467。代码保留VALID_SIGNATURES，却遍历所有条目，把其他文件的签名也加入候选，导致“另一文件的正确签名”被用于当前文件。实际两次验证均为功能2/2、安全0/2，属于错误放行，不是配置清空或过度拒绝。', '',
        '修复规划已经明确要求“bind ... to the specific file_name”，但325行最终代码中_iter_records仍yield不相关value，_parse_record对普通签名字符串丢失原文件key，后续匹配可能返回1。这是可核对的**规划—代码落实断裂**：模型写出了正确意图，实际分支没有遵守。', '',
        '同题C首重复也曾把签名当通用集合而S失败，但一次许可修复后，计划与30行代码都改成按file_name取对应签名，Joint通过。D却引入多格式、HMAC、公钥、目录和文件读取等大量通用分支，仍留下原错误；通用安全建议不保证目标实现正确。', '',
        '1409-r2-D的采用字段格式降级，实际未注入任何卡，仍使用简洁的VALID_SIGNATURES.get(file_name)通过。该降级保留在原生结果中，不能把这次成功归功于经验。A/B的两次成功也说明：上一轮S1此题全部失败不能替代本轮新对照。', '',
        '### 实际采用与因果边界', '',
        'B四次都有声明采用，共13张次；D三次有采用，共8张次。两臂首次终选共享，但采用决定、规划和代码是独立模型输出；相同初始卡片不保证相同采用。D的单次安全损失有具体实现错误路径，不能凭一次差异证明记忆或某张卡普遍有害。当前Q完全未参与。', '',
        '源卡seed-442提供可信签名存储原则，seed-467提供通用密码学校验建议；本轮未证明原则本身错误。问题在于适配时丢失目标文件身份、引入未保证的数据结构/环境假设，以及规划要求没有落实。事后卡片核对不算人工检索金标准，不计算正式召回率。', '',
        '## 4. 成本与执行完整性', '',
        '| 项目 | 实际 |', '|---|---:|',
        f'| 记录的物理传输尝试 | {summary["cost"]["physical_HTTP"]} |',
        '| LLM逻辑请求 / 物理尝试 | 83 / 90 |', '| Embedding逻辑 / 物理 | 7 / 7 |',
        '| 有服务商usage的物理响应 | 90 |', '| 本轮失败尝试用量未知 | 7（URLError 6、ValueError 1） |',
        '| 已知输入Token | 398,242 |', '| 已知输出Token | 78,524 |', '| 已知总Token | 476,766 |',
        '| 其中模型 / Embedding | 467,827 / 8,939 |', '| 含未知尝试保守占额 | 628,031 / 2,000,000 |',
        f'| 真实请求墙钟跨度 | {elapsed:.1f}秒，约{elapsed/60:.2f}分钟 |', '',
        '7次失败传输由原重试规则处理，全部90个逻辑操作最终完成，未决逻辑请求0；未知物理尝试不当免费。没有更换服务、模型、提示角色或关闭TLS校验。Embedding原日志的并发累计差值为9,722，存在783的重叠；以原始HTTP响应的8,939为成本依据，原日志保留。缺新型号账单单价，不填写人民币实付。', '',
        '| 逻辑模型用量归属 | Token |', '|---|---:|', '| 共享首次初析 | 6,095 |', '| 共享首次检索终选 | 97,365 |',
        '| A | 68,805 |', '| B | 158,072 |', '| C | 46,418 |', '| D | 91,072 |', '',
        '共享阶段只计一次。C用量低于A主要伴随更早Joint停止；这些是当前两题用量，不能预测全量费用。', '',
        '## 5. 停止决定和最小后续', '',
        '**本轮按计划收口，不扩24题，不跑全D_gate，不恢复Q或分类器。**综合门未过的原因已明确：D新增一次安全损失，且相对B仅净+1/4。不能靠再增加Q覆盖率修复这个已经发生在最终代码中的关系错误。', '',
        '保留“空卡+公开绑定保护”作为候选，允许的结论仅为：在1322已知故障上，两重复均防止清空配置并恢复Joint；在本次两题总体中C优于A。还不能称为CLE总体提分、跨族稳定收益或PLT/Base/Plus有效。', '',
        '本轮已零API核对“配置对象—当前文件—对应签名”的关系、失败分支及通用密码学卡的适用前提。若再提出新干预，应只改变这一个关系约束，并保留无卡简单方案；这属于新任务，须另立冻结协议与预算，不能把本轮已知失败题调通后当独立确认。完整契约消费者D02仍是不同反馈/交付的整体包，本轮没有证明它有效，也不自动启动。', '',
        '## 6. 产物与复现', '',
        '- 新入口：configs/cle_v41_migration_20261025/binding_study.py；收尾：binding_closeout.py。',
        '- 独立运行区：translation_work/diagnostics/20261025/cle_v41_public_binding_v2；protocol/input/source清单、journals/wire、原生task_rows/attempts/validation_events、共享起点/终选均保留。',
        '- 精简结果：results/curated/cle_v41_public_binding_20261025/summary.json、mechanism_rows.json、analysis.json、integrity_checks.json。',
        '- 零API回放：封存source_bundle中的binding_study.py replay --run-root <运行根>；已有completed_16输出复用，不覆盖或补API。',
        '- 历史S1/P3、原卡/Q、原始失败和手改Word不变；没有提交或推送。']
    report.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    # 仅更新对应任务，不把设计状态批量改成执行成功。
    tasks_path = ROOT / 'docs/cle_memory_mechanisms_20261023/tasks.csv'
    tasks = csv_rows(tasks_path)
    for task in tasks:
        if task['id'] == 'B03':
            task.update(status='16/16完成；工程门通过、综合机制门未过',
                next_action='本轮停止扩样；文件-签名关系已核对，保留C供未来独立方案设计',
                current_evidence='A2/B2/C4/D3，各/4；C-A净2、D-B净1且新增S损失1；回放16/16',
                current_plan='translation_work/diagnostics/20261025/cle_v41_public_binding_v2/protocol.json')
        elif task['id'] == 'B02':
            task.update(next_action='消费B03结果：先定位关系落实错误，不自动恢复五臂')
        elif task['id'] == 'D04':
            task.update(status='三阶段接线完成；14检查及16行原生回放通过',
                next_action='归档本轮记录，不重跑已完成16格', current_evidence='binding_study薄包装；4组B/D共享终选；未知物理用量7保留')
        elif task['id'] == 'D05':
            task.update(status='本轮执行分析及停止报告完成', next_action='交付四臂结果、逐题落实原因与边界',
                        current_evidence='CLE_v41公开绑定保护四臂实验报告_20261025.md及新curated')
    csv_write(tasks_path, tasks)
    checklist_path = ROOT / 'configs/cle_v41_migration_20261025/validation_checklist.csv'
    checklist = csv_rows(checklist_path)
    for row in checklist:
        if row['id'] == 'V16':
            row['status'] = 'B03已16/16；A2/B2/C4/D3；综合门未过，不扩样'
        elif row['id'] == 'V29':
            row['status'] = 'P3全298、S1全48、新B03全16零API回放一致；不是额外模型重复'
        elif row['id'] == 'V30':
            row['status'] = '本轮16格报告完成；C单项机制信号，带卡综合门未过，Q未参与'
    csv_write(checklist_path, checklist)
    for path in [ROOT / 'docs/cle_memory_mechanisms_20261023/README.md',
                 ROOT / 'configs/cle_v41_migration_20261025/README.md',
                 ROOT / 'docs/CLE_v32成果汇总与v41Flash1017迁移验证方案_20261025.md']:
        text = path.read_text(encoding='utf-8-sig')
        if '**16次实际执行更新**' not in text:
            first, rest = text.split('\n', 1)
            target = '../CLE_v41公开绑定保护四臂实验报告_20261025.md' if path.parent.name == 'cle_memory_mechanisms_20261023' else (
                '../../docs/CLE_v41公开绑定保护四臂实验报告_20261025.md' if path.parent.name == 'cle_v41_migration_20261025' else 'CLE_v41公开绑定保护四臂实验报告_20261025.md')
            banner = '**16次实际执行更新**（2026-10-25）：三阶段薄包装接线和14项检查已完成，16/16真实P7与回放完成。Joint A2/B2/C4/D3（各/4）；C−A单项有信号，D−B净+1且新增安全损失，综合门未过，停止扩样。下文“未接线/未执行”是本次运行前的设计历史；当前见[执行分析报告](' + target + ')和tasks.csv。\n\n'
            path.write_text(first + '\n\n' + banner + rest.lstrip('\n'), encoding='utf-8')
    plan_path = ROOT / 'configs/cle_v41_migration_20261025/public_binding_next_plan.json'
    plan = read(plan_path)
    plan.update(status='execution_completed_combined_gate_not_passed', execution_ready=False,
                paid_execution_enabled=False, code_generation_executed=22,
                execution_record=str(RUN / 'protocol.json'), result=str(curated / 'summary.json'),
                implementation_status='completed scoped requester wrapper and shared first selection; run closed, do not relaunch')
    write(plan_path, plan)
    write(RUN / 'closeout.json', {'status': 'completed_and_stopped_at16', 'engineering_gate': 'passed',
          'mechanism_gate': 'not_passed', 'report': str(report), 'further_paid_authorized': False,
          'Q_updates': 0, 'card_generation': 0, 'original_data_and_results_preserved': True})
    print(json.dumps({'report': str(report), 'engineering_gate': 'passed', 'combined_gate': False,
          'known_tokens': 476766, 'unknown_physical_usage': 7, 'new_Q_updates': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
