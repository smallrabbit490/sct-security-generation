"""仅用精简CSV/Q表核对结果计数；零API，不重新运行F/S验证。"""
import csv
import json
from pathlib import Path

root=Path(__file__).resolve().parent
summary=json.loads((root/'summary.json').read_text(encoding='utf-8'))
with (root/'task_scores.csv').open(encoding='utf-8-sig',newline='') as stream:
    rows=list(csv.DictReader(stream))
values=json.loads((root/'learned_q_values.json').read_text(encoding='utf-8'))['values']
actual={k:sum(r[k]=='True' for r in rows) for k in ('functional','security','joint','measured','first_joint')}
actual.update(n=len(rows),errors=sum(bool(r['workflow_error']) for r in rows),
              calls=sum(int(r['calls']) for r in rows),total_tokens=sum(int(r['total_tokens']) for r in rows))
for key,value in actual.items():
    assert summary['arms']['Q0'][key]==value,(key,value)
assert len({r['task_id'] for r in rows})==len(rows)==summary['tasks']
assert len({r['family_id'] for r in rows})==summary['families']
assert len(values)==summary['Q_learning']['visited_cards']
assert sum(v['q_visits'] for v in values)==summary['Q_learning']['positive_updates']+summary['Q_learning']['negative_updates']
assert sum(v['independent_families']>=2 for v in values)==summary['Q_learning']['cards_two_independent_families']
print(json.dumps({'status':'pass','training_tasks':len(rows),'families':summary['families'],
    'learning_only':True,'model_calls':0,'F_S_Joint_recomputed':actual,
    'visited_cards':len(values)},ensure_ascii=False,indent=2))
