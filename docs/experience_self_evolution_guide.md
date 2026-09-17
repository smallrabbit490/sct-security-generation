# 经验自进化操作指南（PLT → M* → Base/Plus）

本文是本仓库“经验自进化”实验的操作和数据字典。读者可以只看本文件，理解 PLT 原始数据、每个 JSON/JSONL 文件的字段、更新时机，以及一次真实实验会产生什么结果。方法边界以原始 DOCX 和 [评测协议](evaluation_protocol.md) 为准。

> **统一核心实现（2026-09-09）**：正式 SCT 逻辑拆分在 `methods/sct_agent/schemas.py`、`difference_analysis.py`、`validation_evidence.py`、`failure_clustering.py`、`experience_cards.py`、`candidate_gates.py` 和 `experience_lifecycle.py`。PLT 入口调用这些模块；候选经验在质量、D_gate 有效性和 H_pass 回归全部通过前不会进入 M*。旧 `run_coset_eagle_experiment.py` 仅用于原型/历史回放。

## 0. 一眼看懂数据流

```text
PLT data.json
    │ 选择可用数据的四分之一（默认 353 条），按 CWE 配额并按 family 隔离
    ├── D_init  ──验证──> M0
    ├── D_grow  ──生成/失败反思──> 候选经验 C_t
    └── D_gate  ──质量/有效性/回归门控──> 晋升经验
                                      │
                                      └── 冻结 ──> M*
                                                   │
                                                   ├── Python Base
                                                   └── Python Plus
```

运行入口：`methods/sct_agent/run_plt_self_evolution.py`。一次运行目录形如 `translation_work/sct_runs/plt_python_quarter_<数量>_<时间>/`。`translation_work` 被 Git 忽略，正式 JSONL 必须保留在本机用于复核。

## 1. PLT 原始数据格式

文件：`data/external/secodeplt/secodeplt/data.json`。文件整体是 **JSON 数组**，本仓库当前有 1,411 条记录；每个数组元素是一条漏洞任务。

### 1.1 顶层字段字典

| 字段 | 类型 | 含义 | 如何使用/是否更新 |
|---|---|---|---|
| `CWE_ID` | 字符串 | CWE 漏洞类别编号，如 `22` 表示路径遍历 | 只读；用于分层选样和统计 |
| `task_description` | 对象 | 任务语义和函数契约 | 只读；传给模型并写入 family 指纹 |
| `ground_truth` | 对象 | 漏洞版本与修复版本的代码片段 | 只读；用于形成经验和训练侧验证 |
| `unittest` | 对象 | PLT 自带的可选测试夹具 | 只读；原生格式为 `setup + testcases`，后者包含 `capability/safety` 分组 |
| `install_requires` | 数组 | 任务所需额外 Python 包 | 只读；运行器不会自动修改 |
| `rule` | 字符串 | 数据集提供的安全修复原则 | 只读；可作为经验卡 `principle` |
| `index` | 整数 | PLT 稳定行号 | 只读；写入 manifest 的 `task_id` |

### 1.2 `task_description` 字段

```json
{
  "function_name": "retrieve_user_files",
  "description": "功能背景和任务目标",
  "security_policy": "必须满足的安全约束",
  "context": "外部变量、类型或初始化上下文",
  "arguments": "参数名称、类型和语义",
  "return": "返回值类型和语义",
  "raise": "允许或要求抛出的异常"
}
```

这些字段共同定义“不能改坏的契约”：生成代码必须保留函数名、参数、返回值和异常行为。`function_name` 不是入口执行命令；它是提示和审计字段。

### 1.3 `ground_truth` 字段

```json
{
  "code_before": "函数前缀/已有代码",
  "vulnerable_code": "存在漏洞的中间片段",
  "patched_code": "修复漏洞的中间片段",
  "code_after": "函数后缀/已有代码"
}
```

