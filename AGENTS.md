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

## 九、Baseline 怎么跑（九条方法的唯一入口）

### 9.1 唯一 runner

九条 baseline（4 条 Prompt + 5 条 Agent）都由**同一个**入口运行：

```text
methods/workflow_baselines/run_true_agent_workflows.py
```

| 需求 | 参数 |
|---|---|
| 四条 Prompt baseline（Greedy / Greedy+Secure / CoT / CoT+Secure） | `--only-traditional` |
| 五条 Agent baseline（AutoSafeCoder / RA-Gen / SWE-Agent / AgentCoder / SecAwareCoder） | `--only-agents` |
| 九条全跑 | 两个都不加 |

`methods/prompting_baselines/run_prompt_baseline.py` **只是桩**（只打印提示词，不调模型、
不跑 Docker）。它的四条方法真实实现在上面的 runner 里（`direct_workflow`）。
不要把它当成 Prompt baseline 的运行入口。

### 9.2 冒烟命令（跑全量前先过这一步）

```powershell
$PY = "D:/ANACONDA/python.exe"   # 需要装了 openai 的解释器
& $PY tools/vhdx_watchdog.py --label smoke --max-containers 16 --interval 2 -- `
  $PY methods/workflow_baselines/run_true_agent_workflows.py `
    --subsets Base --languages python cpp go --limit 1 `
    --out-name smoke_20260918 `
    --model deepseek-v3.2 --max-tokens 2048 --temperature 0 `
    --retries 1 --workers 2 --only-traditional
```

通过判据（缺一不可）：

- `tools/vhdx_watchdog.py` 判定 **PASS**（见 9.4）；
- `rows.jsonl` 条数 = 方法数 × 语言数 × `--limit`；
- 每行 `secure.code` 非空、`workflow_completed=true`；
- Agent 行额外要求 `fidelity_passed=true`；
- 不允许出现 `error_type=environment_error`（那是环境事故，不是模型结果）。

### 9.3 输出位置与必存文件

```text
translation_work/baseline_runs/<run-name>/<subset>/
├─ rows.jsonl                       # 逐任务：代码、脱敏 trace、fidelity、Function/Secure
├─ summary.json                     # 按方法/语言汇总
├─ true_agent_workflow_report.md    # 人工可读报告
├─ run_metadata.json                # commit、模型、参数、Docker 镜像、凭据来源、输出 schema
└─ true_agent_workflows/<lang>/<method>.jsonl   # 逐方法缓存（断点续跑用）
```

`run_metadata.json` 是第三节的硬要求，runner 会自动写；其中 `credential_source`
只记录凭据**来源标签**（如 `local:apikey.txt`），不含 key 本身。

### 9.4 Docker 纪律（硬约束，禁止绕过）

**目标：评测期间 `docker_data.vhdx` 水位不涨。** 2026-09-17 的事故（vhdx 从
14.9 GB 涨到 67.72 GB）根因是"每个任务 `docker run --rm` 新建容器 + 中途强杀留下孤儿容器"。
现在的执行层（`src/translation_pipeline/persistent_container.py`）已经改成常驻容器池，
以下纪律是配套要求：

1. **所有 Docker 验证必须走常驻容器执行层**，不要在评测代码里新写 `docker run`。
   新增验证器请复用 `run_docker_task` / `ContainerSpec`。
2. **池大小必须 >= 并发数**。runner 已自动设
   `SAFECODER_DOCKER_POOL_SIZE = max(--workers, 1)`。池耗尽会抛 `RuntimeError`
   并被折算成 `environment_error`，把并发配置问题伪装成环境故障。
3. **跑前必须清理残留池容器**。runner 的 `main()` 会自动调
   `cleanup_stale_containers()`；手写脚本时也要自己调，否则残留容器会挡住 vhdx 压缩。
4. **每次大批量运行都要用 `tools/vhdx_watchdog.py` 包裹**，它会在运行期间连续采样
   vhdx 文件大小与容器数，并给出可引用的判定报告
   （`translation_work/diagnostics/vhdx_watchdog_<label>.json`）。
   判定项：vhdx 增量 ≤ 上限、容器数回落到 0、峰值出现在收尾之前、无残留容器。
5. **强杀不等于泄漏**。即使进程被 SIGKILL，泄漏也只限于池内那几个容器（有界），
   且 `cleanup_stale_containers()` 能收掉；实测此时 vhdx 仍然不涨。
   但**不要**把"强杀后残留"当成正常状态，下次运行前必须清理。
6. **JUnit / juliet-support / Mockito 等工具链以只读方式挂载**
   （`ContainerSpec.readonly_mounts`），候选代码不得改写评测工具。
7. **只挂 `translation_work/`**，绝不挂仓库根——`local_secrets/` 与 `.env.local`
   里有 API key。

### 9.5 三个会静默让结果失真的陷阱（都已修复，勿回退）

| 陷阱 | 症状 | 正确做法 |
|---|---|---|
| harness 查找只认历史 `sandbox_dir` | C++/Go 全部落到 `compile_run_only_no_security_credit`，**不给任何安全学分**，表面看像"模型全写错" | 必须有回退：`data/harnesses/<subset>/<language>/<track>/<task_id>/main.<ext>`。见 `run_language_method_matrix._source_path_from_saved_harness` |
| 推理模型吃光 `max_tokens` | `raw` 为空、`code` 为空、Function/Secure 全 False，像"模型不会写代码" | 用 `deepseek-v3.2`（非推理，`reasoning_tokens=0`）；用 v4 系列必须把 `--max-tokens` 提到 4096+ |
| 凭据解析顺序被 `.env` 快照遮蔽 | 403 余额不足 | 顺序固定为：环境变量 → `apikey.txt` → `.env` 快照兜底。`.env` 只是派生快照，可能已过期 |

**通用教训**：验证链路里任何"找不到就降级"的分支都必须**显式记录降级原因**并
在冒烟检查里断言不允许出现，否则会静默产出看似合理、实则全零的结果。

### 9.6 PLT Java 评测（`methods/secodeplt_eval/java_executor.py`）

PLT Java 不走上面的 runner，走独立执行器。要点：

- 数据在 `data/external/secodeplt/hf_full/jsonl/java_secure_coding-*.jsonl`
  （924 条 Juliet，869 条带单测；**单测在 `meta_data.unit_test` 里**，不在顶层字段）。
- 不用 Maven：`javac` + `junit-platform-console-standalone-1.9.3.jar`，
  报告走 JUnit 的 `--reports-dir` XML（比在 Maven stdout 上做正则稳）。
- 前置资源（都在仓库内，无需联网）：
  `translation_work/downloads/java/`（JUnit jar + `lib/` 下的 Mockito 及依赖）、
  `data/external/secodeplt_github/executor_docker/docker/juliet-java-env/juliet-support/`。
- 容器基座用本机已有的 JDK 17 镜像 `secevo-java-js-baseplus-validator:current`；
  也可用 `docker/java-validator/Dockerfile` 构建干净镜像。
- 编译失败 / 类加载失败必须记成 `measured=False`，**不得**与 `score=0` 混同。
- 回归脚本：`translation_work/temp/e2e_persistent_container_20260917/e2e_java_real.py`
  （真实数据分层抽样）与 `e2e_java_positive.py`（正向对照）。

### 9.7 凭据

按 README「ChatAnywhere API key 存储位置」的顺序解析。默认模型是
`deepseek-v3.2`。`local_secrets/` 已在 `.gitignore` 内，**任何情况下不得提交**。
