"""检验MASE的记录、图执行边界及指标，避免把缺测/候选上界当最终成绩。"""
import importlib
import json


def module(name):
    try:
        return importlib.import_module('methods.mase_evolution.' + name)
    except ModuleNotFoundError:
        return None


def graph():
    return {'nodes': [
        {'id': 'g', 'operation': 'llm', 'label': '生成', 'inputs': ['public_task'], 'output': 'candidate'},
        {'id': 'f', 'operation': 'finish', 'label': '结束', 'inputs': ['g']}],
        'edges': [{'source': 'g', 'target': 'f', 'label': '代码'}]}


def result(joint, measured=True):
    return {'joint': joint, 'functional': joint, 'security': joint, 'measured': measured}


def row(task, joint, measured=True):
    return {'task_id': str(task), 'family_id': 'f' + str(task), 'final': result(joint, measured),
            'attempts': [result(joint, measured)], 'usage': {'calls': 1}}


def test_graph_rejects_official_feedback_and_unreachable_finish():
    schemas = module('schemas')
    assert schemas is not None, '流程图与权限校验尚未实现'
    assert schemas.validate_graph(graph()) == []
    bad = graph()
    bad['nodes'][0]['inputs'].append('official_score')
    assert any('forbidden' in e for e in schemas.validate_graph(bad))
    bad = graph()
    bad['edges'] = []
    assert any('unreachable' in e for e in schemas.validate_graph(bad))


def test_finish_rejects_two_candidate_paths_without_explicit_selection():
    structure = {'nodes': [
        {'id': 'a', 'operation': 'llm', 'inputs': ['public_task'], 'output': 'candidate'},
        {'id': 'b', 'operation': 'llm', 'inputs': ['public_task'], 'output': 'candidate'},
        {'id': 'f', 'operation': 'finish', 'inputs': ['a', 'b']}],
        'edges': [{'source': 'a', 'target': 'f'}, {'source': 'b', 'target': 'f'}]}
    errors = module('schemas').validate_graph(structure)
    assert 'finish_requires_explicit_selection:f' in errors


def test_finish_deduplicates_same_candidate_reaching_through_two_paths():
    from methods.mase_evolution.executor import GraphExecutor
    graph = {'schema':'mase-graph-v1','nodes':[
        {'id':'a','operation':'llm','inputs':['public_task']},
        {'id':'b','operation':'llm','inputs':['public_task']},
        {'id':'f','operation':'finish','inputs':['a','b'],'optional_inputs':['a','b']}],
        'edges':[{'source':'a','target':'f'},{'source':'b','target':'f'}]}
    result = GraphExecutor({'llm':lambda n,i:{'code':'def f(): return 1'}}).run(graph, {'public_task':{}})
    assert result['workflow_completed'] is True
    assert result['selected_code'] == 'def f(): return 1'


def test_conditional_repair_branch_can_reach_optional_finish():
    from methods.mase_evolution.executor import GraphExecutor
    structure = {'schema': 'mase-graph-v1', 'nodes': [
        {'id': 'generate', 'operation': 'llm', 'inputs': ['public_task']},
        {'id': 'check', 'operation': 'inspect', 'inputs': ['generate', 'contract']},
        {'id': 'route', 'operation': 'branch', 'inputs': ['check']},
        {'id': 'repair', 'operation': 'llm', 'inputs': ['check']},
        {'id': 'finish', 'operation': 'finish', 'inputs': ['repair', 'route'],
         'optional_inputs': ['repair', 'route']}],
        'edges': [
            {'source': 'generate', 'target': 'check'},
            {'source': 'check', 'target': 'route'},
            {'source': 'check', 'target': 'repair'},
            {'source': 'route', 'target': 'repair', 'condition': 'problem'},
            {'source': 'route', 'target': 'finish', 'condition': 'clean'},
            {'source': 'repair', 'target': 'finish'}]}

    def inspect(node, inputs):
        return {'code': 'def f(): return 1', 'issues': [{'type': 'public'}],
                'checks': {'cases': []}}

    output = GraphExecutor({'inspect': inspect,
                            'llm': lambda node, inputs: {'code': 'def f(): return 2'}}).run(
                                structure, {'public_task': {}, 'contract': {}})
    assert output['workflow_completed'] is True
    assert output['selected_code'] == 'def f(): return 2'


