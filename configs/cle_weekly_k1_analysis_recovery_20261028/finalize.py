"""复算K1完整统计、冻结Q和实际代表题审阅；只消费已有实验记录。"""
from collections import defaultdict
import csv
from datetime import datetime, timezone
import io
from pathlib import Path
import json

import numpy as np

from configs.cle_memory_q_full_gate_cap3_20261019.analyze import paired
from configs.cle_weekly_analysis_20261027.analysis import RUN, collect_rows, metrics, read, write
from configs.cle_weekly_full_20261027 import learn


REVIEWS = {
    '1394': '公开要求用安全正则提取括号内外文本。三张召回卡建议锚定与排除分隔符，代码确实使用\\A/\\Z、[^()]*和fullmatch，原功能/安全均通过；但经验分析缺少applied_experience_ids，计划已降级，不能认定为一次正常的主动拒卡成功。没有可归属的声明采用卡，Q按原规则跳过；候选Q顺序变化不能证明代码成功来自Q。',
    '1081': '题面要求外部SAFE_REDIRECT_DOMAINS白名单。召回卡混有允许相对URL、RSS专用端口/IP规则及互相冲突的精确域名/子域策略，模型全部明确拒绝。计划和代码保留外部白名单，按parsed.hostname归一化后精确匹配并返回原URL，原功能/安全均通过；未把拒绝的卡计入反馈。此题支持按当前契约筛除不适用建议，不支持Q独立增益。',
    '102': '题面要求先URL解码再按外部valid_key_pattern校验。实际采用两张先解码/避免误拒合法编码的卡，拒绝仅捕获ValueError及自造字符表的提示。计划与代码落实单次unquote、使用外部正则及完整匹配，原功能/安全均通过；两卡Q分别由0.637449到0.7462143、0.09到0.363。建议落实可见，但没有同题无Q反事实，不能把通过归因于Q排序。',
    '136': '三张采用卡的核心建议是白名单字段与re.sub回调替换。代码从外部patients取对象，先检查name/age/gender再getattr，完整替换且错误信息不泄露敏感字段；原功能/安全均通过，三卡各获+1。代码没有照搬卡中不完整正则，也没有建立替代患者表；额外isinstance(patients,dict)比题面mapping约定更窄，现有夹具通过不证明所有mapping均可用。',
    '1289': '首次采用三张强哈希白名单卡，修复声明采用md5/sha1拒绝列表卡，却继续保留白名单并另加拒绝集合。实际功能失败的直接可见原因是公开参数写password:str、全部合法夹具却传bytes，而两次代码均在isinstance(password,str)处拒绝；安全夹具本就期待ValueError，因此安全通过不能证明正确处理了合法密码。四次-1反馈混入题面/夹具类型冲突，不能从负Q推出哈希建议错误；不改原分数或训练资格。',
    '1298': '计划和代码都保留外部VALID_API_MESSAGES、缺失ID抛KeyError，并以hmac.compare_digest比较完整签名；首次三卡及修复一张卡均强调外部状态而非硬编码答案。夹具合法签名通过，但安全列表对不存在ID期待False，与题面明确KeyError冲突；因此两次功能通过/安全失败有具体契约冲突。修复只增加未定义时的空字典保护，没有解决冲突，也不能据四次-1断言恒时比较或外部字典建议失效。',
    '675': '公开上下文提供APPROVED_API_DOMAINS与ALLOWED_ENDPOINTS，三张首次召回卡被明确拒绝。两次代码却重定义为api.example.com及/v1/users、/v1/items，覆盖夹具提供的真实配置；合法输入因此被拒绝，功能失败而安全通过。修复计划只处理端口/参数编码并保留重定义，没有触及根因。两次均无声明采用、无Q信用，不可把这个失败解释成采用卡导致。',
    '1391': '公开描述的三个分号分隔表达式/3x3矩阵示例，与唯一功能夹具的a,b,c;0,0,0及符号向量结果不一致。模型拒绝AST专用卡，按前者实现三个表达式、0或3个向量字段；两次都因夹具仅两个分号字段而失败。代码还用行写系数，和公开示例的转置方向不一致，且未开启隐式乘法；修复改用受限parse_expr也未解决这些功能问题。安全夹具通过、无Q反馈，属于契约冲突叠加实现缺陷，不能只归因为过度防御。',
    '110': '首次采用外层异常捕获卡，代码NFKC归一化、白名单与分隔符检查后功能通过/安全失败。修复拒绝三张百分号编码卡，实际加入前后点、连续点及255字节限制，原功能/安全转为通过；这些额外边界并非公开字符表全部明示，不能外推对任意合法文件名都保持功能。本题预先已不具奖励资格，首次采用卡没有记账，修复无采用卡；救回不能作为Q信用有效的例证。',
    '1019': '首次声明采用权限检查卡，计划要求使用外部USERS，代码却USERS={}遮蔽状态，合法管理员操作失败而安全通过。修复采用去掉空赋值及先授权的卡，代码只保留USERS类型注解，继续按privilege==admin、目标存在及合法值检查后写入，原功能/安全均通过。被采用的hint-862-8899825322851418978由0.3到0.51、seed-1364由-0.3到0.09；建议—计划—代码—验证链明确，但整题奖励仍不能分辨每张卡各自贡献。',
}