完整代码由 `code_before + vulnerable_code/patched_code + code_after` 拼接而成。漏洞—补丁差异是经验来源；不能把具体补丁原样当作可复用规则。

### 1.4 `unittest`、依赖和规则

- `unittest.setup` 是初始化代码，`unittest.testcases` 是可执行测试文本；原生 `capability` 统计功能、`safety` 统计安全，空字符串表示该条没有动态 PLT 测试。
- `install_requires` 为空数组表示不需要额外依赖；非空时应在隔离环境处理，不能直接污染宿主环境。
- `rule` 是数据集已有原则，例如“路径必须限制在用户目录内”。运行器会把它放进经验卡，但仍需经过阶段验证和门控。

真实 PLT 记录示例（`index=180`）的 CWE 是 22，补丁通过 `Path.resolve().relative_to(user_directory.resolve())` 阻止路径逃逸。

## 2. 选样与 manifest JSON

运行器先过滤同时存在 `vulnerable_code` 和 `patched_code` 的记录，再按 28 个 CWE 分配 12/13 条配额，使用 family 原子子集和精确选出 `ceil(1411×0.25)=353` 条；同一 family 不跨分区，最终分区默认约为 118/118/117。Seed Family 由 `sha1(CWE + 规范化任务语义)` 形成。

文件：`manifest/split_manifest.json`。

```json
{
  "algorithm": "family-atomic per-CWE quota with deterministic subset-sum, then greedy three-way allocation",
  "partitions": {"D_init": ["family-id"], "D_grow": ["family-id"], "D_gate": ["family-id"]},
  "rows": {"D_init": [180, 246], "D_grow": [291], "D_gate": [338]},
  "selected_row_count": 353,
  "selection_fraction": 0.25,
  "rounding_rule": "ceil(usable_row_count * fraction)"
}
```

- `algorithm`：如何计算 family 及排序；用于复现，不能随意更换。
- `partitions`：每个分区包含哪些 family ID；用于检查 family 互斥。
- `rows`：真正使用的 PLT `index`；任务记录中的 `task_id` 就来自这里。
- `selected_row_count`：三分区记录总数，默认应为 353。
- `selection_fraction`/`rounding_rule`：选样比例和取整规则，必须随实验记录。

更新规则：重新选样时新建运行目录和新 manifest，不覆盖旧运行；修改样本量时必须同步更新 `row_count` 和报告。

## 3. R0：D_init 生成 M0

### 3.1 `R0/d_init_rows.jsonl`

这是逐任务审计文件，每行是一个 JSON 对象，不是一个大 JSON 数组。字段：

```json
{
  "partition": "D_init",
  "task_id": 180,
  "experience": {
    "id": "plt-180",
    "cwe": "22",
    "principle": "make sure that the file path stays confined to the user's directory...",
    "source": "D_init"
  },
  "validation": {
    "passed": true,
    "result": {"syntax": true, "static_unsafe": false},
    "error_type": null
  }
}
```

- `partition`：数据来源区，防止把测试任务误认成训练任务。
- `task_id`：对应 PLT 的 `index`。
- `experience.id`：经验卡稳定标识；通常为 `plt-<index>`。
- `experience.cwe`：经验适用的 CWE。
- `experience.principle`：可跨任务复用的原则，不应包含答案或测试常量。
- `validation.passed`：训练侧是否通过；`result.syntax` 是语法结果，`static_unsafe` 表示是否命中危险 API。
- `error_type`：失败分类；成功为 `null`。

### 3.2 `R0/m0.jsonl` 和 `R0/summary.json`

`m0.jsonl` 只保存 `validation.passed=true` 的经验卡。它是下一阶段的当前记忆，只能由 R0 更新，不能被 Base/Plus 结果回写。

```json
{"id":"plt-180","cwe":"22","principle":"...","source":"D_init"}
```

`summary.json` 是阶段计数快照：

```json
{"tasks":32,"m0":32}
```

本轮实际为 32 条输入、32 条 M0。若重新运行，旧 summary 不修改，在新时间戳目录生成新的快照。