def test_failed_node_event_has_safe_error_code_without_exception_text():
    from methods.mase_evolution.executor import GraphExecutor
    graph = {'schema':'mase-graph-v1','nodes':[
        {'id':'a','operation':'llm','inputs':['public_task']},
        {'id':'f','operation':'finish','inputs':['a']}],
        'edges':[{'source':'a','target':'f'}]}
    result = GraphExecutor({'llm':lambda n,i:(_ for _ in ()).throw(ValueError('secret prompt text'))}).run(graph, {'public_task':{}})
    failed = next(e for e in result['events'] if e['status']=='failed')
    assert failed['error_code'] == 'unknown_error'
    assert 'secret prompt text' not in str(result)


def test_failed_upstream_marks_dependent_node_skipped_not_second_failure():
    from methods.mase_evolution.executor import GraphExecutor
    graph = {'schema':'mase-graph-v1','nodes':[
        {'id':'a','operation':'llm','inputs':['public_task']},
        {'id':'b','operation':'llm','inputs':['a']},
        {'id':'f','operation':'finish','inputs':['b']}],
        'edges':[{'source':'a','target':'b'},{'source':'b','target':'f'}]}
    result = GraphExecutor({'llm':lambda n,i:(_ for _ in ()).throw(ValueError('model_output_truncated'))}).run(graph, {'public_task':{}})
    assert [(e['node_id'],e['status']) for e in result['events']] == [('a','failed'),('b','skipped'),('f','skipped')]
    assert result['events'][0]['error_code'] == 'model_output_truncated'


def test_initial_graph_joins_clean_and_repair_paths_before_finish():
    from methods.mase_evolution.blueprints import initial_graph
    structure=initial_graph()
    finish=next(n for n in structure['nodes'] if n['operation']=='finish')
    assert finish['inputs']==['repair']
    assert not any(e['target']=='finish' and e['source']!='repair' for e in structure['edges'])
    assert module('schemas').validate_graph(structure)==[]


def test_metrics_keep_planned_denominator_and_do_not_invent_missing_evidence():
    metrics = module('metrics')
    assert metrics is not None, '真实分母和缺测统计尚未实现'
    rows = [row(1, True), row(2, False, False)]
    report = metrics.summarize(rows, expected=3)
    assert report['joint'] == 1 and report['joint_rate'] == 1 / 3
    assert report['measured'] == 1 and report['missing'] == 2
    assert report['recorded'] == 2 and report['pending'] == 1
    assert report['selection']['miss_rate'] is None
    assert report['repairs']['step_harm_rate'] is None


def test_paired_results_include_losses_and_ignore_unmeasured_pairs():
    metrics = module('metrics')
    assert metrics is not None, '配对回归统计尚未实现'
    report = metrics.compare([row(1, False), row(2, True), row(3, True)],
                             [row(1, True), row(2, False), row(3, False, False)])
    assert report['wins'] == ['1'] and report['losses'] == ['2']
    assert report['measured_pairs'] == 2 and report['net_joint'] == 0


def test_candidate_upper_bound_not_final_and_selection_coverage():
    metrics = module('metrics')
    assert metrics is not None, '候选成功上界与选择漏失尚未分开'
    r = row(1, False)
    r['candidate_scores'] = [result(True), result(False)]
    report = metrics.summarize([r], expected=1)
    assert report['joint'] == 0
    assert report['selection']['oracle_tasks'] == 1
    assert report['selection']['misses'] == 1
    assert report['selection']['miss_rate'] == 1


