"""原生分析完成后的零API交付：回写研究叙事、相关图和阶段收据。"""
import argparse
import json
from pathlib import Path
import re
import shutil

from . import app
from .autonomy import AutonomousPlan

FIELDS = {'source_requirement':'来源要求', 'stage_reason':'阶段理由', 'results':'实测结果',
          'analysis':'结果分析', 'conclusion':'结论', 'next_step':'下一步'}
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')


def publish(task_id, draft_path, run=RUN):
    from tools import build_cle_horizontal_ideas as diagrams

    manager = AutonomousPlan(run, persist=False)
    task = manager.definitions[task_id]
    contract = task['narrative']
    receipt_path = manager.evidence_path(contract['receipt'])
    if receipt_path.is_file():
        if manager.native_done(task, app.Collector(run).collect(app.process_inventory())):
            return app.read_json(receipt_path)
        raise ValueError('existing_delivery_requires_inspection')
    if manager.omitted_by_protocol(task):
        raise ValueError('omitted_task_has_no_experiment_delivery')
    snapshot = app.Collector(run).collect(app.process_inventory())
    if not manager.native_evidence_done(task, snapshot):
        raise ValueError('native_analysis_or_case_review_not_complete')
    draft = app.read_json(Path(draft_path))
    if draft.get('task_id') != task_id or set(draft.get('sections', {})) != set(contract['sections']):
        raise ValueError('delivery_task_or_sections_mismatch')
    evidence = draft.get('evidence', [])
    if not evidence or any(not manager.evidence_path(p).is_file() for p in evidence):
        raise ValueError('delivery_result_evidence_missing')
    for value in draft['sections'].values():
        if any(not isinstance(value.get(k), str) or not value[k].strip() for k in FIELDS):
            raise ValueError('delivery_requires_six_explanations')
        diagram = value.get('diagram', {})
        if not diagram.get('answer') or not (diagram.get('tasks') or diagram.get('cards')):
            raise ValueError('delivery_requires_actual_diagram_text')

    destination = receipt_path.parent
    destination.mkdir(parents=True, exist_ok=True)
    story_path = app.ROOT / contract['source']
    story = story_path.read_text(encoding='utf-8')
    updates_path = manager.control / 'deliveries/diagram_updates.json'
    updates = app.read_json(updates_path, {})
    stage = manager.control / 'deliveries' / task_id
    stage.mkdir(parents=True, exist_ok=True)
    app.write_json(stage / 'delivery_draft.json', draft)
    (stage / 'narrative_before.md').write_text(story, encoding='utf-8')
    for anchor, value in draft['sections'].items():
        begin, end = f'<!-- {task_id} begin -->', f'<!-- {task_id} end -->'
        block = begin + '\n\n' + f'### {task["title"]}（{snapshot["time"]}）\n\n'
        block += '\n\n'.join(f'**{label}。** {value[key]}' for key,label in FIELDS.items())
        block += '\n\n' + end + '\n\n'
        pattern = rf'(?s)({re.escape(begin)}.*?{re.escape(end)}\s*)'
        if re.search(pattern, story):
            story = re.sub(pattern, lambda _:block, story)
        else:
            marker = f'<a id="{anchor}"></a>'
            if marker not in story:
                raise ValueError('narrative_anchor_missing:' + anchor)
            start = story.index(marker)
            following = story.find('<a id="idea', start + len(marker))
            index = following if following >= 0 else len(story)
            story = story[:index].rstrip() + '\n\n' + block + story[index:]
        number = str(int(anchor.removeprefix('idea')))
        prior = updates.get(number, {})
        current = value['diagram']
        updates[number] = {**prior, **current,
            'tasks':{**prior.get('tasks', {}), **current.get('tasks', {})},
            'cards':{**prior.get('cards', {}), **current.get('cards', {})}}

    # 先验证图中文字所属的思路，避免写到另一个分支。
    specs = diagrams.specifications()
    diagrams.apply_updates(specs, {k:{} for k in diagrams.CARD_TEXT}, updates)
    app.write_json(updates_path, updates)
    story_path.write_text(story, encoding='utf-8')
    (stage / 'narrative.md').write_text(story, encoding='utf-8')
    statuses = app.read_json(manager.control / 'status.json', {}).get('tasks', [])
    diagram_snapshot = {'time':snapshot['time'], 'workers':snapshot['workers'],
        'packages':snapshot['packages'],
        'tasks':[{**t, 'status':'completed'} if t['id']==task_id else t for t in statuses]}
    app.write_json(stage / 'snapshot.json', diagram_snapshot)
    numbers = [int(s.removeprefix('idea')) for s in contract['sections']]
    diagrams.main(stage / 'snapshot.json', numbers, updates_path)
    files = [stage / 'narrative.md', stage / 'delivery_draft.json', stage / 'snapshot.json']
    for number in numbers:
        stem = specs[number-1]['stem']
        for suffix in ('.svg', '.png'):
            source = diagrams.OUT / (stem + suffix)
            target = stage / source.name
            shutil.copy2(source, target)
            files.append(target)
    receipt = {'task_id':task_id, 'status':'completed', 'sections':contract['sections'],
        'completed_at':app.now(), 'experiment_API_calls':0,
        'evidence':[str(manager.evidence_path(p)) for p in evidence] + list(map(str,files))}
    app.write_json(receipt_path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['publish'])
    parser.add_argument('--task', required=True)
    parser.add_argument('--draft', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.task, args.draft), ensure_ascii=False))


if __name__ == '__main__':
    main()
