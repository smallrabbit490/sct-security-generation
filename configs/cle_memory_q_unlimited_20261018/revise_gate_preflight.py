"""正式阶段前吸收历史公开契约排除记录；不读取新Q或模型成绩，不调用API。"""
import ast
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
CONFIG=Path(__file__).resolve().parent
OUT=ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_v1'


def main(out=OUT):
    if (out/'gate/rows.jsonl').exists():
        raise RuntimeError('cannot amend gate manifest after evaluation begins')
    revision=out/'gate_preflight_revision.json'
    if revision.exists():
        print('gate preflight revision already fixed'); return
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    review=read(ROOT/'configs/cle_retrieval_q_public_contract_20261017/contract_review.json')
    excluded={key:value['reason'] for key,value in review.items() if not value['qualified']}
    old_path=ROOT/'configs/cle_memory_q_shared_initial8_20261016/prepare.py'
    tree=ast.parse(old_path.read_text(encoding='utf-8'))
    decisions=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                   and any(isinstance(t,ast.Name) and t.id=='DECISIONS' for t in n.targets))
    excluded.update({key:value for key,value in decisions.items() if value.startswith('exclude:')})
    checks=read(out/'gate_preflight.json')['tasks']
    bad_families={c['family_id'] for c in checks if c['task_id'] in excluded}
    selected=[];seen=set()
    for c in checks:
        if c['qualified'] and c['family_id'] not in bad_families and c['family_id'] not in seen:
            selected.append(int(c['task_id']));seen.add(c['family_id'])
        if len(selected)==48:break
    if len(selected)!=48:raise RuntimeError('fewer than 48 qualified unique families')
    manifest=read(out/'manifest.json')
    shutil.copy2(out/'manifest.json',out/'manifest.initial_reference_preflight.json')
    amendment={'revision':2,'reason':'Reference-only screening missed historical known public-contract exclusions.',
               'selection_basis':'Historical reviews + existing zero-API checks; no new outcomes or Q scores used.',
               'previous':manifest['development'],'development':selected,'excluded':excluded,
               'bad_families':sorted(bad_families),'sources':[str(old_path.relative_to(ROOT)),
               'configs/cle_retrieval_q_public_contract_20261017/contract_review.json']}
    manifest.update(development=selected,preflight_revision=2,
                    known_contract_exclusions='gate_preflight_revision.json')
    for p,value in [(revision,amendment),(out/'manifest.json',manifest),(CONFIG/'manifest.json',manifest),
                    (CONFIG/'gate_preflight_revision.json',amendment)]:
        p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'revision':2,'gate48':selected,'known_bad_families_excluded':len(bad_families)},ensure_ascii=False))


if __name__=='__main__':main()