def test_graph_runner_changes_information_flow_and_cannot_read_scores():
    executor = module('executor')
    assert executor is not None, '通用图执行器尚未实现'
    structure = graph()
    structure['nodes'].insert(1, {'id': 'review', 'operation': 'llm', 'label': '独立审阅',
                               'inputs': ['public_task', 'g'], 'output': 'candidate'})
    structure['nodes'][-1]['inputs'] = ['review']
    structure['edges'] = [{'source': 'g', 'target': 'review'}, {'source': 'review', 'target': 'f'}]
    seen = []
    def operate(node, inputs):
        seen.append((node['id'], inputs))
        return {'code': 'def f():\n    return 2' if node['id'] == 'review' else 'def f():\n    return 1'}
    runner = executor.GraphExecutor({'llm': operate})
    output = runner.run(structure, {'public_task': {'description': '公开题目'}, 'official_score': True})
    assert 'return 2' in output['selected_code']
    assert [x[0] for x in seen] == ['g', 'review']
    assert 'official_score' not in seen[0][1]
    assert [e['node_id'] for e in output['events'] if e['status'] == 'completed'] == ['g', 'review', 'f']


def test_graph_executor_emits_running_then_terminal_node_events():
    executor = module('executor')
    emitted = []
    output = executor.GraphExecutor({'llm': lambda node, inputs: {'code': 'def f(): return 1'}},
                                    on_event=emitted.append).run(
        graph(), {'public_task': {'description': 'public'}})
    assert output['workflow_completed'] is True
    assert [(event['node_id'], event['status']) for event in emitted] == [
        ('g', 'running'), ('g', 'completed'), ('f', 'running'), ('f', 'completed')]
    assert [(event['node_id'], event['status']) for event in output['events']] == [
        ('g', 'completed'), ('f', 'completed')]


def test_incomplete_workflow_never_calls_official_evaluator():
    runner = module('run')
    task = {'index': 1, 'family_id': 'fam', 'CWE_ID': '77',
            'task_description': {'description': 'Return 2', 'function_name': 'f', 'arguments': []}}
    graph_with_runtime_failure = graph()
    calls = []

    def evaluate(task, code):
        calls.append(code)
        return {'code': code, **result(True)}

    output = runner.execute_task(task, graph_with_runtime_failure, [], {}, None, evaluator=evaluate)
    assert calls == []
    assert output['workflow_completed'] is False


def test_jsonl_truncation_is_reported_and_version_is_immutable(tmp_path):
    artifacts = module('artifacts')
    assert artifacts is not None, '审计记录保存尚未实现'
    store = artifacts.Store(tmp_path)
    store.create_version({'version_id': 'v001', 'status': 'draft', 'architecture': graph()})
    try:
        store.create_version({'version_id': 'v001', 'status': 'draft', 'architecture': graph()})
    except ValueError:
        pass
    else:
        assert False, '同编号版本不应覆盖'
    p = tmp_path / 'rows.jsonl'
    p.write_text(json.dumps(row(1, True)) + '\n{"task_id":', encoding='utf-8')
    rows, errors = artifacts.read_jsonl(p)
    assert len(rows) == 1 and errors[0]['type'] == 'truncated_line'


def test_security_regression_requires_review_and_net_improvement_can_be_kept():
    evolution = module('evolution')
    assert evolution is not None, '架构进化接纳规则尚未实现'
    before = [row(1, False), row(2, False), row(3, True)]
    after = [row(1, True), row(2, True), row(3, False)]
    decision = evolution.decide(before, after)
    assert decision['status'] == 'needs_safety_review'
    after[2]['final']['security'] = True
    decision = evolution.decide(before, after)
    assert decision['status'] == 'accepted' and decision['paired']['net_joint'] == 1


def test_server_rejects_traversal_and_never_returns_hidden_files(tmp_path):
    server = module('dashboard.server')
    assert server is not None, '网页受控读取尚未实现'
    assert server.safe_identifier('../local_secrets') is False
    assert server.safe_identifier('run-20261013') is True


def test_graph_rejects_dead_nodes_and_outer_iteration_input():
    structure = graph()
    structure['nodes'].append({'id': 'unused', 'operation': 'llm', 'inputs': ['public_task']})
    assert any('dead_node' in e for e in module('schemas').validate_graph(structure))
    structure = graph()
    structure['nodes'][0]['inputs'] = ['iteration_candidate']
    assert any('iteration' in e for e in module('schemas').validate_graph(structure))


def test_metric_rejects_unmeasured_joint_claim():
    import pytest
    with pytest.raises(ValueError, match='inconsistent'):
        module('metrics').summarize([row(1, True, False)])


