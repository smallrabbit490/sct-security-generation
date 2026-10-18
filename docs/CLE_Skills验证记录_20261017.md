# CLE Skills 验证记录

日期：2026-10-17。范围：7项新技能、只读运行概况工具、项目导航及本机发现入口。验证期间没有实验模型请求、Embedding请求、生成代码执行、Q更新或Docker验证；未提交或推送。

## 文件结构与发现入口

- 7个SKILL.md均通过skill-creator的quick_validate.py：名称、YAML前置说明和未完成模板检查通过。
- 7个agents/openai.yaml均解析成功；中文短说明长度25–64字符；default_prompt包含相应$skill名称；保持默认可自动选择。
- 全部技能文本为UTF-8，无替换字符或遗留TODO模板；初始化工具按Windows本地编码写出的UI元数据已转为UTF-8。
- 技能内部reference链接均可解析。项目调研报告、验证记录与README/AGENTS导航已关联。
- 本机 `C:/Users/fujunye/.codex/skills/cle-*` 的7个新目录入口为指向项目 `skills/cle-*` 的junction，逐项核对解析目标及SKILL正文一致。没有覆盖原有技能；没有复制一份会与项目源分叉的正文。

验证器使用本机已存在且带PyYAML的研究解释器，只运行校验脚本；没有安装新依赖，也没有修改该解释器所属仓库的课题文件。CLI与技能新脚本使用现CLE解释器完成实际只读检查。

## 真实产物检查

| 输入 | 工具实际输出 | 判定 |
|---|---|---|
| 当前public_contract_v2研究目录 | awaiting_human_review；gate_B缺914对人工标签；未发现rows.jsonl | 没有把检索初标当生成成绩，未继续付费 |
| shared_initial8/compare | 24行原生final，三臂各8题；Q1/Q2/Q3 Joint=2/3/2，流程错误计数保留 | 与已有逐题汇总一致；没有把尝试数当新样本 |
| E盘旧aligned_full冻结评测 | 实际元数据为semantic相关向量、4096额度、persistent_docker；510行均不是新P7 final schema | 标记未归纳，没有生成0分或套用错误成功定义 |

使用的工具是 `skills/cle-research/scripts/inspect_cle_run.py`。它仅提供概况，不能替代原项目的格式审计、逐题统计或科学有效性检验。

额外在忽略运行区建立两条明确标为synthetic_case的样例：一条含未知security/joint，一条无原生final。检查未知字段仍计unknown，未误记为已测失败；不执行这些记录中的任何代码。

## 路由情景静态演练

以下是当前作者按技能逐条检查的情景，不是独立Agent端到端评测，不声称已证明自动路由准确率。

| 请求 | 路由 | 核查点 |
|---|---|---|
| 接续旧CLE，先说明正在做什么 | cle-research | 找真实仓库和指定协议，不以cwd或最新文件名选结果 |
| 解释PLT/译本并补136公开依赖 | cle-data-contracts | 原始/可测/分池分母不同；只补接口、不泄露患者实例 |
| 复现54题层次检索对照 | cle-experiment-design | 采用其实际臂/预算，不套当前Q的914人工门 |
| 从完成Phase2的运行恢复Phase3 | cle-training-run | 复用旧阶段写新目录，不重跑全部冷启动、不改旧指纹 |
| 运行Base/Plus Q三臂 | cle-frozen-evaluation | 检查原镜像和实际Q3支持；不照抄PLT隐藏反馈早停 |
| 解释多候选或Q失败 | cle-result-analysis | 区分任一候选上界、实际交付、采用及落实；按实际协议统计 |
| 继续当前检索四指标和Q任务 | cle-retrieval-q | 读取实际gate，区分模型/人工标签，不把0次人工确认写成性能失败 |

## 验证边界

结构合格、入口可读和只读工具的计数正确，证明本次技能包可被读取和复用；它们不证明CLE或Q已提升正确率，也不证明7项技能在所有未来任务中都不会误路由。后续出现真实使用失败时，修订对应技能或reference，不增加全项目的普遍审批和重复检查。

原有实验源码、经验库、数据、人工字段和历史运行目录未改写。仓库变化限项目skills源、两份中文调研/验证文档和README/AGENTS导航；本机发现入口留在Git仓库之外。
