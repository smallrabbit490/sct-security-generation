# 仓库协作与产物管理规范

本文件是本仓库目录分类、实验产物保存和清理规则的唯一入口。README 负责导航，具体评测定义见 `docs/evaluation_protocol.md`。

## 一、目录职责

| 目录 | 类型 | 规则 |
|---|---|---|
| `data/SecEvoBasePlus/` | 正式数据 | Base/Plus 数据集；不得删除或混入临时结果。 |
| `data/harnesses/` | 正式测试夹具 | C++/Go 等语言的功能与安全 harness；与数据集一一对应。 |
| `data/external/` | 外部数据 | 经验提取和补充分析专用；不得直接计入正式得分。 |
| `src/translation_pipeline/` | 核心源码 | 验证器、模型接口、质量指标和运行脚本；不得放实验输出。 |
| `methods/prompting_baselines/` | Prompt 方法源码 | 四条单请求 baseline。 |
| `methods/workflow_baselines/` | Agent 方法源码 | 五条多阶段 workflow、fidelity 合约和统一入口。 |
| `methods/sct_agent/` | SCT 方法源码 | 经验卡、检索、进化和门控实现。 |
| `methods/legacy_prompt_adapters/` | 历史兼容源码 | 仅用于旧结果回放；不能冒充正式 Agent baseline。 |
| `configs/` | 无密钥配置 | 只放可提交配置；key 放在 `.env.local` 或 `local_secrets/`。 |
| `docker/` | 镜像定义 | Dockerfile 和验证器构建上下文。 |
| `docs/` | 中文实验文档 | 协议、复现、审计、限制和数据来源。 |
| `results/curated/` | 精简结果 | 只放小型、脱敏、标注完整的最终摘要。 |
| `translation_work/` | 忽略的运行区 | 所有生成代码、逐任务 JSONL、日志、缓存和临时容器目录。禁止提交。 |

## 二、translation_work 子目录命名

新的实验必须使用以下层次，不再把不同用途的目录平铺混在一起：

```text
translation_work/
├─ baseline_runs/<run-name>/<subset>/       # 九条 baseline 正式运行
├─ sct_runs/<run-name>/<round>/             # SCT R0/R1/R2/R3 运行
├─ validation_runs/<run-name>/<language>/   # 独立 Docker 重验证
├─ diagnostics/<date>/<topic>/              # 可复现诊断，不作为正式得分
├─ cache/<tool>/                             # 可重建缓存
└─ temp/<run-id>/                            # 一次性临时文件
```

`run-name` 应包含日期、模型或实验变体，例如 `agents_deepseek_v4_flash_20260904`。`subset` 使用 `Base` 或 `Plus`，语言目录使用 `python`、`cpp`、`go`、`java`、`javascript`。

## 三、每次 baseline 运行必须保存什么

正式运行目录至少包含：

- `rows.jsonl`：逐任务方法、生成代码、脱敏 trace、fidelity、Function/Secure 结果和终态错误；
- `summary.json`：按方法/语言汇总的指标；
- `true_agent_workflow_report.md`：人工可读报告；
- `run_metadata.json`：commit、数据清单、模型、参数、Docker 镜像、输出 schema。

五条 Agent 必须额外检查 `workflow_completed` 和 `fidelity_passed`；四条 Prompt 的 fidelity 为“不适用”。代码生成失败和评测失败要保留结构化原因，不能只写一个布尔值。

## 四、哪些产物可以删除

### 每次实验结束即可删除

- `translation_work/temp/<run-id>/`；
- 原始 API 响应、未脱敏 prompt、临时 token 调试文件；
- 已写入 `rows.jsonl` 后的重复中间 JSON；
- 已确认失败且没有审计价值的单任务重试目录。

### 运行结束并确认报告后可删除

- `translation_work/cache/` 下可由 Docker/Go 重新生成的缓存；
- `diagnostics/` 中已被审计报告引用、但不再需要复核的重复副本；
- 同一实验族中较早的失败版本，前提是最新版本和失败原因已记录。

### 默认必须保留

- `baseline_runs/` 中用于论文表格或审计的最终 `rows.jsonl`、`summary.json` 和报告；
- `sct_runs/` 中每个 R0–R3 的门控记录、冻结清单和最终摘要；
- `validation_runs/` 中作为当前验证器基线的最终汇总；
- 正式数据、harness、源码、配置、审计文档和 DOCX 规范原件。

删除前必须先检查文件内容，确认不是唯一的最终结果、唯一的失败证据或复现实验所需的元数据。大目录删除使用清单，目标必须解析到 `translation_work/` 内；优先移入回收站，不直接删除用户仓库外的内容。

## 五、实验后清理流程

1. 先生成目录清单：记录路径、文件数、大小和用途。
2. 分类为“保留、待确认、可删除”，不得凭目录名猜测。
3. 检查最终报告是否引用待删除文件。
4. 只删除已确认的可删除项，并核验目标在 `translation_work/` 内。
5. 清理后重新扫描，确认正式结果仍可读取、没有 key、没有孤立临时目录。
6. 在对应中文文档中记录保留位置和删除范围。

## 六、禁止事项

- 不得把 `R0–R3` 当作目录或缓存删除；它们是 DOCX 正式方法轮次。
- 不得把 Base/Plus 的最终测试失败反馈给 SCT 经验生成或门控。
- 不得提交 API key、`.env.local`、原始长日志、Docker VHDX、构建缓存或未脱敏响应。
- 不得将 `legacy_prompt_adapters` 的单 prompt 结果写成官方 Agent workflow 结果。
- 不得用一次成功 API 响应替代代码提取、Docker 功能测试和安全测试证据。

## 七、文档语言与层级

- 根目录 `README.md` 是唯一总导航，按“项目概览 → 数据 → 评测协议 → 环境复现 → 方法审计”递进。
- `docs/*.md` 是面向用户的中文说明；新增实验规则先写入对应主题文档，再在 README 建立链接。
- `docs/superpowers/plans/` 和 `docs/superpowers/specs/` 是开发过程记录，可以保留英文原文，不作为项目运行说明；不要把其中的临时计划当成正式协议。
- `data/external/` 下的第三方 `README.md` 和 `LICENSE.md` 属于上游材料，除非许可证允许，不改写其原文；本仓库的中文说明放在 `docs/external_dataset_provenance.md`。
