"""从精简真实得分重算原生统计；不调用模型、不执行候选代码。"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from methods.direction_screening.protocol import summarize
from methods.cle_ablation.report_memory_q import paired_effect

base=Path(__file__).parent
rows=[json.loads(line) for line in (base/'paired_outcomes.jsonl').read_text(encoding='utf-8').splitlines()]
stored=json.loads((base/'summary.json').read_text(encoding='utf-8'))
recomputed=summarize(rows,'Q1')
assert recomputed['arms']==stored['arms']
assert recomputed['paired']==stored['paired_complete_measured']
effect=paired_effect(rows,'Q1','Q2')
assert effect['conservative_95_ci_percentage_points']==stored['primary_full_denominator_Q2_vs_Q1']['conservative_95_ci_percentage_points']
print(json.dumps({'status':'pass','rows':len(rows),'Q2_vs_Q1':effect,'model_calls':0},ensure_ascii=False,indent=2))
