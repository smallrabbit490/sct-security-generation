"""Resume Base/Plus evaluation from a frozen PLT memory directory."""
import argparse, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from run_plt_self_evolution import _client, _generate, _validate, BASE, PLUS

def main():
    p=argparse.ArgumentParser(); p.add_argument('run_dir'); p.add_argument('--model',default='deepseek-v4-flash'); p.add_argument('--timeout',type=float,default=40); p.add_argument('--workers',type=int,default=8); p.add_argument('--retries',type=int,default=1); a=p.parse_args()
    out=Path(a.run_dir); memory=[json.loads(x) for x in (out/'frozen/m_star.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]; client=_client()
    for name,path in [('Base',BASE),('Plus',PLUS)]:
        data=json.loads(path.read_text(encoding='utf-8'))
        def one(task):
            code,err,retries=_generate(client,task['Problem'],memory,a.model,a.timeout,a.retries)
            val=_validate(task,code) if code else {'passed':False}
            return {'subset':name,'task_id':task['ID'],'generated_code':code,'error':err,'retries':retries,'validation':val}
        with ThreadPoolExecutor(max_workers=a.workers) as pool: rows=list(pool.map(one,data))
        d=out/f'validation_runs/{name}'; d.mkdir(parents=True,exist_ok=True)
        (d/'rows.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf-8')
        summary={'total':len(rows),'passed':sum(bool(r['validation'].get('passed')) for r in rows),'generation_errors':sum(bool(r.get('error')) for r in rows),'empty_model_content':sum(r.get('error')=='empty_model_content' for r in rows)}
        (d/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    br=[json.loads(x) for x in (out/'validation_runs/Base/rows.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]; pr=[json.loads(x) for x in (out/'validation_runs/Plus/rows.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    report=f'''# PLT 自进化实验报告（多 CWE 选样）\n\n- 模型：`{a.model}`\n- PLT：96 条，覆盖 28 个 CWE\n- 分区：D_init/D_grow/D_gate=32/32/32\n- M0：32 条；候选经验：32 条；晋升：32 条；拒绝：0 条\n- Python Base：{len(br)} 条，Function+Secure 通过 {sum(bool(r["validation"].get("passed")) for r in br)} 条，生成错误 {sum(bool(r.get("error")) for r in br)} 条\n- Python Plus：{len(pr)} 条，Function+Secure 通过 {sum(bool(r["validation"].get("passed")) for r in pr)} 条，生成错误 {sum(bool(r.get("error")) for r in pr)} 条\n\n所有逐任务记录保存在 `validation_runs/*/rows.jsonl`。\n'''
    (out/'plt_self_evolution_report.md').write_text(report,encoding='utf-8'); print(out)
if __name__=='__main__': main()
