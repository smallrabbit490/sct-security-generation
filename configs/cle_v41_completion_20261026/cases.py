"""挑选事后解释案例供当前Codex逐代码复核；不改样本、不生成代码、不自动签署解释。"""
from __future__ import annotations

from pathlib import Path

from .policies import RUN,ROOT,read,rows_for,final
from .report import REPORT,ids,paired
from methods.cle_ablation.runner import plt_contract
from methods.sct_trajectory.context_pipeline import experience_text
from methods.sct_trajectory.replay_journal import write_json


def packet(row):
    attempts=[]
    for a in row.get('attempts',[]):
        g=a.get('generation',{})
        attempts.append({k:a.get(k) for k in ('attempt','code','functional','security','joint','measured','error_type','validation')})
        attempts[-1].update(retrieved_ids=ids(g.get('retrieved_cards',[])),adopted_ids=ids(g.get('cards',[])),
            adopted_memory=experience_text(g.get('cards',[])),adoption=g.get('adoption'),
            experience_analysis=g.get('experience_analysis'),plan=g.get('plan_parsed'),
            retrieval_trace=a.get('retrieval_trace'))
    return {'cell_id':row['cell_id'],'condition':row['condition'],'attempts':attempts,'final':final(row),
            'selected_attempt':row.get('selected_attempt'),'selected_index':row.get('selected_index'),
            'memory':row.get('memory'),'public_requirements':row.get('requirements')}


def prepare():
    path=RUN/'CLOSEOUT/analysis_queue.json'
    if path.exists():return read(path)
    protocol=read(ROOT/'configs/cle_v41_completion_20261026/protocol.json')
    for stage in protocol['stages']:
        if stage['planned_runs'] and len(rows_for(stage['id']))!=stage['planned_runs']:
            raise ValueError('base_grid_incomplete_before_case_selection:'+stage['id'])
    index=read(RUN/'execution_index.json');cases=[]
    comparisons=[('D03b','Q2','Q1',2),('B02','BFS','BM',2),('C02','L4','L2',1),
                 ('D02','PUBLIC','P7',1),('S4','SELECTED','CONTROL',1)]
    for stage,treated,control,limit in comparisons:
        rows=rows_for(stage);groups={arm:{(str(r['task_id']),r['repeat']):r for r in rows if r['condition']==arm} for arm in (treated,control)}
        if not rows or stage not in index:continue
        latest=Path(index[stage][-1]);tasks={str(t['index']):t for t in read(latest/'inputs/tasks.json')}
        categories={'rescue':[],'loss':[],'unchanged':[]}
        for key in sorted(groups[treated].keys()&groups[control].keys()):
            a,b=groups[treated][key],groups[control][key]
            av,bv=bool(final(a).get('joint')),bool(final(b).get('joint'))
            category='rescue' if av and not bv else 'loss' if bv and not av else 'unchanged'
            categories[category].append((key,a,b))
        for category,values in categories.items():
            count=limit if category!='unchanged' else 2 if stage=='D03b' else 0
            chosen=[];seen=set()
            for value in values:
                family=value[1]['family_id']
                if family not in seen:chosen.append(value);seen.add(family)
                if len(chosen)==count:break
            chosen=(chosen+[value for value in values if value not in chosen])[:count] if count else []
            for key,a,b in chosen:
                identifier=f'{stage}_{key[0]}_r{key[1]}_{category}'
                target=RUN/'CLOSEOUT/cases'/(identifier+'.json')
                write_json(target,{'case_id':identifier,'stage':stage,'status':'pending_Codex_code_review',
                    'family_id':a['family_id'],'selection':'posthoc sorted representative prioritizing different families; explanation only, not new evidence or training labels',
                    'public_contract':plt_contract(tasks[key[0]]),'treated':packet(a),'control':packet(b)})
                cases.append({'case_id':identifier,'path':str(target),'status':'pending_Codex_code_review'})
    queue={'cases':cases,'review_output':str(RUN/'CLOSEOUT/agent_case_review.json'),
        'synthesis_output':str(RUN/'CLOSEOUT/agent_synthesis.md'),
        'review_fields':['case_id','reviewer','conclusion','code_evidence','unresolved'],
        'requirements':'Actual Codex reads public contract, cards and code. Distinguish contract/fixture, implementation, Q/selection, output randomness and technical errors; missing evidence stays unresolved. No model/API reruns. Not human retrieval gold.'}
    write_json(path,queue)
    return queue


