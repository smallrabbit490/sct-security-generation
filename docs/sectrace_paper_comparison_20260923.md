# SecTrace 论文与当前 Plus 结果对照研究（2026-09-23）

本次读取 README 最新报告、用户提供的 9 页论文、当前实现和已保存逐题结果；未重新调用模型、未启动 Docker、未修改方法实现或经验库。论文中的文字均作为研究材料处理。

## 1. 结论与代码公开情况

**论文值得借鉴的是“任务威胁分析 → 语义适配检索 → 内部测试 → 针对失败的修复 → 有证据的经验更新”整个闭环，不能把高分归因于经验更具体或 agent 更多。** 当前最明确的差距包括：检索没有利用分析结果和修复失败现场、内部动态测试缺位、大量未确认经验参与注入，以及若干报告结论超过证据支持范围。

截至本次检索，**未找到能确认属于该论文的公开 GitHub 仓库，因此未向 `data/external/` 下载任何冒名或无关仓库**。这不等于证明代码未公开；匿名仓库、未索引链接或补充材料仍可能存在。

论文标题为 *SecTrace: Evolving Cross-Task Security Experience for Secure Code Generation*，作者栏为 Anonymous submission；PDF 无超链接，也没有 code availability 地址。正文第 3、6 页把 prompts、检索细节、交互协议、配置、token 消耗等指向 supplementary material，但用户提供的 9 页文件只有正文及参考文献，没有该补充材料。

公开搜索覆盖 GitHub 仓库名、README、代码全文中的 `SecTrace`、完整标题、`Evolving Cross-Task Security`、`SecTrace SafeMem`，并用 Exa 搜索标题及方法组合。排除的候选包括：

