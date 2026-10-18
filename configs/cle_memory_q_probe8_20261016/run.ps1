$py = "translation_work/temp/cle_memory_q_env/Scripts/python.exe"
$configRoot = "configs/cle_memory_q_probe8_20261016"
$runRoot = "translation_work/diagnostics/20261016/cle_memory_q/probe8_cwe_shuffle"
$learnRoot = "translation_work/diagnostics/20261016/cle_memory_q/full_dgrow"
& $py "$configRoot/prepare.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $py -u -m methods.cle_ablation.run_memory_q --stage compare `
  --memory "$learnRoot/frozen/m_star_q.jsonl" --calibration "$configRoot/calibration.compare.json" `
  --pools configs/cle_memory_q_autonomous_20261015/pools.recovered.json `
  --manifest "$configRoot/manifest.json" --split development --arms Q1 Q2 Q3 `
  --shuffle-scope cwe --shuffle-seed 20261015 --thinking disabled `
  --max-tokens 4096 --lambda-q 0.5 --workers 4 --out "$runRoot/compare"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $py -m methods.cle_ablation.report_memory_q_probe --root $runRoot `
  --out results/curated/cle_memory_q_probe8_20261016
