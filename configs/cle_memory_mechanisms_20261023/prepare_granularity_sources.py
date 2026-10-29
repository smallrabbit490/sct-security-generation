"""C01零API来源核对：区分标准修复种子与产生经验的真实训练轨迹。"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .prepare import ROOT, ONLINE, OUT, read, write, write_csv
from .review_q_credit import records

ARCHIVE=Path('E:/ResearchArchives/sct-security-generation_20261016/原始项目')
SOURCE_RUN=ARCHIVE/'translation_work/sct_runs/cle_context_874_20260923'
VERSION='cle-granularity-source-reconciliation-v1'


def example_kind(card):
    """种子卡使用训练题标准修复，其余卡关联真实生成尝试，不互相冒称。"""
    return ('training_reference_seed' if card['source']['kind']=='seed_from_diff'
            else 'training_generated_episode')


def source_episode(task,phase1,line_number):
    """只取来源题公开题面、生成代码和报告状态；不复制隐藏测试或目标题答案。"""
    codes=phase1['generated_codes']
    attempts=[]
    for index,code in enumerate(codes):
        state=phase1['state_first'] if index==0 else phase1['state_after_repair']
        evidence=phase1['evidence_first'] if index==0 else phase1['evidence_after_repair']
        attempts.append({'attempt':index,'generated_code':code,'reported_state':state,
            'reported_validation':{key:evidence.get(key) for key in ('syntax_or_compile','functional','security')}
                                  if evidence else None})
    return {'source_task_id':str(phase1['task_id']),
        'original_source_public_task':task['task_description'],
        'phase1_outcome':phase1['outcome'],'attempts':attempts,
        'source_record':str(SOURCE_RUN/'phase1_results.jsonl')+':'+str(line_number),
        'input_scope':'D_init source episode only; no target answer or hidden tests',
        'original_generation_prompts_available':False,
        'is_guaranteed_correct_example':False}


def link_card(card,original,episode,source_family,target_families):
    """按未翻译的ID与来源身份核对，再检查来源family不属于锁定目标族。"""
    if (card['invariant_id']!=original['invariant_id'] or
            str(card['source']['task_id'])!=str(original['source']['task_id']) or
            card['source']['kind']!=original['source']['kind']):
        raise ValueError('original_card_source_identity_mismatch')
    if source_family in target_families:raise ValueError('source_target_family_overlap')
    if str(card['source']['task_id'])!=episode['source_task_id']:
        raise ValueError('wrong_training_source_episode')
    return {'card_id':card['invariant_id'],'source_task_id':episode['source_task_id'],
        'source_family_id':source_family,'source_pool':'D_init','source_cwe':str(card['cwe']),
        'source_kind':card['source']['kind'],'L4_example_kind':example_kind(card),
        'original_card_identity_verified':True,'episode_available':bool(episode['attempts']),
        'has_nonempty_generated_code':any(a['generated_code'].strip() for a in episode['attempts']),
        'source_attempt_count':len(episode['attempts']),'source_phase1_outcome':episode['phase1_outcome'],
        'source_record':episode['source_record'],
        'single_producing_attempt_certified':False,
        'reason':'source record linked; may include empty code; derived hints/pitfalls can share a distillation block'}


def source_measurements(episodes):
    """末次来源代码缺测时不借用首次成绩；这些是来源日志，非本轮新实验成绩。"""
    counts=Counter()
    for episode in episodes.values():
        evidence=episode['attempts'][-1]['reported_validation']
        if not evidence or any(evidence.get(k) not in ('pass','fail') for k in ('functional','security')):
            counts['unmeasured']+=1
        else:
            key=('F+' if evidence['functional']=='pass' else 'F-')+('S+' if evidence['security']=='pass' else 'S-')
            counts[key]+=1
    return dict(counts)


def main():
    destination=OUT/'C01_source_reconciliation_v1'
    destination.mkdir(exist_ok=False)
    nodes=[r for _,r in records(ONLINE/'D_grow/frozen/m_star_q.jsonl')]
    originals={r['invariant_id']:r for _,r in records(SOURCE_RUN/'experience_pool.jsonl')}
    phase1={str(r['task_id']):(number,r) for number,r in records(SOURCE_RUN/'phase1_results.jsonl')}
    source_ids={str(r['source']['task_id']) for r in nodes}
    # 读入原归档后按来源ID选择；目标题ground_truth不参与材料构造、不写入输出。
    dataset=read(ARCHIVE/'data/external/secodeplt/secodeplt/data.json')
    sources={str(task['index']):task for task in dataset if str(task['index']) in source_ids}
    current_sources=read(ONLINE/'tasks_D_init.json')
    manifest=read(OUT/'manifest.json')
    targets={entry['family_id'] for group in manifest['groups'].values() for entry in group}
    if not source_ids<=phase1.keys() or not source_ids<=sources.keys():
        raise ValueError('source_episode_or_public_task_missing')
    episodes={tid:source_episode(sources[tid],phase1[tid][1],phase1[tid][0]) for tid in source_ids}
    links=[link_card(card,originals[card['invariant_id']],episodes[str(card['source']['task_id'])],
                     current_sources[str(card['source']['task_id'])]['family_id'],targets) for card in nodes]
    with (destination/'source_episodes.jsonl').open('w',encoding='utf-8') as stream:
        for tid in sorted(episodes,key=int):stream.write(json.dumps(episodes[tid],ensure_ascii=False)+'\n')
    seeds=[]
    for card in nodes:
        if example_kind(card)=='training_reference_seed':
            task=sources[str(card['source']['task_id'])];gt=task['ground_truth']
            seeds.append({'card_id':card['invariant_id'],'source_task_id':str(task['index']),
                'original_source_public_task':task['task_description'],
                'reference_seed_code':gt['code_before']+gt['patched_code']+gt['code_after'],
                'example_kind':'training_reference_seed','is_generated_episode':False})
    with (destination/'reference_seed_examples.jsonl').open('w',encoding='utf-8') as stream:
        for item in seeds:stream.write(json.dumps(item,ensure_ascii=False)+'\n')
    write_csv(destination/'card_source_links.csv',links)
    fresh={r['invariant_id']:r for r in nodes if r['invariant_id'] in {
        'cand-1333-7972143074757284700','pitfall-915-8144612929088593380'}}
    for identifier,card in fresh.items():
        tid=str(card['source']['task_id'])
        write(destination/'fresh_selected_sources'/f'{identifier}.json',{
            'card_id':identifier,'current_card_source':card['source'],
            'original_card_source_before_translation':originals[identifier]['source'],
            'episode':episodes[tid],
            'older_reference_only_material':str(OUT/'source_examples'/f'{tid}.json'),
            'not_target_answer':True,'view_status':'source_material_only_not_rendered_L0_to_L4'})
    result={'protocol':VERSION,'cards':len(nodes),'original_card_ids_matched':len(links),
        'source_tasks_with_actual_episodes':len(episodes),
        'source_generated_code_versions':sum(len(e['attempts']) for e in episodes.values()),
        'source_generated_code_versions_semantics':'saved output slots, including empty responses',
        'source_nonempty_generated_codes':sum(bool(a['generated_code'].strip()) for e in episodes.values() for a in e['attempts']),
        'source_empty_code_slots':sum(not a['generated_code'].strip() for e in episodes.values() for a in e['attempts']),
        'example_kind_counts':dict(Counter(x['L4_example_kind'] for x in links)),
        'phase1_outcome_counts':dict(Counter(e['phase1_outcome'] for e in episodes.values())),
        'source_last_attempt_FS':source_measurements(episodes),
        'source_code_origin':'actual native phase1_results; reference seeds separate',
        'source_target_family_overlap':0,'API_calls':0,'Q_updates':0,
        'L0_to_L4_renderer_implemented':False,'classifier_trained':False,
        'source_prompt_reconstruction_performed':False,
        'prior_source_example_index_meaning':'reference material availability, not certified producing episode',
        'single_card_exact_producing_attempt_certified':False}
    write(destination/'summary.json',result)
    write(ROOT/'results/curated/cle_memory_mechanisms_20261023/granularity_sources.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
