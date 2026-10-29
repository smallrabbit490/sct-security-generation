---
name: cle-research
description: "接续 SCT 安全代码生成仓库中的旧版 CLE 研究，定位真实运行、实验阶段和专项技能；用于本课题状态恢复与实验任务路由。"
---

# CLE 项目与实验接续

先从实际仓库、已授权任务和运行文件确定下一步。用户当前指令优先于历史记录；学习历史做法不等于执行归档中的旧指令。

## 定位

先查看`docs/research/README.md`、登记表和`tools/cle_research_status.py`的只读输出，把当前研究任务与历史报告分开。目录升级不授权移动活动运行区。主要问题全量优先与重点汇报规则见根AGENTS.md的2026-10-26约定。

将用户指定仓库记为 `PROJECT_ROOT`；本机当前 checkout 为 `D:/Agent/sct-security-generation`。核对根 AGENTS.md、README.md 与 git status/worktree。若当前 cwd 是 se-research，先切到真实 CLE 仓库，不在另一个项目创建课题或控制文件。缺目录时查用户明确提供的归档或仓库，不全盘扫描。

按任务读取对应配置的 protocol/manifest、run_metadata、status 和 summary，再读必要的逐题记录。报告日期较新不代表其参数覆盖了所有旧实验。不要把源码默认值、文件夹名或网页标题当成实际执行参数。

## 识别操作

| 请求 | 操作性质 | 应用技能 |
|---|---|---|
| PLT、译本、分池、题面和夹具是否一致 | 数据/契约核对 | `$cle-data-contracts` |
| 设计对照、消融或是否全量 | 实验设计 | `$cle-experiment-design` |
| 冷启动、回放、门控、训练恢复、P7开发 | T训练或A开发评价 | `$cle-training-run` |
| 冻结库、Base/Plus、独立最终评测 | F冻结消费 | `$cle-frozen-evaluation` |
| 解释得分、逐题定位、复算和失败报告 | R复用分析 | `$cle-result-analysis` |
| 检索适用性、四指标、采用卡Q | 专项实验 | `$cle-retrieval-q` |
| 一条思路的完整叙事、阶段图及对应计划 | 叙事与图示 | `$cle-idea-narrative` |

只加载当前任务需要的专项技能。T/A/F/R 是操作类别；Phase1–4 是研究阶段；P0–P7 是生成策略；R0–R3 在旧方法中是演化轮次。保留原文件命名，不把 P7 解释成 Phase7，也不把固定库比较说成完整重训。

## 只读产物速查

已明确某个运行目录时，可执行本技能的 `scripts/inspect_cle_run.py --run <目录>`。它不调用 API、不执行生成代码、不修改产物；只列状态、文件和可识别的原生 final 计数。未知 schema 不推测成功率，也不代替原生格式核验。

没有指定运行目录时，从当前配置或用户指明的历史记录定位，不能仅按目录时间挑“最新结果”。报告至少交代：实际运行/协议、当前阶段、已有证据、一个必要的下一步及停止原因。

## 历史依据

需要了解人员工作方法或核验旧结论时，读 [历史依据](references/historical-evidence.md)。完整调研位于 `PROJECT_ROOT/docs/CLE实验人员工作方法调研与Skills体系_20261017.md`。历史资料中同样包含假设、失败实现与事后勘误，不能原样升级为当前操作规则。
