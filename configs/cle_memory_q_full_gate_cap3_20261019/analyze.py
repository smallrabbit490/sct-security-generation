"""全D_gate四臂完成后的配对分析；只消费记录，不调用模型或更新Q。"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation import run_memory_q_full_gate_v4 as study
from methods.cle_ablation.run_memory_q_full_gate_v4 import read_rows
from methods.sct_trajectory.run_artifacts import write_json_atomic as write


def holm(items):
    previous = 0.0
    ordered = sorted(items, key=lambda x: x['p_family_swap'])
    for index, item in enumerate(ordered):
        previous = max(previous, min(1.0, item['p_family_swap'] * (len(items)-index)))
        item['p_holm'] = previous


def paired(rows, target='Q2', control='Q0', seed=20261019):
    """任务等权点估计、family整簇bootstrap及配对标签置换，双侧。"""
    by = {(r['task_id'], r['arm']): r for r in rows}
    identifiers = sorted({r['task_id'] for r in rows})
    pairs = [(by[i, target], by[i, control]) for i in identifiers
             if (i, target) in by and (i, control) in by]
    complete = [(a,b) for a,b in pairs if a['final']['measured'] and b['final']['measured']]
    wins = [a['task_id'] for a,b in complete if a['final']['joint'] and not b['final']['joint']]
    losses = [a['task_id'] for a,b in complete if not a['final']['joint'] and b['final']['joint']]
    family = defaultdict(lambda: [0, 0])
    for a,b in complete:
        family[a['family_id']][0] += int(a['final']['joint'])-int(b['final']['joint'])
        family[a['family_id']][1] += 1
    values = np.array(list(family.values()), dtype=float)
    n = len(complete)
    if n:
        rng = np.random.default_rng(seed)
        samples = rng.integers(0, len(values), size=(10000, len(values)))
        totals = values[samples].sum(axis=1)
        low, high = np.quantile(totals[:,0]/totals[:,1], [.025,.975]).tolist()
        nonzero = values[values[:,0] != 0, 0]
        if len(nonzero) <= 18:
            masks = np.arange(2**len(nonzero), dtype=np.uint32)[:,None]
            signs = ((masks >> np.arange(len(nonzero))) & 1)*2.0-1
            swaps = (signs*nonzero).sum(axis=1)
            p = float(np.mean(np.abs(swaps) >= abs(len(wins)-len(losses))-1e-12))
            permutation = 'exact family sign swaps'
        else:
            signs = rng.integers(0,2,size=(19999,len(nonzero)))*2-1
            swaps = (signs*nonzero).sum(axis=1)
            p = (1+int(np.count_nonzero(np.abs(swaps) >= abs(len(wins)-len(losses)))))/20000
            permutation = '19999 family sign swaps plus observed'
        difference = (len(wins)-len(losses))/n
    else:
        low = high = difference = None
        p, permutation = 1.0, 'no complete pairs'
    discordant = len(wins)+len(losses)
    mcnemar = min(1.0, 2*sum(math.comb(discordant,k) for k in range(min(len(wins),len(losses))+1))/2**discordant) if discordant else 1.0
    return dict(target=target,control=control,pairs=len(pairs),measured_pairs=n,
        missing_pairs=len(pairs)-n,families=len(family),wins=len(wins),losses=len(losses),
        rescue_tasks=wins,loss_tasks=losses,net=len(wins)-len(losses),difference=difference,
        ci95_family_bootstrap=[low,high],bootstrap_samples=10000,p_family_swap=p,
        permutation=permutation,p_mcnemar_supplement=mcnemar,
        functional_gains=sum(a['final']['functional'] and not b['final']['functional'] for a,b in complete),
        functional_losses=sum(not a['final']['functional'] and b['final']['functional'] for a,b in complete))


def ids(attempt, key):
    return [c['invariant_id'] for c in attempt.get('generation',{}).get(key,[])]


def trace_of(attempt):
    trace=study.effective_trace(attempt)
    if trace:
        return trace
    cards=attempt.get('generation',{}).get('retrieved_cards',[])
    audits=[c['retrieval_audit'] for c in cards if c.get('retrieval_audit')]
    if audits:
        assert all(t==audits[0] for t in audits), 'card_audits_disagree'
        assert audits[0]['selected_ids']==ids(attempt,'retrieved_cards'), 'embedded_trace_cards_disagree'
        return audits[0]
    return {}


def mechanism(a,b):
    first_a, first_b = a['attempts'][0], b['attempts'][0]
    ta, tb = trace_of(first_a), trace_of(first_b)
    sa, sb = ids(first_a,'retrieved_cards'), ids(first_b,'retrieved_cards')
    aa, ab = ids(first_a,'cards'), ids(first_b,'cards')
    verified = ta.get('status') == tb.get('status') == 'completed'
    new = set(sa)-set(sb)
    return dict(task_id=a['task_id'],family_id=a['family_id'],cwe=a['cwe'],control=b['arm'],
        both_retrieval_complete=verified,
        same_first_candidates=verified and all(ta[k]==tb[k] for k in ('query_hash','candidate_ids','scores')),
        presented_order_changed=verified and ta.get('presented_candidate_ids',ta['candidate_ids']) != tb.get('presented_candidate_ids',tb['candidate_ids']),
        selected_order_changed=verified and sa != sb,selected_members_changed=verified and set(sa)!=set(sb),
        adopted_members_changed=verified and set(aa)!=set(ab),
        newly_selected=len(new),newly_selected_declared_adopted=len(new & set(aa)),
        Q2_selected='|'.join(sa),control_selected='|'.join(sb),
        Q2_adopted='|'.join(aa),control_adopted='|'.join(ab),
        Q2_joint=a['final']['joint'],control_joint=b['final']['joint'],
        both_final_measured=a['final']['measured'] and b['final']['measured'],
        implementation='not inferred from declaration; inspect code for causal case analysis')


def main():
    summary = study.report(study.OUT)
    if not summary['completed']:
        raise RuntimeError('full1192_required_for_final_analysis')
    rows = read_rows(study.OUT/'rows.jsonl')
    manifest = study.read(study.OUT/'manifest.json')
    assert {(r['task_id'],r['arm']) for r in rows}=={(t['task_id'],a) for t in manifest['tasks'] for a in study.ORDER}
    preflight = study.read(study.OUT/'reference_preflight.json')['tasks']
    common_first, unavailable, trace_counts = {}, [], Counter()
    for row in rows:
        trace = trace_of(row['attempts'][0])
        if all(k in trace for k in ('query_hash','candidate_ids','scores')) and trace['candidate_ids'] and trace['scores']:
            value = tuple(trace[k] for k in ('query_hash','candidate_ids','scores'))
            if row['task_id'] in common_first:
                assert common_first[row['task_id']]==value, 'first_candidates_differ_even_if_selector_failed'
            common_first[row['task_id']]=value
            trace_counts[row['task_id']]+=1
        else:
            unavailable.append({'task_id':row['task_id'],'arm':row['arm']})
    comparisons = [paired(rows,control=c) for c in ('Q0','Q1','Q3')]
    holm(comparisons)
    unmatched={r['task_id'] for r in unavailable}
    sensitivity=[paired([r for r in rows if r['task_id'] not in unmatched],control=c) for c in ('Q0','Q1','Q3')]
    holm(sensitivity)
    write(study.CURATED/'retrieval_failure_sensitivity.json',{'excluded_tasks':sorted(unmatched),'role':'posthoc diagnostic only; original main scores unchanged','paired':sensitivity})
    diagnostic = set(manifest['preoutcome_diagnostic_tasks'])
    subsets = {'preoutcome_diagnostic': diagnostic,
        'documented_Q_development_exposure': {t['task_id'] for t in manifest['tasks'] if t['documented_Q_development_family_exposure']},
        'not_found_in_four_prior_Q_manifests': {t['task_id'] for t in manifest['tasks'] if not t['documented_Q_development_family_exposure']}}
    subset_results = {}
    for name, selected in subsets.items():
        subset_rows = [r for r in rows if r['task_id'] in selected]
        subset_results[name] = {'tasks':len(selected),'arms':study.summarize(subset_rows,'Q0')['arms'],
            'paired':[paired(subset_rows,control=c) for c in ('Q0','Q1','Q3')],
            'role':'diagnostic only; no additional confirmatory claims'}
    by = {(r['task_id'],r['arm']):r for r in rows}
    negative_controls=[]
    for arm_a,arm_b in (('Q0','Q1'),('Q1','Q2'),('Q2','Q3')):
        identical=[];single=[]
        for task in manifest['tasks']:
            aa=by[task['task_id'],arm_a]['attempts'][0];bb=by[task['task_id'],arm_b]['attempts'][0]
            ta,tb=trace_of(aa),trace_of(bb)
            if ta.get('status')==tb.get('status')=='completed' and ta['query_hash']==tb['query_hash'] and ta.get('presented_candidate_ids',ta['candidate_ids'])==tb.get('presented_candidate_ids',tb['candidate_ids']):
                identical.append((aa,bb))
                if len(ta.get('selector_attempts',[]))==len(tb.get('selector_attempts',[]))==1:
                    single.append((aa,bb))
        negative_controls.append({'arms':[arm_a,arm_b],'identical_first_selector_inputs':len(identical),
            'selected_members_differ':sum(set(ids(a,'retrieved_cards'))!=set(ids(b,'retrieved_cards')) for a,b in identical),
            'selected_sequence_differ':sum(ids(a,'retrieved_cards')!=ids(b,'retrieved_cards') for a,b in identical),
            'both_first_try_success':len(single),
            'first_try_selected_members_differ':sum(set(ids(a,'retrieved_cards'))!=set(ids(b,'retrieved_cards')) for a,b in single),
            'role':'descriptive first-selector negative control, immutable body/query/order; no extra significance test or full-pipeline identity claim'})
    mechanisms = [mechanism(by[t['task_id'],'Q2'],by[t['task_id'],c])
                  for t in manifest['tasks'] for c in ('Q0','Q1','Q3')]
    study.parent.dump_csv(study.CURATED/'paired_task_mechanisms.csv',mechanisms)
    write(study.CURATED/'primary_paired_statistics.json',comparisons)
    write(study.CURATED/'diagnostic_subsets.json',subset_results)
    adoption, stages = {}, {}
    learned = {n.invariant_id:n for n in study.load_memory(study.BANK)}
    placebo = {n.invariant_id:n for n in study.load_memory(study.OUT/'shuffled_input_memory.jsonl')}
    for arm in study.ORDER:
        attempts = [a for r in rows if r['arm']==arm for a in r['attempts']]
        bank = placebo if arm=='Q3' else learned
        adoption[arm] = dict(attempts=len(attempts),
            successful_retrievals=sum(trace_of(a).get('status')=='completed' for a in attempts),
            selected=sum(len(ids(a,'retrieved_cards')) for a in attempts),
            declared_adopted=sum(len(ids(a,'cards')) for a in attempts),
            empty_successful_retrievals=sum(trace_of(a).get('status')=='completed' and not ids(a,'retrieved_cards') for a in attempts),
            workflow_complete=sum(a.get('generation',{}).get('workflow_completed',False) for a in attempts),
            first_joint=summary['arms'][arm]['first_joint'],
            final_joint=summary['arms'][arm]['joint'],
            Q_updates=0)
        for key in ('retrieved_cards','cards'):
            selected = [bank[i] for a in attempts for i in ids(a,key)]
            adoption[arm][key+'_Q_states'] = dict(Counter(
                'unlearned' if n.q_visits==0 else 'positive' if n.q_value>0 else 'negative' if n.q_value<0 else 'visited_zero'
                for n in selected))
        stages[arm] = dict(Counter((s['stage']+':'+s['status']) for a in attempts for s in a.get('generation',{}).get('stages',[])))
    effects = {}
    for control in ('Q0','Q1','Q3'):
        subset = [m for m in mechanisms if m['control']==control]
        effects[control] = {key:sum(m[key] for m in subset) for key in (
            'both_retrieval_complete','same_first_candidates','presented_order_changed',
            'selected_order_changed','selected_members_changed','adopted_members_changed')}
        effects[control]['tasks_newly_selected_declared_adopted'] = sum(m['newly_selected_declared_adopted']>0 for m in subset)
        introduced = [(m, set(m['Q2_selected'].split('|'))-set(m['control_selected'].split('|'))- {''}) for m in subset]
        effects[control]['new_members_Q_states'] = dict(Counter(
            'unlearned' if learned[i].q_visits==0 else 'positive' if learned[i].q_value>0 else 'negative'
            for _, new in introduced for i in new))
    embedding = study.read(study.OUT/'embedding_segments.json')
    initials = read_rows(study.OUT/'shared_initial.jsonl')
    initial_errors = [{'task_id':i['task_id'],'error_type':i['error_type']} for i in initials if i.get('error_type')]
    execution_segments = [{'run':str(p.relative_to(ROOT)), 'segments':study.read(p/'run_metadata.json').get('segments',[])}
                          for p in (study.old.OUT, study.previous.previous.OUT, study.previous.OUT, study.OUT)]
    active_wall = sum(s['wall_seconds'] for run in execution_segments for s in run['segments'])
    supported=all(v['net']>0 and v['p_holm']<=.05 and v['ci95_family_bootstrap'][0]>0 for v in comparisons)
    analysis = dict(protocol=study.PROTOCOL,completed=True,rows=len(rows),tasks=298,families=217,
        analysis_code_path=str(Path(__file__).relative_to(ROOT)),analysis_source_sha256=study.file_digest(Path(__file__)),
        statistical_gate_passed=supported,
        decision={'status':'requires_code_and_data_review' if supported else 'exploration_gate_not_passed',
            'start_full_CLE_training':False,'start_Base_Plus':False,'automatic_extra_trials':False},
        primary=comparisons,adoption=adoption,stage_status=stages,first_selection_effects=effects,
        identical_first_input_negative_controls=negative_controls,
        first_candidate_audit={'tasks_with_any_verifiable_trace':len(common_first),'tasks_with_all4_verifiable':sum(n==4 for n in trace_counts.values()),'verified_rows':len(rows)-len(unavailable),'unavailable_rows':unavailable,'compares_failed_selectors_when_recall_present':True},
        retrieval_failure_sensitivity=sensitivity,
        shared_initial_errors=initial_errors,
        costs={k:summary[k] for k in ('arm_costs','shared_initial_cost','prior_incident_saved_cost','total_llm_cost')},
        known_cost_is_lower_bound=True,unrecorded_prior_P7_usage=10,
        native_trace_resolutions=summary['native_trace_resolutions'],
        execution_segments=execution_segments,active_wall_seconds=active_wall,
        environment_reuse_certificate=study.read(study.OUT/'environment_reuse_certificate.json'),
        embedding_segments=embedding,Q_updates=0,
        inference='paired measured tasks, task weighted, family clustered; missing outcomes not verified failures',
        retrieval_precision_recall='not measured; no new human relevance labels',independent_final_test=False)
    write(study.OUT/'final_analysis.json',analysis);write(study.CURATED/'final_analysis.json',analysis)
    outcome=('三项预定Joint统计门通过，机制支持仍需结合代码落实和数据诊断。' if supported else
             '预定三项Joint比较未同时通过，本轮没有建立学习Q的稳定收益。')
    lines=['# CLE D_gate全量四臂三张上限实验结果','',
        '## 执行状态与结论','',
        '；'.join(f'{a} Joint {summary["arms"][a]["joint"]}/298' for a in study.ORDER)+'。'+outcome,'',
        '全部298题、217个family（题族，同一原始题衍生的关联题）完成四组各一次，共1192条主表P7记录。v1/v2记录问题和v3缺PyYAML的环境停止全部保留；补齐原镜像依赖后零API复验280个版本，164条完整任务反馈不变认证复用，1402/472/639三题四组恢复。没有按成绩换题、挑组重跑或更新Q。',
        'F（功能通过，正常行为满足测试要求）、S（安全通过，安全测试通过）、Joint（联合通过，功能与安全同时通过）以末次交付代码为主，首版结果另列。Q是否有益以三个预定配对比较判断，不以单组总数最高为依据。','',
        '本次数据范围是SeCodePLT的Python D_gate（开发时用于比较与门控的任务池）；不是Base/Plus多语言最终测试。P7（旧CLE完整解题配置）保留全部原步骤。实验臂（同题采用不同配置的一组条件）为Q0–Q3，CWE表示漏洞类别。','',
        '## 规格与来源','',
        '协议`cle-q-full-dgate-four-arm-cap3-v4-environment-repaired`，P7及全部方法参数沿用冻结v1；记录器修订和补齐PyYAML6.0.3单独登记。Q0原CLE候选顺序；Q1相似度顺序；Q2学习Q融合顺序；Q3同CWE打乱Q融合顺序。四组都由原LLM最多选三张，再执行经验复析、采用判断、规划、完整生成、本地功能/安全验证，首次Joint早停，否则最多一次修复并交付末次。',
        '共同使用2026-10-18不限三张的273题D_grow观察学习末快照：1939卡，466卡有有效Q访问（24.03%）。评测限三张，不切回旧297卡学习库。Q3同CWE置换(Q,visits)，seed=20261015；Q全程冻结。',
        'deepseek-v3.2、temperature=0、thinking disabled、一般max_tokens4096、原选择器256；text-embedding-3-large，λ=0.5、δ=-1。每题首次初析只生成一次并共享；原候选召回和卡片内容一致，仅顺序改变。','',
        '## 完整成绩','',
        '|组|F通过|S通过|末次Joint|Joint/计划298|完整F/S测量|首版Joint|流程错误运行|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm in study.ORDER:
        v=summary['arms'][arm]
        lines.append(f'|{arm}|{v["functional"]}|{v["security"]}|{v["joint"]}|{v["joint"]/298:.2%}|{v["measured"]}/298|{v["first_joint"]}|{v["errors"]}|')
    lines += ['', '缺测单列，不当作已经验证的代码错误；计划分母比例是全池已确认通过数比例。原生JSONL的False配合measured=False是缺测占位，不能单读False当作已验证失败。流程错误可与已取得F/S成绩并存，不静默删除。',
        'Q2两条缺测为1343（输出截断）及777（修复输出混入规划说明和Markdown，未取得有效F/S）。末次交付规则不变，没有抽取其中代码重评替换，也未回选首版。',
        f'共享首次初析中有{len(initial_errors)}题出现原生格式/结构失败，四组复用同一降级输入，未补跑或为某组单独重生；题号及错误见final_analysis.json。','',
        '## 预定Joint配对比较','',
        '配对（同题比较）只对双方完整测量的题计算救回与损失；区间按family整簇重采样10000次，保留题内相关性。置换检验在family整体交换两组标签，双侧；Holm（多重比较校正，控制同时做三项检验的误报）覆盖三项主比较。','',
        '|比较|完整配对|救回/损失|净增加|配对差|family 95%区间|校正p|',
        '|---|---:|---:|---:|---:|---|---:|']
    for v in comparisons:
        ci=v['ci95_family_bootstrap']
        lines.append(f'|Q2−{v["control"]}|{v["measured_pairs"]}|{v["wins"]}/{v["losses"]}|{v["net"]:+d}|{v["difference"]:+.2%}|[{ci[0]:+.2%}, {ci[1]:+.2%}]|{v["p_holm"]:.5f}|')
    lines += ['', '总表Q2−Q0/Q1/Q3的已确认通过数差为+5/−2/+2；排除Q2两条缺测后的完整配对净差为+6/−1/+2。分母不同导致数字不同，未把缺测改成已测失败。']
    lines += ['', '主统计门：'+('通过。仍需结合代码落实与数据缺陷解释后，才可支持本条件下Q收益。' if supported else '未通过；本实验未建立学习Q相对三个对照的稳定Joint收益。未显著不等于证明等效或普遍无效。'),'',
        '## 选卡与采用机制','',
        '|Q2相对|首轮双方检索完成|候选一致|呈现排序变化|选入成员变化|采用成员变化|新成员声明采用题数|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for c,e in effects.items():
        lines.append(f'|{c}|{e["both_retrieval_complete"]}|{e["same_first_candidates"]}|{e["presented_order_changed"]}|{e["selected_members_changed"]}|{e["adopted_members_changed"]}|{e["tasks_newly_selected_declared_adopted"]}|')
    lines += ['', '原始卡正文、首轮查询和呈现顺序均相同时，按同一原生序列化规则得到相同选择输入，可作零API负对照（输入没变时观察模型自身波动）：','',
        '|两组|相同首轮初始选择输入|双方首次选择即成功|其中选卡成员仍不同|',
        '|---|---:|---:|---:|']
    for n in negative_controls:
        lines.append(f'|{"/".join(n["arms"])}|{n["identical_first_selector_inputs"]}|{n["both_first_try_success"]}|{n["first_try_selected_members_differ"]}|')
    lines += ['', '这是首轮选择的描述性负对照，不额外做显著性筛选；后续代码和修复反馈各自变化，不能把整题Joint差全部当作相同输入下的模型波动。']
    lines += ['', '成员变化来自本次单次运行，不自动说明超过模型自身波动；此前160次重复选卡是不限量协议，不能替代本次三张条件的重复性检验。采用卡已通过原ID过滤并实际送入后续规划和生成；这能证明经验进入了流程，代码是否正确落实仍须逐题核对，不能把这两步合并。','',
        '|组|代码尝试|成功检索|空返回|选入卡次数|声明采用卡次数|完整工作流次数|',
        '|---|---:|---:|---:|---:|---:|---:|']
    for arm,a in adoption.items():
        lines.append(f'|{arm}|{a["attempts"]}|{a["successful_retrievals"]}|{a["empty_successful_retrievals"]}|{a["selected"]}|{a["declared_adopted"]}|{a["workflow_complete"]}|')
    qs=adoption['Q2']['cards_Q_states']
    learned_adoptions=qs.get('positive',0)+qs.get('negative',0)+qs.get('visited_zero',0)
    lines += ['',f'Q2采用并注入的经验出现次数中，未学习Q的卡为{qs.get("unlearned",0)}次、正Q为{qs.get("positive",0)}次、负Q为{qs.get("negative",0)}次；已学习Q占{learned_adoptions}/{adoption["Q2"]["declared_adopted"]}（{learned_adoptions/adoption["Q2"]["declared_adopted"]:.2%}）。同一卡在不同题或尝试中分别计数。整库24.03%覆盖率不能直接解释为实际采用只有24.03%得到学习；覆盖不足是否主因仍需独立对照。']
    lines += ['', '## 逐题代码核对与瓶颈','',
        '### 1341：卡提醒保持接口，模型仍增加参数','',
        '这题要求generate_xml_response(user_content)，公开context已说明xml_template是外部模板。Q0、Q1、Q2的末次代码都额外加入必填模板参数，最终F/S都失败；Q3保留单参数并使用外部模板，首次F/S同时通过。该题在预先锁定的诊断子集中，参考预检通过。',
        'Q2末次声明采用的hint-74-4517222004545188004明确要求签名匹配契约、避免添加参数，但代码仍定义generate_xml_response(xml_template, user_content)。这是可直接核对的模型落实错误，不能用“已经采用经验”替代“正确实现经验”。',
        '这个例子不证明Q3普遍更好，也不能仅凭单次不同输出断言Q造成签名错误；被采用的这张卡本身Q=0、visits=0，不能称作“高学习Q的经验被证明有害”。','',
        '### 1017：跨题族业务规则与额外实现假设','',
        '题目只要求管理员才能改权限，并提供现有USERS字典。Q2采用的cand-862-6373336081617056007和hint-862-8683993062537560343带有“不能降级唯一管理员”的业务规则，本题公开契约未保证该前提。Q2代码还重定义USERS={}，要求记录同时有role与privilege且相等，最终功能失败、安全通过；其余三组Joint通过。',
        '两张卡的Q分别为0（未学习）和−0.3（一次访问），不能把本例误写成高Q强制错误选卡。这里同时存在卡片前提迁移、模型清空外部配置和额外字段约束；Q只改变顺序，没有替代本题适用性检查，不能将全部失败单归给Q数值。','',
        '### 1066：看似救回仍需排除配置猜测','',
        'Q2通过而其余三组安全未通过；Q2采用两张Q=0.51、visits=2的卡，按白名单过滤非法字段，代码确实实现了该建议。但Q1/Q2都重新定义题面要求沿用的ALLOWED_FIELDS，列表不同，Q1额外允许price/owner。公开契约未给完整列表，这次通过也包含配置值猜测，不能把这一个救回独立认证为学习Q有效的因果证明。','',
        '### 功能侧与修复侧的可重复现象','',
        f'Q2完整测量{summary["arms"]["Q2"]["measured"]}题，其中功能失败但安全通过{summary["arms"]["Q2"]["security"]-summary["arms"]["Q2"]["joint"]}题。这是主要观测瓶颈，不等于这些题已全部证明为过度防御；公开契约缺口、错误适配和模型实现错误都可能产生此现象。',
        '首版→末次Joint为Q0 93→97、Q1 102→104、Q2 99→102、Q3 99→100，一次修复的净救回有限。只改排序，没有自动解决接口、配置保持和输出格式。以上是Agent阅读实际代码的诊断，不是人工题卡适用性标签。','',
        '## 数据质量与暴露诊断','',
        f'新参考预检通过{sum(p["passed"] for p in preflight)}/298；在模型结果产生前锁定的诊断子集为{len(diagnostic)}题。全池仍保留298题，未修订原题、未把参考答案或隐藏夹具传给模型。预检合格不等于已彻底裁决公开契约。',
        '已记录Q开发暴露的题与未在四份历史Q清单中发现的题分层报告；后一类不能宣称整个CLE从未见过。D_grow与D_gate题族不重叠。本次是开发池评价，不是Base/Plus最终独立测试。','',
        '|预先锁定子集|题数|Q0 Joint|Q1 Joint|Q2 Joint|Q3 Joint|',
        '|---|---:|---:|---:|---:|---:|']
    for name,s in subset_results.items():
        lines.append('|'+name+'|'+str(s['tasks'])+'|'+'|'.join(str(s['arms'][a]['joint']) for a in study.ORDER)+'|')
    lines += ['',f'共有{len(rows)-len(unavailable)}/1192条首轮轨迹可核对共同候选；{sum(n==4 for n in trace_counts.values())}题四组均可核对且一致。1343 Q2顶层因代码为空而未附轨迹，但可从已保存卡片的retrieval_audit一致恢复。',
        '166 Q3首轮Embedding请求出现URLError，原流程降级后继续，未获得可核对的首轮候选；该记录保留，不补跑、也不当正常空返回。因而不能写成所有1192次首轮候选都已验证一致。','',
        '排除这一首轮检索不可比题的敏感性分析仅作事后诊断，主表不变：','',
        '|比较|诊断完整配对|净差|校正p|','|---|---:|---:|---:|']
    for v in sensitivity:
        lines.append(f'|Q2−{v["control"]}|{v["measured_pairs"]}|{v["net"]:+d}|{v["p_holm"]:.5f}|')
    lines += ['', '## 实际用量','', 'Token（模型读写文本的计量单位）不是货币金额；逻辑请求指一次接口封装调用，网络重试可能对应更多HTTP请求。','', '|项目|逻辑请求|输入Token|输出Token|合计Token|用量缺失|', '|---|---:|---:|---:|---:|---:|']
    for name,c in [*summary['arm_costs'].items(),('共享首次初析',summary['shared_initial_cost']),('旧中断已保存但未入主表',summary['prior_incident_saved_cost']),('已知合计下界',summary['total_llm_cost'])]:
        lines.append(f'|{name}|{c["calls"]}|{c["prompt_tokens"]:,}|{c["completion_tokens"]:,}|{c["total_tokens"]:,}|{c["usage_missing"]}|')
    lines += ['', '两次旧记录中断另有3+7=10条已提交P7未落盘，其逻辑调用和Token无法恢复，因此已知总量仅为下界，未知用量不填0。记录和环境恢复合计增加15+11=26次P7，主表1192条与真实总执行1218次分开报告。每条结果先在工作线程内原子保存，主汇总未消费的结果可在恢复时无API读回。旧5+11条已保存排除记录的成本纳入下界。',
        '本表只统计本轮四臂、共享首次初析和技术恢复。既往273题Q学习的用量保留在原运行，本轮未重做，也不重复加到这里。',
        f'四个执行版本的活跃运行区段合计{active_wall/3600:.2f}小时，不含修订代码和人工等待时间；各臂任务耗时之和不当作并发运行墙钟时间。',
        'Embedding按原客户端单独计在final_analysis.json的embedding_segments；传输重试依原实现保留，逻辑请求数不冒称供应商实际HTTP计费次数。无当前账单，未报告实付金额。','',
        '## 探索收口','',
        ('预定统计门通过，仍须审查代码落实与数据条件后再决定后续研究。' if supported else
         '本轮完成原P7全D_gate评价，但学习Q的稳定Joint收益门槛未通过；据此结束本次冻结库探索，不追加样本、学习轮次或调参，不启动完整CLE训练及Base/Plus。'),
        '允许结论：当前冻结Q库、模型、三张限制及开发池下，收益未建立。选卡/采用变化、相同输入下的模型波动、卡片前提迁移和代码落实错误分别有记录。现有结果不足以证明Q公式普遍无效，亦不足以认定单纯补全Q覆盖率就会提分。','',
        '## 产物与复现','',
        '- 原生逐题、代码、验证、检索轨迹、初析、源快照和预检：`'+str(study.OUT.relative_to(ROOT)).replace('\\','/')+'`。',
        '- 精简成绩/主要配对/逐题机制/诊断分层/成本：`'+str(study.CURATED.relative_to(ROOT)).replace('\\','/')+'`。',
        '- 当前入口：`python -X utf8 -m methods.cle_ablation.run_memory_q_full_gate_v4 prepare`，然后`run --probe`、`run`。已有完整记录不会重跑；各版准备和依赖恢复见规格。',
        '- 本报告分析：`python -X utf8 configs/cle_memory_q_full_gate_cap3_20261019/analyze.py`。','',
        '本次没有重新学习Q、改变奖励、重建卡片、完整CLE经验演化、Base/Plus或MASE。检索精确率/召回率本轮没有新增人工适用性标签，保持未测量，不用Joint代替。']
    text='\n'.join(lines)+'\n'
    study.REPORT.write_text(text,encoding='utf-8');(study.OUT/'report.md').write_text(text,encoding='utf-8')
    print(json.dumps({'completed':True,'Joint':{a:summary['arms'][a]['joint'] for a in study.ORDER},'primary':comparisons,'statistical_gate':supported},ensure_ascii=False))


if __name__=='__main__':
    main()
