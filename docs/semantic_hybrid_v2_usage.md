# CLE `semantic_hybrid_v2` 检索器

## 用途

`semantic_hybrid_v2` 是 CLE 的实验性语义混合检索模式。它把题目的公开上下文整理成固定字段，同时把经验卡整理成机制、触发条件、正向原则、负向护栏和语言提示，然后并行使用 embedding 召回与机制词面召回，最后由选择器从融合后的候选中最多选择三张卡。

默认模式仍然是 `flat_llm`。本模式不会自动改变默认配置，也不会把 Base/Plus 的测试结果写回经验库或检索规则。

## 启用方式

在仓库根目录运行 CLE 闭环入口：

```powershell
& D:/ANACONDA/python.exe `
  -m methods.sct_trajectory.run_closed_loop `
  --out translation_work/sct_runs/cle_semantic_hybrid_v2_dev/python `
  --retrieval-mode semantic_hybrid_v2 `
  --embedding-model text-embedding-3-large `
  --embedding-cache translation_work/cache/embeddings/cle.sqlite3
```

实际运行时仍需按开发实验指定 `--limit`、`--pool-manifest`、`--workers`、`--model` 等参数。`--out` 必须是新的空目录，且正式运行应遵守 `AGENTS.md` 中的 `translation_work/sct_runs/<run-name>/<round>/` 目录规则。

## 一次检索发生什么

1. 从题目公开字段提取语言、CWE、入口点、签名、不可信输入、敏感操作、功能与安全要求等信息。
2. 对完整候选经验池计算 embedding，保留相似度最高的 32 张；再按机制词、敏感操作等词面重叠保留 16 张。
3. 用 Reciprocal Rank Fusion 合并两路排名，最多交给选择器 12 张候选。
4. 选择器只能返回候选编号组成的 JSON，最多选择 3 张。重复编号、越界编号、截断或非法 JSON 都会被拒绝；格式重试仍失败时只允许在高置信条件下确定性选择 Top1，否则返回空结果。
5. 检索失败会在 `retrieval_audit` 和运行日志中显式记录，CLE 不会把失败静默伪装成“没有相关经验”。成功选择的卡片才进入原有 Analysis → Planning → CodeGen 流程。

## embedding 模型与缓存

默认模型是 ChatAnywhere 兼容的 `text-embedding-3-large`，可通过 `--embedding-model` 替换。缓存按模型、文本版本和内容哈希保存到 SQLite；相同题目或经验卡再次检索时会复用缓存，避免重复调用。缓存是可重建实验产物，不属于长期经验库。

## 如何查看结果

运行目录中的 `run_metadata.json` 记录实际 embedding 模型和参数；逐条检索轨迹会写入经验卡的 `retrieval_audit`。检查 `status`、候选数量、选择器尝试、错误类别和缓存用量时，应把“检索成功”与后续 Function/Secure/Joint 测试分开报告；本检索器本身不证明代码已经正确或安全。

