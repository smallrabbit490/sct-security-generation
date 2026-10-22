"""从资格复核与真实P7记录生成本轮报告；不调用模型，不读取D_gate。"""
from collections import Counter
import argparse
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation.run_memory_q_coverage import OUT,OLD,CURATED,read,rows,credit,load_memory,write,FIELDS


def csv_write(path,items):
    if not items:return
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(items[0]));writer.writeheader();writer.writerows(items)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--finalize',action='store_true');args=parser.parse_args()
    CURATED.mkdir(exist_ok=True,parents=True)
    q=read(OUT/'qualification.after_dependencies.json');manifest=read(OUT/'manifest.json');meta=read(OUT/'run_metadata.json')
    source=load_memory(OUT/'input_memory.jsonl');support=read(OUT/'base_family_support.json')
    stages={};all_rows={}
    probe_rows=rows(OUT/'probe/rows.jsonl')
    for arm in ['L0','L1']:
        p=OUT/'probe'/arm
        if probe_rows and not (p/'summary.json').exists() and args.finalize:
            p.mkdir(exist_ok=True)
            credit([r for r in probe_rows if r['arm']==arm],source,support,manifest['probe'],p)
        if (p/'summary.json').exists():stages['probe/'+arm]=read(p/'summary.json')
    for stage in ['probe','round1','round2']:
        for r in rows(OUT/stage/'rows.jsonl'):
            k=(r['stage'],r['task_id'],r['arm'])
            if k in all_rows:assert all_rows[k]==r
            all_rows[k]=r
        if stage!='probe' and (OUT/stage/'summary.json').exists():stages[stage+'/L1']=read(OUT/stage/'summary.json')
    gate=read(OUT/'probe_gate.json') if (OUT/'probe_gate.json').exists() else {'passed':None,'reason':'running'}
    round2=read(OUT/'round2_gate.json') if (OUT/'round2_gate.json').exists() else None
    if gate['passed'] is False:
        status='technical_stop' if gate.get('reason')=='first2_technical_stop' else 'probe_gate_not_passed'
    elif 'round2/L1' in stages:
        status='completed_maximum_two_rounds' if stages['round2/L1']['rows']==manifest['N'] and not stages['round2/L1']['technical_issues'] else 'technical_stop_round2'
    elif 'round1/L1' in stages:
        s=stages['round1/L1']
        status='technical_stop_round1' if s['technical_issues'] or s['rows']!=manifest['N'] else 'coverage_target_met' if s['learned_cards']>=970 and s['fixed_anchor_learned']>=955 else 'round2_gate_not_passed' if round2 and not round2['passed'] else 'running'
    else:status='running'
    costs={k:sum(r['accounting']['total'][k] for r in all_rows.values()) for k in FIELDS}
    initial={k:sum(r['accounting'][k] for r in rows(OUT/'new_shared_initial.jsonl')) for k in FIELDS}
    total={k:costs[k]+initial[k] for k in FIELDS}
    newly_bad={t['task_id'] for t in q['tasks'] if t['previous_reward_eligible'] and not t['reward_eligible']}
    old_events=[e for e in rows(OLD/'observe/memory_q_events.jsonl') if e.get('invariant_id') and e.get('reward') is not None]
    affected=[e for e in old_events if e['task_id'] in newly_bad]
    by=Counter();card_support={}
    for e in old_events:card_support.setdefault(e['invariant_id'],set()).add(e['task_id'])
    for t in q['tasks']:
        by[t['cwe']+'_tasks']+=1;by[t['cwe']+'_eligible']+=t['reward_eligible']
    qualification_small=[{k:t[k] for k in ['task_id','cwe','previous_reward_eligible','reference_state','reward_eligible','exclusion_reasons','placeholder_paths','undeclared_setup_bindings']} for t in q['tasks']]
    csv_write(CURATED/'qualification.csv',qualification_small)
    task_rows=[]
    for r in all_rows.values():
        f=r.get('final',{})
        task_rows.append({'stage':r['stage'],'arm':r['arm'],'task_id':r['task_id'],'family_id':r['family_id'],
            'measured':f.get('measured',False),'F':f.get('functional') if f.get('measured') else None,
            'S':f.get('security') if f.get('measured') else None,'Joint':f.get('joint') if f.get('measured') else None,
            'attempts':len(r['attempts']), 'selected':sum(len(a['generation'].get('retrieved_cards',[])) for a in r['attempts']),
            'adopted':sum(len(a['generation'].get('cards',[])) for a in r['attempts']),
            'tokens':r['accounting']['total']['total_tokens'],'error':r.get('error_type',r.get('worker_error'))})
    csv_write(CURATED/'scores.csv',task_rows)
    result={'protocol':manifest['protocol'],'status':status,'P7_runs':len(all_rows),'maximum_P7_runs':manifest['maximum_P7_runs'],
        'qualified_Dgrow_tasks':manifest['N'],'probe_gate':gate,'round2_gate':round2,'stages':stages,
        'costs':{'P7':costs,'new_shared_initials':initial,'known_total':total,'historical_shared_initials_reused':read(OUT/'initial_reuse.json'),
                 'embedding_segments':rows(OUT/'embedding_segments.jsonl'),'currency_paid':None},
        'qualification':{'former43_recovered':q['former_excluded_recovered'],'former43_remaining':43-len(q['former_excluded_recovered']),
            'newly_disqualified_old_tasks':len(newly_bad),'old_bank_updates_from_newly_disqualified_tasks':len(affected),
            'old_bank_affected_cards':len({e['invariant_id'] for e in affected}),
            'old_bank_cards_supported_only_by_newly_disqualified_tasks':sum(v<=newly_bad for v in card_support.values())},
        'D_gate_runs':0,'Base_Plus_runs':0,'old_results_modified':False,
        'whole_CLE_training':False,'scope':'fixed-card D_grow Q observation only',
        'targets':manifest['coverage_targets']}
    write(CURATED/'summary.json',result)
    lines=['# CLE Q覆盖学习与43题奖励资格复核结果','',
        f'协议：{manifest["protocol"]}。状态：{status}。已保存{len(all_rows)}次新P7，D_gate运行0次；旧成绩、原题和原Q库保持不变。','',
        '## 奖励资格复核','',
        f'先复核43道旧排除题，再在同一环境预检全部273道拟学习任务。补齐原镜像/任务已要求的requests、idna、sympy等实际缺失依赖后，1391恢复资格；其余42题继续禁止奖励。当前允许学习{manifest["N"]}题，77题在清单中保留但跳过。',
        'CWE601的8题、CWE918的24题仍全部不合格。主要问题是测试夹具中的URL被替换成<LOCAL_PATH>，参考实现正常功能测试也失败；部分题同时缺少公开外部绑定名称。没有猜测恢复URL、修改隐藏测试、把答案常量补给模型或为了覆盖率放行。',
        '1342虽参考Joint通过，但夹具仍有来源不可追溯的替换样本，按本轮保守资格规则继续排除；这不表示模型或参考实现已证明错误。108依赖补齐后仍有安全/公开绑定问题；1405依赖补齐后仍有夹具和公开绑定问题。',
        '资格检查增加了原项目reference_check已有的公开绑定核对：35道旧允许题这次发现未声明的运行变量，未纳入新学习；这是资格规格收紧，不将旧运行原地改写成同一协议。',
        f'当前起点M1仍保留历史Q：上述35题曾贡献{len(affected)}次有效历史更新，涉及{len({e["invariant_id"] for e in affected})}张卡，其中{sum(v<=newly_bad for v in card_support.values())}张只有这类题的反馈。本轮没有重算或清空它们，因此不能称新快照完全清除了历史契约问题；新奖励仅来自本轮合格题。','',
        '|原43题ID|CWE|当前参考状态|允许奖励|占位符字段|其他排除原因|',
        '|---|---:|---|---|---|---|']
    for t in q['tasks']:
        if not t['previous_reward_eligible']:
            lines.append(f'|{t["task_id"]}|{t["cwe"]}|{t["reference_state"]}|{t["reward_eligible"]}|{", ".join(t["placeholder_paths"])}|{", ".join(t["exclusion_reasons"])}|')
    lines += ['', 'A=功能与安全均通过，B=功能通过安全失败，C=功能失败安全通过，D=均失败；编译/环境错误仍按原evidence中的measured字段另记，不能由字母推断测量完整。','',
        '## 执行规格与锁定名单','',
        '起点为原1939卡、466张已学习的M1。L0原CLE候选顺序，L1仅将visits=0候选提前、各组按余弦降序；同一召回集全部呈现，原LLM每次至多选三张。Q数值不参与学习期排序。原P7复析、采用、规划、生成、本地验证、首次Joint早停/最多一次修复/末次交付均保留。',
        'deepseek-v3.2，temperature=0，thinking disabled，一般4096 Token、选择器256，text-embedding-3-large，δ=-1，α=0.3。每批访问计数冻结、批末按原清单和c0/c1顺序更新实际采用卡，Joint奖励+1，完整测量未联合通过−1；不采用或技术/工作流不完整不赋分。',
        '新12题在新模型输出前，仅用合格D_grow题的旧候选增量覆盖和不同family锁定：'+', '.join(manifest['probe'])+'。不同于上一轮12题提案之处来自资格变化；未按新成绩换题。',
        '历史有效初析复用；旧初析失败的题仅重新生成一次共享初析并单独计费。L0/L1采用同一个首次初析，同查询/候选/余弦核对，不将修复轮当独立样本。','',
        '## Q覆盖 采用 Joint与成本','',
        '|阶段|完成P7|完整测量|F|S|Joint|新增Q卡|当前Q卡|整库覆盖|固定1193候选覆盖|选入/采用次数|Token|',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name,s in stages.items():
        joint=f'{s["Joint"]}/{s["rows"]}' if s['measured'] else '未测量'
        lines.append(f'|{name}|{s["rows"]}|{s["measured"]}|{s["F"]}|{s["S"]}|{joint}|{s["new_cards"]}|{s["learned_cards"]}|{s["whole_bank_coverage"]:.2%}|{s["fixed_anchor_coverage"]:.2%}|{s["selected_occurrences"]}/{s["adopted_occurrences"]}|{s["cost"]["total_tokens"]:,}|')
    lines += ['', '各阶段快照与访问次数/独立反馈题族、正负Q分布见summary.json。L0是独立控制副本，不合并进L1；round1含已复用的L1探针，其Token不是额外发生的重复费用，实际新总量按唯一运行去重。','',
        '## 预设门与停止决定','', '探针门原样为：L1新增至少12张有效Q卡，比L0至少多6张；L1/L0 Token≤1.25；24次完成、共同候选成立、没有未解决技术问题。先2题两组通过技术检查才继续余下10题。',
        '实际门记录：`'+json.dumps(gate,ensure_ascii=False)+'`。',
        '通过探针才补齐第一轮N题；达到970张整库Q卡及固定1193候选955张覆盖即停止。未达目标时，第一轮新增至少30张且技术问题清零才开第二轮；最多两轮，不自动扩大。',
        '未执行阶段不填写失败成绩；技术停止、覆盖探索未过门与Joint收益不成立是不同结论。覆盖增长也不能证明新Q能改善D_gate。本轮不做新的D_gate或Base/Plus。','',
        '## 用量与产物','',
        f'已知新LLM逻辑调用{total["calls"]}次，Token {total["total_tokens"]:,}（其中新共享初析{initial["total_tokens"]:,}）；用量缺失{total["usage_missing"]}次。Embedding分段单列于精简summary，未报告货币实付金额。历史复用初析不重复计为新调用。',
        '逐题原生记录、任务先落盘副本、资格证据、每臂Q事件和冻结快照：translation_work/diagnostics/20261019/cle_memory_q/coverage_learning_v1/。',
        '精简结果与逐题分数：results/curated/cle_q_coverage_learning_20261019/summary.json、scores.csv、qualification.csv。',
        '复核入口：configs/cle_q_coverage_learning_20261019/qualification.py；执行入口：python -X utf8 -m methods.cle_ablation.run_memory_q_coverage run --workers 6；报告入口：python -X utf8 configs/cle_q_coverage_learning_20261019/report.py --finalize。已有完成记录不会再次调用模型；源/输入变动时停止，不能改旧元数据绕过。']
    text='\n'.join(lines)+'\n'
    (ROOT/'docs/CLE_Q覆盖学习记录器停止_v1_20261019.md').write_text(text,encoding='utf-8')
    (OUT/'report.md').write_text(text,encoding='utf-8')
    if args.finalize:
        assert status!='running','cannot_finalize_active_or_incomplete_study'
        meta['status']=status;meta['new_P7_runs']=len(all_rows);meta['new_initials']=len(rows(OUT/'new_shared_initial.jsonl'))
        meta['decision']={'continue_learning':False,'D_gate':False,'Base_Plus':False,'reason':status}
        write(OUT/'run_metadata.json',meta)
    print(json.dumps({'status':status,'P7_runs':len(all_rows),'stages':{k:{x:v[x] for x in ['rows','new_cards','learned_cards','Joint']} for k,v in stages.items()},'cost':total},ensure_ascii=False))


if __name__=='__main__':main()
