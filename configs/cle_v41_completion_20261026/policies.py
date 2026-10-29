"""固定的来源示例、粒度路由和迁移验证策略；仅训练侧真实结果可用于拟合。"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

import numpy as np

from methods.sct_trajectory.memory_granularity import public_task
from methods.sct_trajectory.replay_journal import write_json

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'translation_work/diagnostics/20261026/cle_v41_completion'
RAW=ROOT/'translation_work/diagnostics/20261023/cle_memory_mechanisms_v1'
ARCHIVE=Path('E:/ResearchArchives/sct-security-generation_20261016/原始项目/translation_work/diagnostics/20261009/a7_exploration/source_bank.json')
LEVELS=('L0','L1','L2','L3','L4')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows_for(stage):
    roots=[RUN/stage]
    index=RUN/'execution_index.json'
    if index.exists():roots=[Path(p) for p in read(index).get(stage,roots)]
    rows={}
    for root in roots:
        for path in (root/'task_rows').glob('*.json'):
            value=read(path)
            rows[value['cell_id']]=value
    return list(rows.values())


def run_m1(task,arm,request):
    from methods.a7_exploration.workflow import run_one
    snapshot=RUN/'shared_inputs/m1_source_bank.json'
    bank=read(snapshot)
    # 来源质量和异族限制仍由原eligible_cards实施；不把不合格来源改成成功。
    row=run_one(task,arm,bank,{4096:request},max_repairs=1)
    row['source_bank_path']=str(ARCHIVE)
    row['source_bank_snapshot']=str(snapshot)
    row['consumer']='original A7 protect architecture; not P7'
    row['repair_budget_amendment']='Both arms at most one public-evidence repair; historical prototype could iterate until stagnation.'
    return row


FEATURE_NAMES=('public_chars','parameter_words','context_chars','external_bindings',
               'return_explicit','exception_explicit','side_effect_mentions','security_chars')


def features(task):
    p=public_task(task);text=json.dumps(p,sort_keys=True)
    return [math.log1p(len(text)),len(re.findall(r'\w+',p.get('arguments',''))),
        math.log1p(len(p.get('context',''))),len(set(re.findall(r'\b[A-Z][A-Z_0-9]{2,}\b',text))),
        float(bool(p.get('return'))),float(bool(p.get('raise'))),
        len(re.findall(r'\b(write|delete|modify|update|execute|open|send|save)\b',text.lower())),
        math.log1p(len(p.get('security_policy','')))]


def rule_level(task,has_cards=True):
    if not has_cards:return 'L0'
    x=features(task)
    return 'L3' if x[3] or x[6] else 'L2'


def fit_logistic(x,y,c=1.):
    """小型L2多项逻辑回归；固定迭代数，不在开发集调特征或阈值。"""
    classes=sorted(set(y));x=np.asarray(x,dtype=float)
    mean=x.mean(0);scale=x.std(0);scale[scale==0]=1
    z=np.column_stack([np.ones(len(x)),(x-mean)/scale])
    w=np.zeros((z.shape[1],len(classes)))
    onehot=np.eye(len(classes))[[classes.index(t) for t in y]]
    for _ in range(2000):
        logits=z@w;logits-=logits.max(axis=1,keepdims=True)
        probabilities=np.exp(logits);probabilities/=probabilities.sum(axis=1,keepdims=True)
        penalty=w.copy();penalty[0]=0
        w-=.05*(z.T@(probabilities-onehot)/len(z)+penalty/(c*len(z)))
    return {'classes':classes,'mean':mean.tolist(),'scale':scale.tolist(),'weights':w.tolist(),'C':c}


def predict(task,model):
    if model['type']=='constant':return model['fixed'],1.
    x=np.r_[1.,(np.asarray(features(task))-model['fit']['mean'])/model['fit']['scale']]
    logits=x@np.asarray(model['fit']['weights']);logits-=logits.max()
    probabilities=np.exp(logits);probabilities/=probabilities.sum()
    i=int(probabilities.argmax());confidence=float(probabilities[i])
    return (model['fit']['classes'][i] if confidence>=.5 else model['fixed']),confidence


def final(row):
    result=copy.deepcopy(row.get('final') or (row.get('attempts') or [{}])[-1])
    if 'code' not in result:
        if type(row.get('selected_attempt')) is int:
            result['code']=row['attempts'][row['selected_attempt']].get('code','')
        elif 'selected_code' in row:result['code']=row['selected_code']
    return result


def train_classifier():
    rows=rows_for('C02');by={(r['task_id'],r['repeat'],r['condition']):r for r in rows}
    train=read(RAW/'v2/tasks_train.json');dev=read(RAW/'v2/tasks_development.json')
    if len(rows)!=480:raise ValueError('classifier_requires_complete_480_grid')
    labels=[]
    index=read(RUN/'execution_index.json')
    start_roots=[Path(p) for p in index.get('C02',[str(RUN/'C02')])]
    for task in train+dev:
        tid=str(task['index']);accepted=[];costs={}
        for level in LEVELS:
            items=[by[tid,r,level] for r in (1,2)]
            tokens=[item.get('usage',{}).get('prompt_tokens') for item in items]
            costs[level]=sum(tokens)/2 if all(type(v) is int for v in tokens) else None
            if all(final(item).get('measured') and final(item).get('joint') for item in items):accepted.append(level)
        candidates=[level for level in accepted if costs[level] is not None]
        has_intervention=any(a.get('generation',{}).get('retrieved_cards') for level in LEVELS for repeat in (1,2)
                             for a in by[tid,repeat,level].get('attempts',[]))
        counts=[]
        for repeat in (1,2):
            snapshots=[root/'shared_starts'/f'{tid}_r{repeat}.json' for root in start_roots]
            available=[p for p in snapshots if p.exists()]
            counts.append(len(read(available[-1])['selected_cards']) if available else None)
        if not has_intervention or None in counts:candidates=[]
        label=min(candidates,key=lambda l:(costs[l],l)) if candidates else None
        labels.append({'task_id':tid,'family_id':task['family_id'],'accepted_levels':accepted,
            'preferred_level':label,'input_tokens_P7_mean':costs,
            'first_selected_card_counts':counts,
            'any_generation_or_repair_memory_intervention':has_intervention,
            'label_status':'stable_success' if label else 'no_memory_intervention' if not has_intervention else
                'missing_shared_selection' if None in counts else 'unknown_input_cost' if accepted else 'no_stable_success'})
    training_ids={str(t['index']) for t in train}
    usable=[item for item in labels if item['task_id'] in training_ids and item['preferred_level']]
    scores={level:sum(bool(final(by[str(t['index']),r,level]).get('joint')) for t in train for r in (1,2)) for level in LEVELS}
    fixed=max(LEVELS,key=lambda l:(scores[l],-LEVELS.index(l)))
    model={'type':'constant','fixed':fixed,'features':FEATURE_NAMES,'confidence_threshold':.5,
        'fit_families':[item['family_id'] for item in usable], 'label_definition':'2/2 measured Joint; min mean P7 input tokens; material/selector costs reported separately',
        'task_only_router':True,'Q_or_CWE_or_ID_features':False,'development_used_for_fitting':False}
    if len({item['preferred_level'] for item in usable})>1:
        tasks={str(t['index']):t for t in train}
        x=[features(tasks[item['task_id']]) for item in usable];y=[item['preferred_level'] for item in usable]
        # family隔离三折；只选择一个正则化参数，开发12题从不用于选择。
        candidates=[]
        for c in (.1,1.,10.):
            correct=total=0
            for fold in range(3):
                a=[i for i in range(len(y)) if i%3!=fold];b=[i for i in range(len(y)) if i%3==fold]
                if not a:continue
                fit=fit_logistic([x[i] for i in a],[y[i] for i in a],c)
                temporary={**model,'type':'multinomial_logistic','fit':fit}
                for i in b:
                    correct+=predict(tasks[usable[i]['task_id']],temporary)[0]==y[i];total+=1
            candidates.append((correct/max(1,total),-c,c))
        chosen=max(candidates)[2]
        model.update(type='multinomial_logistic',fit=fit_logistic(x,y,chosen),CV_C_scores=candidates)
    else:model['degenerate_reason']='fewer_than_two_stable_preferred_classes; constant fallback is not learned superiority'
    write_json(RUN/'C03_C04a/model.json',model)
    write_json(RUN/'C03_C04a/labels.json',labels)
    pilot=train[:12]
    stable={str(t['index']):{level:sum(bool(final(by[str(t['index']),r,level]).get('joint')) for r in (1,2)) for level in LEVELS}
        for t in pilot if all(final(by[str(t['index']),r,level]).get('measured') for r in (1,2) for level in LEVELS)}
    contrasts={f'{a}_vs_{b}':{'a_wins':sum(v[a]==2 and v[b]==0 for v in stable.values()),
        'b_wins':sum(v[b]==2 and v[a]==0 for v in stable.values())} for i,a in enumerate(LEVELS) for b in LEVELS[i+1:]}
    stable_gap=sum(2 in v.values() and 0 in v.values() for v in stable.values())
    oracle=sum(max(v.values())/2 for v in stable.values())/len(stable) if stable else None
    fixed_pilot=max(sum(v[level]/2 for v in stable.values())/len(stable) for level in LEVELS) if stable else None
    gap=oracle-fixed_pilot if stable else None
    C1={'fully_measured_pilot_families':len(stable),'stable_gap_families':stable_gap,'bidirectional_contrasts':contrasts,'optimistic_oracle_minus_fixed':gap,
        'passed':len(stable)==12 and stable_gap>=4 and any(v['a_wins']>=2 and v['b_wins']>=2 for v in contrasts.values()) and gap>=.1,
        'interpretation':'heterogeneity diagnostic only; oracle is optimistic; user authorized all base comparisons regardless'}
    write_json(RUN/'C03_C04a/C1_diagnostic.json',C1)
    results={arm:[] for arm in ('fixed','rule','classifier')}
    label_map={item['task_id']:item for item in labels}
    for task in dev:
        tid=str(task['index'])
        for arm in results:
            for repeat in (1,2):
                has_cards=bool(label_map[tid]['first_selected_card_counts'][repeat-1])
                level=fixed if arm=='fixed' else rule_level(task,has_cards) if arm=='rule' else predict(task,model)[0]
                results[arm].append({'task_id':tid,'repeat':repeat,'level':level,'final':final(by[tid,repeat,level])})
    write_json(RUN/'C03_C04a/development.json',results)
    baselines={arm:{(r['task_id'],r['repeat']):r['final'] for r in items} for arm,items in results.items()}
    C2={}
    for baseline in ('fixed','rule'):
        keys=sorted(baselines['classifier'])
        difference={k:int(bool(baselines['classifier'][k].get('joint')))-int(bool(baselines[baseline][k].get('joint'))) for k in keys}
        delta=sum(difference.values())/len(keys)
        repeat_deltas={r:sum(value for key,value in difference.items() if key[1]==r)/12 for r in (1,2)}
        leaves=[sum(value for key,value in difference.items() if key[0]!=task_id)/22 for task_id in {k[0] for k in keys}]
        no_decline=all(sum(bool(baselines['classifier'][k].get(metric)) for k in keys)>=sum(bool(baselines[baseline][k].get(metric)) for k in keys) for metric in ('functional','security'))
        complete=all(baselines[arm][k].get('measured') for arm in ('classifier',baseline) for k in keys)
        C2[baseline]={'difference':delta,'repeat_differences':repeat_deltas,'F_S_non_decreasing':no_decline,
            'leave_one_family_out_minimum':min(leaves),'fully_measured':complete,
            'passed':complete and delta>=.05 and all(d>0 for d in repeat_deltas.values()) and no_decline and min(leaves)>=0}
    write_json(RUN/'C03_C04a/C2_diagnostic.json',{'comparisons':C2,'passed':all(v['passed'] for v in C2.values()),'controls_dispatch':False})
    write_json(RUN/'C03_C04a/state.json',{'status':'completed','paid_calls':0,'fit_family_count':len(usable),
        'classifier_type':model['type'],'benefit_gate_controls_dispatch':False})
    return model


def predict_level(task,arm,has_cards=True):
    model=read(RUN/'C03_C04a/model.json')
    return model['fixed'] if arm=='fixed' else rule_level(task,has_cards) if arm=='rule' else predict(task,model)[0]


def run_counterfactual(task,cell,request):
    from methods.cle_ablation import runner
    from methods.sct_trajectory.context_pipeline import experience_text
    from methods.sct_trajectory.closed_loop import validate_and_state
    from methods.sct_trajectory.agent_pipeline import _content
    from methods.direction_screening.adjustment import extract_candidate
    tid=str(task['index']);repeat=cell['repeat']
    source=next(r for r in rows_for('B02') if str(r['task_id'])==tid and r['repeat']==repeat and r['condition']=='BM')
    attempt=source['attempts'][0]
    cards=attempt.get('generation',{}).get('cards',[]) if cell['condition']=='memory_edit' else []
    prompt=('Return only complete Python code. Revise this fixed candidate using the public task and confirmed safe feedback. '
        'Preserve valid behavior and caller-provided bindings. Experience is provisional advice. '
        '\nPublic task:'+json.dumps(runner.plt_contract(task),ensure_ascii=False)+
        '\nFixed candidate:'+attempt.get('code','')+'\nConfirmed safe feedback:'+json.dumps(attempt.get('validation',{}),ensure_ascii=False)+
        '\nExperience:'+experience_text(cards))
    response=request(prompt);code,extraction=extract_candidate(_content(response))
    evidence,state=validate_and_state(task,code,timeout=20)
    measured=all(evidence.get(k,{}).get('status') in ('pass','fail') for k in ('functional','security'))
    f=evidence.get('functional',{}).get('status')=='pass';s=evidence.get('security',{}).get('status')=='pass'
    return {'task_id':tid,'source_cell_id':source['cell_id'],'source_attempt':0,'cards':cards,
        'final':{'code':code,'functional':f,'security':s,'joint':f and s,'measured':measured,
            'validation':evidence,'state':state,'extraction':extraction},'usage':response.get('usage'),
        'consumer':'single counterfactual edit; same source code and safe feedback; not independent new task'}


def freeze_validation():
    from .batch import fast_tasks
    ids={str(t['index']) for t in fast_tasks()}
    candidates=[]
    comparisons=[('B02','BM','B0','views'),('B02','BFS','BM','views'),('B02','BF','BM','views'),
        ('B02','BS','BM','views'),('S2_M1','protect_m1','protect_none','m1'),
        ('S2_P13_P22','P13','P00','profiles'),('S2_P13_P22','P22','P00','profiles'),
        ('D02','PUBLIC','P7','contract')]
    for stage,treated,control,kind in comparisons:
        # B/C使用自身训练区；D02等只消费冻结的12个开发ID，绝不使用S4验证题成绩选方案。
        rows=rows_for(stage)
        if kind not in ('views',):rows=[r for r in rows if str(r['task_id']) in ids]
        a={(str(r['task_id']),r['repeat']):r for r in rows if r['condition']==treated}
        b={(str(r['task_id']),r['repeat']):r for r in rows if r['condition']==control}
        keys=sorted(a.keys()&b.keys())
        if len(keys)!=24:continue
        gain=sum(bool(final(a[k]).get('joint'))-bool(final(b[k]).get('joint')) for k in keys)/len(keys)
        candidates.append({'stage':stage,'kind':kind,'treated':treated,'control':control,'development_gain':gain,
            'selection_pairs':len(keys),'selection_task_ids':sorted({k[0] for k in keys})})
    p=RUN/'C03_C04a/development.json'
    if p.exists():
        d=read(p)
        for arm in ('rule','classifier'):
            gain=(sum(bool(r['final'].get('joint')) for r in d[arm])-sum(bool(r['final'].get('joint')) for r in d['fixed']))/len(d['fixed'])
            candidates.append({'stage':'C03_C04a','kind':'granularity_confirmation','treated':arm,'control':'fixed',
                'development_gain':gain,'selection_pairs':len(d['fixed']),
                'selection_task_ids':sorted({str(r['task_id']) for r in d['fixed']})})
    if not candidates:raise ValueError('no_complete_development_comparison')
    chosen=max(enumerate(candidates),key=lambda item:(item[1]['development_gain'],-item[0]))[1]
    write_json(RUN/'S4_selection.json',{'chosen':chosen,'all_candidates':candidates,
        'rule':'largest paired development Joint gain; prespecified list order breaks ties; complete even if gain is nonpositive',
        'frozen_before_S4':True,'D02_prior_validation_family_exposure_disclosed':True})
    return chosen


def validation_cell(batch,cell):
    chosen=read(RUN/'S4_selection.json')['chosen']
    arm=chosen['treated'] if cell['condition']=='SELECTED' else chosen['control']
    consumer=copy.copy(batch)
    consumer.kind=chosen['kind']
    row=consumer.one({**cell,'condition':arm})
    row['migration_policy']=chosen
    return row
