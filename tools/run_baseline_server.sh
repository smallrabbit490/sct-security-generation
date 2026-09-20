#!/usr/bin/env bash
# 服务器侧 baseline 运行启动脚本（第一项验证跑）
#
# 目标：deepseek-v4.1-flash × Base × python × 9 条方法（4 Prompt + 5 Agent）全跑。
# 用途：确认输出形态与表格口径正确，再铺开到 5 模型 × 2 subset × 3 语言。
#
# 为什么包一层看门狗：评测期间要保证 docker_data.vhdx 不涨，
# 看门狗全程采样水位与池容器数，跑完给出可引用的判定报告。
set -euo pipefail

cd "$(dirname "$0")/.."

RUN_NAME="${1:?用法: run_baseline.sh <run-name> <model> [max-tokens] [workers] [subsets] [languages] [limit]}"
MODEL="${2:?缺少 model}"
MAX_TOKENS="${3:-4096}"
WORKERS="${4:-6}"
SUBSETS="${5:-Base}"
LANGUAGES="${6:-python}"
LIMIT="${7:-0}"

LOG="$HOME/baseline_${RUN_NAME}.log"

echo "运行名   : $RUN_NAME"
echo "模型     : $MODEL"
echo "max_tokens: $MAX_TOKENS"
echo "workers  : $WORKERS"
echo "subsets  : $SUBSETS"
echo "languages: $LANGUAGES"
echo "limit    : $LIMIT（0=全部）"
echo "日志     : $LOG"
echo

nohup .venv/bin/python tools/vhdx_watchdog.py \
    --label "$RUN_NAME" \
    --max-containers 16 \
    --interval 5 \
    -- \
    .venv/bin/python methods/workflow_baselines/run_true_agent_workflows.py \
        --subsets $SUBSETS \
        --languages $LANGUAGES \
        --limit "$LIMIT" \
        --out-name "$RUN_NAME" \
        --model "$MODEL" \
        --max-tokens "$MAX_TOKENS" \
        --temperature 0 \
        --retries 2 \
        --workers "$WORKERS" \
    > "$LOG" 2>&1 &

echo "已启动，PID=$!"