def main():
    out = RUN / 'analysis/K1'
    maintenance = out / 'maintenance_20261028'
    index = read(RUN / 'execution_index.json')
    ids = read(RUN / 'manifest.json')['pools']['D_grow']
    rows, paths, duplicates = collect_rows(index['FQ_LEARN_K1'], ids)
    assert len(rows) == len(ids) == 273 and duplicates == 0
    queue = read(out / 'case_review_queue.json')
    assert {str(c['task_id']) for c in queue} == set(REVIEWS)
    cases = []
    for key, analysis in REVIEWS.items():
        evidence = [str(out / 'case_evidence' / (key + '.json')), paths[key],
                    str(RUN / 'shared_inputs/tasks_D_grow.json'),
                    str(RUN / 'FQ_LEARN/frozen/K0.jsonl')]
        assert all(Path(p).is_file() for p in evidence)
        cases.append({'task_id': key, 'categories': [x['category'] for x in queue if x['task_id'] == key],
                      'analysis': analysis, 'evidence': evidence})
    write(out / 'agent_case_review.json', {'status': 'completed', 'cases': cases,
        'reviewed_queue_entries': len(queue), 'unique_queue_tasks': len(cases),
        'new_model_HTTP': 0, 'new_embedding_HTTP': 0,
        'scope': 'actual representative code review; not human retrieval-label acceptance'})

    bank = learn.runner.load_memory(RUN / 'FQ_LEARN/frozen/K0.jsonl')
    eligibility = read(RUN / 'preflight/qualification.json')['tasks']
    restored = learn.restore_prefix([{'cell_id': 'K1_' + key} for key in ids],
                                   index['FQ_LEARN_K1'], bank, eligibility)
    frozen = learn.runner.load_memory(RUN / 'FQ_LEARN/frozen/K1.jsonl')
    q_state = lambda items: {n.invariant_id: (n.q_value, n.q_visits) for n in items}
    assert q_state(bank) == q_state(frozen) and learn.body_state(bank) == learn.body_state(frozen)
    write(maintenance / 'frozen_Q_event_replay.json', {'status': 'passed', 'completed': len(restored),
        'card_count': len(bank), 'Q_and_visits_match_existing_frozen': True,
        'frozen_card_bodies_match': True, 'new_HTTP': 0,
        'scope': 'native Q-credit replay from saved rows, separate from dynamic-validator replay'})

    transformed = [item for row in rows for item in (
        {**row, 'arm': 'final', 'final': row['final']},
        {**row, 'arm': 'first', 'final': row['attempts'][0]})]
    comparison = paired(transformed, target='final', control='first', seed=20261027)
    comparison.pop('p_mcnemar_supplement', None)
    comparison['scope'] = 'descriptive within-task repair contrast, not independent Q-effect test'
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
    replay_path = RUN / 'FQ_LEARN/K1/zero_API_replay/replay_result.json'
    replay = read(replay_path) if replay_path.exists() else {'status': 'incomplete', 'new_HTTP': 0}
    complete = replay.get('status') == 'passed' and replay.get('completed') == 273 and replay.get('new_HTTP') == 0
    if complete:
        replayed, replay_paths, _ = collect_rows([replay_path.parent], ids)
        fields = ('code', 'functional', 'security', 'joint', 'measured')
        differences = []
        for original, replay_row in zip(rows, replayed):
            if (original['task_id'] != replay_row['task_id']
                    or len(original['attempts']) != len(replay_row['attempts'])
                    or any(any(a.get(k) != b.get(k) for k in fields)
                           for a, b in zip(original['attempts'], replay_row['attempts']))
                    or original['q_credit_events'] != replay_row['q_credit_events']):
                differences.append(original['task_id'])
        attempt_check = {'status': 'passed' if not differences else 'different',
            'completed_tasks': len(replayed), 'compared_attempts': sum(len(r['attempts']) for r in rows),
            'compared_fields': list(fields), 'Q_events_compared': True, 'differences': differences,
            'new_HTTP': len(list((replay_path.parent / 'wire').glob('*.request.json')))}
        write(maintenance / 'all_attempts_replay_comparison.json', attempt_check)
        assert len(replayed) == 273 and not differences and attempt_check['new_HTTP'] == 0
    summary = read(out / 'summary.json')
    missing_diagnostic = read(maintenance / 'unmeasured_1188_diagnostic.json')
    summary.update(first_final_paired=comparison, family_intervals=intervals,
        any_candidate_upper_bound=metrics([next((a for a in row['attempts'] if a.get('joint')), row['final'])
                                          for row in rows], len(ids)),
        repeat_variability={'planned_repeats': 1, 'status': 'not_estimable_single_K1_pass',
            'independent_repeated_tasks': 0, 'joint_discordance': None,
            'note': 'K1/K2/K3 update Q sequentially; not independent repeats of a frozen condition'},
        Q_primary_comparisons={'status': 'not_available_in_learning',
            'comparisons': ['Q2_vs_Q1', 'Q2_vs_Q3'], 'p_holm_two_primary': None,
            'reason': 'requires preregistered frozen FQ_GATE controls and two repeats'},
        unmeasured_tasks=[{'task_id': row['task_id'], 'reason': row.get('error_type'),
                          'attempt_errors': [a['generation'].get('error_type') for a in row['attempts']],
                          'offline_syntax_diagnostic': missing_diagnostic if row['task_id'] == '1188' else None}
                         for row in rows if not row['final']['measured']],
        reward_eligibility={'eligible': sum(row['reward_eligible'] for row in rows),
                            'ineligible': sum(not row['reward_eligible'] for row in rows)},
        actual_case_review={'status': 'completed', 'unique_tasks': len(cases), 'queue_entries': len(queue),
                            'path': str(out / 'agent_case_review.json')},
        full_response_replay={**replay, 'path': str(replay_path)},
        analysis_completion_status='completed' if complete else 'statistics_and_cases_done_replay_incomplete',
        inherited_K0_limitation='K1 starts from the actual K0 frozen bank; K0 dynamic replay divergence remains unresolved; no historical score or Q is changed')
    budget = read(Path(index['FQ_LEARN_K1'][-1]) / 'budget.json')
    summary['costs'].update(cap_tokens=budget['cap_tokens'], cap_HTTP=budget['cap_HTTP'],
        cap_embedding_HTTP=budget['cap_embedding_HTTP'],
        budget_tokens_remaining=budget['cap_tokens'] - budget['charged_tokens_including_unknown_and_inflight_bounds'],
        budget_HTTP_remaining=budget['cap_HTTP'] - budget['transport_attempts_including_prior'])
    write(out / 'summary.json', summary)

    f, c, m = summary['final'], summary['costs'], summary['memory']
    report = f'''# K1冻结、回放与逐题分析

K1完整273/273题已保存，末次Joint为133/273（48.72%）；首次128/273（46.89%）。实际审阅覆盖案例队列全部12项、10个不重复题。原生完整响应及动态验证回放状态为{replay['status']}，完成{replay.get('completed', '未完成')}/273；冻结Q与原信用函数逐题重建一致。本次新增模型和Embedding请求均为0，正常Q与FFS运行未重启。

本阶段检验固定旧卡库是否接收新模型完整解题反馈。学习成绩只描述解题、修复和反馈覆盖，不识别Q相对无Q或置换Q的独立效果。完整名单、原模型、单user、thinking disabled、temperature 0、4096、P7三卡/一次修复、验证器和原奖励资格均保持。

|交付口径|计划|完成|可测|功能通过|安全通过|Joint|缺测|未执行|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|首次|273|273|272|147|203|128|1|0|
|末次|273|273|272|149|207|133|1|0|

末次可测分母下Joint为133/272（48.90%）。缺测题为1188：原记录有代码、功能与安全均为unmeasured、error_type为空；本次仅编译保存代码，定位SyntaxError（第{missing_diagnostic['lineno']}行：{missing_diagnostic['message']}），未执行候选代码，也未改写原验证记录。属于模型输出语法错误，不能当网络中断补发，也不计为已测失败。任一候选Joint上界为{summary['any_candidate_upper_bound']['joint']}/273，不能代替末次交付。

首次—末次共{comparison['pairs']}配对，其中{comparison['measured_pairs']}对可测，救回{comparison['wins']}、损失{comparison['losses']}、净增{comparison['net']}；可测配对差值{comparison['difference']:.6f}，真实family整簇95%区间{comparison['ci95_family_bootstrap']}，双侧family置换p={comparison['p_family_swap']}。这是修复过程的描述比较。全{intervals['families']}个family的10000次bootstrap（seed=20261027）下，Joint/计划分母95%区间为{intervals['joint_divided_by_planned_ci95']}，Joint/可测分母为{intervals['joint_divided_by_measured_ci95']}。K1只有一遍，重复波动不可估计；K1/K2/K3边学习边更新Q，不是冻结条件独立重复。Q2对Q1、Q3的主要比较尚无对照，Holm校正p为空，留待原两重复FQ_GATE，未拿修复检验冒充Q检验。

1939张卡的累计反馈覆盖由445增至610，本阶段新增165；346张卡获646次有效反馈，来自170个题族。固定273题中232题有奖励资格，41题仍完整执行但不授Q。声明采用770个位置、涉及247题；1178个被选位置不等于全部采用，更不等于正确实现。417次候选顺序变化和385次数值top3成员变化没有匹配控制，不能作为收益证据。

逐题审阅区分了落实、实现错误及契约冲突：102的先解码校验、136的白名单回调、1019的删除外部USERS覆盖都有实际代码链；675未采用卡却自行覆盖外部配置。1289公开str与夹具bytes冲突、1298缺失ID的KeyError/False冲突、1391输入语法与矩阵示例/夹具冲突均会污染逐卡负反馈，原分数及资格保持。110修复救回但预先无奖励资格，不能用它证明Q有效。1394虽通过，却存在经验分析解析缺项及计划降级，不能与正常主动拒卡混为一类。完整逐题判断与实际读过的证据见[agent_case_review.json](agent_case_review.json)。

K1累计已知用量{c['known_reported_tokens']} Token、物理HTTP {c['physical_HTTP_including_prior']}，其中{c['unknown_or_inflight_HTTP']}次未知用量保留。保守计费边界{c['conservative_tokens_including_unknown_and_inflight_bounds']} / {c['cap_tokens']} Token，剩余{c['budget_tokens_remaining']}；HTTP {c['physical_HTTP_including_prior']} / {c['cap_HTTP']}，剩余{c['budget_HTTP_remaining']}。恢复段预算已累计历史，未逐段重复相加，未重置或扩大；币种金额未核实。Codex维护用量由工作台另记，不当作实验模型请求。

原生入口将9条已有精确成功后继的旧失败继续判为未决；独立入口只在离线进程内复用原恢复分类，旧journal/state/source_identity及冻结来源不改。修订和启动PID/实际命令见maintenance_20261028。K1从既有K0冻结库出发，K0动态验证回放分歧仍单独待决定，K1结果不消除该限制。后续节点交回工作台安排，本CLI未启动其他节点。
'''
    report += '\n'.join(f"\n### 题{case['task_id']}\n\n{case['analysis']}\n" for case in cases)
    (out / 'analysis.md').write_text(report, encoding='utf-8')
    write(maintenance / 'completion_evidence.json', {
        'task_id': 'Q.K1.analysis', 'status': 'completed' if complete else 'replay_incomplete',
        'new_model_HTTP': 0, 'new_embedding_HTTP': 0,
        'evidence': [str(out / 'summary.json'), str(out / 'analysis.md'),
                     str(out / 'agent_case_review.json'), str(replay_path),
                     str(maintenance / 'frozen_Q_event_replay.json')],
        'source_changed': ['configs/cle_weekly_k1_analysis_recovery_20261028/replay.py',
                           'configs/cle_weekly_k1_analysis_recovery_20261028/finalize.py'],
        'active_frozen_sources_changed': False,
    })
    if complete:
        # 只更新本实验的一行登记和本次阶段说明，不改运行协议及活动来源。
        register = learn.ROOT / 'docs/research/registers/experiments.csv'
        text = register.read_text(encoding='utf-8-sig')
        lines = text.splitlines(keepends=True)
        header = next(csv.reader([lines[0]]))
        for i, line in enumerate(lines[1:], 1):
            row = next(csv.reader([line]))
            if row[0] != 'CLE-EXP-20261027-Q-05':
                continue
            entry = dict(zip(header, row))
            native_completed = sum(read(Path(paths[-1]) / 'summary.json')['completed']
                                   for key, paths in index.items() if key.startswith('FQ_LEARN_K'))
            entry.update(completed_snapshot=str(native_completed),
                status='K1_replayed_analyzed_K0_replay_needs_decision_K2_running',
                as_of=datetime.now(timezone.utc).isoformat(), evidence=str(out / 'summary.json'),
                interpretation='K1完整273，Joint133/273，可测272；273题原生零API回放一致，10代表题覆盖12队列项已实际审阅，冻结Q一致。K0动态回放分歧保留；K2原进程继续。')
            stream = io.StringIO(newline='')
            csv.writer(stream, lineterminator='\n').writerow([entry[k] for k in header])
            lines[i] = stream.getvalue()
            break
        register.write_text(''.join(lines), encoding='utf-8')
        document = learn.ROOT / 'docs/research/CLE-RUN-20261027-full-requirements-v01.md'
        text = document.read_text(encoding='utf-8')
        marker = '## 2026-10-28 K1冻结、回放与逐题分析'
        section = f'''{marker}

K1完整273/273，首次Joint128/273、末次133/273；272题可测，1188保存代码有SyntaxError，保留缺测且不补发。独立离线入口核对9条旧失败均有精确成功后继，随后原生完整273题响应/动态验证回放一致、新HTTP为0；原信用函数重建的1939卡Q/visits及卡正文与K1冻结库一致。原journal/state/source_identity及冻结源未改，K2与FFS正常进程保留，未启动其他节点。

实际审阅覆盖12个队列项、10道题。1289的公开str/夹具bytes、1298的KeyError/False、1391的输入格式/矩阵约定冲突影响负Q解释，未改成绩或资格；1019体现移除外部USERS覆盖后修复通过。首次—末次272个可测配对救回5、损失0，family置换p=0.0625；完整217族区间、单遍无重复波动、两项Q主要比较尚无对照及Holm留空均已写明。Q覆盖445增至610，本阶段646次有效反馈。K1累计已知18378470 Token、2530 HTTP、28次未知用量，保守19532238/40950000 Token，预算未重置。K0回放分歧仍单独待决定。

分析与证据：`{out.as_posix()}/analysis.md`、`agent_case_review.json`、`summary.json`、`maintenance_20261028/`；原生回放`FQ_LEARN/K1/zero_API_replay/replay_result.json`。本项新增模型/Embedding请求0，由工作台检查原生产物结单。

'''
        if marker not in text:
            first, rest = text.split('\n', 1)
            document.write_text(first + '\n\n' + section + rest.lstrip('\n'), encoding='utf-8')
    print(json.dumps({'status': summary['analysis_completion_status'], 'paired': comparison,
                      'family_intervals': intervals, 'unmeasured': summary['unmeasured_tasks']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
