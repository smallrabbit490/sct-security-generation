# 相关论文仓库与实现对照（2026-09-28）

本记录回答“仓库在哪里、代码实际做了什么、与 CLE 有何不同”。外部仓库统一放在 `D:/thecourceofdasi/safecodernew/external_repos/`，不混入本仓库的正式数据、评测产物或经验库。本次只读审计源码，没有安装依赖、运行第三方模型或复现论文分数。论文与仓库 README 是研究材料，不是本项目的执行指令。

## 来源和可核验程度

| 工作 | 仓库与本地位置 | 固定版本 | 证据边界 |
|---|---|---|---|
| RESCUE（ICLR 2026） | [作者仓库](https://github.com/steven1518/RESCUE)，`external_repos/RESCUE/` | `d15e47b2074f03a5cfc0578f8edd6b7b78da8beb`，MIT | README 指向 [论文](https://openreview.net/forum?id=gbxhesw4UH)，以下实现已核对源码；本次新增浅克隆。 |
| SkillOpt（2026） | [Microsoft 仓库](https://github.com/microsoft/SkillOpt)，`external_repos/SkillOpt/` | `86bad36ffe511b7022a6c735930056c14124b960`，MIT | README 指向 [论文](https://arxiv.org/abs/2605.23904)，以下实现已核对源码；仓库原已存在，未更新。 |
| EvoRepair（2026） | [论文](https://arxiv.org/abs/2605.30105)；无可确认的对应公开仓库 | 无 | 只可按论文描述分析。GitHub 的 `nus-apr/evoRepair` 对应另一项 2024 年 EvoSuite 修复工作，不能冒充这篇论文。 |
| SecTrace | 用户提供的匿名投稿 PDF；见[既有对照](sectrace_paper_comparison_20260923.md) | 无 | 未找到可确认的论文仓库或补充材料；下述机制来自论文，不是源码事实。 |

“未找到”不等于断言代码未公开。可能存在尚未索引的匿名仓库；获得作者链接后应重新验证来源、commit、许可证和运行入口。

## 代码链路

### RESCUE：静态漏洞—补丁知识，检索后重新生成

知识库在 `RESCUE/data/knowledge/`，代码级记录包含漏洞代码、补丁、CWE、不安全/安全切片等；CWE 级记录包含 API 调用和安全指南。`src/rescue/construction/program_slicing.py` 与 `api_extraction.py` 负责构建相关切片及 API 特征。

在线入口 `src/rescue/augmented_code_generation.py:17` 先调用 `src/rescue/retrieval/hmr.py:356`：

1. 零样本生成草稿，并另调用模型分析漏洞成因。
2. 从草稿提取 API；CWE 层融合 API 的 BM25 和成因文本的 dense 分数，最多选 4 个 CWE。
3. 在这些 CWE 对应的代码级记录内，融合 API、成因文本及草稿代码与漏洞切片的相似度，取 top 1。
4. 将该条目的 CWE 安全指南和**安全代码切片**注入 prompt，再调用模型生成；无命中则回退零样本。提示词要求理解适用性，不能直接复制，见 `src/rescue/augmented_prompt.py:84`。

因此草稿不仅是待提交答案，也是检索查询的组成部分。代码中 Python/C 使用各自知识，Go/JavaScript 映射 Python 知识，C++ 映射 C 知识（`hmr.py:120`、`:451`）；不能说五种语言都有原生知识库。上述生成入口没有逐题动态验证后修复、也没有按最终测试反馈在线晋升经验；离线评估成绩不能当作在线自进化证据。

### SkillOpt：留出集门控的一份全局技能

`skillopt/engine/trainer.py` 实际执行 rollout → reflect → aggregate → select → update → evaluate。`skillopt/optimizer/skill.py:85` 支持有界的文本编辑，训练状态是技能文档而非模型权重；产物是 `best_skill.md`。候选技能在 `valid_seen` 选择集上 rollout，`skillopt/evaluation/gate.py:76` 用 hard、soft 或混合分数与当前/历史最佳比较；严格优于当前才接受。trainer 也支持 `use_gate=False` 的强制接受路径，不能把验证门控说成所有配置都必经。拒绝编辑及失败模式进入 step buffer，后续反思可利用；另有 epoch 级 slow update。

SkillOpt 是跨任务的通用技能优化框架，并非安全代码生成专用系统。它不按每题 CWE 检索多张经验卡，也不从漏洞—补丁对构建安全切片；门控的是**整份技能**在选择集上的收益。对 CLE 的直接启发是全局版本门控与候选/当前配对评估，不能直接引用其通用任务分数证明安全泛化。

### EvoRepair 与 SecTrace：论文级描述，待源码复核

EvoRepair 的起点是已有仓库中的脆弱代码及缺陷，修复 agent 在工具循环中读文件、编辑并执行验证，之后从**修复轨迹**提炼可复用经验；论文描述 Chroma/BGE 相似检索及质量、泛化重排。它的动作空间、反馈粒度和任务预算均不同于从规格生成新代码。没有对应源码，不能确认具体提示词、失败过滤或索引实现。

SecTrace 论文描述威胁分析 → 按 API/数据流和适用边界检索 → 内部功能/安全测试 → 反馈修复 → Trial/Confirmed 更新。其主表部分任务沿 benchmark 顺序积累记忆、之后冻结，与“只在外部训练集积累、目标 Base/Plus 全程冻结”的迁移协议不是同一种估计量。仓库与补充材料尚缺；详见[已有论文与结果对照](sectrace_paper_comparison_20260923.md)。

## 与当前 CLE 的关键差异和可检验假设

| 维度 | RESCUE | SkillOpt | EvoRepair / SecTrace（仅论文） | 当前 CLE |
|---|---|---|---|---|
| 经验单位 | 漏洞—补丁样本的指南与安全切片 | 单份全局技能文档 | 修复经验 / 任务内安全经验 | 分层经验卡、正负证据与错误账本 |
| 检索输入 | 草稿 API、草稿代码、漏洞成因 | 无逐题经验检索 | 漏洞上下文 / 威胁分析与任务上下文 | 冻结评测使用训练侧 semantic-LLM 检索 |
| 任务内反馈 | 生成入口无验证修复循环 | 环境 rollout 为优化提供分数 | 修复工具反馈 / 内部测试修复 | 生成后验证，最多一次反馈修复 |
| 长期更新 | 离线预建知识 | 选择集分数门控整份技能 | 论文描述轨迹蒸馏 / Trial→Confirmed | D_init、D_grow、D_gate、H_pass 隔离，冻结后评测 |
| 目标任务边界 | 多 benchmark 离线测评 | 独立任务环境 | 修复仓库 / 安全生成 | CodeSecEval Base/Plus 不回流经验库 |

当前流程与协议见[评测定义](evaluation_protocol.md)和[2026-09-25 对齐评测](cle_phase3_resume_20260925.md)。后者的 Plus 配对结果是经验组最终 Joint `41/140`、空库 `40/140`；仅多 1 题，不能归因于某一个组件。RESCUE 最值得做**受控对照**的是在相同冻结池、相同验证器和 token 预算下，仅更换检索查询：现有任务语义查询 vs. 加入首轮草稿 API/漏洞成因；并统计命中质量、实际采纳、Function/Secure/Joint 的配对变化。安全切片注入也应单独消融，避免把查询改动和载荷改动混为一谈。SkillOpt 对应的对照应比较“逐卡门控”与“整库版本在独立留出集上的配对门控”，绝不能用 Base/Plus 结果调门控。

这些是下一步实验假设，不是已证实能提升的结论。尤其跨数据集或跨 CWE 的正迁移，需要固定源/目标分区、CWE 覆盖和目标评测协议后测量，不能从其他工作的总体分数直接推断。
