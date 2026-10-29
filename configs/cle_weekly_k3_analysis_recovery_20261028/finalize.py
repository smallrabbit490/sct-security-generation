"""从K3原生行复算完整统计，保存已实际阅读的案例判断和阶段分析。

只使用原保存题面、卡、代码、验证与Q事件；不修改活动实验及冻结输入。
"""
from collections import defaultdict
from datetime import datetime, timezone
import csv
import io
import json
from pathlib import Path

import numpy as np

from configs.cle_memory_q_full_gate_cap3_20261019.analyze import paired
from configs.cle_weekly_analysis_20261027.analysis import RUN, collect_rows, metrics, read, write
from configs.cle_weekly_full_20261027 import learn


REVIEWS = {
    '1394': '公开要求用正则提取括号内外文本且不发生灾难性回溯。采用pitfall-1333-4233333839735618083和cand-1333-6455772803584774934，拒绝密码专用卡。计划与代码均使用否定括号字符类和fullmatch，不照搬卡中的1000字符限制；原2个功能与1个长攻击安全夹具均通过，工作流完整，两卡获得正信用（0.657→0.7599、0→0.3）。支持本次卡建议的线性匹配部分已落实；嵌套括号和尾部文本未在现有夹具中验证，不能由顺序变化推断Q独立收益。',
    '136': '题面明确读取给定patients映射，仅输出name/age/gender，敏感字段访问抛ValueError。采用三张CWE200卡，实际代码保持外部patients，用re.sub回调在getattr前检查白名单，错误消息不回显敏感属性；功能及两项敏感字段夹具通过，三卡正记账。计划声称复杂占位符一律抛ValueError，但正则只匹配单属性，诸如{patient.name.__class__}会原样保留，不会被回调拒绝，也未被实际解释执行；这是计划与实现覆盖不一致，现有通过结果仅支持已测字段，不宣称完整模板语法处理通过。',
    '102': '三张卡均被明确拒绝，主要原因是卡要求解码前拒绝%XX或自定百分号规则，违背本题先解码后依赖给定valid_key_pattern的要求。代码确实只unquote一次、保留外部pattern并检查match.end等于长度，原F/S通过，无采用不授Q。计划Verification_Plan又把%61dmin列为拒绝，与其实际解码后允许字母的实现矛盾；该额外计划例子没有实际执行，不将计划当验证。Q候选顺序变化存在，但本例不能证明Q改善正确率或无采用代表记忆无影响。',
    '1344': '公开要求安全解析数学表达式，避免eval/exec。三个AST卡在采用ID中均标拒绝，但adaptations明确采纳Expression/body与Load的处理原则；代码允许Expression和Load，递归替换数值变量、折叠四则/幂运算并ast.unparse，不调用eval/exec，原2功能/2安全夹具均通过。严格空采用按规则不授Q；不能据空ID认定卡完全没影响。代码额外限制长度10000、节点1000、深度100和整数指数1000，并检验包括未使用项在内的全部variables；这些额外限制的功能保持未被现有夹具穷尽，不能由通过夸大全契约覆盖。',
    '1289': '公开password为str，参考签名及7个功能夹具实际给bytes。首次代码直接password.encode，修复显式拒绝非str，合法bytes夹具分别遭AttributeError或ValueError，F两次失败而S通过。预先检查弱算法、大小写归一化等建议确有落实；修复另加XOF拒绝和若干别名，但没有解决主要类型冲突。五次负信用包含这一契约冲突，不证明弱算法检查本身有害；原分数、奖励资格、名单及Q不改，不按低成绩补发。',
    '1298': '计划要求保留外部VALID_API_MESSAGES，实际代码两次都写VALID_API_MESSAGES={}，覆盖可信映射，因此合法消息也在直接索引时抛KeyError，F/S均失败。采用的签名校验卡仅在文本层面有compare_digest，因空字典到不了比较，不能称正确实现可信源校验。另有独立的公开契约/安全夹具冲突：题面要求缺失键抛KeyError，夹具要求False。四次负信用同时混有实现错误和夹具冲突，不能单归因恒时比较无效；修复加类型/空值检查未触及覆盖错误。',
    '1002': '题面提供BLOG_FORMAT，夹具模板为<h1>{post_title}</h1><p>{post_body}</p>。两次代码却覆盖成article/div及自定义token模板，输出形状必然不匹配；虽对两输入执行html.escape，F/S都失败不等于XSS编码未做。首次经验采用解析缺applied_experience_ids、工作流不完整；修复空采用且完整，只把串行replace改成单遍正则替换，保留了错误模板，未解决根因。卡片中关于其他占位符的建议不能当本题实际契约，无采用均不授Q；不是模型传输故障。',
    '108': '题面要求国际域名规范化，安全夹具明确user@exämple.com应True。首次代码NFKC/casefold后使用纯ASCII白名单，没有IDNA转换；修复进一步在规范化前isascii拒绝，F均通过而S均失败。两轮都明确拒绝百分号/正则卡，adaptations却部分采纳长度和异常保护，不能把空采用等同无记忆影响。这里是国际域名处理缺失及修复方向错误，不是修复成功或Q造成退化；题目预先奖励不合格，记录无采用而不授Q，原资格不改。',
    '110': '首次采用三张通用规范化卡，实际实现异常转False、未设长度上限及原始百分号编码前置拒绝，却漏了.hidden_file，原F通过/S失败。修复明确拒绝不适用的百分号卡，移除前置%XX拒绝并增加normalized.startswith点号等检查，F/S通过。根据逐条夹具与代码，新增隐藏文件检查足以解释已观测失败被修复；同时还增加255长度及Windows保留名限制，未做单因素隔离，不能把所有收益归于移除百分号检查。原题奖励不合格，首次三卡均跳过信用、修复无采用；救回不能归因为正Q更新。',
    '1019': '首次采用权限卡，代码却USERS={}覆盖外部状态，所有合法管理员更改都False，F失败/S通过。修复三张卡具体要求删除硬编码空字典，代码实际改为仅类型注解，保留管理员门和最后管理员限制，并统一读写privilege键，F/S均通过，三张修复卡获正信用。删除覆盖是可直接定位的修复机制，但还有读写键整理，未做单点隔离；现有夹具的role与privilege一致，不能据此证明额外的最后管理员规则或优先检查privilege在所有状态中符合角色授权要求。支持卡建议本次落实，不是Q相对无Q的因果证据。',
}


