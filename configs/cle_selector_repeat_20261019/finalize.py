"""仅复用本轮真实选卡记录，补充通俗解释、同提示案例和频率；零API。"""
import csv
import itertools
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation import run_selector_repeat as study


def main():
    study.verify(study.OUT)
    summary=study.read(study.CURATED/'summary.json')
    specs={s['task_id']:s for s in study.read(study.OUT/'inputs.json')}
    rows=study.read_rows(study.OUT/'rows.jsonl')
    with (study.CURATED/'pairwise_by_task.csv').open(encoding='utf-8-sig',newline='') as stream:
        pairs=list(csv.DictReader(stream))
    with (study.CURATED/'card_selection_frequencies.csv').open(encoding='utf-8-sig',newline='') as stream:
        frequencies=list(csv.DictReader(stream))
    arm_order=[]
    for arm in study.ARMS:
        identical_members=0;only_order=0;total=0
        for task_id in specs:
            values=[r['selected_ids'] for r in rows if r['task_id']==task_id and r['arm']==arm and r['status']=='completed']
            for a,b in itertools.combinations(values,2):
                total+=1
                if set(a)==set(b):
                    identical_members+=1
                    only_order+=a!=b
        arm_order.append({'arm':arm,'within_repeat_pairs':total,'same_members':identical_members,
                          'same_members_different_output_order':only_order})
    order_effect=summary['Q_reorders_vs_similarity_detectable']
    assignment=summary['Q_assignment_vs_shuffle_detectable']
    if order_effect and assignment:
        conclusion='在本批固定输入中，学习Q排序造成的选卡集合差异超出了模型自身波动，并且与打乱Q有可检测差异。仍未测量选卡更准确或Joint提高。'
    elif order_effect:
        conclusion='在本批固定输入中，Q融合排序相对相似度造成了超出自身波动的选卡差异；但尚不能区分学习Q与打乱Q的作用，不能据此说学习到的价值有独特帮助。'
    else:
        conclusion='本批未达到“学习Q相对相似度的影响超出自身波动”的预设门槛。确实换过卡，不足以把变化归因于Q；这也不等于证明Q完全没有影响。'
    summary['plain_language_conclusion']=conclusion
    summary['output_order_diagnostics']=arm_order
    responses=[m for r in rows for m in r['response_metadata']]
    summary['response_identity']={'reported_models':sorted({m['model'] for m in responses if m.get('model')}),
        'system_fingerprints':sorted({m['system_fingerprint'] for m in responses if m.get('system_fingerprint')}),
        'fingerprint_missing_responses':sum(not m.get('system_fingerprint') for m in responses)}
    summary['native_format_retries']={a:sum(len(r['retrieval_trace']['selector_attempts'])>1 for r in rows if r['arm']==a) for a in study.ARMS}
    retry_tasks={r['task_id'] for r in rows if len(r['retrieval_trace']['selector_attempts'])>1}
    clean_groups={i:{a:[r['selected_ids'] for r in sorted(rows,key=lambda r:r['repeat'])
                       if r['task_id']==i and r['arm']==a and r['status']=='completed'] for a in study.ARMS}
                  for i in specs if i not in retry_tasks}
    sensitivity=[study.compare(clean_groups,t,c)[0] for t,c in study.read(study.CONFIG/'protocol.json')['primary_comparisons']]
    study.holm(sensitivity)
    summary['posthoc_retry_task_sensitivity']={'excluded_from_sensitivity_only':sorted(retry_tasks),
                                             'comparisons':sensitivity,'primary_rows_unchanged':True}
    usage=[u for r in rows for u in r['usage_responses'] if isinstance(u,dict)]
    cached=[(u.get('prompt_tokens_details') or {}).get('cached_tokens') for u in usage]
    summary['cached_tokens_reported']=sum(v for v in cached if isinstance(v,int)) if any(isinstance(v,int) for v in cached) else None
    summary['valid_empty_selections']={a:sum(r['status']=='completed' and r['selected_ids']==[] for r in rows if r['arm']==a) for a in study.ARMS}
    study.write(study.CURATED/'summary.json',summary);study.write(study.OUT/'summary.json',summary)
    study.write(study.CURATED/'run_metadata.json',study.read(study.OUT/'run_metadata.json'))
    study.write(study.CURATED/'protocol.json',study.read(study.CONFIG/'protocol.json'))
    sections=['## 8. 通俗解释与真实例子','',conclusion,'',
        '可以把五次选择理解成让同一位模型做五遍同一道选卡题。组内差异是它自己反复做会变多少；跨组差异还混有排序变化，扣除组内差异后才观察额外影响。这里的距离只衡量换卡程度，不是正确率。','',
        '四组自身平均集合距离约0.53–0.58，说明单次选卡仍很不稳定。总体上检出排序影响，不表示每道题都受影响，也不表示某张卡只要往前排就一定更常被选。','',
        '| 组别 | 同组重复集合对 | 成员完全相同 | 成员相同但输出次序不同 |',
        '|---|---:|---:|---:|']
    for a in arm_order:
        sections.append(f'| {a["arm"]} | {a["within_repeat_pairs"]} | {a["same_members"]} | {a["same_members_different_output_order"]} |')
    sections+=['','输出次序另列，不混入本研究主要的“成员是否改变”指标。各题之间不是同一道选卡题，不能跨题直接比较卡ID或把所有集合对当独立样本。','',
               '### 8.1 输入完全相同，模型是否仍会换卡','']
    cases=[]
    for control in summary['identical_prompt_controls']:
        task_id=control['task_id'];spec=specs[task_id]
        sections.append(f'题目 {task_id}：{control["left"]}/{control["right"]} 的首次选卡提示逐字相同，包括候选短编号。')
        sections+=['','| 组别 | 五次选择数量 | 五次出现的不同集合数 | 触发格式重试 |','|---|---|---:|---:|']
        case={'task_id':task_id,'type':'identical_prompt_negative_control','arms':{}}
        for arm in (control['left'],control['right']):
            values=[r['selected_ids'] for r in sorted(rows,key=lambda r:r['repeat']) if r['task_id']==task_id and r['arm']==arm and r['status']=='completed']
            unique=len({tuple(sorted(v)) for v in values})
            retried=sum(len(r['retrieval_trace']['selector_attempts'])>1 for r in rows if r['task_id']==task_id and r['arm']==arm)
            sections.append(f'| {arm} | '+', '.join(str(len(v)) for v in values)+f' | {unique} | {retried} |')
            case['arms'][arm]=values
        sections+=['','这里即便两组不同，也是同提示下的服务/模型输出波动，不能归功Q或相似度。这是负对照（输入没变，用来观察自身变化），不是选卡质量标签。','']
        cases.append(case)
    scored=[p for p in pairs if p['test']=='Q2' and p['control']=='Q1']
    if scored:
        highest=max(scored,key=lambda p:float(p['excess_distance']))
        lowest=min(scored,key=lambda p:float(p['excess_distance']))
        for label,item in [('超额差异最大',highest),('超额差异最小',lowest)]:
            task_id=item['task_id'];spec=specs[task_id]
            sections+=['### 8.2 '+label+'的事后诊断：题目 '+task_id,'',
                f'Q2−Q1 跨组距离为 {float(item["between"]):.4f}，两组自身距离为 {float(item["within_test"]):.4f}/{float(item["within_control"]):.4f}，超额差异为 {float(item["excess_distance"]):.4f}。这些案例是在完整统计后选出，仅作解释，不是独立显著性发现。','',
                '| 卡ID | 历史Q | Q1/Q2呈现位置 | Q1五次选中 | Q2五次选中 |','|---|---:|---|---:|---:|']
            by_card={}
            for f in frequencies:
                if f['task_id']==task_id and f['arm'] in ('Q1','Q2'):
                    by_card.setdefault(f['card_id'],{})[f['arm']]=f
            ordered=sorted(by_card,key=lambda card:(-abs(int(by_card[card]['Q2']['selected_times'])-int(by_card[card]['Q1']['selected_times'])),card))[:6]
            for card in ordered:
                a=by_card[card]['Q1'];b=by_card[card]['Q2']
                sections.append(f'| {card} | {float(a["learned_Q"]):.3f} | {a["presentation_rank"]}/{b["presentation_rank"]} | {a["selected_times"]}/5 | {b["selected_times"]}/5 |')
            cases.append({'task_id':task_id,'type':label,'metrics':item,'cards':{c:by_card[c] for c in ordered}})
            sections+=['','位置变化、选择频率变化是排序传导线索。没有适用性标签、复析采用、代码或测试，所以不能说这些卡更正确，更不能把高Q解释为当前题目一定适用。','']
    sections+=['## 9. 本轮收口','',
        '本轮固定160次选择操作已结束，不追加重复以追求显著性，不继续到代码生成或Q学习。接下来若研究三张上限，应使用单独的数量干预协议；本次所有组均不限三张，不能回答三张上限是否正确。',
        '相同提示下的变化在这里统称模型/服务重复波动，不能进一步断言全部来自模型内部随机性。响应身份统计：'+json.dumps(summary['response_identity'],ensure_ascii=False)+'。提供方没有返回指纹时，不推断后台完全未变。',
        '原生格式重试操作数：'+json.dumps(summary['native_format_retries'],ensure_ascii=False)+'。重试会追加格式提醒，因此主要结果衡量包含原重试机制的真实选卡流程；同提示负对照指首次提示相同，发生重试时不声称全过程提示始终相同。',
        '事后敏感性分析（不替换主分析）：仅从敏感性副本排除发生格式重试的题族，保留其全部原始记录和8题主分母；余下'+str(len(clean_groups))+'题族的超额差异/校正p为 '+ '; '.join(f'{c["test"]}−{c["control"]}: {c["excess_distance"]:.4f}/{c["p_holm"]:.5f}' for c in sensitivity)+'。这是检查一次格式修复是否主导结论，不作为新的主要检验。',
        '该敏感性副本中，Q2−Q1和Q2−Q3的题族区间仍在0以上；Q2−Q0区间跨0，因此相对原顺序的判断更脆弱，不能把三项比较统称为同等稳健。完整区间保存在summary.posthoc_retry_task_sensitivity。',
        '提供方明确报告的缓存Token合计：'+str(summary['cached_tokens_reported'])+'；未报告部分不估填。全部已回执输入/输出Token继续按原始用量保存，缓存不直接换算为实付金额。',
        '合法空返回按空集纳入，分组次数为 '+json.dumps(summary['valid_empty_selections'],ensure_ascii=False)+'；它们不是技术失败，也不是缺测。',
        '4项专项离线测试通过，覆盖集合距离、已知分离/不分离例子、失败不冒充空集、原选择器超过三张及短ID映射。实际160次后核对冻结输入/Q、共同候选、唯一身份及旧Q0/父记录指纹；另用纯集合/均值公式独立复算三项超额差异，与主实现吻合。详情见verification.json。',
        '原生report生成基础版，本finalize只用真实数据补充解释；刷新时先report再finalize。']
    study.write(study.CURATED/'cases.json',cases)
    text=study.REPORT.read_text(encoding='utf-8')
    meta=study.read(study.OUT/'run_metadata.json')
    identity_line=f'实际分支：`{meta["branch"]}`；基线提交：`{meta["commit"]}`；未提交源码以运行区source_snapshot和run_metadata为准。'
    if identity_line not in text:
        text=text.replace('\n## 1. 结论','\n'+identity_line+'\n\n## 1. 结论',1)
    marker='\n## 8. 通俗解释与真实例子'
    text=text.split(marker)[0].rstrip()+'\n\n'+'\n'.join(sections)+'\n'
    study.REPORT.write_text(text,encoding='utf-8');(study.OUT/'report.md').write_text(text,encoding='utf-8')
    print(conclusion)


if __name__=='__main__':
    main()