def finalize():
    queue=prepare();file=RUN/'CLOSEOUT/agent_case_review.json'
    reviews=read(file) if file.exists() else []
    by_id={r['case_id']:r for r in reviews}
    if any(item['case_id'] not in by_id for item in queue['cases']):return False
    for item in queue['cases']:
        r=by_id[item['case_id']]
        if not all(r.get(k) for k in ('reviewer','conclusion','code_evidence')):return False
    synthesis=RUN/'CLOSEOUT/agent_synthesis.md'
    if not synthesis.exists() or not synthesis.read_text(encoding='utf-8-sig').strip():return False
    from .report import report,interpretation
    result=report();lines=['# CLE v4.1迁移基础实验结果与Q探索结论','',
        '## 结论','', '本轮固定基础比较已执行，以下按实际结果陈述；不把提分作为验收条件，也不把未显著解释为普遍无效。','']
    if any(s['completed']!=s['planned'] for s in result['stages'] if s['planned']):return False
    lines.extend([synthesis.read_text(encoding='utf-8-sig'),''])
    for stage in result['stages']:
        if stage['comparisons'] or stage['kind'] in ('classifier','q_selection'):
            lines.append(f"- **{stage['id']}**：{interpretation(stage)}")
    lines+=['','## 执行规格与产物','',
        '完整模型、任务、题族、记忆、反馈边界、协议调整和原始路径见[完整执行记录](CLE_v41迁移基础实验完整执行记录_20261026.md)。M1、P7、公开契约消费者分别报告；本次不更新Q或经验。','',
        '## 真实结果与统计','', '| 包 | 逻辑完成/计划 | 唯一题族 | F/S/Joint |', '|---|---:|---:|---|']
    for stage in result['stages']:
        if not stage['completed']:continue
        rows=rows_for(stage['id'])
        n=len({r['family_id'] for r in rows})
        if stage['kind']=='q_selection':
            values='只选卡，无代码Joint；有效与缺测见D03a_selector_noise.json'
        else:
            values='；'.join(f"{arm}:F{v['functional']}/S{v['security']}/J{v['joint']}/{v['completed']}（可测{v['measured']}），首次J{v['first']['joint']}/可测{v['first']['measured']}，任一候选J{v['any_candidate_upper_bound']['joint']}/完全可测{v['any_candidate_upper_bound']['fully_measured_tasks']}" for arm,v in stage['arms'].items())
        lines.append(f"| {stage['id']} | {stage['completed']}/{stage['planned']} | {n} | {values} |")
    lines+=['','主要配对的救回/损失、按family重采样95%区间、题族区组精确符号置换检验和两项Q比较的Holm校正在精简JSON中。缺测单列；重复及同档精确复用不当独立题族。','',
        '## 逐题机制核对','']
    for item in queue['cases']:
        r=by_id[item['case_id']]
        lines.extend([f"### {item['case_id']}",'',str(r['conclusion']),'',f"代码证据：{r['code_evidence']}",'',f"未区分：{r.get('unresolved') or '本条未补充其他归因'}",''])
    lines+=['## 成本','',f"已报告Token {result['known_reported_tokens']:,}；物理HTTP {result['physical_HTTP']}；已结束但用量未知{result['unknown_usage_HTTP']}。共享和材料按独立操作列账，未知不当免费；人民币实付未获得当前v4.1账单证据。",'',
        '## 限制与收口决定','',
        '小样本、历史题族暴露、模型波动、来源AI分区及1348公开语义歧义均限制结论。人工检索金标准、Notion原始配对和原Base/Plus镜像仍缺；未执行不记失败。完整基础比较到此收口，不自动追加Q学习、全298题Q或其他全量实验。','',
        '## 复现','',
        '各包运行根保留source_bundle、protocol、schedule、共享起点、原始请求/响应、代码、原验证器事件和恢复段；CLOSEOUT保存零API回放、代码足迹、成本与本次实际Codex复核。回放缺响应禁止补发。']
    replay=read(RUN/'CLOSEOUT/state.json')
    lines+=['',f"全部回放一致：{replay.get('all_replays_passed')}。若有差异，原始结果不重写，差异保留在CLOSEOUT/replay_results.json；不将未解决差异宣称为通过。"]
    target=ROOT/'docs/CLE_v41迁移基础实验结果与Q探索结论_20261026.md'
    target.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    state=read(RUN/'CLOSEOUT/state.json');state.update(status='completed',agent_case_analysis_complete=True,final_report=str(target))
    write_json(RUN/'CLOSEOUT/state.json',state)
    return True


if __name__=='__main__':print({'finalized':finalize()})
