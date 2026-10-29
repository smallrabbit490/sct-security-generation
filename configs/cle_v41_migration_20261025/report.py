"""零API汇总S1原生记录、声明采用和真实用量；不把声明采用当作代码落实。"""
import json
from collections import Counter
from pathlib import Path
from .run import ROOT, RUN, read, summarize
from .resume import usage_from_bytes
from methods.sct_trajectory.replay_journal import write_json


def report(run=RUN):
    parts=[run]+([Path(p) for p in read(run/'recovery_segments.json')] if (run/'recovery_segments.json').exists() else [])
    result=summarize(run)
    rows=[read(p) for base in parts for p in sorted((base/'task_rows').glob('*.json'))]
    result['state']=read(parts[-1]/'state.json')
    result['prior_states']=[read(base/'state.json') for base in parts[:-1]]
    result['protocols']=[read(base/'protocol.json') for base in parts]
    result['technical_gate']=read(run/'technical_gate.json') if (run/'technical_gate.json').exists() else {'status':'pending'}
    result['replay']=read(run/f'replay_results/completed_{len(rows)}/summary.json') if (run/f'replay_results/completed_{len(rows)}/summary.json').exists() else None
    complete_ids={r['cell_id'] for r in rows}
    result['partial_cells']=[{'cell_id':p.name,'saved_requests':len(list((p/'requests').glob('*.json'))),'source':str(p)}
        for base in parts for p in (base/'journals').iterdir() if p.is_dir() and not p.name.startswith('embedding')
        and not p.name.startswith('shared_') and p.name not in complete_ids
        and list((p/'requests').glob('*.json'))]
    result['cost']['wire_error_types']=dict(Counter(read(p).get('reason_type') or read(p).get('error_type')
        for base in parts for p in (base/'wire').glob('*.status.json') if read(p).get('status')!='response_closed'))
    result['cost']['logical_buckets']={}
    physical_usage={}
    for base in parts:
        for path in (base/'wire').glob('*.request.json'):
            model=read(path)['body']['model']
            raw=path.with_name(path.name.replace('.request.json','.response.raw'))
            u=usage_from_bytes(raw.read_bytes(),model) if raw.exists() else None
            if isinstance(u,dict):
                totals=physical_usage.setdefault(model,Counter())
                totals.update({k:int(u.get(k) or 0) for k in ('prompt_tokens','completion_tokens','total_tokens')})
    result['cost']['physical_usage_by_model']={k:dict(v) for k,v in physical_usage.items()}
    for bucket in ('shared','E0','E1','embedding'):
        usage=Counter();statuses=Counter();count=0
        for p in (p for base in parts for p in (base/'journals').glob('*/requests/*.json')):
            identity=p.parents[1].name
            match=(identity.startswith('shared_') if bucket=='shared' else
                   identity.startswith('embedding') if bucket=='embedding' else identity.endswith('_'+bucket))
            if not match:continue
            d=read(p);count+=1;statuses[d['status']]+=1
            u=(d.get('response') or {}).get('usage') or {}
            for k in ('prompt_tokens','completion_tokens','total_tokens'):
                usage[k]+=int(u.get(k) or 0)
        result['cost']['logical_buckets'][bucket]={'logical_requests':count,'statuses':dict(statuses),'known_usage':dict(usage)}
    embed_bucket=result['cost']['logical_buckets']['embedding']
    embed_bucket['physical_usage']=dict(physical_usage.get('text-embedding-3-large',{}))
    embed_bucket['usage_basis']='physical response authoritative; original shared-client delta counters retained for diagnosis'
    a,b=result['arms']['E0'],result['arms']['E1']
    complete=len(rows)==48
    quantitative=(complete and all(x['final']['measured']==24 and x['technical_errors']==0 for x in (a,b))
        and b['final']['joint']-a['final']['joint']>=2
        and all(x>=0 for x in result['net_joint_by_repeat'].values())
        and all(b['final'][k]>=a['final'][k] for k in ('functional','security')))
    result['development_gate']={'quantitative_passed':quantitative if complete else None,
        'mechanism_review':'pending_actual_code_review','passed':False,
        'reason':'requires complete scores plus >=2 family rescue paths with selected/adopted/implemented evidence'}
    revised=(complete and all(x['final']['measured']==24 for x in (a,b))
        and result['state']['status']=='completed'
        and b['final']['joint']-a['final']['joint']>=2
        and all(x>=0 for x in result['net_joint_by_repeat'].values())
        and all(b['final'][k]>=a['final'][k] for k in ('functional','security')))
    result['v2_development_gate']={'quantitative_passed':revised if complete else None,
        'mechanism_review_required':'at least2 distinct family selected-adopted-implemented rescues',
        'passed':False,'model_degradations_counted':sum(x['technical_errors'] for x in (a,b)),
        'original_strict_gate_not_relabelled':True}
    curated=ROOT/'results/curated/cle_v41_migration_20261025'
    write_json(curated/'summary.json',result)
    metadata={**read(run/'protocol.json'),'protocol_versions':result['protocols'],'state':result['state'],'input_manifest':read(run/'input_manifest.json'),
              'source_bundle':str(run/'source_bundle'),'task_rows':str(run/'task_rows'),
              'rows_schema':'native run_one(P7) plus migration_arm/repeat/family_id/cell_id/protocol/Q_updates'}
    write_json(run/'run_metadata.json',metadata)
    mechanism=[]
    for r in rows:
        for i,a0 in enumerate(r['attempts']):
            g=a0.get('generation',{})
            mechanism.append({'task_id':r['task_id'],'family_id':r['family_id'],'repeat':r['repeat'],
                'arm':r['migration_arm'],'attempt':i,
                'selected_ids':[c['invariant_id'] for c in g.get('retrieved_cards',[])],
                'adopted_ids':[c['invariant_id'] for c in g.get('cards',[])],
                'adoption':g.get('adoption'), 'analysis':g.get('experience_analysis'),
                'code':a0.get('code'),'functional':a0.get('functional'),
                'security':a0.get('security'),'joint':a0.get('joint'),
                'implementation_review':None})
    write_json(run/'mechanism_review.json',mechanism)
    lines=['# v4.1 Flash 1017：原P7空卡与1939卡迁移实验', '',
        f"状态：{result['state']['status']}；完成{len(rows)}/48次P7。两题8次技术检查计入总数。",'',
        'E0与E1均为原P7，保留复析、规划、一次修复、PLT首次Joint早停及末次交付；只改变是否提供经验。',
        '每题每重复共享一次新模型首次初析。E1使用旧v3.2来源1939卡，原LLM终选最多3张，Q不排序、不更新，不生成新卡。','',
        '| 臂 | 完成/计划 | 首次Joint | 最终F | 最终S | 最终Joint | 最终完整测量 | 有声明采用的运行 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm in ('E0','E1'):
        s=result['arms'][arm]
        lines.append(f"| {arm} | {s['completed']}/24 | {s['first']['joint']} | {s['final']['functional']} | {s['final']['security']} | {s['final']['joint']} | {s['final']['measured']} | {s['rows_with_adoption']} |")
    lines+=['',f"技术门：{result['technical_gate']['status']}。重复内Joint净差：{json.dumps(result['net_joint_by_repeat'],ensure_ascii=False)}。",
        f"原v1严格门：{result['development_gate']['quantitative_passed']}；v2数量门：{result['v2_development_gate']['quantitative_passed']}。代码落实机制证据另行逐题核对。",'',
        '| 任务 | 重复 | E0 Joint | E1 Joint | 两臂完整测量 |', '|---|---:|---:|---:|---|']
    for item in result['paired']:
        lines.append(f"| {item['task_id']} | {item['repeat']} | {int(item['E0_joint'])} | {int(item['E1_joint'])} | {item['both_measured']} |")
    c=result['cost']
    lines+=['',f"记录的传输尝试：{c['physical_HTTP']}；有用量响应：{c['HTTP_with_usage']}；未知用量尝试：{c['unknown_usage_HTTP']}。错误可能发生在实际HTTP前，不将全部尝试断言为服务端已执行。",
        f"已知Token：{json.dumps(c['known_usage'],ensure_ascii=False)}。没有本模型账单单价，人民币实付未测量。",'',
        '| 成本类别 | 逻辑请求 | 输入Token | 输出Token | 总Token |','|---|---:|---:|---:|---:|']
    for key,v in c['logical_buckets'].items():
        u=v['physical_usage'] if key=='embedding' else v['known_usage']
        lines.append(f"| {key} | {v['logical_requests']} | {u.get('prompt_tokens',0)} | {u.get('completion_tokens',0)} | {u.get('total_tokens',0)} |")
    lines+=['','共享初析和Embedding单列；逻辑响应Token与物理HTTP尝试分别统计。未知用量不记作免费。',
        f"原始HTTP尝试错误：{json.dumps(result['cost']['wire_error_types'],ensure_ascii=False)}。原生客户端重试后逻辑请求均获得响应；历史错误保留，不以成功重试抹除。",
        '预算账本是派发前按UTF-8字节估计的保守预留，不是Token实付账单；费用采用原始响应usage。',
        f"Embedding原逻辑日志按共享客户端累计差值记账，共{embed_bucket['known_usage'].get('total_tokens',0)} Token；并发时该差值会重复包含其他调用。成本表采用原始物理响应的{embed_bucket['physical_usage'].get('total_tokens',0)} Token，原日志保留。",
        '实际采纳包含“检索选入”和“复析声明采用”两层；代码落实需查看mechanism_review.json中的建议、代码和验证结果。',
        '本批是历史暴露开发题的热迁移筛查；两重复不是24个独立题族。未启动Q学习、分类器、24题验证、全量D_gate、Base/Plus。','',
        f'完整原始记录：{run}。精确请求/响应在journals与wire，原生attempts、generation、validation、retrieval_trace保存在task_rows/rows.jsonl，源码在source_bundle。',
        '已交付行的零API回放入口：python -B -X utf8 configs/cle_v41_migration_20261025/replay_saved.py；仅回放已交付行，不生成缺失响应；已有输出不覆盖。',
        f"本次回放：{json.dumps(result['replay'],ensure_ascii=False)}。",
        f"另有仅保存部分阶段响应、未交付整行的格：{json.dumps(result['partial_cells'],ensure_ascii=False)}；它们的请求成本计入总成本，不计为已完成P7，也不记0分。"]
    if result['state']['status']=='stopped_technical':
        lines+=['','## 停止原因与结论', '',
            '335_r1_E0修复轮复析返回3595字符，finish_reason=stop。JSON外层在字符2901提前闭合，随后追加applied_experience_ids等字段；原解析器报JSONDecodeError: Extra data。',
            '这是模型结构化输出格式错误，发生在空卡组，不能归因于1939卡、Q或Token截断。原P7按既有规则以初析降级继续，代码和验证均已保存；外层实验按已批准的技术错误停止条件终止后续派发。',
            '已完成15/48：E0为8次、E1为7次，两个分母不同，不直接相减50%与57.14%。共同完成的7个同题同重复配对，Joint均相同：两臂各4/7。尚不能判断完整12题热迁移收益。',
            'E1在7次已交付运行中6次声明采用，累计选入28张次、采用19张次；没有观察到配对Joint救回，不能把这些采用次数当作提分证据。',
            '零API回放15行一致，除选择器实际耗时这一不可重演字段外逐字段比较。原1939库和运行快照未变，旧实验不重写。',
            '另有4次PermissionError及1次TLS错误。原wire只记录错误类别，不能逐次确认PermissionError发生位置；代码中存在共享.tmp并发写入隐患，已在当前源码串行化预算文件写入，未改本次封存源码或重跑付费。5次错误继续保守列为未知用量尝试，未证明免费。',
            '后续最小修订应单列协议：对本次复析原响应做严格单对象解析修复的离线验证，保持所有旧得分；若继续运行，复用已完成格与精确阶段响应，不重付已完成请求。当前停在原方案门槛，不启动其他实验。']
    if len(parts)>1:
        reuse=read(parts[-1]/'reused_requests.json') if (parts[-1]/'reused_requests.json').exists() else []
        result['reused_request_count']=len(reuse)
        lines+=['','## v2续段与结论','',
            '用户授权更新停止规则后继续。v1原15行、335题非法JSON及成绩保持原样；v2只变更外层中止分类、断点恢复和预算记账设施。P7、提示词、解析器、最多三卡、一次修复、验证器及模型均来自原source_bundle。',
            'v2将模型JSON/选卡/代码输出降级交给原P7处理并计入结果；未决请求、环境故障、模型不符和预算耗尽仍停止。不把原v1严格门改写为通过。',
            f"精确阶段响应已复用{len(reuse)}次，原15次P7整行跳过；两个旧部分格从精确前缀续接，未重发旧请求。",
            '预算上限仍为800万Token、2000次HTTP尝试、200次Embedding；已知usage结算预留，在途/未知仍占保守额度，历史5次未知量保留。并发预算写入已串行化。',
            f"当前完成{len(rows)}/48，E1−E0最终Joint净差{b['final']['joint']-a['final']['joint']}，各重复净差{json.dumps(result['net_joint_by_repeat'])}。",
            '两臂的“实际采用”统计是模型声明采用；代码落实与救回机制单独核对。',
            '原v1中止报告封存在recovery_20261025_001/prior_report_v1.md；本报告为合并后的当前状态。']
        write_json(curated/'summary.json',result)
    if complete:
        both=[p for p in result['paired'] if p['both_measured']]
        cases=[p for p in result['paired'] if p['delta']]
        analysis={'completed_P7':48,'end_to_end_Joint':{'E0':a['final']['joint'],'E1':b['final']['joint'],'denominator_each':24},
            'paired_complete_measurements':len(both),'paired_measured_joint':
                {'E0':sum(p['E0_joint'] for p in both),'E1':sum(p['E1_joint'] for p in both)},
            'changed_pairs':cases,'native_degraded_runs':{'E0':a['technical_errors'],'E1':b['technical_errors']},
            'mechanism_gate_passed':False,'decision':'stop_S1_no_validation24_no_Q_learning',
            'reason':'only one apparent rescue; baseline code truncated/unmeasured; second repeat both pass; <2 net rescues and <2 families',
            'one_case_review':{'task_id':'1343','repeat':1,'E0':'planning invalid JSON, generation finish_reason=length, no executable final code',
                'E1_adopted_ids':['seed-842','seed-831'],'E1_implementation':'restricted tokenizer/parser, whitelisted operator functions, no eval/exec',
                'E1_validation':'F and S pass','repeat2':'both E0 and E1 Joint pass',
                'claim':'implemented adopted parser advice; isolated truncation-sensitive rescue, no established broad benefit'}}
        write_json(curated/'analysis.json',analysis)
        result['analysis']=analysis
        write_json(curated/'summary.json',result)
        lines+=['','## 完整结果与后续决策','',
            f"48/48次已执行，两个重复的Joint分别为E0：3/12、4/12；E1：4/12、4/12。最终E0为7/24（29.17%），E1为8/24（33.33%），差4.17个百分点。",
            'E0有1次代码截断缺测，完整测量23/24；E1完整测量24/24。共同可测23个配对中，Joint两臂均为7/23，没有净变化。端到端通过数与完整测量分母同时保留。',
            '唯一变化是1343第一次重复：E0规划JSON错误后代码输出达到4096预算而截断；E1采用seed-842与seed-831，代码落实了受限词法/语法解析器和静态操作符白名单，F/S均通过。第二次重复两臂均通过。此例支持经验被采用并正确实现，不足以证明稳定提分。',
            f"带卡组21/24次运行声明采用经验（87.5%），两轮尝试累计选入113张次、采用72张次。E0/E1各生成尝试40次；阶段降级分别3/24与4/24，均保留原始成绩。",
            '排除共享初析与Embedding，E1模型逻辑用量1,577,287 Token，E0为404,357 Token，约3.90倍。成本较高，当前增益集中于一个截断案例。',
            '决策：本批完成后收口，不启动24题验证、全量D_gate、Q学习、分类器或Base/Plus。净增1次未达到至少2次，且只有1个题族，存在缺测；v1严格门与v2修订门均未通过。结论为“旧1939卡热迁移的稳定收益尚未建立”，不是证明记忆普遍无效。',
            '若后续另行设计，只针对1343的输出长度/规划格式问题做小范围等预算复核；不凭本轮扩大卡库、Q学习或总生成预算。']
    path=ROOT/'docs/CLE_v41Flash1017_P7空卡与1939卡迁移实验报告_20261025.md'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return {'report':str(path),'completed_P7':len(rows),'state':result['state'],'summary':str(curated/'summary.json')}


if __name__=='__main__':print(json.dumps(report(),ensure_ascii=False))
