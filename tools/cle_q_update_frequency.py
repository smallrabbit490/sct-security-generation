"""零API统计已完成学习轮次：更新事件数/期末已有反馈卡数，恢复副本不重复计数。"""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CURATED=ROOT/'results/curated'
RUN=Path('E:/ResearchRuns/CLE/20261027_full_requirements')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    rows=[]
    def add(name,model,tasks,updates,covered,source,unique=None,new=None):
        rows.append({'experiment':name,'model':model,'completed_tasks':tasks,
            'valid_update_events':updates,'covered_cards_at_end':covered,
            'events_per_covered_card':updates/covered if covered else None,
            'updated_distinct_cards':unique,'updated_distinct_share':unique/covered if unique is not None and covered else None,
            'newly_covered_cards':new,'source':str(source)})
    def load(name,file='summary.json'):
        p=CURATED/name/file
        return read(p),p
    d,p=load('cle_memory_q_full_dgrow_20261016')
    q=d['Q_learning'];add('10-16 D_grow限三张观察学习','v3.2',273,q['positive_updates']+q['negative_updates'],q['visited_cards'],p,297,297)
    d,p=load('cle_memory_q_unlimited_complete_20261018')
    q=d['stages']['observe']['summary']['Q_learning'];add('10-18 D_grow不限三张观察学习','v3.2',273,q['updates'],q['visited_cards'],p,466,466)
    d,p=load('cle_dgrow_url_q_learning_20261020','learning_summary.json')
    add('10-20 修复32题补学习','v3.2',d['executed'],d['valid_card_updates'],d['visited_after'],p,d['changed_cards'],d['new_cards_learned'])
    d,p=load('cle_dinit_full_learning_20261020_v4b')
    q=d['credit']['all_feedback'];add('10-20 D_init完整303题限三张学习','v3.2',d['executed'],q['valid_updates'],q['learned_cards'],p,None,q['new_cards'])
    d,p=load('cle_dinit_card_cap_20261020_v2')
    for arm,label in [('L3','限三张12题对照'),('Lall','不限三张完整303题学习')]:
        a=d['arms'][arm];q=a['credit']['all_feedback']
        add('10-20 D_init'+label,'v3.2',a['executed'],q['valid_updates'],q['learned_cards'],p,None,q['new_cards'])
    d,p=load('cle_q_online_20261020','D_init_summary.json')
    add('10-21 D_init Q参与排序在线学习','v3.2',d['executed'],d['valid_updates'],d['visited_after'],p,None,d['visited_after']-d['visited_before'])
    for stage in ('K0','K1','K2','K3'):
        p=RUN/'analysis'/stage/'summary.json'
        if not p.exists(): continue
        d=read(p)
        if d.get('status')!='completed' or d['completed']!=d['planned']: continue
        q=d['memory'];cards=read(p.parent/'per_card_feedback.json')
        if sum(c['events'] for c in cards.values())!=q['credit_events_this_stage']:
            raise ValueError('per_card_event_sum_differs:'+stage)
        # 用该轮冻结快照独立核对期末有反馈卡数；Q恰为0但visits>0仍计入。
        bank=[json.loads(v) for v in (RUN/'FQ_LEARN/frozen'/(stage+'.jsonl')).read_text(encoding='utf-8-sig').splitlines() if v.strip()]
        covered=sum(v.get('q_visits',0)>0 for v in bank)
        if covered!=q['covered_after_saved_prefix']: raise ValueError('frozen_coverage_differs:'+stage)
        add('10-27/28 '+stage+' '+d['pool'],'v4.1-1017',d['completed'],q['credit_events_this_stage'],covered,p,q['credited_cards_this_stage'],q['newly_covered_this_stage'])
    target=CURATED/'cle_q_update_frequency_20261028';target.mkdir(parents=True,exist_ok=True)
    output={'definition':'valid credited update events in the stage / distinct cards with q_visits>0 at stage end',
        'unit':'updates per covered card, not coverage percentage',
        'event_semantics':'each credited card feedback event, including repeated card updates and repair attempts; not unique cards or tasks',
        'historical_credit_policy':'all_feedback; cross_family counterfactual tables are not added',
        'no_summing_independent_libraries':True,'API_calls':0,'rows':rows}
    (target/'summary.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (target/'statistics.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    text=['# 已完成Q学习的反馈更新频次','','更新频次＝本轮合法更新事件数÷轮末有反馈卡数。相同卡可以多次更新，故结果可以大于1；它不是唯一卡覆盖率。有反馈按q_visits>0定义。','','| 已完成实验 | 题数 | 更新次数 | 期末有Q反馈卡数 | 平均更新次数/卡 | 本轮更新不同卡数 | 新增反馈卡数 |','|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        text.append(f"|{r['experiment']}|{r['completed_tasks']}|{r['valid_update_events']}|{r['covered_cards_at_end']}|{r['events_per_covered_card']:.3f}|{r['updated_distinct_cards'] if r['updated_distinct_cards'] is not None else '摘要未列'}|{r['newly_covered_cards']}|")
    text+=['','历史分支的起始Q快照与反馈资格不同，不将这些实验直接累计成一条学习曲线。冻结回测和D_gate只读Q，更新次数为0；它们不属于学习轮次。未完成轮次另列运行进度，不纳入完整轮次表。']
    (target/'report.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False))


if __name__=='__main__':main()
