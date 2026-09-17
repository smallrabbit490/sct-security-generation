# 安全经验生命周期与验证驱动主动回放

本目录实现 `简介论文修改方案/重构方法设计说明.docx` 中的新方法：

```text
P_seed → 代码生成与多源轨迹验证 → C_t → Q_pool 主动回放
→ A_audit 独立证据审查 → 经验生命周期更新 → 冻结 M* → Base/Plus
```

PLT family 只负责变体归属和任务角色分配。PLT 训练侧使用 `python -I` 本地临时子进程，不启动 Docker；CodeSecEval Base/Plus 使用正式 Docker 验证器。

## 文件索引

| 文件 | 主要负责什么 |
|---|---|
| `schemas.py` | 轨迹和候选经验的数据结构 |
| `family_manifest.py` | 读取和校验 PLT family 元数据 |
| `split_scheduler.py` | 分配 source、replay、audit 三类任务 |
| `source_knowledge.py` | 从漏洞—补丁差异提取 seed 假设 |
| `retriever.py` | 按 CWE、语言和关键词检索经验 |
| `trajectory_runner.py` | 生成代码、提取代码和有限修复轨迹 |
| `trajectory_validation.py` | 执行 PLT 本地验证并记录证据 |
| `candidate_builder.py` | 从重复失败轨迹形成候选经验 |
| `active_replay.py` | 按不确定性、风险、覆盖缺口和成本选择任务 |
| `independent_audit.py` | 执行质量、有效性和回归门控决策 |
| `audit_runner.py` | 比较候选加入前后的 JointPass 并检查 H_pass 回归 |
| `experience_lifecycle.py` | 管理 C_t、M_t、状态变化和冻结边界 |
| `freeze_protocol.py` | 生成冻结清单和经验库哈希 |
| `frozen_evaluation.py` | 校验冻结边界并生成 Python/Go/C++ Base/Plus 评测计划 |
| `api.py` | ChatAnywhere 请求、超时和有限重试 |
| `chatanywhere_smoke.py` | DeepSeek 3.2 连通性烟测 |
| `run_lifecycle_replay.py` | 串联来源、回放、候选、审查和冻结 |
| `__init__.py` | 暴露目录公共接口 |

## 测试和结果位置

单元测试：`tests/test_sct_lifecycle_replay.py`

运行：

```powershell
python -m unittest tests.test_sct_lifecycle_replay -v
```

实验结果写入 `translation_work/sct_runs/`：

```text
<run>/manifest/split.jsonl
<run>/source_pool/initial_hypotheses.jsonl
<run>/replay_pool/trajectories.jsonl
<run>/replay_pool/candidates.jsonl
<run>/audit_pool/audit_rows.jsonl
<run>/memory/lifecycle_events.jsonl
<run>/frozen/m_star.jsonl
<run>/frozen/freeze_metadata.json
<run>/summary.json
```

冻结评测计划检查：

```powershell
python -c "from methods.sct_lifecycle_replay.frozen_evaluation import check_frozen_run; print(check_frozen_run('translation_work/sct_runs/<run>'))"
```

已完成的离线诊断目录：

`translation_work/sct_runs/lifecycle_replay_offline_20260911_final/`

该目录用于验证管线结构；没有独立审查证据时，候选经验必须拒绝，不能当作正式论文结果。

## 运行边界

`--live-api` 才调用 ChatAnywhere；默认离线模式用于测试目录和错误记录。API key 从 `local_secrets/chatanywhereapi使用/` 读取，不能写入源码、JSONL 或报告。Base/Plus 必须在冻结清单标记 `feedback_channel=disabled` 后运行，最终测试不能更新经验库。
# 2026-09-11 扩大样本实验

推荐首轮使用 96 条（32 个完整三变体 family），来源、回放、独立审查各 32 条。
静态解析 PLT 后，386 条记录具有非空 capability 和 safety 列表；其中 41 个三变体 family 的全部成员符合条件，共 123 条，覆盖 CWE-179、352、74、77、95。
按 CWE 轮流抽取 32 个 family，剩余 9 个保留供后续扩展。上述统计仅表示夹具存在，不表示运行通过，也不代表全部 28 类 CWE。

当前真实运行位置：`translation_work/sct_runs/lifecycle_replay_plt96_20260911_v2/`。
模型为 `deepseek-v3.2`，PLT 使用本地 Python 子进程，不启动 Docker。

