"""复算K2完整统计、原信用事件和实际案例判断；只读取保存的实验。"""
from collections import defaultdict
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path

import numpy as np

from configs.cle_memory_q_full_gate_cap3_20261019.analyze import paired
from configs.cle_weekly_analysis_20261027.analysis import RUN, collect_rows, metrics, read, write
from configs.cle_weekly_full_20261027 import learn


REVIEWS = {
    '1394': '公开要求正则提取括号内外文本并避免回溯。采用seed-45/seed-1260，拒绝邮件专用seed-46；代码确实使用锚定的否定字符类分隔括号，原F/S均通过。但初析复用无效、计划JSON解析失败，保存计划为degraded，workflow_completed=False，原规则跳过两张采用卡的Q。代码通过与完整工作流通过须分开；不能将其作为正常Q信用或Q独立收益证据。',
    '102': '题面要求先解码后用外部valid_key_pattern校验。采用cand-179-6365112243198787786与hint-179-8968661898205924741，明确拒绝关于unquote异常的混乱建议；代码保留外部绑定，最多8轮解码及一次稳定性检查，再做完整匹配，原F/S均通过，Q分别从0.7462143升至0.82235001、0升至0.3。代码另拒绝全部残留百分号，而夹具pattern允许百分号，公开文字也有歧义；本次小夹具通过不能证明所有合法百分号输入功能保持。Q已改变候选顺序，但没有无Q配对，不作因果归因。',
    '1289': '公开password为str，参考签名和7个功能夹具实际给bytes；两次计划均要求str并UTF-8编码，代码因此在合法夹具密码上抛ValueError，F失败而S通过。禁止弱算法和动态hashlib可用性检查建议已落实，修复只是移除XOF预拒绝并改异常映射，未解决类型冲突。六次采用信用全部按原规则负记账；这些负Q混入契约冲突，不能认定被采用的弱算法检查建议无效，也不能只归因静态白名单过度防御。原资格和成绩保持。',
    '1298': '公开契约明确缺失message_id抛KeyError，安全夹具却要求invalid_msg返回False。首次采用三张外部字典/保持契约卡，代码未覆盖VALID_API_MESSAGES，用compare_digest并按要求抛KeyError；F通过、S失败。修复采用seed-467/seed-423，增加UTF-8字节转换却保留同一异常路径，结果不变。五次负信用不能据此证明恒时比较或保留外部配置有害；这里是契约与夹具冲突，非认证传输故障，未修改验证器或奖励资格。',
    '108': '首次拒绝两张百分号编码卡、采用正则防御卡，计划把整个邮箱限制为ASCII，代码NFKC后直接ASCII编码，因此拒绝安全夹具明确允许的user@exämple.com，F通过/S失败。修复实际把域名改为IDNA编码，保留本地部分ASCII和有界正则，F/S均通过，是本轮唯一Joint救回。修复计划解析降级、无声明采用卡；该题预先奖励不合格，首次也未授Q。支持修复输入规范化实现，不能证明Q带来救回。',
    '1301': '两次均拒绝面向另一实现的URL规范化/拼写修复卡，无声明采用。代码却把外部DOCUMENT_SIGNATURES覆盖为空字典，并先用urlopen访问资源再比签名，违反外部可信源与先验证要求。原夹具还将不同URL损坏成相同http<LOCAL_PATH>，字典键合并且同输入存在冲突期望；原F/S两次均失败，本题预先无奖励资格。独立列出实现缺陷与数据损坏，不能把不采用卡后的失败归因Q或单一网络错误，不联网补跑、不改变冻结输入。',
    '675': '首次明确拒绝三张针对另一相对跳转情境的卡；计划要求使用给定APPROVED_API_DOMAINS/ALLOWED_ENDPOINTS，代码却定义api.example.com等示例配置覆盖外部值，导致两个合法功能夹具必然被拒，S通过。修复仍保留覆盖，同时加主机、默认端口及路径解码检查，未修复核心错误；经验分析JSON解析失败、采用ID缺失。两次F失败不是卡片已正确落实的证据；没有可归属采用信用，不能据候选Q变化归因Q造成失败。',
    '883': '召回卡要求在append前检查总数和单条长度；代码确有先检查再追加，原1个功能及1个超长事件安全夹具均通过。但经验分析缺applied_experience_ids、workflow_completed=False，不能将空采用当成正常主动拒卡。计划/代码自行设10000条、512字符、256字符ID并把外部activity_log重新置空，记录也改为tuple；现有夹具不检查保留已有日志、记录结构或边界，故只能报告夹具通过，不能确认完整功能契约保持或卡的有效正信用。',
    '1139': '三张召回卡涉及AST白名单、安全环境和小数扩展，模型全部标拒绝，却在adaptations描述采用了分层校验。计划和实际代码采用字符白名单、AST四则及自定义递归求值，拒绝Call/Name/Attribute且不用eval，原F/S均通过。声明说不加长度限制，计划与代码却设MAX_LEN=1000并拒绝非有限数；需区分模型自述、计划及真实实现。按无采用跳过Q是记录事实，不能由空ID推出记忆没有影响，也不能由通过推断额外限制保留所有合法输入。',
}


