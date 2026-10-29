"""从当前原生记录生成迁移进度和配对分析；不请求模型、不补造缺失结果。"""
from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .policies import RUN,ROOT,read,rows_for,final
from methods.sct_trajectory.replay_journal import write_json

REPORT=ROOT/'docs/CLE_v41迁移基础实验完整执行记录_20261026.md'
CURATED=ROOT/'results/curated/cle_v41_completion_20261026'


def ids(cards):
    return [str(c.get('invariant_id') or c.get('id')) if isinstance(c,dict) else str(c) for c in cards or []]


def paired(rows,treated,control):
    from methods.cle_ablation.run_memory_q_equal_k import exact_family_sign_flip,cluster_pair
    arms={arm:{(str(r['task_id']),r['repeat']):r for r in rows if r.get('condition',r.get('relation_arm'))==arm}
          for arm in (treated,control)}
    keys=sorted(arms[treated].keys() & arms[control].keys())
    rescue=loss=0;families=defaultdict(list);unmeasured=0
    for key in keys:
        a,b=arms[treated][key],arms[control][key];x,y=final(a),final(b)
        if not x.get('measured') or not y.get('measured'):unmeasured+=1
        av=bool(x.get('joint'));bv=bool(y.get('joint'))
        rescue+=av and not bv;loss+=bv and not av
        families[a['family_id']].append(int(av)-int(bv))
    means=[sum(v)/len(v) for v in families.values()]
    rng=random.Random(20261026)
    estimates=sorted(sum(rng.choice(means) for _ in means)/len(means) for _ in range(4000)) if len(means)>=2 else []
    p=exact_family_sign_flip(means)
    ci=[estimates[100],estimates[3899]] if estimates else None
    if len(means)>=2 and all(len(values)==2 for values in families.values()):
        native_rows=[{'family_id':arms[a][key]['family_id'],'arm':a,'final':{'joint':bool(final(arms[a][key]).get('joint'))}}
                     for a in (treated,control) for key in keys]
        native=cluster_pair(native_rows,control,treated)
        p=native['p_exact_sign_flip'];ci=native['ci95']
    return {'treated':treated,'control':control,'paired_runs':len(keys),'paired_families':len(means),
        'rescues':rescue,'losses':loss,'net_joint':rescue-loss,'unmeasured_pairs':unmeasured,
        'family_mean_difference':sum(means)/len(means) if means else None,
        'family_bootstrap_95_interval':ci,
        'interval_unavailable_reason':'fewer_than_two_families' if len(means)<2 else None,
        'family_block_permutation_two_sided_p':p,'inference':'native cluster_pair family-block interval and exact sign-flip permutation; two repeats are not independent families'}


def summarize(rows):
    grouped=defaultdict(list)
    for row in rows:grouped[row.get('condition',row.get('relation_arm','unknown'))].append(row)
    result={}
    for arm,items in grouped.items():
        outcomes=[final(r) for r in items];adoptions=[];retrieved=[];firsts=[];upper=[]
        for row in items:
            attempts=row.get('attempts') or [final(row)]
            first=attempts[0]
            if first.get('code')==final(row).get('code') and final(row).get('measured'):first=final(row)
            firsts.append(first)
            scores=[a if a.get('measured') else final(row) if a.get('code')==final(row).get('code') else {} for a in attempts]
            if scores and all(s.get('measured') for s in scores):upper.append(any(s.get('joint') for s in scores))
            adoptions.append(bool(row.get('memory',{}).get('injected_ids')) or any(a.get('generation',{}).get('cards') for a in row.get('attempts',[])))
            if row.get('memory',{}).get('retrieved_id'):retrieved.append(row['memory']['retrieved_id'])
            for attempt in row.get('attempts',[]):
                retrieved.extend(ids(attempt.get('generation',{}).get('retrieved_cards',[])))
        repeats=defaultdict(list)
        for row in items:repeats[row['family_id']].append(final(row).get('joint'))
        result[arm]={'completed':len(items),'measured':sum(bool(x.get('measured')) for x in outcomes),
            **{k:sum(bool(x.get('measured')) and bool(x.get(k)) for x in outcomes) for k in ('functional','security','joint')},
            'adopted_tasks':sum(adoptions),'retrieved_occurrences':len(retrieved),'unique_retrieved_cards':len(set(retrieved)),
            'repeat_discordant_families':sum(len(set(v))>1 for v in repeats.values()),
            'first':{'measured':sum(bool(a.get('measured')) for a in firsts),
                **{k:sum(bool(a.get('measured')) and bool(a.get(k)) for a in firsts) for k in ('functional','security','joint')}},
            'any_candidate_upper_bound':{'fully_measured_tasks':len(upper),'joint':sum(upper),
                'not_delivered_score':True,'unknown_reason':'unscored public-consumer candidates remain unknown; never substituted for delivered score'},
            'implementation_verified':None}
    return result


