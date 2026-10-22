$runRoot = "translation_work/diagnostics/20261016/cle_memory_q/full_dgrow"
$manifest = "configs/cle_memory_q_full_dgrow_20261016/manifest.json"
# 首次准备只执行一次；已有运行目录不要重跑preflight。
python -m methods.cle_ablation.run_memory_q_full --stage preflight --out $runRoot --manifest $manifest --workers 8
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m methods.cle_ablation.run_memory_q_full --stage learn --out $runRoot --manifest $manifest --workers 8
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m methods.cle_ablation.report_memory_q_full --root $runRoot --out results/curated/cle_memory_q_full_dgrow_20261016