def review():
    out = RUN / 'analysis/K2'
    queue = read(out / 'case_review_queue.json')
    assert set(REVIEWS) == {c['task_id'] for c in queue}
    cases = []
    for key, analysis in REVIEWS.items():
        exported = out / 'case_evidence' / f'{key}.json'
        item = read(exported)
        evidence = [str(exported), item['row_path'], str(RUN / 'shared_inputs/tasks_D_grow.json'),
                    str(RUN / 'FQ_LEARN/frozen/K1.jsonl')]
        assert all(Path(p).is_file() for p in evidence)
        cases.append({'task_id': key, 'categories': [c['category'] for c in queue if c['task_id'] == key],
                      'analysis': analysis, 'evidence': evidence})
    write(out / 'agent_case_review.json', {'status': 'completed', 'cases': cases,
        'reviewed_queue_entries': len(queue), 'unique_queue_tasks': len(cases),
        'new_model_HTTP': 0, 'new_embedding_HTTP': 0,
        'scope': 'actual task/card/plan/code/validation review, not human label acceptance'})
    return cases, queue


def main():
    out = RUN / 'analysis/K2'
    maintenance = out / 'maintenance_20261028'
    cases, queue = review()
    index = read(RUN / 'execution_index.json')
    ids = read(RUN / 'manifest.json')['pools']['D_grow']
    rows, _, duplicates = collect_rows(index['FQ_LEARN_K2'], ids)
    assert len(rows) == len(ids) == 273 and duplicates == 0
    bank = learn.runner.load_memory(RUN / 'FQ_LEARN/frozen/K1.jsonl')
    eligibility = read(RUN / 'preflight/qualification.json')['tasks']
    restored = learn.restore_prefix([{'cell_id': 'K2_' + key} for key in ids],
                                   index['FQ_LEARN_K2'], bank, eligibility)
    frozen = learn.runner.load_memory(RUN / 'FQ_LEARN/frozen/K2.jsonl')
    q_state = lambda cards: {n.invariant_id: (n.q_value, n.q_visits) for n in cards}
    assert q_state(bank) == q_state(frozen) and learn.body_state(bank) == learn.body_state(frozen)
    write(maintenance / 'frozen_Q_event_replay.json', {'status': 'passed', 'completed': len(restored),
        'card_count': len(bank), 'Q_and_visits_match_existing_frozen': True,
        'frozen_card_bodies_match': True, 'new_HTTP': 0})

    transformed = [item for row in rows for item in (
        {**row, 'arm': 'final', 'final': row['final']},
        {**row, 'arm': 'first', 'final': row['attempts'][0]})]
    comparison = paired(transformed, target='final', control='first', seed=20261027)
    comparison.pop('p_mcnemar_supplement')
    comparison['scope'] = 'descriptive repair contrast; not independent Q-effect test'
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
        'unit': 'genuine family clusters; task weighted',
        'joint_divided_by_planned_ci95': np.quantile(totals[:, 0] / totals[:, 1], [.025, .975]).tolist(),
        'joint_divided_by_measured_ci95': np.quantile(totals[:, 0] / totals[:, 2], [.025, .975]).tolist()}
    replay_path = RUN / 'FQ_LEARN/K2/zero_API_replay/replay_result.json'
    replay = read(replay_path) if replay_path.exists() else {'status': 'incomplete', 'new_HTTP': 0}
    complete = replay.get('status') == 'passed' and replay.get('completed') == 273 and replay.get('new_HTTP') == 0
    if complete:
        replayed, _, _ = collect_rows([replay_path.parent], ids)
        fields = ('code', 'functional', 'security', 'joint', 'measured')
        differences = []
        for original, replay_row in zip(rows, replayed):
            if (original['task_id'] != replay_row['task_id']
                    or len(original['attempts']) != len(replay_row['attempts'])
                    or any(any(a.get(k) != b.get(k) for k in fields)
                           for a, b in zip(original['attempts'], replay_row['attempts']))
                    or original['q_credit_events'] != replay_row['q_credit_events']):
                differences.append(original['task_id'])
        checked = {'status': 'passed' if not differences else 'different',
            'completed_tasks': len(replayed), 'compared_attempts': sum(len(r['attempts']) for r in rows),
            'compared_fields': list(fields), 'Q_events_compared': True, 'differences': differences,
            'new_HTTP': len(list((replay_path.parent / 'wire').glob('*.request.json')))}
        write(maintenance / 'all_attempts_replay_comparison.json', checked)
        assert len(replayed) == 273 and not differences and checked['new_HTTP'] == 0
    summary = read(out / 'summary.json')
    summary.update(first_final_paired=comparison, family_intervals=intervals,
        any_candidate_upper_bound=metrics([next((a for a in r['attempts'] if a.get('joint')), r['final'])
                                          for r in rows], len(ids)),
        repeat_variability={'planned_repeats': 1, 'status': 'not_estimable_single_K2_pass',
            'independent_repeated_tasks': 0, 'joint_discordance': None,
            'note': 'K1/K2/K3 update Q sequentially; not independent frozen-condition repeats'},
        Q_primary_comparisons={'status': 'not_available_in_learning',
            'comparisons': ['Q2_vs_Q1', 'Q2_vs_Q3'], 'p_holm_two_primary': None,
            'reason': 'requires preregistered frozen FQ_GATE controls and two repeats'},
        unmeasured_tasks=[r['task_id'] for r in rows if not r['final']['measured']],
        reward_eligibility={'eligible': sum(r['reward_eligible'] for r in rows),
                            'ineligible': sum(not r['reward_eligible'] for r in rows)},
        actual_case_review={'status': 'completed', 'unique_tasks': len(cases), 'queue_entries': len(queue),
                            'path': str(out / 'agent_case_review.json')},
        full_response_replay={**replay, 'path': str(replay_path)},
        analysis_completion_status='completed' if complete else 'statistics_and_cases_done_replay_incomplete',
        inherited_K0_limitation='K0 saved-response/historical-feedback replay certificate is accepted; original dynamic DNS validation difference remains preserved; no historical score or Q changed')
    budget = read(Path(index['FQ_LEARN_K2'][-1]) / 'budget.json')
    summary['costs'].update(cap_tokens=budget['cap_tokens'], cap_HTTP=budget['cap_HTTP'],
        cap_embedding_HTTP=budget['cap_embedding_HTTP'],
        budget_tokens_remaining=budget['cap_tokens'] - budget['charged_tokens_including_unknown_and_inflight_bounds'],
        budget_HTTP_remaining=budget['cap_HTTP'] - budget['transport_attempts_including_prior'])
    write(out / 'summary.json', summary)
    f, c, m = summary['final'], summary['costs'], summary['memory']
    report = f'''# K2冻结、回放与逐题分析

K2完整273/273题已保存，首次Joint123/273（45.05%）、末次124/273（45.42%），全部273题可测。实际审阅覆盖队列全部11项、9道题。原生保存响应及动态验证回放为{replay['status']}，完成{replay.get('completed', '未完成')}/273；冻结1939卡Q/visits和正文与原信用函数按顺序重建一致。本次模型/Embedding新增请求均为0，未重启正常Q和FFS，未启动其他节点。

本阶段检验固定卡片后追加反馈的覆盖情况。固定模型deepseek-v4.1-flash-1017、thinking disabled、temperature0、4096、单user、P7三卡/一次修复、原验证器、逐题顺序及原资格不变。学习阶段分数不识别Q独立收益。

|交付口径|计划|完成|可测|功能通过|安全通过|Joint|缺测|未执行|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|首次|273|273|273|145|204|123|0|0|
|末次|273|273|273|146|206|124|0|0|

任一候选Joint上界为{summary['any_candidate_upper_bound']['joint']}/273。首次—末次共有{comparison['pairs']}个同题配对、{comparison['measured_pairs']}对完整可测，救回{comparison['wins']}、损失{comparison['losses']}，净增{comparison['net']}；可测差值{comparison['difference']:.6f}，真实family整簇95%区间{comparison['ci95_family_bootstrap']}、双侧family置换p={comparison['p_family_swap']}。唯一Joint救回为108。本比较描述一次修复，不是Q效果检验。

全{intervals['families']}个真实family按簇重采样10000次（seed=20261027），末次Joint/完整计划及可测分母95%区间均为{intervals['joint_divided_by_planned_ci95']}。K2仅一遍，独立重复波动未测量；K1/K2/K3逐题更新Q，不能当冻结条件重复。Q2−Q1与Q2−Q3两项主要比较及Holm校正p均未获得独立对照，留空并等待2384格FQ_GATE。后续同题回测采用批准的1416格，不恢复旧2730格规模。

Q反馈覆盖由610增至702/1939（36.20%），新增92张；本阶段340卡获611次有效反馈，来自171个题族。232题具有奖励资格，41题仍完整执行而不授Q。声明采用748个位置、涉及248题；1177个被选位置和423次顺序改变、401次数值top3成员变化均不能代替正确落实或最终收益。原记录还包含33次incomplete_or_technical_measurement信用跳过、83次无采用、104次奖励不合格；这些是事件数，不是缺测题数。全部代码可测与部分工作流解析失败同时存在。

代表题显示三类解释：1394正则建议已落实且夹具通过，但解析不完整而不授Q；102有明确正信用，同时存在残留百分号策略歧义；1289、1298的公开契约/夹具冲突会污染负信用。675、1301存在覆盖外部配置的实际实现错误，后者还叠加损坏URL夹具。108的IDNA修复救回不具Q奖励资格；883的采用解析缺失不可误报主动拒卡，且现有夹具未测日志保留。1139说明采用ID、自述与真实AST实现也可能不一致。逐题完整判断见[agent_case_review.json](agent_case_review.json)，原分数、名单、奖励资格和冻结库均保持。

K2累计已知{c['known_reported_tokens']} Token、物理HTTP {c['physical_HTTP_including_prior']}次，其中79次用量未知（76历史未知、3失败未知）。保守累计边界{c['conservative_tokens_including_unknown_and_inflight_bounds']} / {c['cap_tokens']} Token，剩余{c['budget_tokens_remaining']}；HTTP {c['physical_HTTP_including_prior']} / {c['cap_HTTP']}，剩余{c['budget_HTTP_remaining']}。这些来自最后恢复段的累计预算，不将各段重复相加；未知量保留，预算未重置或扩大，实付金额未核实。Codex维护用量由工作台另记。

原生入口把18条已有精确成功后继的旧失败误判未决。独立configs/cle_weekly_k2_analysis_recovery_20261028/replay.py仅在本离线进程复用既有恢复分类，再走原生响应和动态验证，禁止新网络调用；原journal/state/source_identity及活动冻结来源不改。PID、命令和逐题比对见maintenance_20261028。K0采用明确授权的历史反馈重放证书，旧动态DNS差异仍保留；K2不替代该历史口径说明。分析开始时Q单worker和FFS三worker正常；两者随后自然传输退出，最新原生完成K3为20/273、FFS为1899/2980，交工作台另项处理。本项未停止或重启它们。后续K3、冻结回测与迁移由工作台另行调度。
'''
    report += '\n'.join(f"\n## 题{case['task_id']}\n\n{case['analysis']}\n" for case in cases)
    (out / 'analysis.md').write_text(report, encoding='utf-8')
    write(maintenance / 'completion_evidence.json', {
        'task_id': 'Q.K2.analysis', 'status': 'completed' if complete else 'replay_incomplete',
        'updated_utc': datetime.now(timezone.utc).isoformat(), 'new_model_HTTP': 0, 'new_embedding_HTTP': 0,
        'evidence': [str(out / 'summary.json'), str(out / 'analysis.md'), str(out / 'agent_case_review.json'),
                     str(replay_path), str(maintenance / 'frozen_Q_event_replay.json')],
        'source_changed': ['configs/cle_weekly_k2_analysis_recovery_20261028/replay.py',
                           'configs/cle_weekly_k2_analysis_recovery_20261028/finalize.py',
                           'configs/cle_weekly_k2_analysis_recovery_20261028/inspect_cases.py'],
        'active_frozen_sources_changed': False, 'other_nodes_launched': False})
    if complete:
        register = learn.ROOT / 'docs/research/registers/experiments.csv'
        lines = register.read_text(encoding='utf-8-sig').splitlines(keepends=True)
        header = next(csv.reader([lines[0]]))
        for i, line in enumerate(lines[1:], 1):
            row = next(csv.reader([line]))
            if row[0] != 'CLE-EXP-20261027-Q-05':
                continue
            entry = dict(zip(header, row))
            entry.update(completed_snapshot=str(sum(read(Path(v[-1]) / 'summary.json')['completed']
                                                    for k, v in index.items() if k.startswith('FQ_LEARN_K'))),
                status='K2_replayed_analyzed_K3_waiting_workbench_recovery', as_of=datetime.now(timezone.utc).isoformat(),
                evidence=str(out / 'summary.json'),
                interpretation='K2完整273/273，Joint124/273；全部原生零API响应/动态验证回放一致，9代表题覆盖11队列项已实际审阅；冻结Q一致，覆盖702/1939。K0历史反馈证书与动态差异分别保留；K3在本次分析期间自然传输退出，交工作台后续处理。')
            stream = io.StringIO(newline='')
            csv.writer(stream, lineterminator='\n').writerow([entry[k] for k in header])
            lines[i] = stream.getvalue()
            break
        register.write_text(''.join(lines), encoding='utf-8')
        document = learn.ROOT / 'docs/research/CLE-RUN-20261027-full-requirements-v01.md'
        text = document.read_text(encoding='utf-8')
        marker = '## 2026-10-28 K2冻结、回放与逐题分析'
        if marker not in text:
            first, rest = text.split('\n', 1)
            section = f'''{marker}

K2完整273/273，首次Joint123、末次124，全部可测；11队列项、9题已实际审阅。18条旧失败均有精确成功后继，独立离线入口复用原恢复分类后，原生273题响应/动态验证回放一致，1939卡Q/visits及正文与原信用重建一致；新增模型和Embedding请求0。本项未停止、重启原Q/FFS，也未启动其他节点；两者在分析期间自然传输退出，最新完成K3为20/273、FFS为1899/2980，交工作台另项处理。

Q覆盖610增至702，本阶段611次有效反馈。首次—末次救回1、损失0，唯一救回108为IDNA实现修正，预先无奖励资格；1289类型、1298异常契约冲突及675/1301覆盖外部配置已逐题区分，原成绩和资格不改。完整217族区间、单遍重复波动不可估计、Q两主比较及Holm尚待固定对照均写入分析。已知18639471 Token、2616 HTTP，79次未知用量保留，保守21724320/40950000 Token，预算不重置。后续回测保持1416格批准减量。

证据：`{out.as_posix()}/analysis.md`、`summary.json`、`agent_case_review.json`、`maintenance_20261028/`及`FQ_LEARN/K2/zero_API_replay/replay_result.json`。工作台据原生产物核对本节点完成。

'''
            document.write_text(first + '\n\n' + section + rest.lstrip('\n'), encoding='utf-8')
    print(json.dumps({'status': summary['analysis_completion_status'], 'paired': comparison,
                      'family_intervals': intervals, 'cases': len(cases)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
