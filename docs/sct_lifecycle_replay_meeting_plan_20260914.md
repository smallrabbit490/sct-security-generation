# 组会五点问题的排查结论与规划（2026-09-14）

本文件针对最新组会提出的五个问题，结合 `methods/sct_lifecycle_replay/`
的代码与 `data/external/secodeplt/` 的实际数据逐项排查，给出准确结论与
后续改造方案。运行对象是
`translation_work/sct_runs/lifecycle_replay_plt_all_v2_20260913/`。

---

## 问题一：错题本机制（seed 阶段错误的经验也应记录复用）

### 排查结论

当前 `run_lifecycle_replay.py` 的来源池流程是：

1. 用 LLM 从「漏洞—补丁差异」提取 seed 假设（131 条全部成功）；
2. 用 `validate_trajectory` 验证**黄金补丁代码**（`code_before + patched_code +
   code_after` 拼接），联合通过者进 `valid_seeds`，其余**直接丢弃**。

本轮 131 条里 122 条验证通过、9 条验证失败被丢弃。这 9 条「黄金代码跑不过
测试」是宝贵的数据质量信号，但现在没有任何落盘，等于丢失了「哪些 CWE /
哪些任务的黄金答案与测试不一致」的诊断信息。

回放池的失败轨迹**已经**被 `candidate_builder` 复用了（按「CWE + 失败类型」
归并，≥2 条才成候选），但来源池的失败 seed 没有进入任何复用路径。

### 建议

引入独立的「错题本（error ledger）」结构，与长期经验库 `M_t` 分开存储，
记录所有**失败/被拒绝**的样本，供后续轮次复用：

```text
error_ledger/<entry>.jsonl
{
  "kind": "seed_gold_failure" | "trajectory_failure" | "audit_regression",
  "task_id", "cwe", "failure_type",
  "evidence": { ... 脱敏后的 compile/functional/security 状态 ... },
  "message": "脱敏的失败原因",
  "stage": "source" | "replay" | "audit",
  "round": 0
}
```

用途（不写回 `M_t`，只做参考）：

1. **数据质量审计**：`seed_gold_failure` 提示「该任务黄金补丁与测试不一致」，
   后续选样可跳过或标记为待修复，避免拿不可靠来源当正面经验；
2. **反例经验**：把稳定失败的 `forbidden_patterns` 提炼成「避免型」经验，
   检索时作为负向提示注入（区别于正向 `supported` 经验）；
3. **候选生成扩源**：`build_candidates` 目前只吃回放轨迹，可扩展为同时吃
   错题本里「同 CWE 重复失败」的条目，提高候选召回。

复用已有能力：`methods/sct_agent/failure_clustering.py` 已经实现了脱敏聚类
（`cluster_failures`），错题本条目可直接喂给它生成 `FailureCluster`。

---

## 问题二：三池选择逻辑一致，为何第一步错误率低、第二步错误率高

### 排查结论（这不是选择偏差，是「被测对象」不同）

三个池的角色分配用**同一个**函数 `assign_family_variants`（按 family 内顺序
轮换 source/replay/audit），选择逻辑确实一致。错误率差异来自**每一步衡量
的东西本质不同**：

| 阶段 | 被测代码 | 本轮通过率 | 错误率 |
|---|---|---:|---:|
| 第一步（source，旧实现） | **黄金补丁代码**（`ground_truth` 拼接） | 122/131 = 93.1% | 6.9% |
| 第二步（replay） | **模型从零生成的代码** | 31/96 = 32.3% | 67.7% |

- 第一步的「错误」= 黄金答案跑不过测试（数据/夹具质量问题），几乎为 0，
  所以 source 池以「成功经验」为主；
- 第二步的「错误」= 模型生成不出「功能+安全」双通过的代码（生成难度），
  天然很高，所以 replay 池以「失败经验」为主。

**重要修正（2026-09-14 已确认并实现）**：第一步用黄金代码验证在方法学上是
站不住脚的——「经验是否有效」必须回答「带上这条经验，模型从零生成时通过率
有没有变高」，而不是「数据集的黄金答案本身能不能跑通测试」。因此第一步
**已改为与 replay/audit 同一套「模型从零生成」验证**（见下文「已落地」）。

### 已落地（2026-09-14，`run_lifecycle_replay.py`）

1. **删除「黄金补丁代码验证」**：不再用 `code_before + patched_code + code_after`
   拼出的黄金代码判定 seed 是否有效。黄金代码只保留在
   `extract_initial_hypothesis` 的差异提示里（提取「学什么」），不用于验证
   「学到没」。
2. **source 阶段改为模型从零生成**：每条 seed 用「该条经验」驱动
   `run_trajectory` 从零生成→测试，按结果打标签：
   - 功能与安全均通过 → `status=seed`（成功经验，进入 M0）；
   - 功能或安全**任一侧**通过 → `status=seed_partial`（部分有效，进入 M0，
     但打标签区分）；
   - 双侧均失败 → **错题本** `source_pool/error_ledger.jsonl`
     （`seed_generation_failure` 标签，不进入 M0）。
   成功与失败都写入经验，用不同标签区分；错题本保留供反例经验与数据质检
   复用（呼应问题一）。