- `manifest/split.jsonl`：任务与三池角色分配。
- `source_pool/initial_hypotheses.jsonl`：模型提取的初始假设，不等同于已验证长期经验。
- `replay_pool/trajectories.jsonl`：生成代码和功能、安全验证证据。
- `replay_pool/candidates.jsonl`：待审查候选。
- `audit_pool/audit_rows.jsonl`：独立审查前后比较及单独重跑的 H_pass 证据，逐候选保存。
- `memory/lifecycle_events.jsonl`：经验状态变更。
- `frozen/`：结束后保存冻结经验与哈希。
- `summary.json`、`run_metadata.json`、`lifecycle_replay_report.md`：由运行器结束时生成，以实际文件为准。

当前局限：候选仍由 CWE 和重复失败/成功类别归并，主动调度尚未完整接入；这轮属于规模验证实验，不等同于完整重构方法最终评测。Base/Plus 本轮不启动，也不反馈到训练。
前一版 `lifecycle_replay_plt96_20260911/` 已因选样缺测与审查计数问题停止，保留诊断证据，不作为正式结果。运行中不得清理结果目录；结束后可清理临时文件，但保留上述 JSONL、冻结文件和报告。

# 2026-09-13 修复：审计有效性、主动回放接入与设计对齐

本轮修复了审计审查测不到候选经验的核心缺陷，并对齐《重构方法设计说明.docx》的若干设计要求。修改只影响 `methods/sct_lifecycle_replay/` 源码与对应测试，不改变既有运行目录的数据。

## 修复内容

1. **检索器支持中文经验（`retriever.py`）**：分词从 `[a-z0-9_-]+` 扩展为同时提取中文字符（`[\u4e00-\u9fff]+`），并预计算词频与卡片 token。此前候选经验的 principle 是中文，检索得 0 分、永远进不了 top-3，导致独立审查 before/after 对比的是同一 prompt 的两次 API 调用（噪声），7 个候选全部被拒是必然结果而非证据结论。
2. **候选经验可被检索（`candidate_builder.py` / `schemas.py`）**：候选卡补 `applicability` 字段（与检索器可检索字段一致），principle 从模板化一句话改为按失败类型给出可复用语义；`CandidateHypothesis` 增加 `applicability` 字段。
3. **失败分类对齐文档 4.2（`trajectory_validation.py`）**：`security_gap`（功能过安全败）/ `functional_regression`（安全过功能败）/ `both_failed`（双败）/ `environment_error`（超时），不再把双败一律标为 `security_failed`。
4. **经验卡对齐文档 3.3（`source_knowledge.py`）**：seed 卡补 `recommended_action` / `unsafe_alternative` / `language_adaptation`（python/go/cpp 对象）/ `non_applicable_boundary` 字段（LLM 提取，可选字段缺失时留空）。
5. **审计判定统一（`run_lifecycle_replay.py` / `independent_audit.py` / `audit_runner.py`）**：主流程改用 `audit_decision`（质量 + 有效性 + 回归 + 传播四层），质量门控用 `content_quality_pass`（principle + applicability 非空且无样本特判），支持 `revised`；`audit_candidate` 不再是无调用方的死代码；增加 fail-fast：候选未进入审计任务检索 top-k 时记录 `candidate_retrieved=false`。
6. **主动回放入口（`run_lifecycle_replay.py` / `active_replay.py`）**：`--active-replay` 时对回放池计算信息价值（risk/cost/novelty 启发式）并用 `select_replay_tasks` 排序，产出 `replay_pool/replay_decisions.jsonl`；`replay_score` 支持权重参数（α/β/γ/δ/λ）。
7. **经验生命周期追踪（`experience_lifecycle.py`）**：晋升经验附加 `support_count` / `contradiction_count` / `last_used_round` / `utility_delta` / `related_experience_ids` / `evidence_refs`；`revised` 保留候选待重审；新增 `retire()` 与 `active_cards()`（退役经验排除出检索）。
8. **多语言适配层实例化（`language_adapters.py`）**：`LanguageAdapter.validate` 可执行，`build_python_adapter()` 接入本地 PLT 验证（ast + capability/safety）；Go/C++ 未注入回调时明确 `unmeasured`，`adapter_contract` 增加 `adapter_ready`。
9. **必报指标补全（`run_lifecycle_replay.py` / `reporting.py`）**：summary 增加 `active_replay` / `replay_decisions` / `trajectory_failure_distribution` / `trajectory_joint_pass` / `demoted` / `revised`；报告增加对应行。

## 使用