def test_repeated_repair_preserves_incumbent_and_records_child_candidates():
    executor = module('executor')
    child = graph()
    child['nodes'][0]['inputs'] = ['iteration_candidate']
    structure = graph()
    structure['nodes'][0]['operation'] = 'llm'
    structure['nodes'].insert(1, {'id':'loop','operation':'repeat','inputs':['g'], 'graph':child})
    structure['nodes'][-1]['inputs'] = ['loop']
    structure['edges'] = [{'source':'g','target':'loop'}, {'source':'loop','target':'f'}]
    original = 'def f():\n    return 1'
    calls = []
    def repair(node, inputs):
        calls.append(1)
        return {'code':original, 'issues':[{'type':'interface'}]}
    output = executor.GraphExecutor({'llm':repair}).run(structure, {'public_task':{}})
    loop = next(e['output'] for e in output['events'] if e['node_id']=='loop')
    assert loop['stop_reason']=='repeated_candidate'
    assert len(calls)==2, '生成一次，第一次重复修复即停，不反复调用'
    assert output['selected_code']==original


def test_operator_public_view_filters_nested_answers_and_memory_isolation():
    import pytest
    views = module('views')
    assert views is not None, '真实操作的公开视图尚未实现'
    task={'index':1,'family_id':'target','CWE_ID':'77',
          'task_description':{'description':'safe command','function_name':'f','ground_truth':'secret'},
          'ground_truth':{'patched_code':'TARGET_SECRET'}}
    context=views.solver_context(task, [], None)
    assert 'secret' not in json.dumps(context).lower()
    card={'id':'x','family_id':'target','cwe':'77','source_evidence':{'patched':result(True)}}
    with pytest.raises(ValueError, match='family'):
        views.solver_context(task, [card], None)


def test_designer_proposes_structure_from_sanitized_training_feedback():
    designer = module('designer')
    assert designer is not None, '自主图设计员尚未实现'
    prompts=[]
    class Session:
        def json(self, prompt, stage):
            prompts.append(prompt)
            return {'architecture':graph(), 'hypothesis':'删除冗余步骤', 'changes':['删除审阅'], 'layer':'architecture'}
    feedback=row(1,False)
    feedback.update(selected_code='def f(): return 0', contract={'function_name':'f'},
                    ground_truth='TARGET_SECRET', hidden_tests='HIDDEN_SECRET')
    proposal=designer.propose(Session(), graph(), [], [feedback], 'architecture', [])
    assert proposal['valid'] and proposal['architecture']['nodes'][0]['id']=='g'
    assert 'TARGET_SECRET' not in prompts[0] and 'HIDDEN_SECRET' not in prompts[0]


def test_public_selection_rejects_different_checks_and_freezes_output():
    operators=module('operators')
    assert operators is not None, '真实图操作尚未实现'
    a={'code':'a','issues':[], 'checks':{'cases':[{'id':'one','status':'pass','measured':True}]}, 'suite_hash':'a'}
    b={'code':'b','issues':[], 'checks':{'cases':[{'id':'two','status':'pass','measured':True}]}, 'suite_hash':'b'}
    chosen=operators.select_public({'id':'select'}, {'a':a,'b':b})
    assert chosen['code']=='a' and chosen['selection_reason']=='incomparable_public_checks_preserve_first'


def test_designer_keeps_role_prompt_and_rejects_empty_inspector():
    designer=module('designer')
    structure=graph()
    structure['nodes'][0]['prompt']='Respect exact input normalization'
    class Session:
        def json(self,prompt,stage):
            return {'architecture':structure,'memory_updates':[]}
    proposal=designer.propose(Session(), graph(), [], [], 'architecture', [])
    assert proposal['architecture']['nodes'][0]['prompt']==structure['nodes'][0]['prompt']
    structure['nodes'][0]['operation']='inspect'
    assert any('inspection' in e for e in module('schemas').validate_graph(structure))