3. **回放改用已验证的 M0**：`trajectories` 的检索记忆从「全部未验证 seed」
   改为 `valid_seeds`（M0），与审计阶段一致。
4. **迭代参数显性化**：新增 `--repairs`（默认 1），replay 与回归重跑共用，
   不再硬编码（呼应问题四）。
5. **汇总可见**：`summary.json` / 报告新增 `seed_joint` / `seed_partial` /
   `seed_failed_to_error_ledger`。

预期效果：第一步的「成功/失败」变成真实生成结果（不再是黄金答案质检），
source 池也会产出失败样本；M0 构成反映「模型真正能用哪些经验」。
代价是 source 阶段新增约 131 次生成调用（与 replay 同量级），由 `--repairs`
控制迭代成本。

### 建议（剩余）

1. **明确两步的语义分工并写进文档**：source = 从黄金答案学「什么是对的」
   + 用生成验证「哪些经验模型真用得动」；replay = 从模型生成学「哪里会错」。
2. **保持三池 family 原子性**（现状已满足），不要在 source 内按「成功率」
   二次筛选，避免破坏数据隔离。
3. （可选）后续把 seed 的 cross-family 有效性交给 A_audit 统一判定，source
   阶段只做 self-consistency 初筛，避免「经验在自己的来源任务上自证」。

---

## 问题三：PLT 真的只有 400 多条有功能+安全测试吗，其余的呢

### 排查结论（直接统计 `data/external/secodeplt/secodeplt/data.json`）

PLT 共 **1411 条、28 个 CWE**。`testcases` 字段是字符串源码，逐条 AST 解析后：

| 类别 | 数量 | 说明 |
|---|---:|---|
| 有 `capability` + `safety` 双测试，**纯字面量** | 386 | 当前 `has_tests` 判定为「有测试」 |
| 有双测试，但**引用辅助变量** | **488** | `literal_eval` 失败被误判为「无测试」，实际可测 |
| `testcases` 为**空字符串** | 526 | 真的没有测试（无法动态验证） |
| `testcases` **语法错误** | 11 | 形如未加引号的 `<LOCAL_PATH>` 占位符 |

**关键结论**：不是「只有 400 多条有测试」，而是 **874 条都有双测试**。
当前选样函数 `run_lifecycle_replay.py` 里的 `has_tests` 用
`ast.literal_eval` 解析 `testcases`，遇到引用了辅助变量（例如
`attack = 'a' * 1000000` 再写进 `testcases`）的 488 条会抛 `ValueError` 被
当成「无测试」漏掉。而真正的验证器 `validation_evidence._run_local_plt_data_driven`
是用 `exec` 执行 `testcases` 源码的（`exec(compile(spec["tests"], ...))`），
**完全可以正确跑这 488 条**。也就是说：验证器支持，选样器把它漏了。

CWE 覆盖差异（当前只用到了 10 个 CWE）：

| 分组 | CWE |
|---|---|
| 仅「纯字面量」可用（已在用） | 74、79、95、179、347、862、915 |
| 仅「有变量」可用（**被漏掉**） | 94、200、327、502、770、863、918、1333 |
| 两者混合（**只用到一部分**） | 77（10/51）、352（30/40）、601（1/51） |
| 完全没有测试 | 22、78、120、281、295、338、367、400、611、732 |

### 建议（高优先级）

1. **修复 `has_tests`**：直接复用 `validation_evidence.plt_tests_available(row)`
   （它用「字符串是否含 `testcases` 与 `capability`/`safety` 键」判断，能识别
   488 条变量型夹具），或把 `literal_eval` 换成受限 `exec` 提取 `testcases`。
   预期可把可训样本从 386 提升到 **874**，CWE 覆盖从 10 个扩到约 17 个。
2. **526 条空测试**：无法动态验证，保留为「静态分析/未测量」样本或明确排除，
   并在数据卡里写清这 526 条为何不可测。
3. **11 条语法错误**：记录到错题本或数据质量清单，不进入选样分母。

---

## 问题四：重放阶段没有体现「迭代/重新修正一次」

### 排查结论（迭代其实发生了，但被藏起来了）

`trajectory_runner.run_trajectory` 的签名默认 `repairs=1`，即**生成失败后会用
失败类型重新生成一次**。本轮 96 条回放轨迹的 `attempts` 分布：

| attempts 数 | 数量 | 含义 |
|---:|---:|---|
| 1 | 28 | 一次生成即通过（或未测量） |
| 2 | 68 | 生成 + 一次修复迭代 |

