"""完整CLE的逐次Q归因和只读边界，不调用外部模型。"""
import pytest
from methods.sct_trajectory import closed_loop as cl
from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode
from methods.sct_trajectory.error_ledger import ErrorLedger


def test_full_rollout_credits_adopted_c0_c1_before_early_stop(monkeypatch):
    runner = cl.CleRunner(lambda p: {}, HskTree(), ErrorLedger(), workers=1,
        context_pipeline=True, retrieval_mode='semantic_q', semantic_delta=0.4, q_learning=True)
    runner.experience_pool = [SecurityInvariantNode(i, '22', 'rule') for i in ('a', 'b', 'unused')]
    count = [0]
    def generate(*args, **kwargs):
        i = count[0]; count[0] += 1
        return {'code': str(i), 'cards': [{'invariant_id': ('a','b')[i]}],
                'retrieved_cards': [{'invariant_id': 'unused'}], 'workflow_completed': True}
    monkeypatch.setattr(cl, 'run_pipeline', generate)
    monkeypatch.setattr(runner, '_distill_round_inline', lambda **kw: 0)
    monkeypatch.setattr(cl, 'validate_and_state', lambda row, code, **kw: (
        {'functional': {'status': 'fail' if code == '0' else 'pass'}, 'security': {'status': 'pass'}},
        'C' if code == '0' else 'A'))
    trace = runner._run_rollout({'index': 1, 'family_id': 'f', 'CWE_ID': '22'}, None, repairs=1)
    assert trace.states == ['C', 'A']
    assert [(n.q_value, n.q_visits) for n in runner.experience_pool] == [(-0.3,1),(0.3,1),(0,0)]
    assert [e['attempt'] for e in runner.memory_q_events] == [0,1]


def test_online_q_rejects_parallel_learning():
    with pytest.raises(ValueError, match='sequential'):
        cl.CleRunner(lambda p: {}, HskTree(), ErrorLedger(), workers=2,
                     context_pipeline=True, retrieval_mode='semantic_q', semantic_delta=0.4, q_learning=True)


def test_json_format_policy_demonstrates_literal_backslashes():
    import json
    from methods.sct_trajectory.context_pipeline import JSON_FORMAT_POLICY, analysis_prompt
    example = JSON_FORMAT_POLICY.split('Valid example: ', 1)[1].split('\n', 1)[0]
    assert json.loads(example)['regex'] == r'\d+\s'
    assert JSON_FORMAT_POLICY in analysis_prompt({'description': 'Use regular expressions'})


def test_source_generation_and_gate_reads_do_not_reward_q(monkeypatch):
    runner = cl.CleRunner(lambda p: {}, HskTree(), ErrorLedger(), context_pipeline=True,
                         retrieval_mode='semantic_q', semantic_delta=0.4, q_learning=True)
    node = SecurityInvariantNode('a', '22', 'rule')
    runner.experience_pool = [node]
    monkeypatch.setattr(cl, 'run_pipeline', lambda *a,**k: {'code':'pass', 'cards':[{'invariant_id':'a'}], 'workflow_completed':True})
    monkeypatch.setattr(cl, 'validate_and_state', lambda *a,**k: (
        {'functional':{'status':'pass'},'security':{'status':'pass'}}, 'A'))
    runner._run_rollout({'index':1}, None, repairs=0, phase='phase1')
    assert runner._joint_pass_rate([{'index':2}], lambda q: [])[0] == 1
    assert runner._regression_probe([{'index':2}], lambda q: [], samples=1) == (0,0)
    assert node.q_visits == 0 and not runner.memory_q_events


@pytest.mark.parametrize('stage', ['phase2', 'phase3', 'final'])
def test_q_configuration_reaches_each_training_retriever(monkeypatch, stage):
    runner = cl.CleRunner(lambda p: {}, HskTree(), ErrorLedger(), context_pipeline=True,
                         retrieval_mode='semantic_q', semantic_delta=0.4, lambda_q=0.7, embedding_client=object())
    seen=[]
    class Stop(Exception): pass
    def capture(*a, **kwargs):
        seen.append(kwargs)
        if kwargs['retrieval_mode']=='flat_rule': return object()
        raise Stop()
    monkeypatch.setattr(cl, 'HskTreeRetriever', capture)
    with pytest.raises(Stop):
        if stage=='phase2': runner.phase2_evolve([])
        elif stage=='phase3': runner.phase3_audit([])
        else: runner.final_evaluate([])
    assert seen[-1]['retrieval_mode']=='semantic_q'
    assert seen[-1]['semantic_delta']==0.4 and seen[-1]['lambda_q']==0.7


def test_frozen_consumer_rejects_modified_q(tmp_path):
    import json
    from methods.cle_ablation.run_memory_q_frozen import load_frozen
    from methods.sct_trajectory.run_branch_gate_study import file_digest
    bank=tmp_path/'memory.jsonl'; config=tmp_path/'config.json'
    bank.write_text(json.dumps(SecurityInvariantNode('a','22','rule').to_dict())+'\n',encoding='utf-8')
    config.write_text(json.dumps({'memory_sha256':file_digest(bank)}),encoding='utf-8')
    assert len(load_frozen(bank, config)[0])==1
    value=json.loads(bank.read_text(encoding='utf-8')); value['q_value']=0.3
    bank.write_text(json.dumps(value)+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='frozen_memory_mismatch'):load_frozen(bank, config)