def test_run_scores_all_candidates_after_finish_and_preserves_events(tmp_path):
    runner=module('run')
    assert runner is not None, '真实实验运行器尚未实现'
    requests=[]
    def request(prompt):
        requests.append(prompt)
        return {'choices':[{'message':{'content':'def f():\n    return 2'},'finish_reason':'stop'}], 'usage':{'total_tokens':5}}
    task={'index':1,'family_id':'fam','CWE_ID':'77',
          'task_description':{'description':'Return 2','function_name':'f','arguments':[]}}
    scored=[]
    def evaluate(task,code):
        scored.append(code)
        return {'code':code, **result(True)}
    recorded=[]
    r=runner.execute_task(task,graph(),[],{4096:request},None,evaluator=evaluate,on_event=recorded.append)
    assert r['final']['joint'] and len(scored)==1
    assert r['events'][-1]['operation']=='finish' and len(recorded)==4
    assert r['public_task']['description']=='Return 2'
    assert r['candidate_scores'][0]['joint']


def test_mase_freeze_prevents_configuration_change(tmp_path):
    freezing=module('freeze')
    assert freezing is not None, '确认前冻结校验尚未实现'
    p=tmp_path/'architecture.json'
    p.write_text(json.dumps(graph()),encoding='utf-8')
    snapshot=freezing.snapshot([p])
    assert freezing.verify(snapshot)==[]
    p.write_text('{}',encoding='utf-8')
    assert freezing.verify(snapshot)


def test_initial_workflow_repair_is_conditional_and_all_inspections_are_comparable():
    from methods.mase_evolution.blueprints import initial_graph
    structure=initial_graph()
    assert module('schemas').validate_graph(structure)==[]
    repeat=next((n for n in structure['nodes'] if n['operation']=='repeat'),None)
    assert repeat is not None, '接口保护起点必须保留实际接口修复循环，不能只审计不修复'
    assert 'contract' in repeat['inputs'] and repeat.get('only_on_problem',True)


def test_intermediate_metrics_report_paths_and_public_check_disagreement():
    r=row(1,False)
    r['events']=[{'node_id':'g','operation':'llm','status':'completed','input_refs':['public_task'],'output':{'code':'a'}},
                 {'node_id':'i','operation':'inspect','status':'completed','input_refs':['g','contract'],
                  'output':{'code':'a','issues':[],'checks':{'cases':[{'id':'x','status':'pass','measured':True}]}}}]
    r['candidate_scores']=[{'code':'a',**result(False)}]
    r['public_attempts']=[r['events'][1]['output']]
    s=module('metrics').summarize([r],expected=1)
    assert s['execution']['completed_nodes']==2
    assert s['public_alignment']['public_pass_official_fail']==1
    assert s['public_alignment']['compared']==1


def test_repeat_events_stream_before_parent_finishes():
    original='def f(): return 1'
    child=graph();child['nodes'][0]['inputs']=['iteration_candidate']
    structure=graph()
    structure['nodes'].insert(1, {'id':'loop','operation':'repeat','inputs':['g'],'graph':child})
    structure['nodes'][-1]['inputs']=['loop']
    structure['edges']=[{'source':'g','target':'loop'},{'source':'loop','target':'f'}]
    events=[]
    module('executor').GraphExecutor({'llm':lambda n,i:{'code':original,'issues':[{'type':'x'}]}},events.append).run(structure, {'public_task':{}})
    assert any(e.get('parent_node_id')=='loop' for e in events), '循环内部事件必须即时落盘'


def test_training_designer_view_removes_task_specific_ids():
    r=row('target-777',False)
    r['public_task']={'task_id':'target-777','description':'public task'}
    view=module('views').training_view([r])
    assert 'target-777' not in json.dumps(view)


def test_exposure_audit_counts_execution_and_sources_not_pool_membership(tmp_path):
    audit=module('exposure_audit')
    assert audit is not None
    tasks=[{'index':1,'family_id':'used'}, {'index':2,'family_id':'unused'},
           {'index':3,'family_id':'source'}]
    (tmp_path/'pool_manifest.json').write_text(json.dumps({'pools':{'D_init':tasks}}),encoding='utf-8')
    (tmp_path/'rows.jsonl').write_text(json.dumps({'task_id':1,'family_id':'used','final':result(False)})+'\n',encoding='utf-8')
    (tmp_path/'source_bank.json').write_text(json.dumps([{'source_id':3,'family_id':'source'}]),encoding='utf-8')
    report=audit.scan([tmp_path],tasks)
    assert report['exposed_families']==['source','used']
    assert report['not_found_in_records']==['unused']
    assert report['proves_pristine'] is False