def stage_pairs(identifier):
    return {'B03R':[('E_rel','E_bind'),('K_rel','K_bind')],
        'B02':[('BF','BM'),('BS','BM'),('BFS','BM'),('BM','B0')],
        'S2_M1':[('protect_m1','protect_none')], 'S2_P13_P22':[('P13','P00'),('P22','P00')],
        'D02':[('PUBLIC','P7')], 'C02':[(l,'L0') for l in ('L1','L2','L3','L4')],
        'C04b':[('classifier','fixed'),('classifier','rule')],
        'D03b':[('Q2','Q0'),('Q2','Q1'),('Q2','Q3')],
        'B05':[('memory_edit','empty_edit')], 'S4':[('SELECTED','CONTROL')]}.get(identifier,[])


def interpretation(stage):
    if stage['completed']<stage['planned']:return '尚未完成原定分母，前缀分数只作进度，不形成最终胜负结论。'
    if stage['id']=='B03R':return '四条件各2/2，单个已知family出现天花板，未观察到可归于关系提醒的净收益；不是总体有效性证据。'
    if stage['kind']=='classifier':
        p=RUN/'C03_C04a/model.json'
        if p.exists():
            model=read(p)
            return f"真实训练标签可用{len(model['fit_families'])}族，策略类型{model['type']}。无稳定成功或无记忆输入的题仍留在端到端分母，不伪造标签。"
        return '模型尚未拟合，不把工程入口当分类器成果。'
    if stage['kind']=='q_selection':return '只测同查询下的排序/成员变化和五重复波动，没有生成代码，因此没有Joint提分结论。'
    if stage['id']=='D03b':
        comparisons=[c for c in stage['comparisons'] if c['control'] in ('Q1','Q3')]
        if len(comparisons)!=2:return '缺主要配对，不判定Q收益。'
        details='；'.join(f"Q2−{c['control']}净{c['net_joint']:+d}，救回{c['rescues']}、损失{c['losses']}，Holm p={c.get('Holm_p',1):.4g}" for c in comparisons)
        if any(c['unmeasured_pairs'] for c in comparisons):claim='存在缺测，不能把全部差额归因于Q。'
        elif all(c['net_joint']>0 and c.get('Holm_p',1)<=.05 for c in comparisons):claim='统计差异为正，仍需核对改选—采用—代码落实的具体救回路径，才能支持Q机制归因。'
        elif all(c['net_joint']>0 for c in comparisons):claim='仅有方向性信号，证据不足；不追加样本追显著。'
        else:claim='本设置未建立Q相对相似度和打乱对照的一致收益，不等于证明Q在所有条件下无效。'
        return details+'。'+claim
    if stage['comparisons']:
        details='；'.join(f"{c['treated']}−{c['control']}净{c['net_joint']:+d}（{c['rescues']}救回/{c['losses']}损失）" for c in stage['comparisons'])
        if stage['id']=='D02':return details+'。反馈来源、公开检查和交付选择共同变化，只能解释为消费者整体包。'
        if stage['id']=='B05':return details+'。共享既有代码的编辑诊断，不是独立新题或新增样本量。'
        if stage['id']=='S4':return details+'。结合题族区间和既往暴露解释，点估计更高不能替代显著性与机制核对。'
        return details+'。结合F/S和重复分歧解释，不把不同包拼成总提升。'
    return '无新的独立代码效果比较。'