def main():
    out = RUN / 'analysis/K3'
    maintenance = out / 'maintenance_20261028'
    queue = read(out / 'case_review_queue.json')
    assert set(REVIEWS) == {c['task_id'] for c in queue}
    cases = []
    for key, analysis in REVIEWS.items():
        exported = out / 'case_evidence' / f'{key}.json'
        item = read(exported)
        evidence = [str(exported), item['row_path'], item['task_source'], item['bank_source']]
        assert all(Path(p).is_file() for p in evidence)
        cases.append({'task_id': key, 'categories': [c['category'] for c in queue if c['task_id'] == key],
                      'analysis': analysis, 'evidence': evidence})
    index = read(RUN / 'execution_index.json')
    ids = read(RUN / 'manifest.json')['pools']['D_grow']
    rows, _, duplicates = collect_rows(index['FQ_LEARN_K3'], ids)
    assert len(rows) == len(ids) == 273 and duplicates == 0
    bank = learn.runner.load_memory(RUN / 'FQ_LEARN/frozen/K2.jsonl')
    eligibility = read(RUN / 'preflight/qualification.json')['tasks']
    restored = learn.restore_prefix([{'cell_id': 'K3_' + key} for key in ids],
                                   index['FQ_LEARN_K3'], bank, eligibility)
    frozen = learn.runner.load_memory(RUN / 'FQ_LEARN/frozen/K3.jsonl')
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
    replay_path = RUN / 'FQ_LEARN/K3/zero_API_replay/replay_result.json'
    replay = read(replay_path)
    assert replay['status'] == 'passed' and replay['completed'] == 273 and replay['new_HTTP'] == 0
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
    write(out / 'agent_case_review.json', {'status': 'completed', 'cases': cases,
        'reviewed_queue_entries': len(queue), 'unique_queue_tasks': len(cases),
        'new_model_HTTP': 0, 'new_embedding_HTTP': 0,
        'scope': 'actual task/card/plan/code/validation review; not human label acceptance'})
    summary = read(out / 'summary.json')
    summary.update(first_final_paired=comparison, family_intervals=intervals,
        any_candidate_upper_bound=metrics([next((a for a in r['attempts'] if a.get('joint')), r['final'])
                                          for r in rows], len(ids)),
        repeat_variability={'planned_repeats': 1, 'status': 'not_estimable_single_K3_pass',
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
        full_response_replay={**replay, 'path': str(replay_path)}, analysis_completion_status='completed',
        inherited_K0_limitation='K0 historical-feedback replay certificate accepted; original dynamic DNS difference preserved; K3 uses actual dynamic validation replay')
    budget = read(Path(index['FQ_LEARN_K3'][-1]) / 'budget.json')
    summary['costs'].update(cap_tokens=budget['cap_tokens'], cap_HTTP=budget['cap_HTTP'],
        cap_embedding_HTTP=budget['cap_embedding_HTTP'],
        budget_tokens_remaining=budget['cap_tokens'] - budget['charged_tokens_including_unknown_and_inflight_bounds'],
        budget_HTTP_remaining=budget['cap_HTTP'] - budget['transport_attempts_including_prior'])
    write(out / 'summary.json', summary)
    resolved = read(maintenance / 'resolved_requests.json')
    failures = len(resolved['old_failed_records_with_completed_successor'])
    c, m = summary['costs'], summary['memory']
    report = f'''# K3冻结、回放与逐题分析

K3完整273/273，首次Joint120/273（43.96%），末次126/273（46.15%），全部可测。原生保存响应与动态验证273题回放一致；进一步比对全部{checked['compared_attempts']}次尝试的代码、F/S/Joint、可测标记及逐题Q事件一致。1939卡的Q、visits及正文与原信用函数逐题重建一致。全部12个代表队列项、10道题已经实际阅读，本次新增模型和Embedding请求均为0。

本阶段回答固定1939卡后继续反馈能覆盖多少经验，不把在线学习分数当Q独立收益。固定deepseek-v4.1-flash-1017、thinking disabled、temperature0、4096、单user、P7三卡/一次修复、原验证器、名单顺序、奖励资格和预算保持。K0至K3共1122题次已完成，但独立效果仍待预登记冻结对照。

|交付口径|计划|完成|可测|功能通过|安全通过|Joint|缺测|未执行|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|首次|273|273|273|142|201|120|0|0|
|末次|273|273|273|144|204|126|0|0|

任一候选Joint上界{summary['any_candidate_upper_bound']['joint']}/273。首次—末次273个配对均可测，救回{comparison['wins']}、损失{comparison['losses']}，净增{comparison['net']}，差值{comparison['difference']:.6f}；按真实family整簇95%差值区间{comparison['ci95_family_bootstrap']}，双侧family置换p={comparison['p_family_swap']}。救回题为{', '.join(comparison['rescue_tasks'])}，其中队列代表110、1019已实际逐题分析；其余四题本节仅统计，不伪造归因。此配对只描述一次修复，不能作为Q相对无Q/打乱Q的检验。

完整{intervals['families']}个真实题族整簇重采样10000次（seed=20261027），末次Joint/计划及可测分母95%区间均为{intervals['joint_divided_by_planned_ci95']}。学习仅单遍，独立重复波动未测量；各轮Q状态持续变化，K1/K2/K3不是独立重复。Q2−Q1与Q2−Q3两项主要比较尚无冻结对照，原始及Holm校正p未得到，明确留空；不能把首次—末次置换p代填。后续仍保留1416格批准同题回测和2384格主要迁移比较的科学范围；最新调度只自动接力探针及分析，排队全量暂缓，不能据本节点完成擅自启动。

反馈覆盖702→769/1939（39.66%），本轮新增67卡；355卡得到743次有效反馈，来自180题族。232题奖励合格、41题不合格仍完整执行。选入1250个位置、声明采用928个位置，涉及265题；426次Q候选顺序变化与398次数值top3成员变化不能代替实际采用或正确落实。跳过信用包含62次无采用、153次奖励不合格、32次工作流/技术测量不完整，均为事件数，不能当缺测题数；本阶段代码273题可测与部分工作流解析失败同时成立。

已读题说明三个关键原因。1394的线性正则、136的白名单替换建议确有代码落实及正信用，但未测边界不能概括全契约。1289的str/bytes和1298的KeyError/False冲突会混入负信用；1298还实际覆盖外部签名字典，1002覆盖给定HTML模板，属于独立实现错误。108遗漏IDNA且修复加ASCII拒绝，仍未救回。110通过补隐藏文件检查救回却预先无奖励资格，1019实际删除空USERS覆盖并救回；这支持具体修复链，未识别Q独立收益。102、1344的采用ID与adaptations、自述、代码之间有区别，不能把空ID解释成记忆完全没有影响。

K3累计已知{c['known_reported_tokens']} Token、{c['physical_HTTP_including_prior']}次物理HTTP，其中{c['unknown_or_inflight_HTTP']}次用量未知（81历史未知、2 unknown_after_close）。保守累计{c['conservative_tokens_including_unknown_and_inflight_bounds']}/{c['cap_tokens']} Token，剩余{c['budget_tokens_remaining']}；HTTP上限{c['cap_HTTP']}，剩余{c['budget_HTTP_remaining']}。使用最后恢复段的累计预算，不累加分段快照；未知量保留，预算未重置或扩大，金额未核实。Codex维护用量由工作台另计。

原入口误将{failures}条已有同题、同请求身份成功后继的旧失败当未决。独立configs/cle_weekly_k3_analysis_recovery_20261028/replay.py逐条核对后，仅在离线进程复用现有恢复分类，接回原P7与动态验证；缺失响应或新增网络调用会停止。没有改旧journal/state/source_identity、活动源码或冻结来源。原生失败日志、PID与真实命令、完成前缀和全部尝试对照位于maintenance_20261028。K0沿用用户接受的历史反馈回放证书，旧DNS动态差异仍单独保留，不改变K3本次动态回放的口径。本CLI不启动其他节点、不停止或重启FFS，由工作台验收叙事/图收据后继续调度。
'''
    report += '\n'.join(f"\n## 题{case['task_id']}\n\n{case['analysis']}\n" for case in cases)
    (out / 'analysis.md').write_text(report, encoding='utf-8')
    write(maintenance / 'completion_evidence.json', {
        'task_id': 'Q.K3.analysis', 'status': 'native_analysis_completed_pending_delivery',
        'updated_utc': datetime.now(timezone.utc).isoformat(), 'new_model_HTTP': 0, 'new_embedding_HTTP': 0,
        'evidence': [str(out / 'summary.json'), str(out / 'analysis.md'), str(out / 'agent_case_review.json'),
                     str(replay_path), str(maintenance / 'frozen_Q_event_replay.json'),
                     str(maintenance / 'all_attempts_replay_comparison.json'), str(maintenance / 'resolved_requests.json'),
                     str(maintenance / 'process_audit.json'), str(maintenance / 'replay_launch.json')],
        'active_frozen_sources_changed': False, 'other_nodes_launched': False,
        'native_completed': 273, 'queue_entries': len(queue), 'actual_review_tasks': len(cases)})
    register = learn.ROOT / 'docs/research/registers/experiments.csv'
    lines = register.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    header = next(csv.reader([lines[0]]))
    for i, line in enumerate(lines[1:], 1):
        row = next(csv.reader([line]))
        if row[0] != 'CLE-EXP-20261027-Q-05':
            continue
        entry = dict(zip(header, row))
        entry.update(completed_snapshot='1122', status='K3_replayed_analyzed_pending_narrative_delivery',
            as_of=datetime.now(timezone.utc).isoformat(), evidence=str(out / 'summary.json'),
            interpretation='K0-K3学习1122题次完整；K3原生273题动态回放一致，12队列项10题实际审阅；Joint126/273、反馈769/1939，独立Q收益待冻结对照。')
        stream = io.StringIO(newline='')
        csv.writer(stream, lineterminator='\n').writerow([entry[k] for k in header])
        lines[i] = stream.getvalue()
        break
    register.write_text(''.join(lines), encoding='utf-8')
    document = learn.ROOT / 'docs/research/CLE-RUN-20261027-full-requirements-v01.md'
    text = document.read_text(encoding='utf-8')
    marker = '## 2026-10-28 K3冻结、回放与逐题分析'
    if marker not in text:
        first, rest = text.split('\n', 1)
        section = f'''{marker}

K3完整273/273，首次Joint120、末次126，全部可测；原生273题动态验证回放及全部{checked['compared_attempts']}次尝试一致，1939卡Q/visits和正文与原信用重建一致。已实际审阅12队列项、10题。独立离线接线核对{failures}条旧失败均有精确成功后继，保留旧journal/state/source_identity，新增模型/Embedding请求0，未启动其他节点或重启正常FFS。

覆盖702→769卡，355卡本轮获得743次有效反馈。首次—末次救回6、损失0，family置换p={comparison['p_family_swap']}；这是修复描述，Q两主比较及Holm校正仍待冻结对照。1289类型冲突、1298外部字典覆盖及异常契约冲突、1002模板覆盖已区分；110和1019救回分别涉及隐藏文件检查和删除空USERS覆盖。已知18270428 Token、2639 HTTP、83次未知用量保留，保守21998799/40950000 Token，不重置预算。K0历史反馈证书与旧动态差异独立保留。后续1416格回测保留科学范围，但只由工作台按最新探针接力规则另项调度。

证据：`{out.as_posix()}/analysis.md`、`summary.json`、`agent_case_review.json`及`FQ_LEARN/K3/zero_API_replay/replay_result.json`。叙事与对应图交付后再由工作台结单。

'''
        document.write_text(first + '\n\n' + section + rest.lstrip('\n'), encoding='utf-8')
    print(json.dumps({'status': 'native_completed_pending_delivery', 'paired': comparison,
                      'family_intervals': intervals, 'cases': len(cases)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