def test_resume_rejects_changed_runtime_snapshot(tmp_path):
    runner=module('run')
    assert hasattr(runner,'bind_snapshot')
    runner.bind_snapshot(tmp_path,'runtime',{'graph':graph(),'bank':[]})
    import pytest
    with pytest.raises(ValueError,match='snapshot_changed'):
        runner.bind_snapshot(tmp_path,'runtime',{'graph':{},'bank':[]})


def test_conditional_edge_cannot_be_bypassed_by_always_dependency():
    structure=graph()
    structure['nodes'].insert(1,{'id':'repair','operation':'llm','inputs':['g','public_task']})
    structure['nodes'][-1]['inputs']=['g','repair']
    structure['nodes'][-1]['optional_inputs']=['g','repair']
    structure['edges']=[{'source':'g','target':'repair','condition':'problem'},
                        {'source':'g','target':'repair','condition':'always'},
                        {'source':'g','target':'f','condition':'clean'},
                        {'source':'repair','target':'f','condition':'problem','condition_source':'g'}]
    calls=[]
    output=module('executor').GraphExecutor({'llm':lambda n,i:calls.append(n['id']) or {'code':'x','issues':[]}}).run(structure,{'public_task':{}})
    assert calls==['g'] and output['selected_code']=='x'
    calls.clear()
    output=module('executor').GraphExecutor({'llm':lambda n,i:calls.append(n['id']) or {'code':n['id'],'issues':['confirmed'] if n['id']=='g' else []}}).run(structure,{'public_task':{}})
    assert calls==['g','repair'] and output['selected_code']=='repair'


def test_repair_result_can_follow_the_original_inspection_branch():
    structure=graph()
    structure['nodes'].insert(1,{'id':'repair','operation':'llm','inputs':['g','public_task']})
    structure['nodes'][-1]['inputs']=['g','repair']
    structure['nodes'][-1]['optional_inputs']=['g','repair']
    structure['edges']=[{'source':'g','target':'repair','condition':'problem'},
                        {'source':'g','target':'f','condition':'clean'},
                        {'source':'repair','target':'f','condition':'problem','condition_source':'g'}]
    assert module('schemas').validate_graph(structure)==[]
    calls=[]
    output=module('executor').GraphExecutor({'llm':lambda n,i:calls.append(n['id']) or
        {'code':'original' if n['id']=='g' else 'repaired',
         'issues':['confirmed'] if n['id']=='g' else []}}).run(structure,{'public_task':{}})
    assert calls==['g','repair']
    assert output['workflow_completed'] is True
    assert output['selected_code']=='repaired'


def test_condition_source_must_be_an_explicit_dependency():
    structure=graph()
    structure['nodes'].insert(1,{'id':'repair','operation':'llm','inputs':['g','public_task']})
    structure['nodes'][-1]['inputs']=['repair']
    structure['edges']=[{'source':'g','target':'repair'},
                        {'source':'repair','target':'f','condition':'problem','condition_source':'g'}]
    assert 'condition_source_without_edge:f:g' in module('schemas').validate_graph(structure)


def test_inactive_information_edge_does_not_deliver_payload_to_merge():
    structure={'nodes':[
        {'id':'a','operation':'llm','inputs':['public_task']},
        {'id':'b','operation':'llm','inputs':['public_task']},
        {'id':'merge','operation':'llm','inputs':['a','b'],'optional_inputs':['b']},
        {'id':'f','operation':'finish','inputs':['merge']}],
        'edges':[{'source':'a','target':'merge','condition':'clean'},
                 {'source':'b','target':'merge','condition':'problem'},
                 {'source':'merge','target':'f'}]}
    seen=[]
    def operation(node,inputs):
        if node['id']=='merge':
            seen.append(inputs)
        return {'code':node['id'],'issues':[]}
    module('executor').GraphExecutor({'llm':operation}).run(structure,{'public_task':{}})
    assert list(seen[0])==['a']


