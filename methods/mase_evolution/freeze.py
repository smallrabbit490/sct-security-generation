"""确认前冻结文件哈希，验证变化即拒绝；该模块不学习、不抽取或评分确认任务。"""
import hashlib
from pathlib import Path
import json
import shutil
import platform
import sys
from datetime import datetime, timezone


def snapshot(paths):
    """冻结阶段输入必要文件→绝对路径/哈希；缺文件失败，无长期库修改。"""
    return {str(Path(p).resolve()):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}


def verify(frozen):
    """确认入口检查冻结文件仍相同；返回缺失/变化路径，不访问模型或回送反馈。"""
    return [p for p,h in frozen.items() if not Path(p).exists() or snapshot([p])[p]!=h]


def freeze_run(run_directory,version_id):
    """探索冻结：仅完整60题且可接纳版本→不可覆盖文件副本及哈希清单。

    核对运行时源码、来源、架构、记忆、公开检查和结果；缺测/安全待审拒绝。
    不运行模型、不抽确认集、不更新长期库；确认按用户选择明确暂缓。
    """
    from .artifacts import write_json,read_jsonl
    from .metrics import summarize
    import re
    if not re.fullmatch(r'v[0-9]{3,}',version_id):
        raise ValueError('invalid_version_id')
    run=Path(run_directory).resolve()
    output=run/'frozen_manifest.json'
    if output.exists():
        existing=json.loads(output.read_text(encoding='utf-8'))
        if existing['version_id']!=version_id or verify(existing['bundle_files']):
            raise ValueError('frozen_bundle_changed_or_different_version')
        return existing
    def read(path):
        return json.loads(path.read_text(encoding='utf-8'))
    if read(run/'run_metadata.json')['status']!='exploration_completed':
        raise ValueError('exploration_not_completed')
    directory=run/'versions'/version_id
    info=read(directory/'version.json')
    if info['status'] not in ('accepted','baseline_completed'):
        raise ValueError('version_not_eligible_for_freeze')
    tasks=read(run/'manifest.json')['tasks']
    rows,errors=read_jsonl(directory/'rows.jsonl')
    expected={(str(t['task_id']),t['family_id']) for t in tasks}
    actual={(str(r['task_id']),r['family_id']) for r in rows}
    summary=summarize(rows,60)
    if errors or len(tasks)!=60 or len(expected)!=60 or len({t['family_id'] for t in tasks})!=60 or actual!=expected or summary['measured']!=60:
        raise ValueError('freeze_requires_complete_measured_60')
    signature=read(run/'signature.json')
    if verify(signature['files']):
        raise ValueError('runtime_source_changed_cannot_freeze')
    paths=[Path(p) for p in signature['files']]
    paths.extend(p for p in run.glob('*.json') if p.name!='frozen_manifest.json')
    paths.extend((run/'public_checks').glob('*.json'))
    paths.extend(directory.glob('*.json'))
    paths.extend(directory.glob('*.jsonl'))
    paths=sorted(set(p.resolve() for p in paths))
    originals=snapshot(paths)
    bundle=run/'frozen_bundle'
    if bundle.exists():
        raise ValueError('partial_freeze_bundle_requires_audit')
    bundle.mkdir()
    mapping={}
    for i,path in enumerate(paths):
        destination=bundle/(str(i).zfill(4)+'_'+path.name)
        shutil.copyfile(path,destination)
        mapping[str(path)]=str(destination)
    environment={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
                 'model':signature.get('model'),'parameters':read(run/'run_metadata.json').get('parameters',{})}
    write_json(bundle/'environment.json',environment)
    frozen={'schema':'mase-exploration-freeze-v1','version_id':version_id,
            'frozen_at':datetime.now(timezone.utc).isoformat(),'data_role':'training_exploration',
            'independent_confirmation':False,'confirmation_status':'deferred_by_user',
            'summary':summary,'original_files':originals,'file_mapping':mapping,
            'bundle_files':snapshot(list(bundle.iterdir()))}
    write_json(output,frozen)
    return frozen


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='冻结已完成的旧60题探索；独立确认暂缓')
    parser.add_argument('run_directory',type=Path)
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    print(json.dumps(freeze_run(args.run_directory,args.version),ensure_ascii=True))
