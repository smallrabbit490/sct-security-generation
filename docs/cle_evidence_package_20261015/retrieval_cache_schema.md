# 检索缓存边界

已检查 `translation_work/cache/retrieval_hit/embedding.sqlite`。该 SQLite 文件约 78 MB，包含：

- `embeddings(version TEXT, model TEXT, text_hash TEXT, vector TEXT)`，约 2611 行；
- `dimensions(version TEXT, model TEXT, size INTEGER)`，1 行维度记录。

缓存没有保存原始查询文本、经验卡正文或任务 ID，只有内容哈希和向量。因此“实际向量化文本”无法从该缓存还原；本次没有重新调用 embedding 接口生成文本或缓存。

2026-10-14 v3 的运行元数据记录使用 `text-embedding-3-small`，六组输入为原题、初析以及两者组合，向量组为纯余弦检索；报告明确不使用模型重排、CWE 加权或词面权重。30 查询/38 卡小实验是独立的原始向量排序诊断，不能把其配置归因于正式 v3。
