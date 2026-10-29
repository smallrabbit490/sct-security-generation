"""人工代码反事实诊断：只在副本局部改动后本地复验，不计为模型新成绩。"""
import ast
import difflib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'translation_work/diagnostics/20261025/cle_v41_migration_S1'
OUT=RUN/'diagnosis_v1/counterfactuals'


class Edit(ast.NodeTransformer):
    def __init__(self,tid,variant):self.tid=tid;self.variant=variant
    def visit_Module(self,node):
        node=self.generic_visit(node)
        forbidden={'1322':{'ALLOWED_DOMAINS'},'1409':{'VALID_SIGNATURES'},'1000':{'BLOG_FORMAT'},
                   '1266':{'_PATIENTS','_PATIENT_STORE','PATIENTS','patients'}}.get(self.tid,set())
        def drop(n):
            if self.tid=='1266' and isinstance(n,ast.ClassDef) and n.name=='Patient':return True
            targets=n.targets if isinstance(n,ast.Assign) else [n.target] if isinstance(n,ast.AnnAssign) else []
            return any(isinstance(x,ast.Name) and x.id in forbidden for x in targets)
        node.body=[n for n in node.body if not drop(n)]
        return node
    def visit_Name(self,node):
        if self.tid=='1266' and node.id in {'_PATIENTS','_PATIENT_STORE','PATIENTS'}:node.id='patients'
        return node
    def visit_Constant(self,node):
        if self.tid=='1266' and node.value in ('_PATIENTS','_PATIENT_STORE','PATIENTS'):node.value='patients'
        return node
    def visit_FunctionDef(self,node):
        node=self.generic_visit(node)
        if self.tid=='1341' and node.name=='generate_xml_response':
            node.args.args=[a for a in node.args.args if a.arg!='xml_template']
            keep=[(a,d) for a,d in zip(node.args.kwonlyargs,node.args.kw_defaults) if a.arg!='xml_template']
            node.args.kwonlyargs=[a for a,d in keep];node.args.kw_defaults=[d for a,d in keep]
            node.body.insert(0,ast.Global(names=['xml_template']))
        if self.tid=='1317':
            if node.name=='convert_to_object':node.args.defaults=[ast.Constant(value='json')]
            if self.variant=='default_and_XML_mapping' and node.name in ('_load_xml','_decode_xml','decode_xml'):
                node.body=ast.parse('''import xml.etree.ElementTree as ET
text = serialized_data.decode('utf-8')
if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
    raise ValueError('Unsafe XML')
root = ET.fromstring(text)
return {child.tag: child.text for child in root}
''').body
        return node
    def visit_Call(self,node):
        node=self.generic_visit(node)
        if self.tid=='335':
            if (isinstance(node.func,ast.Name) and node.func.id=='isinstance' and len(node.args)==2
                and isinstance(node.args[0],ast.Name) and node.args[0].id=='pwd'
                and isinstance(node.args[1],ast.Name) and node.args[1].id=='str'):
                node.args[1]=ast.Tuple(elts=[ast.Name(id='str',ctx=ast.Load()),ast.Name(id='bytes',ctx=ast.Load())],ctx=ast.Load())
            if (isinstance(node.func,ast.Attribute) and node.func.attr=='encode'
                and isinstance(node.func.value,ast.Name) and node.func.value.id=='pwd'):
                return ast.IfExp(test=ast.parse('isinstance(pwd, bytes)',mode='eval').body,
                    body=ast.Name(id='pwd',ctx=ast.Load()),orelse=node)
        if self.tid=='1000' and self.variant=='binding_and_placeholder_adaptation':
            for keyword in node.keywords:
                if keyword.arg=='heading':keyword.arg='headline'
                if keyword.arg=='description':keyword.arg='content'
        return node
    def visit_Compare(self,node):
        node=self.generic_visit(node)
        if (self.tid=='1306' and len(node.ops)==1 and isinstance(node.ops[0],ast.NotEq)
            and isinstance(node.comparators[0],ast.Constant) and node.comparators[0].value=='application/json'):
            name=ast.unparse(node.left)
            return ast.parse(f"not ({name} == 'application/json' or ({name}.startswith('application/') and {name}.endswith('+json')))",mode='eval').body
        return node
    def visit_Dict(self,node):
        node=self.generic_visit(node)
        if self.tid=='1341' and self.variant=='binding_and_escape_fix':
            pairs=[(k,v) for k,v in zip(node.keys,node.values) if not(isinstance(k,ast.Constant) and k.value in ('&','<','>'))]
            node.keys=[k for k,v in pairs];node.values=[v for k,v in pairs]
        return node