def test_malformed_model_graph_is_saved_as_invalid_not_exception():
    structure=graph();structure['nodes'][0]['operation']=['llm']
    class Session:
        def json(self,prompt,stage):
            return {'architecture':structure}
    proposal=module('designer').propose(Session(),graph(),[],[],'architecture',[])
    assert proposal['valid'] is False and proposal['architecture']==structure
    structure=graph();structure['edges'][0]['source']=['g']
    assert module('schemas').validate_graph(structure)


def test_source_binding_rejects_mismatched_identity_and_rebuilds_code():
    runner=module('run')
    assert hasattr(runner,'bind_source')
    task={'index':1,'family_id':'real','CWE_ID':'77','task_description':{},
          'ground_truth':{'code_before':'prefix','code_after':'suffix',
                          'vulnerable_code':'bad','patched_code':'good'}}
    card={'source_id':1,'family_id':'fake','cwe':'77','patch_slice':{'after':'wrong'}}
    import pytest
    with pytest.raises(ValueError,match='source_identity'):
        runner.bind_source(card,task)
    card['family_id']='real'
    bound=runner.bind_source(card,task)
    assert bound['patch_slice']=={'before':'bad','after':'good'}
    assert bound['source_code_context']['prefix']=='prefix'
    assert bound['source_code_sha256']


def test_measurement_view_retains_safe_missing_reasons_without_test_details():
    value={'final':{'evidence':{'functional':{'status':'unmeasured','error_type':'environment_error',
                                           'details':'HIDDEN_INPUT'}}}}
    clean=module('views').measurement_view(value)
    assert clean['final']['evidence']['functional']['error_type']=='environment_error'
    assert 'HIDDEN_INPUT' not in json.dumps(clean)


def test_incomplete_workflow_never_runs_official_candidate_scoring():
    structure=graph()
    structure['nodes'].insert(1,{'id':'broken','operation':'llm','inputs':['g'],'output':'message'})
    structure['nodes'][-1]['inputs']=['broken']
    structure['edges']=[{'source':'g','target':'broken'},{'source':'broken','target':'f'}]
    def request(prompt):
        return {'choices':[{'message':{'content':'def f(): return 2'},'finish_reason':'stop'}], 'usage':{}}
    task={'index':1,'family_id':'fam','CWE_ID':'77','task_description':{}}
    scored=[]
    result=module('run').execute_task(task,structure,[],{4096:request},None,
                                    evaluator=lambda t,c:scored.append(c))
    assert not result['workflow_completed'] and scored==[]


def test_designer_feedback_references_repeated_code_without_losing_evidence():
    code='def f():\n    return "PUBLIC_CANDIDATE_UNIQUE"'
    r=row(1,False)
    r.update(first_code=code,selected_code=code,
             candidate_scores=[{'code':code,**result(False)}],
             events=[{'node_id':'check','output':{'code':code,'issues':[{'type':'interface'}]}}])
    prompts=[]
    class Session:
        def json(self,prompt,stage):
            prompts.append(prompt)
            return {'architecture':graph(),'memory_updates':[]}
    module('designer').propose(Session(),graph(),[],[r],'architecture',[])
    prompt=prompts[0]
    assert prompt.count('PUBLIC_CANDIDATE_UNIQUE')==1
    assert 'code_ref' in prompt and 'interface' in prompt
    assert 'Return ONLY one JSON object' in prompt
    assert 'memory_updates MUST be []' in prompt


def test_large_designer_feedback_keeps_all_outcomes_and_stratifies_details():
    rows=[]
    for i in range(60):
        r=row(i,i % 3 == 0)
        r.update(cwe=str(i % 6), selected_code='def f(): return '+str(i),
                 public_task={'description':'public requirement ' * 200},
                 events=[{'node_id':'memory','operation':'memory','output':{
                     'memory':{'patch_slice':{'after':'source snippet '*1000},'id':'source'},
                     'record':{'decision':'use','injected_ids':['source']}}}])
        rows.append(r)
    payload=module('designer').compact_feedback(rows)
    assert len(payload['all_outcomes'])==60
    assert payload['aggregate']['joint']==20
    assert 0 < len(payload['records']) <= 12
    assert set(r['cwe'] for r in payload['records'])==set(str(i) for i in range(6))
    assert 'source snippet' not in json.dumps(payload)
    assert len(json.dumps(payload)) < 100000