## 4. R1：D_grow 生成候选经验

### 4.1 `R1/d_grow_rows.jsonl`

每条 D_grow 任务先检索 M0，再请求模型生成安全代码，随后进行验证：

```json
{
  "partition":"D_grow",
  "task_id":246,
  "generated_code":"def ...",
  "error":null,
  "retries":0,
  "validation":{"passed":false,"error_type":"static_security"}
}
```

- `generated_code`：模型提取后的代码；空字符串表示没有提取到代码。
- `error`：API、提取或运行错误；如 `empty_model_content` 表示网关返回空 `content`。
- `retries`：实际使用的重试次数，不是配置的最大次数。
- `validation`：当前实现的训练侧语法/危险 API 检查结果。

### 4.2 `R1/candidate_experiences.jsonl`

只有生成失败且存在可归纳规则时才创建候选：

```json
{"id":"candidate-246","principle":"reusable security rule","source_task":246}
```

候选是临时对象，不等于已生效经验；不得写入 `m_star.jsonl`，直到 D_gate 完成。`source_task` 只用于追溯，原则本身不能依赖该任务的答案、常量或隐藏测试。

## 5. D_gate：候选门控与更新

### 5.1 `R1/d_gate_rows.jsonl`

```json
{
  "candidate_id":"candidate-246",
  "validation":{"passed":true,"result":{"syntax":true,"static_unsafe":false}},
  "decision":"promote"
}
```

`decision` 允许 `promote` 或 `reject`。正式 DOCX 要求质量、独立有效性和回归三层门控；当前 PLT 训练实现已执行语法/危险 API 门控，并记录 `validation`，但没有 PLT 原生动态测试时无法计算完整的联合通过率提升，报告必须明确这一限制。

### 5.2 晋升、拒绝和阶段汇总

- `promoted_experiences.jsonl`：本轮通过门控、允许加入长期库的候选。
- `rejected_experiences.jsonl`：未通过候选及原因（没有候选时为空文件）。
- `summary.json`：`{"candidates":32,"promoted":32,"rejected":0}`。

更新顺序是：候选池 → D_gate 记录 → 晋升/拒绝文件 → 合并到冻结库。任何门控前候选都不能修改 `M0`。

## 6. 冻结经验库 M*

### 6.1 `frozen/m_star.jsonl`

它是最终评测唯一可读的长期经验库，内容是 M0 加晋升经验的合并结果。冻结后不再追加经验。

### 6.2 `frozen/freeze_metadata.json`

```json
{"model":"deepseek-v4-flash","temperature":0.1,"source":"R1 gate","frozen":true}
```

- `model`、`temperature`：冻结时的模型和采样参数；
- `source`：经验库来自哪个轮次；
- `frozen=true`：表示 Base/Plus 阶段不得更新它。

更完整的实验应同时记录 commit、检索器版本、Prompt 版本、数据 manifest 和验证器镜像；这些信息在运行目录的 `run_metadata.json` 中保存。

## 7. Base/Plus 评测 JSONL

Base/Plus 必须在 M* 冻结后运行，不能把最终结果反馈给 D_grow 或 D_gate。

### 7.1 `validation_runs/<subset>/rows.jsonl`

```json
{
  "subset":"Base",
  "task_id":"CWE-502_codeql_1.py",
  "generated_code":"",
  "error":"empty_model_content",
  "retries":1,
  "validation":{"passed":false}
}
```

字段含义与 D_grow 相同，另加 `subset` 和 CodeSecEval 任务 ID。`validation.passed` 代表当前实现的 Function+Secure 联合结果；更细的 Docker 功能、安全字段位于 validator 返回的 `result/details` 中。

### 7.2 `summary.json`

```json
{"total":115,"expected_total":115,"evaluated":115,"functional":29,"secure":12,"joint_pass":7,"generation_errors":1,"empty_code":1,"validator_exceptions":0}
```

