# Qualified Risk Review Implementation Plan

> **For agentic workers:** 当前会话内执行，用户已批准完整设计与push。

**Goal:** 659题独立双判、历史低通过交集至多50题、可视化人工复核与主分支发布。

**Architecture:** 新工具复用现有逐尝试落盘调度和密钥解析，独立schema/协议/目录；冻结历史元数据与去重代码哈希；只向API提供题面与测试，不给旧标签/历史；原标签不改。发布时导出共识与人工题包，扩展现有工作台选择题包。

**Tech Stack:** Python标准库、ThreadPoolExecutor、JSONL/CSV/Markdown、现有原生HTML/JS工作台。

- [x] 新增 tests/test_qualified_risk_audit.py：举证伪造、测试损坏不得充当题面风险、共识/缺测、去重/环境排除、50上限；先运行观察失败。
- [x] 新增 tools/qualified_risk_audit.py：prepare/launch/aggregate。prepare冻结659材料与历史分层；launch复用run，10并发，3次总尝试，按身份复用；6次冒烟成功后同名单全量。
- [x] 全量运行同时完善文档、扩展tools/dataset_review.py的题包参数与新题包一致性选项；默认150题不变。针对新包的旧合格确认/否定流程加测试。
- [x] aggregate保留每题双判与缺测，生成A/B/交集和至多50题人工包，独立标签/证据/原合格确认字段。
- [x] 核验原标签未变、输入哈希/逐字引文、计数、抽样与UI数据隔离、Python/Node测试、无密钥。独立Git index基于最新origin/master提交并push，核验远端SHA。
