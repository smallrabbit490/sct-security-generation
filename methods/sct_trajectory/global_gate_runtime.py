"""CLE 训练收尾适配：全量单次生成门控及冻结副本，不读取最终测试集。"""
import copy
import json
from collections import Counter

from .agent_pipeline import _content, _extract_json, strip_code_fence
from .context_pipeline import CONTRACT_POLICY, analysis_prompt, experience_text
from .global_gate import run_global_gate
from .english_policy import assert_english_text
from .hsk_tree import HskTree
from .retriever import HskTreeRetriever


def finalize_global_gate(runner, tasks, out):
    """末尾 D_gate 全量对照→局部归因→过滤后重测；只在新运行副本停用已确认有害卡。

输入训练 runner 的候选快照，输出兼容 final_eval 摘要及 gate_report；缺测和 API
失败在门控中不驱动删除。原始审计前库另存，最终结果仍是训练筛选池、非泛化得分。
"""
    from .closed_loop import validate_and_state
    out.mkdir(parents=True, exist_ok=True)
    memory = copy.deepcopy(runner.experience_pool)
    queries = {}
    def contract(row):
        return {**(row.get('task_description') or {}), 'task_id': row['index'],
                'CWE_ID': str(row.get('CWE_ID', '')), 'language': 'python'}
    def request(prompt):
        runner.cost.set_stage('phase3_global')
        return runner.req_gen(prompt)
    def retrieve(row, retired=frozenset()):
        task = contract(row)
        identity = str(row['index'])
        if identity not in queries:
            analysis = _extract_json(_content(request(analysis_prompt(task))))
            assert_english_text(json.dumps(analysis, ensure_ascii=False), context="global_gate.analysis")
            if not all(isinstance(analysis.get(k), list) and analysis[k] for k in ('vulnerability_hypothesis', 'functional_invariants')):
                raise ValueError('initial_analysis_incomplete')
            queries[identity] = {**task, 'threat_analysis': analysis}
        retriever = HskTreeRetriever(HskTree(), requester=request, ablation=runner.ablation,
            retrieval_mode=runner.retrieval_mode, min_llm_score=runner.min_llm_score,
            cross_cwe_min_score=runner.cross_cwe_min_score,
            antioverdefense_bonus=runner.antioverdefense_bonus, same_task_bonus=runner.same_task_bonus,
            embedding_client=getattr(runner, "embedding_client", None))
        return retriever.search(queries[identity], limit=3,
            pool_nodes=[n for n in memory if n.invariant_id not in retired]) or []
    def generate(row, cards):
        return strip_code_fence(_content(request('Generate complete runnable Python code; output code only. ' + CONTRACT_POLICY +
            '\nTask: ' + json.dumps(contract(row), ensure_ascii=False) + '\nConditional experience: ' + experience_text(cards))))
    def validate(row, code):
        return validate_and_state(row, code, timeout=runner.timeout)[0]
    def dump(name, data):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    dump('gate_input_memory.json', [n.to_dict() for n in memory])
    with (out / 'global_gate_events.jsonl').open('x', encoding='utf-8') as stream:
        def record(row):
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            stream.flush()
            runner.progress(f"[Phase3 全量] {row['kind']} task={row.get('task_id', '')} arm={row.get('arm', '')}")
        result = run_global_gate([{**r, 'pool': 'D_gate'} for r in tasks], retrieve, generate, validate,
            workers=runner.workers, on_record=record, retrieve_filtered=retrieve)
    dump('global_gate_report.json', result)
    # 决策仅作用于新对象；即便上游持有同一节点/树引用，源库也不会被原地写入。
    # 冻结审计快照仍保存全卡及 retired 状态，部署检索按允许状态屏蔽退役节点。
    retired = set(result['retired_ids'])
    runner.experience_pool = copy.deepcopy(runner.experience_pool)
    runner.tree = copy.deepcopy(runner.tree)
    for node in runner.experience_pool:
        if node.invariant_id in retired:
            node.status = 'retired'
    for family in runner.tree.all_families():
        for node in family.invariants:
            if node.invariant_id in retired:
                node.status = 'retired'
    rows = result['rows']['filtered']
    metrics = result['summary']['arms']['filtered']
    summary = {'eval_pool_size': len(rows), 'joint_pass': metrics['joint_pass'],
               'joint_pass_rate': metrics['joint_pass'] / len(rows) if rows else 0,
               'abcd': dict(Counter(r['state'] for r in rows)), 'gate_mode': 'global',
               'generation_policy': 'single_generation_no_repair', 'independent_heldout': False,
               'selection_bias': result['summary']['selection_bias'], 'global_gate': result['summary']}
    return {'rows': rows, 'summary': summary, 'gate_report': result}
