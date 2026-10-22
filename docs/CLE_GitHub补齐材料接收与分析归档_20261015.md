# CLE GitHub 补齐材料接收与分析归档

接收日期：2026-10-15。项目：华南理工大学实验室 CLE 课题。本轮完成远端分支获取、现有材料接收、离线复算和研究记录更新；没有产生新的模型实验成绩。

后续状态：本文记录的是首次文件接收；两条来源分支现已通过`3468b24`和`5ca7b98`实际合入本地`fjy/cle-memory-q-batch2`。14份材料内容未变化，原始pools与完整args仍未提供。新的核验依据见[两分支复盘与合并记录](CLE_两分支复盘与合并记录_20261015.md)，下文保留原接收时的事实与归档位置。

**结论：1939张完整经验卡和30查询/38卡检索小实验已经接收；303个来源任务的题目与参考修复材料可由现有数据文件完整关联。原题“100%检索”、完整原题/抽象对照以及可供Q值学习的逐次采用与测试记录，仍未补齐。** 历史网页包是35个目录的摘要快照，不能替代完整运行目录。

## 1. 分支、版本与本地归档

原克隆的 fetch refspec 仅跟踪 `master`。本轮通过 `git ls-remote --heads origin` 发现新增分支，随后显式获取全部远端分支，固定以下来源版本：