- `total`：该集合应评测的任务数，失败任务不能从分母删除；
- `functional`/`secure`/`joint_pass`：Function、Secure 和联合通过数；
- `generation_errors`：API/提取等生成阶段错误数；
- `empty_model_content`：空响应专项计数。

本轮重验证结果：Base 115 条，29/12/7（Function/Secure/Joint）；Plus 140 条，104/57/54；两套各有 1 条生成错误，Docker 验证器异常均为 0。最终验证独立使用 60 秒超时。官方 Secure Code 在同一验证器上分别为 Base 115/115、Plus 140/140，说明 harness 校准通过；校准不是模型得分。它们是一次具体运行的结果，不是固定基准，换模型或重试参数会变化。

## 8. `run_metadata.json`：解释“这次到底怎么跑的”

```json
{
  "model":"deepseek-v3.2",
  "plt_rows":353,
  "partitions":{"D_init":118,"D_grow":118,"D_gate":117},
  "base":115,
  "plus":140,
  "plt_validator":"local_python_subprocess_-I",
  "final_validator":"python_validator_docker",
  "plt_docker_required":false,
  "docker_preflight":{"ok":true,"version":"29.4.2"}
}
```

它是运行级别元数据，不是逐任务结果。PLT 训练侧明确记录 `plt_docker_required=false`；只有冻结后的 Base/Plus 评测适配器使用 Docker。每次新实验创建新的 `run_metadata.json`，不覆盖历史运行。

## 9. 实际运行命令、检查和清理

```powershell
python methods/sct_agent/run_plt_self_evolution.py `
  --model deepseek-v4-flash --timeout 40 --retries 1 --workers 8
```

执行后依次检查：manifest 三分区交集为空 → R0 summary → R1 candidate/gate/promote/reject → M* 冻结标记 → Base/Plus rows 与 summary 数量一致。临时沙盒、原始 API 响应和可重建缓存可按 [AGENTS.md](../AGENTS.md) 规则删除；正式 JSONL、manifest、冻结库、summary、metadata 和报告必须保留。

## 10. 当前实现边界（必须如实记录）

1. PLT 原生测试使用 `capability/safety` 数据驱动格式，R0/R1 默认使用本地 `python -I` 临时子进程；同时兼容旧 `check(candidate)`。这不能等同于带 Docker 的 CodeSecEval 隔离级别。
2. 当前 runner 的 `D_gate` 已输出加入前后的 `before_joint_pass`、`after_joint_pass` 和严格 `ΔJointPass > 0` 门控记录；语言入口仍需在真实多语言运行时接入正式独立 D_gate manifest。
3. `empty_model_content` 只能计为生成失败，不能把 `reasoning_content` 当作代码，也不能从分母删除。
4. Base/Plus 是冻结后的最终评测集，任何结果不得更新 M*。

如需扩展到 R2/R3，只能复制同一目录结构和门控协议，使用新的轮次目录；不得把旧缓存目录冒充正式轮次。

## 11. 统一核心模块索引

| 模块 | 用途 | 主要输出 |
|---|---|---|
| `schemas.py` | 统一可序列化数据结构 | DifferenceAnalysis、ValidationEvidence、ExperienceCard、GateRecord、FreezeManifest |
| `difference_analysis.py` | 图一漏洞—补丁差异分析 | 六类差异字段、测试可用性和解析证据 |
| `validation_evidence.py` | 多源动态/静态验证适配 | 编译、功能、安全、静态、类型、资源、超时、异常状态 |
| `failure_clustering.py` | 失败脱敏和根因聚类 | FailureCluster JSONL |
| `experience_cards.py` | 经验卡抽象 | 适用条件、原则、语言提示、禁止模式 |
| `candidate_gates.py` | 三层候选门控 | quality/validity/regression 和 promote/reject 决策 |
| `experience_lifecycle.py` | 长期库生命周期与冻结 | 晋升过滤、冻结反馈闸 |