| 公开仓库 | 核实的主题 |
|---|---|
| [Suffeng1/Sectrace](https://github.com/Suffeng1/Sectrace) | 安全事件协同审计与日志分析 |
| [cyber-sudhir/SecTrace](https://github.com/cyber-sudhir/SecTrace) | 数字取证平台 |
| [cyber-sudhir/SecTrace2.o](https://github.com/cyber-sudhir/SecTrace2.o) | API 返回空仓库 |
| [sidhpurwala-huzaifa/sectrace-mps](https://github.com/sidhpurwala-huzaifa/sectrace-mps) | 100M 参数安全编码器 |
| [DeepSecurityTermProject/DeepSecurity](https://github.com/DeepSecurityTermProject/DeepSecurity) | 攻击检测、捕获和溯源 |
| [xiangRuiiii/SafeMem-Agent](https://github.com/xiangRuiiii/SafeMem-Agent) | 邮件、文件、日历工具任务中的安全策略检索 |

所以，下文的 SecTrace 实现描述是**论文所述机制**，不是经公开源码核验的事实。拿到正确链接后，应下载到 `data/external/sectrace/`，记录 commit、许可证及来源，再审计 prompts 和评分器；目前不能提供不存在的 clone 或 commit。

## 2. 先对齐数字：论文究竟提高了多少

原文第 5 页定义 Pass@1 为最终程序同时通过功能和安全测试，即 Joint。它允许内部测试与多轮修复后再提交一个最终程序；不是单次模型调用，也不是只计算安全通过率。

论文与本地均声明 Plus 为 **140 个 Python 任务**。尚未拿到论文数据清单和哈希，数量一致不代表逐题版本、依赖、测试后端一致。

| 结果 | 模型 | Plus Joint/Pass@1 | 协议 |
|---|---|---:|---|
| 本地 prompt 首次 / 修复后 | DeepSeek-v3.2 | 22.86% / 26.43% | PLT 冻结库；一次有限官方反馈修复 |
| 本地 CLE 四步首次 / 修复后 | DeepSeek-v3.2 | 16.43% / 17.86% | 同上；Analysis/Planning/CodeGen 三个生成调用 |
| SecTrace 主表 | DeepSeek-V4-Flash | 40.07% | 同 benchmark 顺序积累经验，前 50% 后冻结 |
| SecTrace 主表 | Gemini-2.5-Flash | 39.36% | 同上 |
| SecTrace 主表 | GPT-5.1 | 44.22% | 同上 |
| SecTrace PLT-Py → Plus，表 3 | DeepSeek-V4-Flash | 40.62% | 源任务前 50% 积累，目标域不更新 |
| SecTrace PLT-Py → Plus，表 3 | Gemini-2.5-Flash | 33.64% | 同上 |

**应优先对照表 3 的 PLT-Py → Plus。** 主表每次从空 SafeMem 开始，在随机排列的 benchmark 任务流前半段更新、后半段冻结，并报告五种共享随机顺序的均值。Plus 前半段约 70 题会贡献内部轨迹经验给后续题。原文明确说官方测试及反馈不暴露给 agent，因此不能仅凭这种任务流适应就指控使用官方答案；但它与本仓库完全在训练侧准备 M* 的协议不同。不能直接照搬这一主表流程并称符合当前冻结评测规范。

论文的消融更能说明增益来源（第 7 页表 2）：

| Plus 设置 | V4-Flash | Gemini |
|---|---:|---:|
| 完整 SecTrace | 40.07 | 39.36 |
| 去掉 SafeMem | 32.22（下降 7.85pt） | 30.79（下降 8.57pt） |
| 去掉威胁建模 | 35.08（下降 4.99pt） | 35.64（下降 3.72pt） |
| 去掉动态测试 | 37.79（下降 2.28pt） | 32.22（下降 7.14pt） |
| 去掉经验进化 | 37.92（下降 2.15pt） | 34.22（下降 5.14pt） |

这些差值不能相加，因为组件存在交互。论文自身无记忆系统已约 31%–32%；不能把它与本地 17.86% 的全部差距归因于经验。主表相对最强基线 ReMe 的 Plus 优势分别为 GPT 1.43pt、V4 4.99pt、Gemini 5.87pt，远小于与部分弱基线比较时的视觉差距。

## 3. 他们的方法怎样工作，当前具体缺在哪里

### 3.1 先分析安全语义，再检索

原文 §3.2–3.3 用威胁分析构造风险类型、敏感操作、输入来源、敏感 sink、数据流/API 用法、适用条件六类检索依据；先排除 API 假设、排除条件或数据流不兼容的经验，再按相关性、生命周期和可靠性排序。Confirmed 优先，Trial 要求更严格匹配。

当前 Plus runner 却先 `retrieve(contract)`，然后把卡片传给 `run_pipeline`；Analysis 输出没有参与本轮检索。修复时仍调用同一个 `retrieve(contract)`，没有加入上一版代码或失败证据。层次化检索已经生效，但其 CWE → kind → card 的索引结构不等价于上述语义适用性检查。

另有一个容易遗漏的事实：**生成器读完整题目，检索 LLM 不一定读完整题目**。`hier_retrieval.py` 三层都把任务 JSON 截到 700 字符；本地 140 题中有 **119 题**的契约 JSON 超过此长度。L3 又把不变量压到 90 字符、根因和修法各 70 字符。这不证明一定选错，却说明“已经排除检索瓶颈”的结论不成立：完整契约末尾的关键限定或 API 语义可能没有进入 LLM 选择阶段。规则预筛仍可读取更完整文本，不能说整条检索链完全丢失了这些信息。

### 3.2 自己构建可执行测试，修复时看到具体证据

原文 §3.4 根据任务说明与威胁分析生成独立功能/安全测试。对期望输出做两次独立采样；不一致时再做第三次、多数表决；无一致结果的用例丢弃。测试生成后在修复循环中固定复用。修复 agent 能看到失败用例、实际输出和运行异常，并用当前代码和失败模式重新检索。

本地这轮只有官方验证后的状态和脱敏异常类别，且只修一次；这解释了为什么很难做“针对具体缺陷的修复”，但只是合理机制假说，尚未用消融证明。现有数据是 prompt 108 次修复仅新增 5 个 Joint，四步 117 次仅新增 2 个。

可借鉴的是添加**由任务说明生成的内部测试反馈**，不是开放官方隐藏测试。模型自生成测试也可能一致地给出错误答案；投票降低部分随机误差，并不提供真值保证。必须区分“内部测试通过”和“最终官方 Joint 通过”，并记录错误测试、空测试集、超时、未测量等情况。

### 3.3 可执行、带适用范围的经验；不是无条件硬命令

原文 §3.1 明确把指导内容拆成触发条件、安全不变量、推荐动作、危险反模式、排除条件，并反复称为 **non-binding guidance/prior**。它不主张直接拷贝历史答案，也不说“抽象原则应全部删除”。

当前经验已有 `fix_directive`、失败现场和语言叶，不是完全没有具体内容。更值得检验的是：这些内容是否准确、是否适用当前 API/返回语义、是否在注入时还保留适用边界。当前 `dual_track_text` 虽拿到卡片的 `applicability`，并未专门渲染这个字段；约束却包含“可直接照做”“务必避免”。最新改动还尝试把成功种类一律变成硬不变量。**在源任务成功，不代表对另一个任务有普适约束力。**

建议的经验单位是“条件 → 最小安全改法/API → 保持哪些合法行为 → 何时不可用 → 支持它的验证证据”，可以附训练侧代码片段；抽象不变量仍作为解释和索引，避免直接把目标任务参考实现当经验。

### 3.4 只有实际使用且有验证证据，经验才升级

原文 §3.6 的新经验初始为 Trial、可靠性 0.30；每个任务证据为 −0.1/0/+0.1。必须至少三个不同后续任务提供正证据且分数达到 0.60 才确认。未使用或证据不足记中性；矛盾触发降级、缩小适用范围或版本替换，旧版本不再正常检索。冻结后仍检索，但不继续更新。

本地完整 M* 的 4518 条中，4446 条 provisional、13 条 active、44 条 unmeasured、15 条 retired。更关键的是，正式 Plus **首轮共享的 342 次卡片注入中，338 次是 provisional、仅 4 次 active**；25/140 题没选到卡片。不能把“读了完整冻结文件”理解为“用了经过充分验证的高质量库”。冻结只保证不再变化，不证明内容可靠。

也不建议直接关掉全部 provisional：只剩 13 条可能造成覆盖不足。应在训练侧测量可靠性与适用条件，建立可审计的 Trial 使用门槛，记录应用位置及后续证据，而不是只增加池大小。

## 4. README 最新报告中需要收回或降低强度的结论

最新文件 `cle_decisive_finding_granularity.md` 修改时间为 2026-09-23 00:28:32；载荷报告为 9 月 22 日 21:45:50；正式 Plus 报告为 19:03:32。修改时间用于定位版本，不等于实验实际执行时间。正式 Plus 的归因以运行目录 `source_snapshot/` 为准：它仍使用 400 字符修法截断，不能把后来 1200 字符等改动当作已在那轮 Plus 中测过。

### 4.1 Oracle 证明答案有帮助，没有隔离“粒度”

最新诊断的 40 题来自训练侧 PLT audit，不是 Plus。`oracle` 卡直接注入本题 `code_before + patched_code + code_after`，同时增加了正确答案、API 选择、实现细节、标签语气等信息。12.5% → 62.5% 是有价值的上界观察，但不能独立证明“粒度是决定性变量”“模型能力瓶颈被排除”或“跨 CWE 迁移与有效性冲突”。

干净的粒度实验应从**其他训练任务的同一条已验证经验**构造抽象版、带条件具体版、带最小代码片段版，固定检索 ID、相关信息量/预算及提示框架，在未参与选择的训练侧留出任务上配对比较。目标答案 oracle 只保留为单独上界。

### 4.2 −10pt 是观察值，尚非统计显著的负效应

逐题核对为 no_exp 5/40、retrieved 1/40，配对不一致样本只有 4 对，全部有利于 no_exp。双侧精确 McNemar（二项）检验为 **p=0.125**；报告采用小样本不适宜的无校正正态近似 z=−2 得出“显著”。此外 retrieved 有两个 `generation:model_output_truncated`，其余两臂没有，说明增加上下文后的输出预算问题尚未排除。

负方向值得查，但不足以据此全局关闭经验。“没有显著改善”也不等于等价，54 题、多臂无显著差异不能排除检索、门控或载荷的作用。API 异常、截断及反复使用同一开发集还会进一步限制推断。

### 4.3 按 kind 修复的证据没有通过真实卡片边界

已做不调用模型的最小复现：

1. 从真实冻结池选择 `source.kind=direct_A` 节点。
2. 走正式 `HskTreeRetriever._to_card`，输出卡片**没有 `kind`**。
3. 原样送进当前 `dual_track_text`，不出现硬不变量标签。
4. 只在内存里的对照卡补上同一个 `kind`，标签随即出现。

根因是 `retriever.py:204` 的转换未传递该字段；而 `agent_pipeline.py:266` 的新逻辑依赖 `c.get('kind')`。`verify_payload_fix.py` 自建的 `to_card` 却手工增加 `kind`，与正式转换不同。`closed_loop.final_evaluate` 直接把检索卡交给生成器，没有补字段。因此“真实链路已恢复 31.5% 硬约束”和“载荷修复无效已被证实”均需要重新核验。这里确认的是传递缺口，不代表将经验改成硬命令就是正确方法；SecTrace 恰好坚持条件化、非强制使用。

### 4.4 Plus 的首要问题是安全漏修，不能用 PLT 状态解释替代

正式 Plus 修复后，prompt 有 69/140 题功能过、安全败，四步有 75/140；功能败、安全过分别只有 2 和 0。训练侧的“功能败、安全过”也不能自动确认为过度防御，还可能是一般功能错误、接口/环境问题或测试覆盖不足。必须看代码及失败证据后才能定因。

所以当前四步 prompt 对“最小改动、禁止额外约束、禁止改变异常”的反复强调值得重新平衡：首轮没有上一版实现时，强行使用修补框架可能不合适；题目未写明的安全不变量也不等于一定禁止实现。应分别处理正常输入契约与恶意输入行为。这是可检验假说，不是本次已证明的根因。

## 5. 论文数字本身还存在复现疑点

第 6 页说每设置运行 5 次，第 5 页说 Plus 140 题、指标为二元任务通过比例。若五次分母都固定 140，则均值必为 `100 × 整数 / 700`，步长约 0.142857pt。

但表 1 的 **40.07、44.22、39.36** 及表 3 的 **40.62** 均不在该步长四舍五入到两位的小数网格上。例如 40.07 相邻可取值只能是 40.00 或 40.14。已对第 7 页渲染图人工确认，非 PDF 列错位。

这可能来自未披露的分母变化、宏平均、额外运行或表格版本问题；**不能据此断言造假，也不能把小数点后的精度当作已验证实验事实**。需要原始逐题结果、每轮分母、汇总脚本和方差才能判断。正文也未给出可直接核实的具体修复上限、解码参数、每题测试数和 token 成本。这些缺口限制了复现和对增益原因的定量归因。

## 6. 建议的下一步顺序（本次未执行）

1. **先修证据链**：核验正式卡片 schema 与最终 prompt，解决 `kind` 丢失、适用条件未呈现、检索文本截断；校正报告统计。把“字段已写入”与“真实生成器收到并使用”分开记录。
2. **接通分析与检索**：保留完整契约，提取 source/sink/API/数据流/排除条件再检索；修复查询加入当前代码和内部失败现场。采用能返回零条的条件化指导，而非强制匹配同 CWE。
3. **补齐内部测试—修复闭环**：在训练侧开发集先验证自生成测试质量、修复收益和误修率；官方 Plus 测试仍只做最终评分。如果后续运行 Docker，必须复用常驻池并由 VHDX watchdog 包裹。
4. **检验经验内容与可靠性**：无经验、现有卡、同源具体条件卡、代码片段卡；训练 seed family 隔离，固定模型及预算，输出不足单列。原答案 oracle 不参与正式得分或长期记忆。
5. **最后才重跑冻结 Plus**：以论文表 3 为目标协议，补无经验臂；分别给首次生成、内部修复后最终 Joint、Function、Secure、成本及配对置信区间。用全新留出任务验证开发选择，避免反复针对同一 Plus 结果调参。

## 7. 证据索引

- 用户论文：`简介论文修改方案/11413_SecTrace_Evolving_Cross_ (1)(2).pdf`；SHA-256 `3A9D5E732974BAF2942D4B5D1A627AB30F41516668C3E401265856ED71370EFA`。第 3–5 页方法、第 5–7 页协议/结果、第 7 页表 1–3。
- 本地最新报告：[粒度报告](cle_decisive_finding_granularity.md)、[层次检索](cle_step1_hierarchical_retrieval.md)、[载荷取证](cle_step1_payload_rootcause.md)、[池对比](cle_step2_pool_comparison.md)、[载荷与门控](cle_step3_gate_and_payload.md)、[正式 Plus](plus_frozen_comparison_20260922.md)。
- 正式逐题结果与运行源码：`translation_work/validation_runs/cle_plus_hier_comparison_20260922/python/`。
- Oracle 原始结果：`translation_work/diagnostics/20260922/oracle_test/arm_{no_exp,retrieved,oracle}.json`。
- 本次只读核验脚本、论文提取文本、表格截图：`translation_work/diagnostics/20260923/sectrace_research/{audit_local.py,paper_text.txt,page7_tables.png}`。
- 关键代码：`methods/sct_trajectory/{run_plus_frozen_comparison.py,retriever.py,hier_retrieval.py,agent_pipeline.py,closed_loop.py}`；载荷报告的手工卡片验证脚本：`translation_work/diagnostics/20260922/verify_payload_fix.py`。

复核命令（仅分析已保存文件，不运行候选代码）：

```powershell
& D:/ANACONDA/python.exe -B -X utf8 translation_work/diagnostics/20260923/sectrace_research/audit_local.py
```
