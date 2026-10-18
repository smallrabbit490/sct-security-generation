$base = "translation_work/diagnostics/20261015/cle_memory_q/autonomous_reproduction"
$manifest = "configs/cle_memory_q_autonomous_20261015/manifest.json"
$pools = "configs/cle_memory_q_autonomous_20261015/pools.recovered.json"
python -m methods.cle_ablation.run_memory_q --stage learn --memory docs/cle_evidence_package_20261015/experience_pool_1939.jsonl --pools $pools --out "$base/learn" --manifest $manifest --split learning --thinking disabled --workers 1
python -m methods.cle_ablation.run_memory_q --stage compare --memory "$base/learn/frozen/m_star_q.jsonl" --calibration "$base/learn/calibration.json" --pools $pools --out "$base/compare" --manifest $manifest --split development --arms Q0 Q1 Q2 Q3 --thinking disabled --workers 4
python -m methods.cle_ablation.report_memory_q --root $base