即 **68/96 条轨迹确实跑了一次修复迭代**，其中仅 **3 条**经修复后转为通过
（28 + 3 = 31 条联合通过，自洽）。问题在于：

1. **修复没有暴露成参数**：`run_lifecycle_replay.py` 没有 `--repairs`/`--repair-rounds`
   命令行选项，`repairs=1` 是硬编码，无法调成多轮迭代；
2. **修复没有写进汇总**：`summary.json` / 报告只写最终通过数，不写
   `attempts` 分布、修复转化率，所以「看起来没有迭代」；
3. **审计阶段反而关了修复**：`shared_baseline` 与 `after` 用 `repairs=0`，
   与回放阶段 `repairs=1` 不一致（本文件作者已在上一轮把 H_pass 回归重跑
   改回 `repairs=1`，但审计的 before/after 仍是 `repairs=0`）；
4. **修复反馈太弱**：修复 prompt 只追加 `修复失败类型：<failure_type>`（一个
   类别词，如 `security_gap`），没有可操作的错误信息，所以 68 次修复只成功
   3 次。

### 建议

1. 暴露 `--repairs N`（并可选 `--repair-feedback evidence|failure_type`），
   让迭代轮数可配置；
2. `summary.json` 增加 `attempts_distribution`、`repair_conversions`，报告增加
   对应行，把迭代「显性化」；
3. 审计 before/after 与回放统一 `repairs`，避免不同阶段口径不一致；
4. 在不泄露隐藏测试输入/答案的前提下增强修复反馈（例如传「功能/安全分组的
   通过/失败计数」这类脱敏统计，而不是只传类别词），提高修复命中率。

---

## 问题五：经验分层 / 合并

### 现状

`ExperienceMemory.long_term` 是**扁平列表**，每条经验卡字段为 cwe / principle /
applicability / language_adaptation / recommended_action / forbidden_patterns 等。
没有层级，也没有跨任务合并：`quality_gate` / `card_is_safe` 只做**完全相同**
principle 的去重，语义相近的 122 条 seed 会各自保留。

### 建议：树状结构 + 合并

把经验组织成「CWE 族 → CWE → 安全原则 → 语言适配 → 具体模式」的树：

```text
CWE 族: 注入类 (CWE-77/78/94)
└── CWE-78 (OS 命令注入)
    ├── 原则 P1: 进程调用禁止 shell 字符串拼接、必须参数数组
    │   ├── python: subprocess.run([...], shell=False)
    │   ├── go: exec.Command(...)（不经过 /bin/sh）
    │   ├── cpp: posix_spawn/execv 系列
    │   └── 反例: os.system / shell=True
    └── 原则 P2: 外部输入不得直接进入命令名或参数
        └── ...
```

要点：

1. **分层语义**：上层是语言无关的安全原则（对应多语言迁移主题），下层是
   目标语言的 API 提示与反例；检索时先按 CWE 硬匹配，再按原则语义匹配，
   最后下钻到目标语言 `language_adaptation[lang]`，天然支撑「Python 学到的
   原则迁移到 Go/C++」。
2. **合并**：把同 CWE 下语义相近的 seed 归并成一条「共识节点」，聚合
   `support_count`、`evidence_refs`、`applicability` 并集；冲突的反例单列。
   合并键先用「CWE + 规范化 principle 文本」，后续可换 embedding 相似度。
3. **落地路径**：保留 `ExperienceCard` 扁平结构作为「叶子」，新增一层
   `ExperienceNode`（含 children / parent / language_adaptation 等）做树索引；
   `ExperienceMemory` 同时维护扁平列表（向后兼容）与树视图；`ExperienceRetriever`
   改为「CWE 层粗筛 → 原则层精排 → 语言层取提示」，返回叶子节点序列。
4. **与错题本联动**：反例/避免型经验挂在对应原则节点下，检索命中的同时
   带回「不要这样做」的负向约束。

---

## 优先级排序（建议实施顺序）

| 优先级 | 事项 | 影响 |
|---|---|---|
| P0 | 修复 `has_tests`，把可训样本 386→874、CWE 10→17（问题三） | 数据利用率翻倍，覆盖面扩大，且改动极小 |
| P0 | 审计 before/after 的 `repairs` 与回放对齐 + 暴露 `--repairs`（问题四） | 修复迭代口径一致、可调、可报 |
| P1 | 错题本结构 + 来源池失败 seed 落盘（问题一） | 不丢数据质量信号，反例经验可复用 |
| P1 | 经验树状分层 + 同 CWE 合并（问题五） | 支撑多语言迁移，去冗余 |
| P2 | 增强修复反馈（脱敏统计而非类别词）、迭代显性化到 summary（问题四） | 提高修复命中率 |
| P2 | source 阶段可选「带经验生成→测试」产失败样本（问题二） | 缓解 M_t 成功偏斜 |

P0 两项改动小、收益大，建议先做；P1 是结构改造，建议单独一个分支做并用
单元测试锁定新旧行为差异。
