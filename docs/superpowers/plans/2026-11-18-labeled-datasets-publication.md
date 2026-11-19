# 标注数据发布实施计划

> **For agentic workers:** 使用 executing-plans 在当前会话逐项执行；用户已授权上传主分支，不再重复询问执行方式。

**Goal:** 发布可追溯的全题标签快照、实际prompt、150条缺陷人工复核材料和许可明确的下载数据。

**Architecture:** 从冻结payload与成功响应离线导出；旧v2保留首判与分歧，新库严格双判；通过独立Git index在origin/master上构造提交，保护现有分支及未提交改动。

**Tech Stack:** Python标准库、JSONL/CSV/Markdown、Git。

- [x] 读取三个审计目录，校验新协议逐字证据，导出每库标签与统计，保留缺测。
- [x] 导出真实system/user模板，记录版本、SHA256及历史口径差异。
- [x] 固定种子分层抽取150条有缺陷样本，PLT60/Base40/Plus20/其他30；导出盲审题包、单独模型标签、空白CSV及人工标注规则。
- [x] 上传许可明确快照、保留许可证；未明确许可的三库只发布标签与恢复清单。
- [x] 校验数量、唯一ID、抽样标签、文件大小、敏感信息；以origin/master构建独立提交，检查后推送并核验远端SHA。