def run():
    # 原生验证器取自实际运行快照；不导入模型请求入口、不读取凭据。
    bundle=RUN/'source_bundle';sys.path.insert(0,str(bundle));sys.path.insert(0,str(bundle/'src'))
    from methods.sct_trajectory.closed_loop import validate_and_state
    from methods.sct_trajectory.replay_journal import write_json
    import urllib.request
    def denied(*a,**k):raise RuntimeError('API_disabled_for_offline_diagnosis')
    urllib.request.urlopen=denied
    global OUT
    registry_followup='--registry-followup' in sys.argv
    if registry_followup:OUT=OUT.parent/'registry_binding_v2'
    OUT.mkdir(parents=True,exist_ok=False)
    tasks={str(t['index']):t for t in json.loads((RUN/'inputs/tasks.json').read_text())}
    rows=[json.loads(s) for s in (RUN/'final/rows.jsonl').read_text().splitlines()]
    results=[]
    for row in rows:
        tid=row['task_id'];original=row['attempts'][-1].get('code','')
        if registry_followup and tid!='1266':continue
        if tid not in {'335','1266','1306','1317','1322','1341','1000','1409'}:continue
        variants=(['default_only','default_and_XML_mapping'] if tid=='1317' else
                  ['binding_only','binding_and_escape_fix'] if tid=='1341' and row['cell_id']=='1341_r1_E1' else
                  ['binding_only','binding_and_placeholder_adaptation'] if tid=='1000' and row['cell_id']=='1000_r2_E1' else
                  ['input_bytes_compat'] if tid=='335' else ['suffix_JSON_compat'] if tid=='1306' else ['binding_only'])
        for variant in variants:
            label=row['cell_id']+'_'+variant
            tree=Edit(tid,variant).visit(ast.parse(original));ast.fix_missing_locations(tree)
            patched=ast.unparse(tree)+'\n'
            ast.parse(patched)
            path=OUT/(label+'.py');path.write_text(patched,encoding='utf-8')
            (OUT/(label+'.diff')).write_text(''.join(difflib.unified_diff(original.splitlines(True),patched.splitlines(True),
                fromfile='saved_model_output',tofile='diagnostic_copy')),encoding='utf-8')
            evidence,state=validate_and_state(tasks[tid],patched,timeout=20)
            entry={'cell_id':row['cell_id'],'task_id':tid,'arm':row['migration_arm'],'repeat':row['repeat'],
                'variant':variant,'original':{k:row['attempts'][-1].get(k) for k in ('measured','functional','security','joint')},
                'after':{k:evidence[k]['status'] for k in ('functional','security')},'state':state,
                'code':str(path),'evidence':evidence,
                'scope':'posthoc manual-code diagnosis using fixture-visible interpretation; not a model result or fresh experiment'}
            write_json(OUT/(label+'.json'),entry);results.append(entry)
            print(json.dumps({'cell':row['cell_id'],'variant':variant,'after':entry['after']}),flush=True)
    # 本批8个失败题族的原生参考验证单列，不与人工修改的模型代码混计。
    refs=[]
    for tid in (() if registry_followup else ('335','1266','1306','1317','1322','1341','1000','1409')):
        g=tasks[tid]['ground_truth'];code=g['code_before']+g['patched_code']+g['code_after']
        evidence,state=validate_and_state(tasks[tid],code,timeout=20)
        refs.append({'task_id':tid,'evidence':evidence,'state':state})
    write_json(OUT/'reference_checks.json',refs)
    write_json(OUT/'summary.json',{'API_calls':0,'new_model_generations':0,'original_scores_changed':False,
        'diagnostic_runs':len(results),'results':results,
        'implementation_note':'1266 first diagnostic version renamed then failed to remove empty registry; corrected in separate v2, original failed diagnostic retained' if registry_followup else None})


if __name__=='__main__':run()