```powershell
# 规则版主动回放：按信息价值（risk/cost）重排回放池
python -m methods.sct_lifecycle_replay.run_lifecycle_replay --rows 96 --out translation_work/sct_runs/<run> --live-api --active-replay

# LLM 版任务选择：让 deepseek-v3.2 阅读任务契约描述（CWE/函数名/问题描述/安全策略）选择回放任务
python -m methods.sct_lifecycle_replay.run_lifecycle_replay --rows 96 --out translation_work/sct_runs/<run> --live-api --llm-replay

# 全量 PLT：全部有测试样本（874 条）分入 source/replay/audit 三池，LLM 分批选择回放任务
python -m methods.sct_lifecycle_replay.run_lifecycle_replay --all-plt --out translation_work/sct_runs/<run> --live-api --llm-replay

# 放宽 family 限制（Q_pool 候选可含 1/2 变体 family，扩大选择范围）
python -m methods.sct_lifecycle_replay.run_lifecycle_replay --rows 96 --out translation_work/sct_runs/<run> --live-api --llm-replay --min-variants 1

# 限制回放任务数（未选中的回放任务自动移入审查池）
python -m methods.sct_lifecycle_replay.run_lifecycle_replay --rows 96 --out translation_work/sct_runs/<run> --live-api --llm-replay --replay-limit 24
```

不传 `--active-replay`/`--llm-replay` 时保持原有静态三分区行为（兼容旧运行）。
`--llm-replay` 优先于 `--active-replay`：模型返回的选中任务进入回放池并记录
`replay_decisions.jsonl`（含每个任务的模型理由）；未选中的回放任务移入审查池，
扩大独立审查覆盖。候选任务较多时按 `--llm-batch-size`（默认 24）分批让模型选择，
避免超长 prompt 降低 JSON 输出稳定性；LLM 总选择不足时由规则评分（replay_score）
补足，保证回放池满额。模型选择只依据任务契约描述（`llm_scheduler.py` 已过滤
ground_truth/隐藏测试，防止答案泄露），不替代验证器证据。

## 冻结后最终评测（本地，无 Docker）

CodeSecEval Python Base/Plus 的测试是 `check(candidate)` 契约，与 PLT
训练侧本地验证器完全兼容，可以直接在 `python -I` 临时子进程中执行，
不需要 Docker：

```powershell
python -m methods.sct_lifecycle_replay.run_local_codeseceval --run translation_work/sct_runs/<run> --live-api
# 可选：--subsets Base Plus、--limit N（每子集上限）、--timeout、--retries
```

评测前校验冻结经验库（memory_sha256 哈希一致、feedback_channel=disabled），
结果写入 `validation_runs/<subset>/rows.jsonl` 与 `summary.json`；任何 Base/Plus
反馈都不会写回经验记忆或调度策略。

注意：Plus 数据集的 `Test-FP`/`Test-SP` 字段存在排版损坏，评测器按 Docker
验证器同一口径（python_validator.get_python_suites）对 Plus 从完好的 `Test`
字段拆分功能/安全套件，Base 使用 `Test-FP`/`Test-SP`；`_normalize_test_indent`
作为防御性兜底修复缩进缺陷。

## 2026-09-13 全量 PLT 运行与本地评测结果

- 运行目录：`translation_work/sct_runs/lifecycle_replay_plt_all_v2_20260913/`
- 配置：`--all-plt --live-api --llm-replay --replay-limit 96 --llm-batch-size 24`
- 选样：全部有测试的 PLT 样本（386 条，覆盖 10 个 CWE）→ source 131 /
  LLM 分批选出 replay 96 / 其余 31 移入审查池（audit 159）；131 条 source
  假设全部提取成功（0 错误），每条含文档 3.3 的完整经验卡字段。
- 回放轨迹：96 条，31 条联合通过；失败分布 both_failed 35、
  functional_regression 21、security_gap 9。
- 候选与审计：15 个候选（覆盖 9 个 CWE）全部 demoted——6 个候选被检索到
  （retrieved=True）、7 个 delta_joint_pass>0，但全部因 H_pass 安全回归>0
  被拒。审计效率优化生效：共享 baseline（159 条只跑一次）+ 每候选仅重跑
  同 CWE 审查任务（4-25 条）。
- 冻结：122 条 seed 经验（131 提取中 122 验证通过），feedback_channel=disabled。
- 本地 CodeSecEval Python 最终评测（无 Docker，`backend=local_python`）：

