# 仓库协作与产物管理规范

本文件是本仓库目录分类、实验产物保存和清理规则的唯一入口。README 负责导航，详细运行区说明见 `docs/translation_work.md`，具体评测定义见 `docs/evaluation_protocol.md`。

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

## 八、SCT 方法代码注释与可审计性

- 修改或新增 `methods/sct_agent/` 下的代码时，必须添加中文注释或中文 docstring，说明该模块、类或函数在 SCT 流程中的具体用途；不能只复述函数名。
- 每个核心函数的注释至少说明：所属阶段、输入和输出、使用的验证证据、可能的失败类型，以及是否允许修改长期经验库。
- 涉及漏洞—补丁差异分析时，注释应指出代码分别负责不可信输入、敏感操作、触发条件、补丁逻辑、安全 API、后置条件或危险模式中的哪一部分。
- 涉及动态验证时，注释应明确区分编译或语法、功能测试、安全测试、静态安全分析、类型检查、资源限制、超时和异常行为；没有执行的验证项必须记录为“未测量”，不能默认为通过。
- PLT 仅含 Python 样本，训练侧默认使用 `python -I` 本地临时子进程、超时和临时目录，不启动 Docker；该沙盒是轻量运行隔离而非 Docker 级安全边界，CodeSecEval 或 C++/Go harness 仍按验证器要求使用 Docker。
- 涉及候选经验门控时，注释应明确区分质量门控、独立有效性门控和 `H_pass` 回归门控，并说明候选经验在何时可以晋升、修订、拒绝或保持临时状态。
- 涉及数据和反馈流时，注释必须标明 `D_init`、`D_grow`、`D_gate`、`H_pass` 与 CodeSecEval Base/Plus 的边界；禁止用最终测试反馈生成或更新经验。
- 禁止为了缩短代码把关键流程压成难以审计的单行语句。阶段切换、门控决策、异常处理、冻结和结果写入必须使用清晰的变量名与分段注释。
- 注释不得包含 API key、原始未脱敏 prompt、隐藏测试输入、答案常量或其他敏感信息；注释描述的是方法职责和安全边界，不是实验秘密。
