"""只读导入历史A7至新审阅格式；统计真实rows，不调用模型、不重测代码。"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from .artifacts import write_json, read_jsonl
from .blueprints import historical_graph, initial_graph, exploratory_graph
from .metrics import summarize

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT/'translation_work/diagnostics/20261013/mase_evolution'
HISTORY = ROOT/'translation_work/diagnostics/20261009/a7_exploration'
NAMES = {'protect':'接口保护后生成','check':'检查后修复','choose':'两候选再选择',
         'none':'无记忆','m1':'质量验证M1','m4':'分流程条件M4'}


def import_history(out=DEFAULT_OUT, source=HISTORY):
    """保存历史各阶段27版本及来源哈希；不补历史缺失的节点/提示词/中间分数。"""
    out, source = Path(out), Path(source)
    historical = out/'history-a7-20261009'
    manifest = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    write_json(historical/'run_metadata.json', {'run_id':historical.name,'label':'旧 A7 · 真实历史证据',
        'origin':'historical','status':'completed','model':'deepseek-v3.2','data_role':'已暴露的历史开发/确认数据',
        'recording_coverage':'阶段调用trace、候选与部分评分；无完整节点事件/逐次修复评分',
        'source':str(source.relative_to(ROOT)),'imported_at':datetime.now(timezone.utc).isoformat()})
    write_json(historical/'manifest.json', manifest)
    files, versions = [], []
    for phase, group in [('development','screen'),('confirmation','confirmation'),('regression','regression')]:
        path = source/phase/'rows.jsonl'
        rows, errors = read_jsonl(path)
        if errors:
            raise ValueError('history_recording_error:'+str(errors))
        files.append({'path':str(path.relative_to(ROOT)), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':len(rows)})
        for arm in sorted({r['arm'] for r in rows}):
            architecture, memory = arm.split('_')
            items = [r for r in rows if r['arm'] == arm]
            vid = phase+'_'+arm
            info = {'version_id':vid,'label':NAMES[architecture]+' + '+NAMES[memory], 'phase':phase,
                    'parent_id':None, 'status':'historical_completed','origin':'historical',
                    'changes':['历史手写流程，非模型自主结构搜索'], 'memory_version':memory,
                    'expected':len(manifest['groups'][group]),'source_path':str(path.relative_to(ROOT)),
                    'coverage_warnings':['没有完整每节点输入/输出事件','逐次修复官方评分未记录；仅首次与最终可比'],
                    'architecture_hash':hashlib.sha256(json.dumps(historical_graph(architecture,memory),sort_keys=True).encode()).hexdigest()}
            directory = historical/'versions'/vid
            write_json(directory/'version.json',info)
            write_json(directory/'architecture.json',historical_graph(architecture,memory))
            write_json(directory/'summary.json',summarize(items,expected=info['expected']))
            directory.mkdir(parents=True,exist_ok=True)
            (directory/'rows.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in items),encoding='utf-8')
            versions.append(info)
    for relative in ['source_quality_audit.json','inner_search/protect/history.json','inner_search/check/history.json','inner_search/choose/history.json']:
        path = source/relative
        if path.exists():
            files.append({'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    quality = json.loads((source/'source_quality_audit.json').read_text(encoding='utf-8'))
    histories = {a:json.loads((source/'inner_search'/a/'history.json').read_text(encoding='utf-8'))
                 for a in ('protect','check','choose')}
    write_json(historical/'audit.json',{'sources':files,'quality':quality,'inner_search':histories,
                                      'llm_calls_for_import':0,'versions':len(versions)})
    draft = out/'mase-design-20261013'
    write_json(draft/'run_metadata.json',{'run_id':draft.name,'label':'MASE · 新流程设计', 'origin':'design',
        'status':'design_review','data_role':'旧60题探索；冻结后另选未参与调参family确认',
        'recording_coverage':'设计草案，不含实验结果','llm_calls':0})
    for vid, label, structure, changes in [
        ('v000','起点：接口保护 + M1', initial_graph(),['新方法起点；可被设计员拆改']),
        ('v001','示例：分工生成 + 共享检查 + 选择', exploratory_graph(),['人工草案展示流程自由度；不是模型已生成或已验证结构'])]:
        directory = draft/'versions'/vid
        write_json(directory/'version.json',{'version_id':vid,'label':label,'phase':'design','status':'draft',
                    'origin':'design','parent_id':'v000' if vid=='v001' else None,'changes':changes,
                    'expected':60,'memory_version':'qualified_m1','coverage_warnings':['未执行，无新方法成绩']})
        write_json(directory/'architecture.json',structure)
    return {'out':str(out),'historical_versions':len(versions),'historical_rows':sum(f.get('rows',0) for f in files),'new_experiment_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    args=parser.parse_args()
    print(json.dumps(import_history(args.out),ensure_ascii=True))


if __name__=='__main__':
    main()
