# Plus 冻结经验双臂评测（2026-09-22）

## 目的与边界

使用训练运行 `cle_full_874_20260922/frozen/m_star.jsonl` 的完整 4518 条冻结记录，
比较纯 prompt 拼接与现有 CLE 四步生成流水线。检索器使用当前
`methods/sct_trajectory/retriever.py` 的 `hier_llm` 模式，底层为
`hier_retrieval.py`，不是 lifecycle 的旧 TF-IDF 检索器。

仅评测 Python Plus 140 题。两臂读取完整 Problem 和 Entry_Point，不提供
Secure Code、测试源码或 Insecure Code；官方安全实现只用于独立正向校准。
两臂首轮共享同一次检索卡片，失败后各重新检索并最多修复一次；通过后提前停止。
修复反馈仅限当前任务的功能/安全/语法状态与异常类别，不含测试输入、期望答案。
不蒸馏 Plus 经验，不修改冻结库，不参与门控或 H_pass。修复后分数属于测试反馈
辅助的有限修复协议，应与首次分数分别报告，不能冒充无反馈 pass@1。

完整冻结文件保留全部状态；实际可检索状态沿用 A7 的
active/provisional/consolidated，并要求 Python 语言叶。retired、unmeasured
记录不会因“完整加载”而绕过现有检索器的状态筛选。

四步臂直接复用 `agent_pipeline.run_pipeline`、`contract_freeze=True`。
与当前 Phase2 调用代码一致，调用方先检索，再运行 Analysis/Planning/CodeGen；
不是另外实现一个“Analysis 输出重写检索查询”的新变体。
纯 prompt 臂使用同一个 `dual_track_text` 渲染器拼接经验，单次生成调用。
模型为 deepseek-v3.2，temperature=0，单请求 max_tokens=2048；两臂均单轮修复。
四步臂调用预算自然高于单 prompt，因此这是方法比较，不是等 token 预算比较。

## Docker 运行纪律

复用 `python_validator.validate_python_secure` → `run_docker_task` → 常驻容器池，
不新增逐任务 docker run。池大小等于 workers；跑前清理残留池，finally 收回池；
仅挂载 translation_work，不挂仓库根。所有真实验证都由 watchdog 包裹。

```powershell
& D:/ANACONDA/python.exe -u tools/vhdx_watchdog.py `
  --label cle_plus_hier_comparison_20260922 --max-containers 8 --interval 2 -- `
  D:/ANACONDA/python.exe -u -m methods.sct_trajectory.run_plus_frozen_comparison `
  --out translation_work/validation_runs/cle_plus_hier_comparison_20260922/python `
  --workers 8
```

结果包含逐题首轮/修复轮代码、生成阶段记录、检索卡片及层次选择轨迹、Docker
功能/安全证据、summary、用量、源码快照、数据与记忆哈希。未执行的静态分析、
类型检查、资源测量保留 unmeasured。最终以 M* 文件哈希检查没有回写。

## 前置检查与运行位置

- `cle_plus_hier_calibration_20260922/python`：官方安全实现 140/140 Joint；watchdog PASS，VHDX +0 字节。
- `cle_plus_hier_smoke_20260922/python`：2 题双臂真实链路；watchdog PASS，VHDX +0 字节。
- `cle_plus_hier_comparison_20260922/python`：全量双臂结果目录。

以上目录均位于 `translation_work/validation_runs/`；watchdog 报告位于
`translation_work/diagnostics/vhdx_watchdog_<label>.json`。保留最终 rows、summary、
元数据与报告，不在本次任务中清理历史实验。

早期 `cle_plus_frozen_hier_20260922` 启动先因缺少 main 调用空运行；随后发现
评测适配器两臂输入与反馈格式不一致，主动中止，不能作为有效对比。该次 watchdog
报告为 FAIL（进程中止/采样收尾），VHDX 增量为 0；残留的单个池容器已显式清理。
此后重新进行全量正向校准、模型冒烟和新目录正式对比，未覆盖此失败证据。

## 全量结果

运行时间 18:28:25–19:01:45，约 33 分钟；deepseek-v3.2，2114 次成功返回的
模型调用，合计 4,638,761 tokens（包含检索）。280 条方法任务记录，505 次候选验证。

| 方法 | 阶段 | Function | Secure | Joint |
|---|---|---:|---:|---:|
| prompt 拼接 + 层次检索 + M* | 首次 | 109/140（77.86%） | 35/140（25.00%） | 32/140（22.86%） |
| prompt 拼接 + 层次检索 + M* | 最多一次修复后 | 106/140（75.71%） | 39/140（27.86%） | 37/140（26.43%） |
| CLE 四步 + 层次检索 + M* | 首次 | 101/140（72.14%） | 23/140（16.43%） | 23/140（16.43%） |
| CLE 四步 + 层次检索 + M* | 最多一次修复后 | 100/140（71.43%） | 25/140（17.86%） | 25/140（17.86%） |

prompt 组修复 108 题，新增 Joint 5 题（4.63%）；四步组修复 117 题，新增 Joint
2 题（1.71%）。两组最终 Joint 相差 12 题、8.57 个百分点。按题配对，prompt 独胜
27 题、四步独胜 15 题，双侧精确 McNemar p≈0.0884；单次结果不能证明稳定优势。

修复后四态：prompt A37/B69/C2/D32，四步 A25/B75/C0/D40。
瓶颈主要是功能通过但安全失败；修复的联合收益小，且两组功能通过数都略有下降。
prompt 108 条修复中 63 条代码发生变化；四步 117 条中 59 条发生变化。
不能单凭这些统计断言层次检索或整个 CLE 无效：本次没有无经验臂，且只做一次运行。
与旧本地评测存在后端、任务输入、记忆定义与反馈协议差异，不能直接归因比较。

核验：官方正向对照 140/140；所有候选代码非空，environment_error 为 0；
505 条轨迹无层次检索规则回退。四步臂出现 2 次中间 JSON 解析降级（一次 Analysis、
一次 Planning），均继续生成并验证，不能称所有中间步骤都无异常。
冻结记忆及运行源码哈希保持一致。watchdog PASS，VHDX 增量 0 字节，池峰值 8、
末次 0，无残留容器。15 项入口/流水线测试通过。

机器结果：`translation_work/validation_runs/cle_plus_hier_comparison_20260922/python/`。
该目录保留 `rows.jsonl`、`summary.json`、`run_metadata.json`、`usage.json`、
`calibration.json`、`source_snapshot/` 和 `report.md`。
