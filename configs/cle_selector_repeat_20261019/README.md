# 四臂重复选卡：固定输入最小验证

仅复用固定48题的前8题首次查询/候选与冻结Q，每组每题重复5次，共160次选择操作。四组为原顺序、相似度、学习Q、同CWE打乱Q，均不限三张；不运行代码生成、验证、Embedding或Q更新。

协议见 `protocol.json`，实际名单由零API prepare 写入 `manifest.json`。原生选择提示与短编号协议保持一致。方法差异以跨组Jaccard距离减去组内重复距离衡量，按题族统计、按同题重复区组置换并作三项Holm校正。

```powershell
python -X utf8 -m methods.cle_ablation.run_selector_repeat prepare
python -X utf8 -m methods.cle_ablation.run_selector_repeat run
python -X utf8 -m methods.cle_ablation.run_selector_repeat report
python -X utf8 configs/cle_selector_repeat_20261019/finalize.py
```

原始记录：`translation_work/diagnostics/20261019/cle_selector_repeat/v1/`；精简结果：`results/curated/cle_selector_repeat_20261019/`。既有失败身份保留、不补跑；离线prompt捕获的模拟空响应只用于渲染提示，不计实验样本。

实际完成160/160合法选择，含一次原生格式重试，共161次逻辑请求、3,956,640回执Token。学习Q相对相似度、打乱Q的超额集合距离为0.0924、0.1122，三比较Holm校正p均0.0006；达到可检测影响门槛，不表示适用性或Joint改善。报告见 `docs/CLE_四臂重复选卡与模型波动分析_20261019.md`。
