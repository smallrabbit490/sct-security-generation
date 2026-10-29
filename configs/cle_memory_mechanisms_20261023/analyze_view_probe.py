"""复算B02两题原生记录，输出成绩、声明采用与待落实审查；零新增模型调用。"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict

from .prepare import ROOT, OUT, read, write
from methods.cle_ablation.run_memory_view_probe import MODES, VERSION, summary, technical_errors


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-name',default='B02_two_task_P7_v1',choices=[
        'B02_two_task_P7_v1','B02_two_task_P7_v2','B02_two_task_P7_v3_stream'])
    args=parser.parse_args()
    run = OUT / args.run_name
    rows = [read(p) for p in sorted((run / 'task_rows').glob('*.json'))]
    meta = read(run / 'run_metadata.json')
    assert len({r['cell_id'] for r in rows}) == len(rows)
    scores = summary(rows, meta['planned_P7'],meta['protocol'])
    scores['status'] = meta['status']
    scores['memory_unchanged'] = meta.get('memory_unchanged')
    scores['technical_probe_passed'] = (meta['status'] == 'completed_technical_probe'
        and len(rows) == 20 and not any(technical_errors(r) for r in rows)
        and meta.get('memory_unchanged') is True)
    # 两题只验流程；不将4个题×重复观察套用12题的收益门。
    scores['full_12_task_effectiveness_gate'] = 'not_evaluated'
    paired = {}
    for stage, position in [('first', 0), ('final', -1)]:
        indexed = {(r['task_id'], r['repeat'], r['view_arm']):r['attempts'][position] for r in rows}
        for mode in MODES:
            comparison = {'pairs': 0, 'rescue': 0, 'loss': 0, 'both_pass': 0, 'both_fail': 0}
            for tid in meta['task_ids']:
                for repeat in (1, 2):
                    a,b = indexed.get((tid,repeat,mode)),indexed.get((tid,repeat,'BM'))
                    if a is None or b is None or not a.get('measured') or not b.get('measured'):
                        continue
                    comparison['pairs'] += 1
                    key = ('both_pass' if a['joint'] else 'loss') if b['joint'] else (
                          'rescue' if a['joint'] else 'both_fail')
                    comparison[key] += 1
            comparison['net_joint'] = comparison['rescue'] - comparison['loss']
            paired[f'{stage}_{mode}-BM'] = comparison
    scores['paired_vs_BM'] = paired
    attempts = []
    for row in rows:
        for a in row['attempts']:
            generation = a.get('generation', {})
            trace = a.get('retrieval_trace') or {}
            retrieval = next((s for s in generation.get('stages',[]) if s['stage']=='retrieval'),{})
            stale = retrieval.get('status')=='degraded' and trace.get('status')=='completed'
            if retrieval.get('status')=='degraded':
                # 保存旧原生产物，不将其误绑的首次成功轨迹当成修复选卡成功。
                trace = retrieval.get('retrieval_trace') or {}
            attempts.append({'cell_id':row['cell_id'],'task_id':row['task_id'],'repeat':row['repeat'],
                'arm':row['view_arm'],'attempt':a['attempt'],
                'native_attempt_trace_stale':stale,
                'retrieval_status':retrieval.get('status'),
                'selected_ids':json.dumps(trace.get('selected_ids',[])),
                'pre_view_selected_ids':json.dumps(trace.get('pre_view_selected_ids',[])),
                'declared_applied_ids':json.dumps(generation.get('adoption',{}).get('applied_ids',[])),
                'declared_rejected_ids':json.dumps(generation.get('adoption',{}).get('rejected_ids',[])),
                'functional':a.get('functional'),'security':a.get('security'),'joint':a.get('joint'),
                'measured':a.get('measured'),'workflow_completed':generation.get('workflow_completed'),
                'error_type':generation.get('error_type') or a.get('error_type'),
                'implementation_review':'pending','mechanism_note':''})
    review = run / 'mechanism_review.csv'
    # 人工/Agent逐题补充列不可被统计重跑抹掉。
    previous = {}
    if review.exists():
        with review.open(encoding='utf-8-sig',newline='') as stream:
            previous = {(r['cell_id'],int(r['attempt'])):r for r in csv.DictReader(stream)}
    for row in attempts:
        old = previous.get((row['cell_id'],row['attempt']),{})
        for key in ('implementation_review','mechanism_note'):
            if old.get(key):row[key]=old[key]
    if attempts:
        with review.open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(attempts[0]),lineterminator='\n')
            writer.writeheader();writer.writerows(attempts)
    records = read(run / 'cost.json')['records']
    cost = defaultdict(lambda:Counter(logical_operations=0,input_tokens=0,output_tokens=0,total_tokens=0,unknown_usage=0))
    for record in records:
        item=cost[record['kind']];item['logical_operations']+=1
        usage=record.get('usage') or {}
        if 'total_tokens' not in usage:item['unknown_usage']+=1
        for field,key in [('input_tokens','prompt_tokens'),('output_tokens','completion_tokens'),('total_tokens','total_tokens')]:
            item[field]+=usage.get(key,0)
    responses=[read(p) for p in sorted((run/'requests').glob('*.response.json'))]
    scores['returned_chat_models']=dict(Counter(str(r.get('model')) for r in responses))
    scores['new_cost_by_kind']=dict(cost)
    if args.run_name!='B02_two_task_P7_v1':
        scores['aggregate_cost_by_kind']=scores.pop('new_cost_by_kind')
        current=defaultdict(lambda:Counter(logical_operations=0,total_tokens=0,unknown_usage=0))
        for record in records:
            if record.get('source_protocol')==meta['protocol']:
                item=current[record['kind']];item['logical_operations']+=1
                usage=record.get('usage') or {}
                item['total_tokens']+=usage.get('total_tokens',0)
                item['unknown_usage']+= 'total_tokens' not in usage
        scores['new_cost_by_kind']=dict(current)
        scores['prior_fault_and_controls_included_in_aggregate']=True
        scores['reused_request_count']=sum(read(p).get('status')=='reused'
                                         for p in (run/'requests').glob('*.status.json'))
    scores['shared_preparation_known_tokens']=183231
    scores['all_stages_known_tokens']=183231+sum(c['total_tokens'] for c in cost.values())
    scores['billing_complete']=False
    diagnostic=run/'api_availability_diagnostic.json'
    if diagnostic.exists():
        d=read(diagnostic)
        scores['api_diagnostic']={k:d.get(k) for k in ['status','expected_text','response_text','reported_model','elapsed_seconds','usage']}
        scores['all_stages_including_diagnostic_known_tokens']=(scores['all_stages_known_tokens']+
            int((d.get('usage') or {}).get('total_tokens',0)))
    scores['generated_code_count']=sum(bool(a.get('code')) for r in rows for a in r['attempts'])
    write(run/'analysis.json',scores)
    curated=ROOT/'results/curated/cle_memory_mechanisms_20261023'
    name='B02_two_task_probe.json' if args.run_name=='B02_two_task_P7_v1' else args.run_name+'.json'
    write(curated/name,scores)
    lines=['# B02两题功能/安全视图技术探针','',
        f"状态：{meta['status']}；完成{len(rows)}/20次原P7；技术门：{scores['technical_probe_passed']}。",
        '','两题属于已锁12题的前缀。本表不检验12题收益门，不更新Q，也不触发旧实验。','',
        '| 条件 | 完成 | 首次F/S/Joint | 交付F/S/Joint | 修复 | 缺测 | 流程错误 |',
        '|---|---:|---|---|---:|---:|---:|']
    for mode,item in scores['arms'].items():
        first=('/'.join(str(item['first'][k]) for k in ['functional','security','joint'])
               if item['first']['measured'] else ('未测量' if item['completed'] else '未执行'))
        final=('/'.join(str(item['final'][k]) for k in ['functional','security','joint'])
               if item['final']['measured'] else ('未测量' if item['completed'] else '未执行'))
        lines.append(f"| {mode} | {item['completed']} | {first} | {final} | {item['repairs']} | {item['unmeasured']} | {item['technical_errors']} |")
    lines += ['',f"实际生成代码{scores['generated_code_count']}份；本协议新调用已知Token合计{sum(c['total_tokens'] for c in scores['new_cost_by_kind'].values())}，"
              f"共享准备183231，累计已知{scores['all_stages_known_tokens']}。未知用量和HTTP预留另见cost.json，不是实付账单。",'',
              '声明采用见mechanism_review.csv；是否正确实现须另读代码，不根据采用ID自动判断。',
              '完整12题继续受1348公开资源政策门约束；914对人审、Notion原件仍待补。']
    if diagnostic.exists():
        lines += ['',f"单独API短诊断状态：{scores['api_diagnostic']['status']}；回复符合预期：{scores['api_diagnostic']['expected_text']}。"
                  f"含诊断的累计已知返回Token：{scores['all_stages_including_diagnostic_known_tokens']}；不是实付账单。"]
    (run/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'status':meta['status'],'completed_P7':len(rows),
          'technical_gate':scores['technical_probe_passed'],'all_stages_known_tokens':scores['all_stages_known_tokens']},ensure_ascii=False))


if __name__=='__main__':
    main()