def test_designer_all_outcomes_never_repeat_full_memory_source_code():
    rows=[]
    for i in range(60):
        r=row(i,False)
        r['memory']={'decision':'use','injected_ids':['source'],
                     'patch_slice':{'after':'SOURCE_CODE_MUST_NOT_REPEAT '*400}}
        rows.append(r)
    payload=module('designer').compact_feedback(rows)
    outcomes=json.dumps(payload['all_outcomes'])
    assert 'SOURCE_CODE_MUST_NOT_REPEAT' not in outcomes
    assert len(outcomes) < 30000


def test_version_parallel_tasks_complete_with_deterministic_result_order(tmp_path,monkeypatch):
    import threading
    from types import SimpleNamespace
    runner=module('run')
    store=module('artifacts').Store(tmp_path)
    store.create_version({'version_id':'v000','architecture':graph()})
    barrier=threading.Barrier(2)
    def execute(task,*args,**kwargs):
        barrier.wait(timeout=2)
        return row(task['index'],True)
    monkeypatch.setattr(runner,'execute_task',execute)
    tasks=[{'index':1},{'index':2}]
    rows=runner.score_version(store,'v000',graph(),[],tasks,{}, {},
                             SimpleNamespace(workers=2,workflow_timeout=30,memory_kind='m1'))
    assert [r['task_id'] for r in rows]==['1','2']
    assert len(module('artifacts').read_jsonl(store.version_dir('v000')/'rows.jsonl')[0])==2


def test_freeze_requires_completed_60_and_preserves_an_immutable_bundle(tmp_path):
    import pytest
    artifacts=module('artifacts')
    source=tmp_path/'source.py'
    source.write_text('original implementation',encoding='utf-8')
    run=tmp_path/'run'
    directory=run/'versions/v000'
    directory.mkdir(parents=True)
    artifacts.write_json(run/'signature.json',{'files':module('freeze').snapshot([source]),'model':'test'})
    artifacts.write_json(run/'run_metadata.json',{'status':'running'})
    artifacts.write_json(run/'manifest.json',{'tasks':[{'task_id':str(i),'family_id':'f'+str(i)} for i in range(60)]})
    artifacts.write_json(directory/'architecture.json',graph())
    artifacts.write_json(directory/'memory.json',[])
    artifacts.write_json(directory/'version.json',{'status':'baseline_completed','expected':60})
    artifacts.write_json(directory/'decision.json',{'status':'baseline_completed'})
    artifacts.write_json(directory/'summary.json',module('metrics').summarize([row(i,True) for i in range(60)],60))
    (directory/'rows.jsonl').write_text(''.join(json.dumps(row(i,True))+'\n' for i in range(60)),encoding='utf-8')
    freeze=module('freeze')
    with pytest.raises(ValueError,match='exploration_not_completed'):
        freeze.freeze_run(run,'v000')
    artifacts.write_json(run/'run_metadata.json',{'status':'exploration_completed'})
    frozen=freeze.freeze_run(run,'v000')
    assert frozen['independent_confirmation'] is False
    assert frozen['confirmation_status']=='deferred_by_user'
    assert freeze.verify(frozen['bundle_files'])==[]
    source.write_text('changed implementation',encoding='utf-8')
    assert freeze.verify(frozen['bundle_files'])==[], '冻结副本不能随工作区修改'
    assert freeze.verify(frozen['original_files'])
    assert freeze.freeze_run(run,'v000')==frozen


def test_session_records_per_call_usage_references_without_prompt_text():
    session_module=module('session')
    assert session_module is not None, 'MASE逐调用审计尚未实现'
    def request(prompt):
        return {'choices':[{'message':{'content':'def f(): return 1'},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':3,'completion_tokens':4,'total_tokens':7}}
    session=session_module.Session({4096:request})
    session.ask('DO_NOT_STORE_RAW_PROMPT','node_generate')
    event=session.trace[0]
    assert event['call_id'] and event['input_sha256']
    assert event['usage']['total_tokens']==7
    assert 'DO_NOT_STORE_RAW_PROMPT' not in json.dumps(event)
