# 仓库协作与产物管理规范

本文件是本仓库目录分类、实验产物保存和清理规则的唯一入口。README 负责导航，详细运行区说明见 `docs/translation_work.md`，具体评测定义见 `docs/evaluation_protocol.md`。

周报时间归属以 `docs/research/weekly_reporting_calendar.md` 为准：10月14–21日为一次性首期，随后10月22–28日、10月29日–11月4日，固定周四至周三。每周三总结写作；周中稿不预填未来结果。历史待做保留当周状态，后续计划和当周待做分列，写作日期不改变实验归属。

每周固定提交三种阅读视图：500字以内一页《本周结论与下一步》、完整思路图汇总Word图册（横版）、完整实验周报。思路图册将现有七阶段完整图逐张汇入Word，每张独立一页，保留阶段栏、实验节点、编号、状态、结果、分支和连线，提供目录及实验链接；不改画为四栏摘要图。摘要保留决定性对照数字并直达实验，完整周报每项实验先给结论再给思路、步骤、图表和分析；保留完整数据与当周待做。三者统计截止一致，汉字宋体、字母数字Times New Roman；图册配Markdown原图索引。统一模板入口为`docs/research/templates/CLE-TPL-weekly-submission-v01.md`，摘要v02、图册v02、完整报告v04；每周仅汇入该周截止图，跨周全系列另册，不影响活动实验与自主执行队列。

## 当前科研工作约定（用户2026-10-26要求）

- **2026-10-28最新探针接力规则优先**：按`docs/research/CLE-TODO-20261022-20261028-v09.md`执行。已启动Q学习和功能安全全量继续；其余排队全量先跳过，不因探针通过自动启动。探针及分析自动接力，54题Q探索、82题记忆、57题检索保留各自范围和原扩大条件。跳过不当完成、不解除真实资产依赖；有界入口未实现时先离线接线，不得直接launch全量。后文“通过后完成全量”仅保留为历史科学计划，不覆盖本调度规则。

- **2026-10-28最新减量及实验审查授权优先**：正在运行的Q学习和功能安全全量保持不变；未启动的Q同题回测采用最终K3/Q1全273题、中间三轮同54题，共1416次；五档记忆标签先82题，按预登记工程条件最多追加82题；检索先57题，按覆盖与区间条件最多追加57题。当前待做与叙事计划为`docs/research/CLE-TODO-20261022-20261028-v08.md`（继承v06完整执行规格及v07原因复验）；后续分析追加R01最多6题/12次本地单点复验，不新增实验API调用；后续分类器按留出题Joint选模，P3外部255次暂缓，目标/成本门与独立接线见`configs/cle_scientific_review_20261028/README.md`；减量及扩大条件见`configs/cle_weekly_reduced_20261028/README.md`，正式名单内前缀检查见`configs/cle_experiment_review_20261028/README.md`。新增前缀目前待执行，不增加原预算；同题回测统一修订契约，学习输入不改。保留的主要全量比较不以探针低Joint取消。

- 研究叙事、单思路阶段图及对应计划使用`skills/cle-idea-narrative/SKILL.md`：先写起因、阶段实验、转折、结果分析、结论和下一步，再转图。当前叙事为`docs/research/CLE-STORY-20261028-nine-ideas.md`，执行补充为`docs/research/CLE-TODO-20261022-20261028-v08.md`（继承v06/v07）。每阶段分析后回写叙事并只刷新相关图；图中运行与恢复统一显示“正在运行”，底层记录不改。

- 研究导航使用`docs/research/README.md`；任务来源、实验、文档旧名与标准名、经验资产和架构位置在其`registers/`登记。现有运行目录及原生文件不为整理而改名；后续新实验按升级方案命名。
- **主要问题默认完整全量验证。** 探针只检查技术链路，并计入固定名单；技术通过后完成预先登记的总体、全部条件和重复，不因少量低分、未采用或收益门未过取消主要全量比较。全量范围和资金上限要明确，不自动把所有可选想法扩大成新付费矩阵。
- 区分科学负结果与执行故障。正常模型错误按协议记录；真实传输、环境或落盘故障修复后从已完成前缀继续，不按低成绩重跑。收益门用于结果解释；真实资金上限、凭据安全、隐藏反馈边界及原验证器要求仍保留。
- 旧卡库、Q反馈状态、使用模型与题面/夹具版本分别登记。P3不代替同P7无卡对照；旧四臂Q成绩不代替后来Q快照；同题不同重复不自动共享响应。原始请求、代码、验证与失败证据按当前完整回放要求保留，本节优先于旧的一般性可删除规则。
- 汇报先给关键决定，再用最少必要数字交代：为什么做（老师/学长/用户哪项任务）、完整结果、主要原因、对主线的影响和下一步。术语首次出现简短解释；不只罗列成绩。无实质变化的自动检查保持安静。
- 周报按`docs/research/templates/CLE-TPL-weekly-experiment-report-v04.md`组织：标题为“10月X日-10月X日实验探索报告”，Word大标题居中，汉字用宋体、字母和数字用Times New Roman，图表文字同样遵循；先写本周主线与逐条要求、综合结论及【A1】等实验链接，再在详细实验列表前设“待做实验”，逐项给出名称、原因与步骤列表，使用【T1】等可跳转编号。已完成实验依次写思路、步骤列表、结果图表和整段分析，回答来源要求是否印证、支持范围及可信度，提供返回链接；Markdown与Word内容对应。阶段报告可参考历史主线互引模板v01。简短进度回复保持重点汇报。改编用户定稿另存版本，登记与原名的映射；不覆盖原件或混合统计截止时间。
- 2026-10-27用户已授权本周未完成的必做全量包及后续分析，当前执行清单为`docs/research/CLE-TODO-20261022-20261028-v01.md`，编排为`configs/cle_weekly_full_20261027/execution_plan.json`。先落实F0协议、预算、精确复用和接线，再按允许时段完成固定全量；不逐包反复请示。已完成20261026基础清单不重启，可选跨库Q扩展仍不执行。新大产物放E盘指定运行根，原结果原位保留。

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
| `skills/` | CLE 项目技能源 | 历史工作方法调研形成的可交接技能；仅在任务匹配时加载，不能替代当次实验协议。 |
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

周报统一使用客观实验叙述，隐去老师、学长、本人等人物称谓；保留研究要求、任务事实及结论的证据边界。

周报标题后直接进入实验主线，不设报告周期或版本状态段，不设独立的跨周结转、来源版本说明或报告使用规范；必要的统计截止和证据限制写在相关实验结果处。
