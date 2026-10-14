"""训练侧开发对照的配对、调度和历史隔离测试，不调模型。"""
import importlib


def module():
    assert importlib.util.find_spec('methods.sct_trajectory.run_context_ablation'), '消融入口未实现'
    return importlib.import_module('methods.sct_trajectory.run_context_ablation')


def test_balanced_order_is_paired_and_rotated():
    schedule = module().interleaved_jobs([{'index': 1}, {'index': 2}, {'index': 3}], ['a', 'b', 'c'])
    assert [(row['index'], arm) for row, arm in schedule] == [(1,'a'),(1,'b'),(1,'c'),(2,'b'),(2,'c'),(2,'a'),(3,'c'),(3,'a'),(3,'b')]


def test_exact_pairing_and_missing_pairs():
    rows = []
    for i in range(6):
        rows.extend([{'task_id': i, 'arm': 'legacy', 'attempts': [{'joint': False}]},
                     {'task_id': i, 'arm': 'context', 'attempts': [{'joint': True}]}])
    rows.append({'task_id': 99, 'arm': 'context', 'attempts': [{'joint': True}]})
    result = module().summarize(rows)
    pair = result['paired_vs_legacy']['context']
    assert pair['pairs'] == 6 and pair['new_only'] == 6 and pair['legacy_only'] == 0
    assert pair['p_exact_two_sided'] == 0.03125
    assert result['arms']['context']['total'] == 7


def test_historical_modules_do_not_replace_current():
    current = importlib.import_module('methods.sct_trajectory.retriever')
    legacy = module().load_legacy_modules()
    assert legacy['retriever'] is not current
    assert 'pipeline_revision' in legacy['retriever'].__file__
    assert importlib.import_module('methods.sct_trajectory.retriever') is current
    assert legacy['hier_retrieval']._node_text is legacy['retriever']._node_text


def test_existing_output_rejected(tmp_path):
    target = tmp_path / 'existing'
    target.mkdir()
    try:
        module().create_output(target)
    except FileExistsError:
        pass
    else:
        assert False, '不能覆盖已有运行目录'
