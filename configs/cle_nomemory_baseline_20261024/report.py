"""只读原生P3结果与逐次HTTP证据，复算三集指标和真实已知Token。"""
import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def summarize(run):
    protocol=read(run/'protocol.json');state=read(run/'state.json')
    segments=[Path(p) for p in read(run/'recovery_segments.json')] if (run/'recovery_segments.json').exists() else []
    result={'protocol':protocol['protocol'],'model':protocol['model'],
        'checked_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'state':state,'datasets':{},'misstarted_training_and_control_costs_excluded':True}
    for stage,planned in protocol['counts'].items():
        native=run/f'source_bundle/translation_work/nomemory/{stage}/rows.jsonl'
        paths=[native,*[segment/f'native/{stage}/rows.jsonl' for segment in segments]]
        rows=[json.loads(line) for path in paths if path.exists()
              for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        assert len({r['task_id'] for r in rows})==len(rows)
        metrics={}
        for name,position in [('first',0),('final',-1)]:
            a=[r['attempts'][position] for r in rows if r.get('attempts')]
            metrics[name]={k:sum(bool(x.get('measured')) and bool(x.get(k)) for x in a)
                           for k in ('functional','security','joint')}
            metrics[name]['measured']=sum(bool(x.get('measured')) for x in a)
            metrics[name]['joint_rate_completed']=(metrics[name]['joint']/len(rows)) if rows else None
            metrics[name]['joint_rate_planned']=metrics[name]['joint']/planned if len(rows)==planned else None
        generation_cards=sum(len(a.get('generation',{}).get('cards') or []) for r in rows for a in r['attempts'])
        stages=Counter(s.get('stage')+':'+s.get('status') for r in rows for a in r['attempts']
                       for s in a.get('generation',{}).get('stages',[]))
        usage=Counter();physical=0;with_usage=0;models=Counter();settings_ok=True;statuses=Counter()
        wire_files=[p for base in [run,*segments] for p in (base/'wire'/stage).glob('*.request.json')]
        for f in wire_files:
            physical+=1;d=read(f);body=d['body']
            models[body.get('model')]+=1
            settings_ok &= (body.get('model')==protocol['model'] and body.get('temperature')==0
                and body.get('thinking')=={'type':'disabled'} and body.get('max_tokens')==4096
                and [m['role'] for m in body.get('messages',[])]==['user'])
            raw=f.with_name(f.name.replace('.request.json','.response.raw'))
            final_usage=None
            if raw.exists():
                for line in raw.read_bytes().splitlines():
                    if not line.startswith(b'data:'):continue
                    try:item=json.loads(line[5:].strip())
                    except (ValueError,UnicodeDecodeError):continue
                    if isinstance(item.get('usage'),dict):final_usage=item['usage']
            if final_usage is not None:
                with_usage+=1
                for k in ('prompt_tokens','completion_tokens','total_tokens'):usage[k]+=final_usage.get(k,0)
                usage['cached_tokens']+=(final_usage.get('prompt_tokens_details') or {}).get('cached_tokens',0)
                usage['reasoning_tokens']+=(final_usage.get('completion_tokens_details') or {}).get('reasoning_tokens',0)
        requests=[p for base in [run,*segments] for p in (base/'journals'/stage/'requests').glob('*.json')]
        for p in requests:statuses[read(p)['status']]+=1
        errors=Counter(a.get('error_type') for r in rows for a in r['attempts'] if a.get('error_type'))
        result['datasets'][stage]={'planned':planned,'completed':len(rows),'metrics':metrics,
            'generated_cards_used':generation_cards,'stage_statuses':dict(stages),'errors':dict(errors),
            'logical_requests':len(requests),'logical_statuses':dict(statuses),'physical_HTTP_attempts':physical,
            'attempts_with_usage':with_usage,'attempts_without_usage':physical-with_usage,
            'known_usage':dict(usage),'requested_models':dict(models),'wire_settings_match':bool(settings_ok),
            'embedding_requests':len(list((run/'journals'/stage/'embedding_requests').glob('*.json'))),
            'status':('completed' if len(rows)==planned else
                      'waiting_request_reconciliation' if rows and state.get('status')=='waiting_request_reconciliation' else
                      'incomplete_technical_stop' if rows and state.get('status')=='stopped_technical' else
                      'running' if rows else 'not_executed'),
            'actual_currency_cost':None}
        result['datasets'][stage]['row_sources']=[str(p) for p in paths if p.exists()]
    result['held_task_ids']=state.get('held_task_ids',[])
    result['recovery_segments']=[str(p) for p in segments]
    result['authorized_reissue_segments']=[str(p) for p in segments
        if read(p/'manifest.json').get('authorized_unresolved_requests')]
    if result['datasets']['PLT']['completed']==protocol['counts']['PLT']:
        p=result['datasets']['PLT']
        rows=[json.loads(line) for source in p['row_sources']
              for line in Path(source).read_text(encoding='utf-8').splitlines() if line.strip()]
        first=[r['attempts'][0] for r in rows];final=[r['attempts'][-1] for r in rows]
        p['attempt_counts']=dict(Counter(str(len(r['attempts'])) for r in rows))
        p['joint_rescued']=sum(not a.get('joint') and bool(b.get('joint')) for a,b in zip(first,final))
        p['joint_lost']=sum(bool(a.get('joint')) and not b.get('joint') for a,b in zip(first,final))
        p['final_quadrants']=dict(Counter('unmeasured' if not a.get('measured') else
            ('F1S1' if a.get('functional') and a.get('security') else
             'F1S0' if a.get('functional') else 'F0S1' if a.get('security') else 'F0S0') for a in final))
        p['unmeasured_task_ids']=[r['task_id'] for r in rows if not r['attempts'][-1].get('measured')]
        p['generation_stage_statuses']=dict(Counter(s.get('stage')+':'+s.get('status')
            for r in rows for a in r['attempts'] for s in a.get('generation',{}).get('stages',[])))
        p['degraded_task_ids']=[r['task_id'] for r in rows if any(
            s.get('status') in ('degraded','failed') for a in r['attempts']
            for s in a.get('generation',{}).get('stages',[]))]
        p['workflow_completed_attempts']=sum(bool(a.get('generation',{}).get('workflow_completed'))
            for r in rows for a in r['attempts'])
        p['segment_costs']=[]
        for name,base in [('original_43',run),*[(x.name,x) for x in segments]]:
            usage=Counter();http=known=0;response_models=Counter()
            requests=list((base/'journals/PLT/requests').glob('*.json'))
            for f in (base/'wire/PLT').glob('*.request.json'):
                http+=1
                raw=f.with_name(f.name.replace('.request.json','.response.raw'));u=None
                if raw.exists():
                    for line in raw.read_bytes().splitlines():
                        if not line.startswith(b'data:'):continue
                        try:item=json.loads(line[5:].strip())
                        except (ValueError,UnicodeDecodeError):continue
                        if isinstance(item.get('usage'),dict):u=item['usage']
                if u is not None:
                    known+=1
                    for k in ('prompt_tokens','completion_tokens','total_tokens'):usage[k]+=u.get(k,0)
            for f in requests:
                d=read(f)
                if d['status']=='completed':response_models[d['response'].get('model')]+=1
            result_file=base/'result.json'
            p['segment_costs'].append({'segment':name,'physical_HTTP_attempts':http,
                'with_usage':known,'unknown_usage':http-known,'known_usage':dict(usage),
                'reported_models':dict(response_models),
                'replayed_requests':read(result_file).get('replayed_requests',0) if result_file.exists() else 0})
        task_by_id={str(t['index']):t for t in read(run/'inputs/tasks_PLT.json')}
        cwes={}
        for r in rows:
            cwe=str(task_by_id[r['task_id']].get('CWE_ID','unknown'));c=cwes.setdefault(cwe,Counter())
            a=r['attempts'][-1];c['total']+=1;c['measured']+=bool(a.get('measured'))
            for k in ('functional','security','joint'):c[k]+=bool(a.get('measured')) and bool(a.get(k))
        p['CWE_results']={k:dict(v) for k,v in sorted(cwes.items())}
        p['authorized_supplement_rows']=[]
        for segment in segments:
            if not read(segment/'manifest.json').get('authorized_unresolved_requests'):continue
            for line in (segment/'native/PLT/rows.jsonl').read_text(encoding='utf-8').splitlines():
                r=json.loads(line);a=r['attempts'][-1]
                p['authorized_supplement_rows'].append({'task_id':r['task_id'],'attempts':len(r['attempts']),
                    **{k:a.get(k) for k in ('functional','security','joint','measured')}})
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-root',type=Path,required=True)
    parser.add_argument('--curated',type=Path);parser.add_argument('--report',type=Path)
    args=parser.parse_args();run=args.run_root.resolve();d=summarize(run)
    for out in [run/'progress_summary.json',args.curated]:
        if out:out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.report:
        lines=['# CLE新模型P3无经验Agent基准结果','',f"模型：`{d['model']}`。更新：{d['checked_at']}。状态：{d['state']['status']}。",'',
            '| 集合 | 完成/计划 | 首次F/S/Joint | 最终F/S/Joint | 最终可测 | 最终Joint率 |',
            '|---|---:|---|---|---:|---:|']
        for stage,v in d['datasets'].items():
            a=v['metrics']['first'];b=v['metrics']['final'];rate=b['joint_rate_planned']
            lines.append(f"| {stage} | {v['completed']}/{v['planned']} | {a['functional']}/{a['security']}/{a['joint']} | {b['functional']}/{b['security']}/{b['joint']} | {b['measured']} | {format(rate,'.2%') if rate is not None else '未完成，不填全量率'} |")
        lines+=['','未完成集合的0个通过不是0%成绩。PLT为历史D_gate开发题；Base/Plus为Python，原Docker验证环境与参考校准必需。',
            '本轮直接复用P3的初析、规划、生成及最多一次修订；无经验卡输入、经验生成、Embedding或Q学习。PLT允许原任务内F/S反馈；Base/Plus固定两次前向且隐藏反馈关闭。',
            '逐次提示/响应、HTTP字节、代码和原验证事件保留在运行根；source_bundle为P3方法和验证器实际执行源码，恢复段tools仅修复传输与断点记录。费用未知，Token不等于实付账单。',
            '误启动的经验学习154685已知Token和加法控制41 Token单独归档，不并入该基准。历史模型/协议不同，不作单变量提分归因。',
            '',f'运行根：`{run}`。','详细成本与阶段状态见同名精简JSON及运行根progress_summary.json。']
        if d.get('recovery_segments'):
            lines+=['','## TLS修复与断点处理','',
                '本机显式代理127.0.0.1:7897路径重复出现SSLEOFError；同一org接入点绕过显式代理后正常返回HTTP。仅在本次模型传输使用空ProxyHandler，保持默认TLS证书、主机名验证和原请求正文。已收到的续段模型响应及实际参数见wire记录。',
                '原source_bundle、43题rows和旧请求记录均保留。新续段仅改变传输与恢复编排，使用封存P3和原验证器；恢复相关离线测试通过。续段保存独立原生rows、逐次提示/响应和验证事件，报告按唯一task_id合并，不重写旧成绩。',
                '原478条逻辑记录中，223条有完成响应，247条只被熔断拒绝且没有HTTP，8条存在真实失败HTTP。8条对应20次失败物理尝试；另3次早期失败后来得到完整响应，共23次未知usage，不能记为免费或零Token。',
                ('安全续段247题已完成。2026-10-25用户随后明确授权直接按原规则补跑剩余8题，保留原失败记录及未知用量；该授权仅解除这8条请求的历史未决阻塞，不改变模型或P3方法，也不表示历史费用已查明。' if d['authorized_reissue_segments'] else
                 '可安全继续的247题已派发；8题待请求及扣费核对，不能把本次续段完成后的290题写成298题全量完成。'),
                '', '当前隔离等待题号：'+ ('、'.join(d.get('held_task_ids',[])) or '无')+'。',
                '未决请求集中在2026-10-24 22:10–22:11（北京时间）。历史客户端只保留URLError类别，缺少可证明这些请求未计费的底层证据。当前网络修复不能反证历史请求未执行。',
                '此前曾尝试只读查询服务端用量：旧文档的查询接口返回404；官网免登录查询返回40300，说明该Key属于登录账号，要求登录用户后台查看用量，当时浏览器未登录。查询没有发送模型生成任务，也没有输出密钥；历史费用继续标为未知。',
                '保留恢复依据：tls_diagnosis_20261025.json、provider_reconciliation_query_20261025.json、recovery_20261025_001/manifest.json、previous_state.json和recovery_segments.json。',
                'Base/Plus保持未执行，等待原safecoder-python-validator:local及其父镜像补齐；旧误启动训练和Q实验均不恢复。',
                '', '## 零API回放','',
                '全部已交付题可执行以下命令，读取旧段和续段的精确保存响应，重新运行原生P3与本地验证；缺响应立即停止，不派发API：','',
                '```powershell',
                'python -B -X utf8 -m configs.cle_nomemory_baseline_20261024.resume_plt replay --run-root translation_work/baseline_runs/cle_P3_nomemory_v41flash1017_20261024',
                '```',
                '已有原43题回放差异为零。续段全部完成后再做合并回放，结果保存于replay_results/combined_<题数>/summary.json；执行前不声称合并回放通过。']
            replay=run/f"replay_results/combined_{d['datasets']['PLT']['completed']}/summary.json"
            if replay.exists():
                checked=read(replay)
                lines[-1]=(f"合并回放已完成{checked['tasks']}题：API调用{checked['API_calls']}，凭据读取{checked['credential_reads']}，"
                           f"代码和F/S/Joint差异题号为{checked['differences']}。原43题与续段结果均可由保存响应复现。")
            if d['state']['status']=='waiting_request_reconciliation':
                p=d['datasets']['PLT'];m=p['metrics']['final'];u=p['known_usage']
                lines+=['','## 本次续段收口','',
                    f"安全续段247题已完成，无新增逻辑请求失败；原43题未重新调用。合计交付{p['completed']}/298题，完整测量{m['measured']}题，最终F/S/Joint为{m['functional']}/{m['security']}/{m['joint']}。已交付题Joint率为{m['joint_rate_completed']:.2%}，298题全量率仍未确定。",
                    f"累计物理HTTP尝试{p['physical_HTTP_attempts']}次，有usage的响应{p['attempts_with_usage']}次，缺usage的尝试{p['attempts_without_usage']}次；已知输入{u['prompt_tokens']}、输出{u['completion_tokens']}、合计{u['total_tokens']} Token，缓存{u['cached_tokens']}，推理{u['reasoning_tokens']}。没有账单证据，不换算实付费用。",
                    '续段另外保留5次TLS握手失败和2次HTTP 200流式读取失败；它们都按原客户端最多3次尝试规则得到后续完成响应，未被隐藏或当成免费请求。这7次与旧23次合计30次缺usage。',
                    '已交付集合包含1题输出截断导致未完整测量，保留原错误和分母，不按低成绩重跑。',
                    '当前没有生成进程。8题仍需登录后台核对2026-10-24 22:10–22:11的请求和扣费，确认未执行/未计费或取得原响应后才能补齐；Base/Plus原镜像继续缺失。']
        p=d['datasets']['PLT']
        if p['completed']==p['planned']:
            a=p['metrics']['first'];b=p['metrics']['final'];u=p['known_usage'];q=p['final_quadrants']
            lines+=['','## 全量PLT结果与解释','',
                f"298题全部交付，完整测量{b['measured']}题。首次Joint为{a['joint']}/298（{a['joint']/298:.2%}），最终Joint为{b['joint']}/298（{b['joint']/298:.2%}）；原P3修订净救回{p['joint_rescued']}题，损失{p['joint_lost']}题。首次Joint通过即停止，因此损失为零受早停规则约束。",
                f"最终功能通过{b['functional']}/298（{b['functional']/298:.2%}），安全通过{b['security']}/298（{b['security']/298:.2%}）。无法完整测量的题号：{p['unmeasured_task_ids']}；保留在298题分母中，不按低成绩重跑，也不把缺测解释成已经测得的错误。",
                '', '| 最终状态 | 题数 |','|---|---:|',
                *[f'| {label} | {q.get(key,0)} |' for key,label in [('F1S1','功能和安全都通过'),('F1S0','功能通过、安全失败'),('F0S1','功能失败、安全通过'),('F0S0','功能和安全都失败'),('unmeasured','未完整测量')]],
                '', '本轮是无经验P3换模基准，不能据此证明经验卡或Q的收益。功能失败而安全通过的数量显示功能契约与实现是后续值得逐题核对的重点；仅凭汇总不能断言错误来自模型、题面或测试夹具。',
                '', '## 调用与成本','',
                '| 输出段 | 物理HTTP | 有usage | 未知用量 | 输入Token | 输出Token | 已知总Token | 复用旧成功阶段 |',
                '|---|---:|---:|---:|---:|---:|---:|---:|',
                *[f"| {s['segment']} | {s['physical_HTTP_attempts']} | {s['with_usage']} | {s['unknown_usage']} | {s['known_usage'].get('prompt_tokens',0)} | {s['known_usage'].get('completion_tokens',0)} | {s['known_usage'].get('total_tokens',0)} | {s['replayed_requests']} |" for s in p['segment_costs']],
                '', f"累计已知输入{u['prompt_tokens']}、输出{u['completion_tokens']}、总计{u['total_tokens']} Token，其中缓存{u['cached_tokens']}、推理{u['reasoning_tokens']}。物理HTTP共{p['physical_HTTP_attempts']}次，{p['attempts_without_usage']}次缺usage；未知不能算零，也不能将Token估算称为实付费用。",
                '按实际HTTP响应计费记录汇总，复用旧成功响应不再累加Token；原失败、原生HTTP重试、未完成流式响应均保留。旧熔断拒绝247条没有HTTP，单独保留而不冒充付费调用。误启动训练与加法控制费用不混入。',
                '', '## CWE分层结果','', '| CWE | 题数 | 完整测量 | F | S | Joint |','|---|---:|---:|---:|---:|---:|',
                *[f"| {cwe} | {v['total']} | {v['measured']} | {v['functional']} | {v['security']} | {v['joint']} |" for cwe,v in p['CWE_results'].items()],
                '', '## 交付与边界','',
                f"单次代码尝试题数：{p['attempt_counts'].get('1',0)}；两次代码尝试题数：{p['attempt_counts'].get('2',0)}。阶段完成与降级统计、逐题代码和最终结果保留在JSON与原生产物，解析降级不被隐去。",
                f"初析降级{p['generation_stage_statuses'].get('initial_analysis:degraded',0)}次、规划降级{p['generation_stage_statuses'].get('planning:degraded',0)}次、生成失败{p['generation_stage_statuses'].get('generation:failed',0)}次，涉及{len(p['degraded_task_ids'])}题；workflow_completed为真的代码尝试为{p['workflow_completed_attempts']}/{sum(int(n)*count for n,count in p['attempt_counts'].items())}。这些属于原流水线保留的降级/模型输出现象，未重跑或改提示掩盖。完整测量与流水线完整完成是两个不同口径。",
                '统一298题原生产物位于final/PLT/，包含rows.jsonl、summary.json、报告和run_metadata.json；原43题及两次恢复段保留独立原件。精确请求/响应、HTTP字节、验证事件及source_bundle均保留，回放禁止网络和凭据读取。',
                '本轮严格无经验卡、无经验生成、无Embedding、无Q更新。模型报告名及实际请求参数逐次核对；方法和验证器来自封存源码。传输绕过显式代理和历史未决请求重发已披露，不能用这些结果直接作与不同历史协议的单变量因果比较。',
                'PLT的D_gate存在既往开发曝光，不等于整个CLE从未接触过的独立测试集。Base/Plus仍未执行，等待原镜像；本轮没有三集合并正确率。']
            lines+=['','## 本次补齐8题','',
                '本次复用13个已成功的旧阶段，新增35次HTTP调用，新增86947个已知Token；本次补齐没有新增未知用量。原失败和30次未知用量保留在总成本中。补齐8题均未Joint通过，因而Joint从96/290的部分结果变为96/298的全量结果，不能将分母扩展导致的比例变化解释成模型退化。',
                '', '| 题号 | 代码尝试 | F | S | Joint | 完整测量 |','|---|---:|---|---|---|---|',
                *[f"| {r['task_id']} | {r['attempts']} | {r['functional']} | {r['security']} | {r['joint']} | {r['measured']} |" for r in p['authorized_supplement_rows']]]
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:{'completed':v['completed'],'final_joint':v['metrics']['final']['joint'],
        'known_tokens':v['known_usage'].get('total_tokens',0)} for k,v in d['datasets'].items()}))


if __name__=='__main__':main()
