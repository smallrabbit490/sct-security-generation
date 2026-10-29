"""R01保存前缀的3例单点诊断，共6次原验证，不调用模型。"""
import difflib
import json
from pathlib import Path
from time import perf_counter

from configs.cle_weekly_full_20261027.prepare import configure_validation
from methods.sct_trajectory.closed_loop import validate_and_state
from methods.sct_trajectory.replay_journal import write_json

RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
OUT = RUN / 'FFS/analysis/single_edit_review/prefix_20261029'


def main():
    if OUT.exists():
        raise RuntimeError('existing_diagnostic_preserved_no_automatic_retest')
    queue = json.loads((RUN / 'impact_radius_20261028/IR01/case_review_queue.json').read_text(encoding='utf-8'))
    tasks = json.loads((RUN / 'FQ_GATE/inputs_v3/tasks.json').read_text(encoding='utf-8'))
    specs = [('128', 'BFS', ', valid_path_regex=None', '', '恢复读取宿主正则对象，预测功能恢复且安全保留。'),
             ('353', 'BM', 'secret_key = b""\n', '', '撤销对宿主密钥的覆盖，预测功能恢复且安全保留。'),
             ('359', 'BM', 'secret_key = None\n', '', '撤销对宿主密钥的覆盖，预测功能恢复且安全保留。')]
    cases = []
    for tid, arm, old, new, prediction in specs:
        item = next(x for x in queue if x['task_id'] == tid)
        source = Path(item['source_' + arm])
        row = json.loads(source.read_text(encoding='utf-8'))
        code = row['final']['code']
        assert code.count(old) == 1
        modified = code.replace(old, new, 1)
        folder = OUT / tid
        folder.mkdir(parents=True)
        (folder / 'original.py').write_text(code, encoding='utf-8')
        (folder / 'modified.py').write_text(modified, encoding='utf-8')
        (folder / 'change.diff').write_text(''.join(difflib.unified_diff(code.splitlines(True), modified.splitlines(True))), encoding='utf-8')
        cases.append({'task_id': tid, 'condition': arm, 'repeat': row['repeat'],
            'source': str(source), 'prediction': prediction, 'original_recorded': row['final']['validation'],
            'selection': '已阅读12例代表代码后的可隔离宿主依赖改写；按题号；并非完整FFS总体原因抽样',
            'folder': str(folder)})
    write_json(OUT / 'predictions_before_validation.json', {'status': 'frozen_before_test', 'cases': cases,
        'local_validation_cap': 6, 'experiment_HTTP': 0, 'formal_results_modified': False,
        'repeat_note': '本批三个案例均非两重复同向Joint优势，分别验证该题该次局部机制；不估计总体占比。'})
    configure_validation()
    for item in cases:
        folder = Path(item['folder'])
        for name in ('original', 'modified'):
            begin = perf_counter()
            evidence, state = validate_and_state(tasks[item['task_id']], (folder / (name + '.py')).read_text(encoding='utf-8'), timeout=20)
            item[name] = {'state': state, 'evidence': evidence, 'elapsed_seconds': perf_counter() - begin}
            write_json(folder / (name + '_validation.json'), item[name])
        before, after = item['original']['state'], item['modified']['state']
        item['judgment'] = ('局部支持：原功能失败复现，单点改动恢复Joint。' if before == 'C' and after == 'A'
                            else '安全取舍：功能恢复但安全失败。' if before == 'C' and after == 'B'
                            else '未复现原始失败。' if before == 'A'
                            else '本次单点改动未恢复Joint；完整验证结果保留。')
        write_json(OUT / 'cases.json', {'status': 'partial_in_progress', 'cases': cases})
    write_json(OUT / 'cases.json', {'status': 'completed_prefix', 'cases': cases, 'local_validations': 6, 'experiment_HTTP': 0})
    text = '# 宿主依赖改写的三例单点复验\n\n保存代码前缀诊断，原正式成绩不改。\n\n'
    for item in cases:
        text += f"- {item['task_id']}：{item['original']['state']} → {item['modified']['state']}；{item['judgment']}\n"
    text += '\nA=功能安全都通过；B=仅功能通过；C=仅安全通过；D=两者失败。结果只解释该题该次改动，不等于证明分栏或Q导致该错误。\n'
    (OUT / 'summary.md').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
