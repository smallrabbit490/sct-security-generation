# 实验运行区与产物清理说明

`translation_work/` 是被 `.gitignore` 忽略的本机运行区，保存实验生成代码、逐任务 JSONL、Docker 工作目录、日志、缓存和临时文件。它不是源码目录，也不是正式结果发布目录。

## 推荐目录层次

```text
translation_work/
├─ baseline_runs/<运行名>/<Base或Plus>/       # 九条 baseline 正式运行
├─ sct_runs/<运行名>/<R0、R1、R2或R3>/         # SCT 经验轮次
├─ validation_runs/<运行名>/<语言>/           # 独立 Docker 重验证
├─ diagnostics/<日期>/<主题>/                 # 诊断结果，不作为正式得分
├─ cache/<工具>/                              # 可重建缓存
└─ temp/<运行编号>/                           # 一次性临时文件
```

新的实验不要再把不同用途的目录直接平铺在根下。运行名应包含日期、模型或实验变体，例如 `agents_deepseek_v4_flash_20260904`。

## 正式结果必须保留

`baseline_runs/` 或 `sct_runs/` 中用于论文表格和审计的最终结果应至少包括：

- `rows.jsonl`：逐任务生成代码、脱敏 trace、fidelity、Function/Secure 结果；
- `summary.json`：按方法和语言汇总的指标；
- Markdown 运行报告；
- `run_metadata.json`：commit、数据清单、模型、参数、Docker 镜像和 schema 版本。

正式摘要需要复制到 `results/curated/`，但不能把 key、原始长响应或本地路径复制进去。

## 可删除产物

实验完成后可删除：

- `temp/` 下的一次性文件；
- 已被 `rows.jsonl` 吸收的重复中间 JSON；
- API 原始响应、未脱敏 prompt 和 token 调试文件；
- `cache/` 下可由 Docker 或 Go 重新生成的缓存；
- 已被最新版本替代、且报告已记录失败原因的重试目录；
- 空的 `downloads/`、`logs/`、`outputs/` 目录。

删除前必须确认目标不是唯一的最终结果、唯一的失败证据或复现实验所需的元数据。大目录先列清单，确认路径在 `translation_work/` 内，再优先移入回收站。

## 不得删除或混用

- `data/`、`src/`、`methods/`、`docker/` 中的源码、数据和验证器；
- SCT 每个 `R0–R3` 的门控记录、冻结清单和最终摘要；
- Base/Plus 的正式逐任务结果，直到对应报告归档；
- `chatanywhere_key_check/` 的脱敏状态报告；
- `R0–R3` 方法概念本身，它们不是缓存目录。

清理结束后重新运行单元测试、`git diff --check` 和 key 泄露扫描，并确认正式结果仍可读取。