| 来源 | 接收提交 | 提交时间（北京时间） | 新增内容 |
|---|---|---|---|
| [codex/branch-global-gate-20260923](https://github.com/smallrabbit490/sct-security-generation/tree/0ae2799dc3a6039b7dcc4e109d85d021172fe0bd) | `0ae2799dc3a6039b7dcc4e109d85d021172fe0bd` | 2026-10-15 13:54:06 | 10个材料包文件 |
| [codex/cle-web-history-20261015](https://github.com/smallrabbit490/sct-security-generation/tree/a6164b2fa833438ce5e395584f90fb194ea8d018) | `a6164b2fa833438ce5e395584f90fb194ea8d018` | 2026-10-15 17:07:44 | 3个历史快照文件、1个导出脚本 |
| `master` | `9716432988a8b8939e4019a6966c24f17bbd1fbb` | 本轮未更新 | 尚未包含上述两个分支的新增包 |

两个新增分支分别包含材料，最新时间的历史分支没有包含经验卡分支。本地继续使用 `fjy/cle-workbench-v2`，原有工作台、Q任务书和README改动保留。接收14个新增文件，合计11,413,798字节；接收后的文件及本报告目前为本地未提交内容。

| 本地位置（相对项目根目录） | 内容 |
|---|---|
| [docs/cle_evidence_package_20261015/](cle_evidence_package_20261015/README.md) | 1939卡、303任务索引、来源/缓存说明、小实验四件套 |
| [docs/cle_web_history_20261015/](cle_web_history_20261015/README.md) | 历史盘点说明、manifest、runs_summary |
| [tools/export_cle_dashboard_history.py](../tools/export_cle_dashboard_history.py) | 源端快照导出脚本；本轮只读代码，没有执行 |
| `translation_work/diagnostics/20261015/cle_github_receipt/` | 两个按提交导出的ZIP、接收单、分析脚本及复算JSON |

归档目录中的文件为：

```text
evidence_0ae2799.zip
history_a6164b2.zip
receipt.json                 # 分支、提交、逐文件路径及大小
analyze_received.py           # 只读JSON/JSONL与Git对象的离线复算
analysis_summary.json         # 完整计数、35个目录的状态/成绩摘录
```

原始包保持接收内容。Git blob采用LF，当前ZIP导出的副本采用CRLF；卡片、gold和历史快照在统一换行后与指定提交的blob一致。卡片本地摘要吻合源端原文件摘要，gold吻合预注册摘要，历史快照吻合manifest。换行导致的字节/摘要差异没有被判作材料损坏。

## 2. 对昨天六类清单的逐项结论

| 清单项 | 本轮接收与独立核验 | 仍缺什么 |
|---|---|---|
| 1. 实际1939张卡 | 完整JSONL可解析，1939个唯一ID；源端说明关联paired273输入；原文件摘要相符 | 翻译前独立版本未提供；paired273原始run_metadata尚未随包接收，历史使用关系目前依据提供方说明 |
| 2. 来源题目与修复材料 | 303个来源ID及计数与卡片一致；全部可关联现有data.json中的题目、漏洞和参考修复；数据与family文件摘要吻合来源说明 | 逐卡生成prompt、真实输入包和原始模型输出未找到 |
| 3. 原题100%检索记录 | 未收到能复算这一说法的逐查询材料 | 原查询、正确卡ID、排序/分数、分母、指标定义、当次配置与代码版本 |
| 4. 实际embedding文本/缓存 | 收到缓存结构与配置说明；小实验有明确文本 | 正式检索实际输入文本、查询/卡ID对应、缓存原件及准确的当次配置；只存text_hash的缓存不能还原文本 |
| 5. 30查询/38卡小实验 | gold、预注册、逐查询结果、报告齐全；三模型Top1/Recall@3重算一致 | 全向量、缓存与执行脚本未随包接收；不妨碍复核已保存的Top1/Recall@3，仍不能重新执行向量计算 |
| 6. 原题/抽象检索对照v3 | 收到清单中的结果说明 | 正式run_metadata、逐条rows、盲评输入/标签、完整摘要报告未接收；人工标签原件仍缺 |

v3的“1194条、模型辅助标签、人工复核待做、动态验证未测”是**提供方清单中的报告**，本轮没有原件可独立复算。不能把“知道原路径”记成“已收到文件”。

## 3. 1939张卡到底包含什么

### 3.1 完整计数

| 项目 | 本轮复算 |
|---|---:|
| 卡片总数 / 唯一invariant_id | 1939 / 1939 |
| 可关联来源任务 | 303 |
| CWE类别 | 18 |
| source.stage=phase1 | 1939 |
| status=provisional | 1939 |
| language_leaves仅含python | 1939 |
| 语言叶中非空的safe/prohibited constructs或pattern_snippet | 0 |
| high_level_invariant不同文本数 | 1905 |
| support_count=0 | 1636 |
| regression_count=0 | 1939 |
| 已有q_value或q_visits | 0 |

`utility`逐条等于 `(support_count+1)/(regression_count+1)`，是原有统计式，不是MemRL式Q。回归计数为0也不能证明从未造成回归；该字段缺少逐次采用、测量和归因信息。

来源类型为：seed_from_diff 246，direct_A 48，minimal_patch_hint 516，overdefense_pitfall 502，round_0_fail 255，round_1_fail 225，C_stalled 75，B_stalled 13，D_stalled 39，D_to_A 3，C_to_A 16，B_to_A 1。卡片混合了参考修复提炼、成功路径、失败轨迹和局部修复提醒；“在库中”不等于“已经验证有效”。

### 3.2 原题信息是否保留

固定结构包含高层原则、适用条件、正向原则、负向护栏；`source`还保留task_id、根因、修复指令和部分轮次/失败信息。它不是只保存题目ID的空索引，也不能整体视为完全泛化的抽象经验。

例如来源Task 834的 `hint-77-758701235808510434` 直接出现 `_select_pattern`、`parse_query`、具体正则和 `SELECT name FROM dataset WHERE age gt 25 ORDER BY name ASC` 等细节，足以体现原任务/运行上下文。其他卡也包含具体异常、函数或修补步骤。卡片没有单设完整原题、漏洞代码和参考修复三个字段，但**保留具体细节与完整字段存储是两回事**。

因此，你原先提出的疑问成立：同题生成的卡再被同题召回，即使命中率很高，也需要排查词面与任务特定信息的贡献，不能直接证明跨题迁移。现有材料同样不能断言当次实验使用了task_id加分；需要该次配置/代码快照，而不能从其他检索模式推定。

### 3.3 与本地来源材料关联

关联链已经核验：

```text
card.source.task_id
  -> data/external/secodeplt/secodeplt/data.json 的 index
  -> task_description.description
  -> ground_truth.vulnerable_code / patched_code

同一index
  -> data/external/secodeplt/derived_metadata/family_manifest.json
     的 row_classification[index]
```

303个来源任务均有描述及两种代码；1939张卡与来源任务的CWE一致。原数据共1411行，不应把1411误记为本次经验来源任务数。family映射是项目推断的语义族，文件注明并非PLT官方谱系字段。

来源数据的本地SHA256分别为 `4779e09d14fb2a2a1a6912cca9e6403fea02470b9963b7d5a438d371c9416839` 和 `6bca9c7eee8a1e93d11256693b24eff73626854bcddcb52ba8bf65008ecf5267`，与接收说明一致，故无需再索要整份数据集。原实验的具体三池分配仍需pools原件。

## 4. 小实验里的100%代表什么

按gold中的相关卡ID，对每条保存的top5重算Top1与Recall@3；MRR由保存的gold_rank复算。三模型均30条查询，数据有38张卡；每模型usage记录68条嵌入文本。

| 模型 | Top1 | Recall@3 | MRR（记录排名复算） |
|---|---:|---:|---:|
| text-embedding-3-large | 21/30（70.00%） | 29/30（96.67%） | 0.836111 |
| text-embedding-3-small | 20/30（66.67%） | 30/30（100.00%） | 0.816667 |
| text-embedding-ada-002 | 16/30（53.33%） | 29/30（96.67%） | 0.747222 |

该100%是**自编英文小集的Recall@3**。small有10条查询的第一名不是目标卡。它没有测试原题查询、1939卡全库、CLE的最终采纳或代码JointPass，也不是独立人工标注的大样本检索评测。保留它作为embedding健全性诊断，不替代原题检索证据。

## 5. 网页历史包能支持哪些判断

### 5.1 35个目录不等于35场已完成实验

复算目录数35、文件数4693、源端总字节4,086,217,751、网页相关候选文件字节439,348,742，与manifest一致。这些是**源端盘点数字**；本轮接收的历史文件及脚本共3,694,586字节。

快照中的status为：completed 13、failed 3、stopped 1、running 7、缺少status 11。running只是文件最后保存的状态，不表示源端现在仍在运行。矩阵容器下的子实验没有被递归展开成独立运行记录；不能据此重建完整消融矩阵。

源端JSONL行数合计为：Phase1 2340、round 31、audit 288、gate 712、final_eval 1600。它们来自不同运行和续跑，不能相加充当独立任务样本量；本轮也没有接收这些逐行原件。

### 5.2 摘要中可以读取的历史结果

| 运行 | 评测池n | Joint通过 | 解释范围 |
|---|---:|---:|---|
| cle_full_874_20260919 | 298 | 64 | 旧流程摘要 |
| cle_full_874_v2_resumed_20260920 | 298 | 59 | 有final摘要，status仍保留running |
| cle_full_874_20260922 | 298 | 54 | 旧流程摘要 |
| cle_context_874_chainverified_20260923_fast80b | 298 | 67 | context链路阶段摘要 |
| cle_full_deepseek32_20260924_phase3_resume_20260925 | 298 | 80 | 使用D_gate选择后的filtered结果，明确非独立heldout |
| cle_prompt_full_20260929 | 64 | 18 | 使用D_gate选择后的filtered结果，明确非独立heldout |

两份较完整的三臂摘要如下，模型元数据均为deepseek-v3.2：

| 运行与分母 | 组别 | 功能通过 | 安全通过 | Joint通过 |
|---|---|---:|---:|---:|
| 20260925 / 298 | baseline | 84 | 198 | 62 |
| 同上 | memory | 83 | 213 | 67 |
| 同上 | filtered | 92 | 224 | 80 |
| 20260929 / 64 | baseline | 27 | 46 | 20 |
| 同上 | memory | 25 | 43 | 16 |
| 同上 | filtered | 25 | 46 | 18 |

这些来自源端保存的汇总，本轮没有逐题原件来重算。两场均明确 `independent_heldout=false`；日期间的配置、样本及流程也不同，不能把64→59→54→67→80串成同条件改进曲线。298题的筛选池结果不能写成Base/Plus或Q机制的独立泛化收益。

### 5.3 导出会丢掉什么

导出脚本的 `redact()` 对所有列表取前100项、所有字符串取前1000字符，并删除args等字段。例如298题运行的失败列表只保留100项，不能据此重新核算失败比例、配对显著性或逐卡奖励。文件中的safe_artifact摘要对应源端原文件，嵌入content则经过裁剪，不能把两者当成逐字一致。

本机 `translation_work/sct_runs/` 仍不存在。旧/新工作台都依赖该运行目录，本包不会自动变成网页上的完整真实运行；历史概览可后续接入摘要，但轨迹、代码对照、实际采用、门控细节仍需对应原件。

## 6. 对记忆Q值任务的直接影响

已经具备：真实固定卡库候选、303任务来源映射、旧检索小实验和部分历史汇总。现在可以检查卡片载入、设计Q字段和排序规则，不必重新生成1939张卡。

尚不具备：确认过的D_init/D_grow/D_audit分配、当次无密钥配置、逐次生成实际采用的卡ID及其对应功能/安全测量。历史 `retrieved_ids` 或失败任务列表不能替代“实际采用→本次生成→本次测量”的配对关系，最终评测/门控反馈也不能转作训练奖励。

实施顺序仍沿用 [Q值接入任务书](CLE_MemRL记忆Q值接入方案与实验任务书_20261015.md)：固定经验内容，在许可训练池校准Q，冻结后以共同候选和预算比较当前CLE、semantic_sim、semantic_q。本轮未实现Q，也没有运行提分实验。

## 7. 后续只需补交的具体原件

1. **固定1939库的运行关联**：`.../paired_full_273/run_metadata.json`、实际无密钥命令/配置及 `source_snapshot/`；源头 `pools.json` 和family/任务ID分配。经验库与整套data.json已经收到，不再重复索要。
2. **许可Q训练轨迹**：选定真实D_grow运行的逐次c0/c1记录，至少保留任务ID、阶段、实际采用卡ID、对应功能/安全状态及测量是否完整。原文件若没有采用记录，注明缺失，不能把召回卡改写成采用卡。
3. **原题100%记录**：若原先没有做过，则结论维持“尚未定位/未验证”；不另生成一个实验冒充历史证据。
4. **v3对照原件**：`translation_work/diagnostics/20261014/retrieval_hit_accuracy_v3/` 下的run_metadata、实际六组输入、rows、盲评包、标签和完整summary/report；人工复核文件若不存在继续标缺。
5. **真实工作台回看**：按需要选定一个完整CLE运行，交付pools、phase1/trajectories/rounds、gate/audit、树快照、经验池和final相关原件。保留原目录关系；目前无需索要全部4GB历史。

以上运行材料按仓库既有规则保留在忽略区或脱敏离线包中。后续归档只接收既有材料，不为补历史启动付费调用。

## 8. 本轮验证

执行 `python -X utf8 translation_work/diagnostics/20261015/cle_github_receipt/analyze_received.py`：1939卡解析和ID唯一性、303任务索引计数/材料关联、三模型逐查询指标、35目录合计及所列源文件摘要均通过。没有运行模型、embedding、任务代码或历史快照导出脚本。