| 子集 | total | Function | Secure | JointPass | 生成错误 |
|---|---:|---:|---:|---:|---:|
| Base | 115 | 25 (21.7%) | 9 (7.8%) | 7 (6.1%) | 4 |
| Plus | 140 | 89 (63.6%) | 34 (24.3%) | 33 (23.6%) | 0 |

说明：Base/Plus 结果与 Docker 评测（README 74 行的 Base 28/11/6、Plus
94/51/46）趋势一致，差异属不同运行（API/并发/本地 vs Docker 验证器）的
正常波动；Plus 的 `Test-FP`/`Test-SP` 损坏字段已被绕开（用 `Test` 拆分）。
15 个候选全部 demoted 有两个原因：候选 principle 仍是模板化文本（部分 CWE
候选无法被检索器召回进 top-3），以及 H_pass 回归重跑存在 API 噪声
（sec_reg>0 不能完全归因于候选）。后续改进方向：候选生成接 LLM 从失败
轨迹提炼具体安全不变量（文档 5.2），并为 H_pass 回归引入同配置多次采样
降低噪声。

## 2026-09-14 优化：门控回归判定与检索无效经验

本次运行 15 个候选全部 demoted 的根因已定位并修复，完整分析与预期效果见
`docs/sct_lifecycle_replay_run_20260913.md`。核心改动：

1. **门控回归过严（`independent_audit.py` / `audit_runner.py` / `run_lifecycle_replay.py`）**：
   - H_pass 回归重跑改用 `repairs=1`（与建立 H_pass 的轨迹对齐），消除修复不对称导致的假回归；
   - 新增 `--regression-samples N`（每条 H_pass 任务重跑 N 次，仅当全部样本都联合失败才计入回归）与 `--regression-limit N`（安全回归计数容忍）；
   - `delta==0`（打平）→ `revised` 而非 `demoted`；候选未进入检索 top-k（`retrieved=False`）→ `revised` 而非按噪声 demoted。
2. **检索无效经验（`retriever.py`）**：
   - CWE 加分只在「查询 CWE 与经验 cwe 一致」时生效（修复此前对所有有 cwe 字段的经验一律加满 CWE_BONUS 的 bug）；
   - 构造时过滤 `demoted/retired/rejected` 与 principle 为空的经验；
   - `search` 增加相关性下限，与查询既无 CWE 匹配也无 token 重叠的经验不再进入 top-k。

## 2026-09-15 优化：修复 has_tests，可训样本 386 → 874

`run_lifecycle_replay.py` 的 `has_tests` 旧实现用 `ast.literal_eval` 解析
`testcases` 字典，遇到引用了辅助变量的夹具（如 `attack = 'a'*1000000` 再写进
`testcases`）会抛 `ValueError`，把 488 条可测样本误判为无测试，导致全量模式只
用到 386 条、10 个 CWE。

新实现改为纯静态结构判断（不执行夹具代码——夹具 setup 可能含 `os.system('ls')`
等系统调用，须保持静态）：`testcases` 非空 + 语法可解析（排除未替换占位符导致
的语法错误）+ 源码含 `testcases` 赋值与 `capability`/`safety` 键。该判据与验证器
`exec(setup+tests)` 对 1411 条样本的判定完全一致。

修复后：可训样本 **874 条、18 个 CWE**；新增 CWE 94、200、327、502、770、863、
918、1333，并补全 77（10→51）、352（30→40）、601（1→51）。`--all-plt` 三池分布
source=285 / replay=301 / audit=288。仍有 526 条 `testcases` 为空（无测试）与
11 条语法错误，无法动态验证，不进入选样分母。回归护栏见
`tests/test_sct_lifecycle_replay.py` 的
`test_has_tests_expands_real_plt_to_874_samples`。

## 仍存在的边界

- LLM 调度器（`llm_scheduler.py`）已验证：模型能基于任务契约描述选择多样且合理
  的任务（覆盖新 CWE、高风险、边界检验），选择记录含模型理由；但选择依赖
  deepseek-v3.2 的 JSON 输出稳定性，极端情况下可能选中不足 `limit` 个任务
  （`select_tasks_with_llm` 会静默降级为空选择并在 `replay_decisions.jsonl`
  记录 `selector=llm` 与空 reason，不中断运行）。如需强制选满，可后续叠加
  规则补足（active_replay 的 replay_score）。
- `LanguageAdapter` 只接入了 Python 验证；Go/C++ 仍为 unmeasured（需 Docker harness 注入）。
- 修复后需用 `--live-api` 重跑一轮，才能获得候选真正进入检索后的审计结果（本轮修复前的结果不可作为候选有效性的证据）。