def report():
    cfg=read(ROOT/'configs/cle_v41_completion_20261026/protocol.json')
    index=read(RUN/'execution_index.json') if (RUN/'execution_index.json').exists() else {}
    stages=[];known=unknown=inflight=physical=0;model_usage=defaultdict(lambda:{'HTTP':0,'reported_total_tokens':0,'reported_prompt_tokens':0,'reported_completion_tokens':0,'reported_cache_hit_tokens':0,'cache_usage_unknown_HTTP':0})
    for stage in cfg['stages']:
        name=stage['id'];roots=index.get(name,[str(RUN/name)])
        if name=='B03R' and name not in index:roots=[str(p) for p in sorted(RUN.glob('B03R_relation*')) if (p/'protocol.json').exists()]
        root=Path(roots[-1]);state=read(root/'state.json') if (root/'state.json').exists() else {}
        rows=rows_for(name) if name!='B03R' else list({r['cell_id']:r for p in roots for f in (Path(p)/'task_rows').glob('*.json') for r in [read(f)]}.values())
        cost=read(root/'budget.json') if (root/'budget.json').exists() else {}
        entries=cost.get('entries',[]);stage_known=sum(e['usage']['total_tokens'] for e in entries if e.get('usage') and type(e['usage'].get('total_tokens')) is int)
        for entry in entries:
            item=model_usage[entry['model']];item['HTTP']+=1;usage=entry.get('usage') or {}
            for source,target in (('total_tokens','reported_total_tokens'),('prompt_tokens','reported_prompt_tokens'),('completion_tokens','reported_completion_tokens')):
                if type(usage.get(source)) is int:item[target]+=usage[source]
            cached=usage.get('prompt_cache_hit_tokens',(usage.get('prompt_tokens_details') or {}).get('cached_tokens'))
            if type(cached) is int:item['reported_cache_hit_tokens']+=cached
            elif entry['model']!='text-embedding-3-large':item['cache_usage_unknown_HTTP']+=1
        stage_unknown=sum(e['status'] in ('unknown_after_close','failed_unknown','historical_unknown') for e in entries)
        known+=stage_known;unknown+=stage_unknown;inflight+=sum(e['status']=='reserved' for e in entries);physical+=len(entries)
        comparisons=[paired(rows,a,b) for a,b in stage_pairs(name)]
        if name in ('D03b','C04b'):
            q=[c for c in comparisons if c['control'] in ('Q1','Q3')] if name=='D03b' else comparisons
            ordered=sorted(q,key=lambda c:c['family_block_permutation_two_sided_p']);last=0
            for i,c in enumerate(ordered):
                last=max(last,min(1.,c['family_block_permutation_two_sided_p']*(2-i)));c['Holm_p']=last
        stages.append({'id':name,'name':stage['name'],'kind':stage['kind'],'planned':stage['planned_runs'],
            'completed':len(rows),'status':state.get('status','not_started'),'root':str(root),
            'arms':summarize(rows),'comparisons':comparisons,'known_reported_tokens':stage_known,
            'physical_HTTP_including_recovery':len(entries),'unknown_usage_HTTP':stage_unknown,
            'conservative_tokens_including_unknown':cost.get('charged_tokens_including_unknown_and_inflight_bounds'),
            'reason':state.get('reason'),'input_unchanged':state.get('inputs_unchanged')})
    closeout=read(RUN/'CLOSEOUT/state.json') if (RUN/'CLOSEOUT/state.json').exists() else {}
    control_path=RUN/'dispatch_control.json'
    control=read(control_path) if control_path.exists() else {'paid_execution_enabled':True}
    for stage in stages:
        stage['dispatch_status']=('paused_paid_by_user' if not control['paid_execution_enabled'] and stage['planned']>stage['completed'] else stage['status'])
    replay_path=RUN/'B02_zero_API_replay_v1/state.json'
    b02_replay=read(replay_path) if replay_path.exists() else {}
    b02_replay_text=('B02真实120格完整零API回放一致、0新HTTP。' if b02_replay.get('status')=='replay_passed' and b02_replay.get('completed_P7')==120
        else 'B02完整120格零API回放尚待核验；已有部分工程回放不能替代完整回放。')
    result={'updated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'protocol':cfg['protocol'],
        'all_replays_passed':closeout.get('all_replays_passed'),'agent_case_analysis_complete':closeout.get('agent_case_analysis_complete',False),
        'stages':stages,'known_reported_tokens':known,'physical_HTTP':physical,'unknown_usage_HTTP':unknown,
        'reported_usage_by_model':dict(model_usage),
        'inflight_HTTP':inflight,'actual_currency_cost':None,'actual_currency_reason':'no verified v4.1 current invoice/rate; do not reuse v3.2 tariff',
        'new_code_runs_completed':sum(s['completed'] for s in stages if s['kind']!='q_selection'),
        'selector_only_completed':sum(s['completed'] for s in stages if s['kind']=='q_selection'),
        'Q_updates':0,'cards_generated':0,'benefit_gate_controls_dispatch':False,
        'dispatch_control':control,
        'external_remaining':cfg['external_constraints']}
    previous=read(CURATED/'summary.json') if (CURATED/'summary.json').exists() else {}
    changed=[(s['id'],s['completed'],s['status']) for s in result['stages']]!=[(s['id'],s['completed'],s['status']) for s in previous.get('stages',[])]
    CURATED.mkdir(parents=True,exist_ok=True);write_json(CURATED/'summary.json',result)
    write_json(RUN/'progress.json',result)
    lines=['# v4.1 迁移基础实验完整执行记录','',f"更新：{result['updated_at']}。状态由真实逐格文件复算；未完成不会写成通过。",'',
        '## 本轮授权与执行变化','',
        '2026-10-26用户明确授权完成既定基础实验清单，允许必要调整，收益门不再阻断基础比较。旧暂停记录保留为历史。工作日09:00–12:00、14:00–18:00仍不派发新请求，边界自动等待后续跑。',
        '', '复用已完成的新P3 298题、S0、S1 48格及B03 16格，不重新付费。新矩阵最多1376次代码任务与160次仅选卡；固定样本与重复数，不靠补题或追加重复追求提分。',
        '', '## 当前真实进度','', '| 包 | 完成/计划 | 当前状态 | 各臂F/S/Joint（缺测保留在分母） |', '|---|---:|---|---|']
    for s in stages:
        counts='；'.join(f"{a} F{v['functional']}/S{v['security']}/J{v['joint']}，n={v['completed']}（可测{v['measured']}）" for a,v in s['arms'].items()) or '尚无代码成绩'
        if s['kind']=='q_selection':counts='只选卡，不计算代码Joint'
        lines.append(f"| {s['id']} {s['name']} | {s['completed']}/{s['planned']} | {s['dispatch_status']} | {counts} |")
    lines+=['','## 逐包结果解释','']
    for s in stages:
        if s['completed'] or s['status']=='completed':lines.append(f"- **{s['id']}**：{interpretation(s)}")
    lines+=['', '## 分析与结论规则','',
        '经验卡是历史解题建议；冻结指本轮不改卡片或Q。视图是同一来源文字的不同组织。L0为无记忆、L1风险提醒、L2原理与前提、L3目标操作模板、L4完整来源例子。family是题族，不能把两重复当成两个独立题族。','',
        '不同包使用不同消费者、题目分池和反馈边界，不能混成一张总提分表。原P7仍是最多三卡、一次修复、首次Joint通过早停、否则交付末次代码；M1和公开契约消费者按各自原型单独报告。',
        '', '逐包分别报告功能F、安全S、Joint（功能与安全同时通过）、实际采用、两重复分歧、配对救回/损失和按题族的区间。采用只说明模型声明使用了卡，不自动证明代码落实，更不证明Q导致提分。',
        '', '准确率、精确率、召回率和F1是题目—卡片是否直接适用的检索指标，与代码Joint分开。无人类标签时只能报告模型辅助估计；候选池召回不冒充全库召回。重复不同只说明不稳定，不能自动把每次失败都归为模型随机噪声。',
        '', 'Q0是原CLE的向量/词面候选顺序和LLM终选；Q1按相似度呈现，Q2按冻结学习Q与相似度呈现，Q3同CWE打乱(Q,visits)。四者均LLM终选最多三卡，不更新Q。选择波动先由8题五重复测量；24题代码对照仍完整执行，波动门仅影响解释。',
        '', '## 必要调整与结论边界','',
        '- 本地选择器180000字符上限拒绝了190305字符的完整原提示，未发送选择器HTTP；本轮上限改为420000，原24+8候选、正文、三卡与256输出预算均保留。旧故障和已完成响应保留，续段复用不重复付费。',
        '- 功能/安全分区使用仅来源文本的AI标注，逐字符覆盖；两次格式失败后按预先固定字段规则分区并标记语义不确定性。此材料不是人类检索金标准。',
        '- 粒度五档共同排除15张无来源代码卡，并逐题共同排除同family来源，保留原1939卡文件；有效候选数逐题记载。L4不以目标答案补造来源。',
        '- 1348的公开资源政策歧义单列有效性分析，不换题、不向模型填入隐藏阈值。',
        '- 分类器仅用36个训练family真实的五档两重复结果，两次均通过才有稳定成功标签；无成功不是L0正确标签。无多类标签时明确使用常数策略。12个开发family只做一次评估。',
        '- S4方案只由训练/开发记录锁定；D02固定48题已包含其中部分family，完整披露先前暴露，因此不称为完全未经接触的最终测试。Q确认集成绩不参与S4挑方案。',
        '- 原始Notion配对、914对真实人工标签和Base/Plus原镜像仍是外部缺项；不代签、不替换验证器，不把未运行写0分。其他实验持续执行。',
        '', '## 成本与回放','',
        f"本轮新增已报告Token：{known:,}；物理HTTP：{physical}；已结束但用量未知：{unknown}；当前在途：{inflight}。包含本轮各包恢复段，不能再次相加历史段summary；不含复用P3/S1/B03的既往费用。实际人民币费用待v4.1账单/单价，未套用v3.2价格。",'',
        '每包保留source_bundle、无密钥protocol、固定schedule、逐请求journal、物理wire、共享初析/选卡、task_rows、完整代码及原验证产物。新段只重试未完成操作，已返回响应精确复用；未知用量继续占预算。已完成格不因低成绩重跑。',
        '', '## 接线与回放验证','',
        '新增迁移矩阵/公共特征/同档复用/共享前缀/精确置换与交付选择等检查通过；原执行控制19项检查通过。B03R真实8格零API回放一致、0新HTTP。'+b02_replay_text, '',
        '历史A7测试16/17通过；剩余一项调用旧抽样器，依赖D盘不存在的20261009/memory_architecture_screening/manifest.json。本轮使用已锁定且单独核对的12题，不调用该旧抽样器，因此记录这项历史材料缺失并继续当前实验，没有修改旧测试来制造全绿。',
        '', '## 下一步计划','',
        '按清单自动推进关系提醒、五臂分区、M1、提示模板、契约消费者、五档粒度、真实标签分类器、两组保留确认及反事实编辑，完成后做零API回放和逐包报告。收益为负也完成原定比较；不自动增加Q学习、全298题Q、完整CLE训练、Base/Plus、新版CLE或MASE。',
        '', '完整机器结果：`results/curated/cle_v41_completion_20261026/summary.json`。执行入口和阶段预算：`configs/cle_v41_completion_20261026/`。']
    if not control['paid_execution_enabled']:
        lines[4:4]=['**最新执行范围：用户要求下一步仅执行零API任务。所有付费生成暂停，原完整清单保留待授权；不再于18:00自动恢复。**','']
        lines=[('只执行已有输入的零API回放、统计、代码分析和清单更新；见[CLE零API复盘](CLE_v41迁移零API复盘与待执行清单_20261026.md)。缺少完整生成结果的分类器和其他付费实验保留待后续指令，不自动续跑。'
            if line.startswith('按清单自动推进关系提醒') else line) for line in lines]
    REPORT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if changed:
        from .update_tasks import main as update_tasks
        update_tasks(quiet=True)
    return result


if __name__=='__main__':
    r=report();print(json.dumps({k:r[k] for k in ('updated_at','new_code_runs_completed','selector_only_completed','known_reported_tokens')},ensure_ascii=False))
