# 已完成成果与原始记录下载

个人分支：[`fjy/cle-contract-conditional-q-20261023`](https://github.com/smallrabbit490/sct-security-generation/tree/fjy/cle-contract-conditional-q-20261023)。本轮包含11月1日Q回测、记忆标签的接续与分层分析代码、报告和案例证据，工作台实时展示改动，以及11月2日已完成的经验检查可行性分析。旧报告、旧成绩和失败记录保留。

## 下载哪些文件？

| 下载入口 | 内容 | 保存位置 |
|---|---|---|
| [10月29日基础原始记录](https://github.com/smallrabbit490/sct-security-generation/releases/tag/cle-project-snapshot-20261029) | 63个`blobs-*.zip`分卷、`manifest.json`、`receipt.json`、`restore.py` | `base/` |
| [11月2日增量原始记录](https://github.com/smallrabbit490/sct-security-generation/releases/tag/cle-completed-evidence-20261102) | 新增或变化的原始记录分卷、`manifest.json`、`receipt.json`、`restore.py` | `increment/` |
| [10月22日历史快照](https://github.com/smallrabbit490/sct-security-generation/releases/tag/cle-project-snapshot-20261022) | 更早的独立历史包 | 单独保留，无需参与本次还原 |

两个新旧包中的文件名相同，请分别放在`base/`和`increment/`，不要相互覆盖。增量包复用基础包内的相同内容；完整下载两套附件后还原。基础包中的项目代码是历史快照，本次复算使用个人分支内的新代码。

基础归档含项目及原始运行记录；增量保留模型响应、生成代码、选卡、验证、旧失败、未知用量、冻结输入、预算、回放和分析。凭据与安装环境不上传，正在运行的工作台状态目录不纳入增量。文本中的凭据匹配项仅在导出副本脱敏，原始运行文件不修改。

## 怎样离线复算？

先下载或检出个人分支，并准备其声明的Python依赖。在仓库根执行：

```powershell
python -B -X utf8 tools/restore_cle_archives.py --base D:/CLE-download/base --increment D:/CLE-download/increment --output D:/CLE-restored --scope recompute
python -B -X utf8 tools/recompute_cle_closeout_20261101.py --run-root D:/CLE-restored/external_runs/20261027_full_requirements --output D:/CLE-restored/recomputed.json
```

`recompute`只还原统计所需的逐题记录、冻结输入及分析原件；程序关闭网络，复算按实际模型来源分层的各条件结果和配对比较，并与已保存统计核对。它不生成代码、不重发请求、不改Q或卡库、不修改实验目录。

预期完成数为Q540条、记忆标签820条；其中分别535条和819条可测。未测保留未测；1017完整结果、无1017完整结果及混合成功前缀分别统计。

需要两批全部请求、代码和回放证据时，换用新的空输出目录并指定`--scope closeout`；需要整个基础包与增量包时使用`--scope all`。还原程序检查路径、ZIP读取完整性及内容摘要，不覆盖已有文件。原生验证器完整回放的证书和对应源码随原始记录保留；上述快捷命令复算保存的测量结果，不重新执行生成代码。

## 结果与分析

- [11月1日综合报告：Markdown](reports/CLE-RPT-20261101-two-batch-closeout-v01/11月1日Q回测与记忆标签结果分析.md) · [Word](reports/CLE-RPT-20261101-two-batch-closeout-v01/11月1日Q回测与记忆标签结果分析.docx)
- [Q回测阶段报告](reports/CLE-RPT-20261101-Q-retest-v01/11月1日Q冻结回测结果与分析.md)
- [11月2日经验检查可行性报告](CLE-RPT-20261102-experience-check-feasibility.md)
- [两批最终统计登记](../../results/curated/cle_weekly_closeout_20261101/two_batch_closeout.json)
- [归档校验及发布登记](../../results/curated/cle_github_sync_20261102/verification.json)

本次同步不启动实验、不切换运行分支、不重启工作台；两批监控已暂停，排队全量继续跳过。
