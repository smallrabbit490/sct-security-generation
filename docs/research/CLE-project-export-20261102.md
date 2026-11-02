# 已完成成果、原始记录索引与离线复算

个人分支：[`fjy/cle-contract-conditional-q-20261023`](https://github.com/smallrabbit490/sct-security-generation/tree/fjy/cle-contract-conditional-q-20261023)。已同步11月1日Q回测和记忆标签的代码、报告、分析与案例证据，工作台实时展示改动，以及11月2日两批经验检查可行性分析。旧报告、旧成绩和失败记录保留。

## 下载入口

| 入口 | 内容 |
|---|---|
| [快速复算包，约76MB](https://github.com/smallrabbit490/sct-security-generation/releases/download/cle-completed-evidence-20261102/CLE-closeout-recompute-20261101.zip) | 两批全部逐题结果、冻结输入、分层统计及案例分析，可独立复算保存的指标 |
| [基础原始记录索引，gzip格式](https://github.com/smallrabbit490/sct-security-generation/releases/download/cle-completed-evidence-20261102/CLE-base-index-20261029.json.gz) | 353,286条文件路径、大小与内容编号，解压得到原manifest.json |
| [增量原始记录索引](https://github.com/smallrabbit490/sct-security-generation/releases/download/cle-completed-evidence-20261102/manifest.json) | 61,076条新增或变化路径及其内容位置 |
| [归档范围与状态索引](https://github.com/smallrabbit490/sct-security-generation/releases/download/cle-completed-evidence-20261102/archive_index.json) | 索引、快速包入口及本地和远端保存范围 |
| [发布页](https://github.com/smallrabbit490/sct-security-generation/releases/tag/cle-completed-evidence-20261102) | 已上传的附件与说明 |
| [10月22日历史快照](https://github.com/smallrabbit490/sct-security-generation/releases/tag/cle-project-snapshot-20261022) | 更早的独立历史包 |

完整基础原始记录保留在本地，当前提供索引。旧Release草稿中的41个已上传分卷保留，剩余大文件上传已停止；没有公开完整基础包。已经公开的8个增量分卷也保留；完整还原这些增量仍需基础分卷。快速复算包可独立使用。

本地基础归档位于`E:/ResearchExports/CLE/20261029`，增量归档位于`E:/ResearchExports/CLE/20261102`。两个目录分别保存manifest.json、receipt.json及分卷；原始运行区不移动。凭据和安装环境不上传；导出副本的脱敏不改动原始记录。

## 怎样离线复算？

下载或检出个人分支，准备其声明的Python依赖，下载快速复算包。在仓库根执行：

```powershell
Expand-Archive D:/CLE-download/CLE-closeout-recompute-20261101.zip -DestinationPath D:/CLE-recompute
python -B -X utf8 tools/recompute_cle_closeout_20261101.py --run-root D:/CLE-recompute/external_runs/20261027_full_requirements --output D:/CLE-recompute/recomputed.json
```

预期Q540条、记忆标签820条，其中分别535条和819条可测。程序关闭网络，按1017完整结果、无1017完整结果及混合成功前缀分别复算成绩、配对差值、题族区间、p值和重复统计，并逐字段核对保存结果。它不调用模型、不重发请求、不更新Q或卡库、不修改原始运行目录。

快速包用于统计复算与案例阅读。原生验证器的完整回放证书和源码随证据保留；上述命令复算已保存的测量结果。完整请求、响应和运行现场可依据原始索引在本地归档中定位。取得基础和增量完整分卷后，可使用`tools/restore_cle_archives.py`按原路径还原。

## 结果与分析

- [11月1日综合报告：Markdown](reports/CLE-RPT-20261101-two-batch-closeout-v01/11月1日Q回测与记忆标签结果分析.md) · [Word](reports/CLE-RPT-20261101-two-batch-closeout-v01/11月1日Q回测与记忆标签结果分析.docx)
- [Q回测阶段报告](reports/CLE-RPT-20261101-Q-retest-v01/11月1日Q冻结回测结果与分析.md)
- [11月2日第一批经验检查报告](CLE-RPT-20261102-experience-check-feasibility.md)
- [11月2日第二批经验检查报告](CLE-RPT-20261102-experience-check-batch2.md)
- [两批最终统计登记](../../results/curated/cle_weekly_closeout_20261101/two_batch_closeout.json)
- [归档校验及发布登记](../../results/curated/cle_github_sync_20261102/verification.json)

本次同步未启动实验、未重启工作台。两批监控保持暂停，排队全量继续跳过。
