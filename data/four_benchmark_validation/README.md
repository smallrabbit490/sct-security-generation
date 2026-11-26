# 四个基准的 Docker 参考回放

论文主线使用 SeCodePLT、CodeSecEval、AutoSUIT 和 CWEval。CodeSecEval 的 Base、Plus 独立统计。`tasks.csv` 固定了 2,199 个任务键及语言。此处的通过数来自对参考实现的测试回放。模型与 Agent 的正式评测应独立记录生成成功率、功能通过率、安全通过率及两项均通过率。

## 2026 年 11 月 24 日全量覆盖结果

| 基准 | 登记任务 | 参考通过 | 其余结果 |
|---|---:|---:|---|
| SeCodePLT，Python | 874 | 752 | 121 项参考检查失败，1 项执行错误 |
| CodeSecEval Base，Python | 115 | 114 | 1 项参考检查失败 |
| CodeSecEval Plus，Python | 140 | 137 | 3 项参考检查失败 |
| AutoSUIT，Python、Java、C、C++ | 951 | 132 | 656 项缺上游 `secure_code`，163 项至少一套测试未通过或缺测 |
| CWEval，Python、JavaScript、C、C++、Go | 119 | 106 | 10 项测试阶段错误，3 项 Go 编译超时 |
| 合计 | 2,199 | 1,241 | 958 项未达到参考回放通过条件 |

`results.csv` 提供按语言和状态的汇总。基数取 `tasks.csv`，结果按 `(group,id)` 去重。表中数据来自发布入口的一次连续全量回放。此前 CWEval 定向复跑同为 106/119 通过，当时有 12 项测试阶段错误和 1 项 Go 编译超时，说明两次运行的失败分布有所变化。AutoSUIT 另有 27 道 C 题无安全套件，这一计数可与缺参考实现重叠。CWEval 使用上游的 `functionality`、`security` 标记检查参考实现。命令退出码 0 表示 runner 正常结束，单题是否通过以 JSONL 的 `status` 为准。

首轮及 Java 修正复跑的 VHDX 检查为 FAIL，采样期间分别增长 1,073,741,824 和 3,892,314,112 字节，与镜像准备有时间重叠。CWEval 和 AutoSUIT C/C++ 定向复跑各自通过 VHDX 检查，增量均为 0 字节，池容器均正常收尾。使用本目录的发布入口在独立 checkout 重跑 CodeSecEval Base/Plus 共 255 项，参考通过数分别为 114、137，VHDX 增量为 0 字节。随后同一入口连续回放 2,199 项，耗时 1,944.74 秒，退出码 0，VHDX 检查通过且增量为 0 字节。峰值为一个池容器，结束时无残留。

## 准备数据和 Java 依赖

从仓库根目录运行命令。SeCodePLT 和 CodeSecEval 的本次输入已随仓库跟踪。

| 输入 | 固定来源 | 仓库根目录下的位置 |
|---|---|---|
| SeCodePLT | 本仓库版本 | `data/external/secodeplt/secodeplt/data.json` |
| CodeSecEval | 本仓库版本 | `data/SecEvoBasePlus/{Base,Plus}/Python_{Base,Plus}.json` |
| AutoSUIT | Hugging Face `amazon/AutoSUIT`，修订 `f76ff8b1cbf0f4859064a60b7621f2a62bdf03d7` | `data/external/autosuit/upstream_20261118/{python,c,cpp,java}/test.jsonl` |
| CWEval | GitHub `Co1lin/CWEval`，提交 `e9a2a124c8c53679b6d8d27adfd2f6c40e7576d7` | `data/external/cweval/upstream_20261117/`，保留 `benchmark/`、`cweval/`、`requirements/`、`go.mod` 和 `go.sum` |

AutoSUIT 的四个 JSONL 可按 `https://huggingface.co/datasets/amazon/AutoSUIT/resolve/<修订>/<语言>/test.jsonl` 下载。CWEval 使用固定提交的源码归档，解压后将归档根目录的上述子目录及文件放到表中位置。上游文件保留原样。

从 Maven Central 获取以下 JAR，放在 `translation_work/validation_runs/candidates_20261118/inputs/java/`。首个 JAR 放在该目录下，其余放在 `lib/` 子目录下。以表中的 group、artifact、version 在 Maven Central 查找，文件名为 `artifact-version.jar`。

| group | artifact | version |
|---|---|---|
| org.junit.platform | junit-platform-console-standalone | 1.9.3 |
| org.mockito | mockito-core | 5.5.0 |
| net.bytebuddy | byte-buddy | 1.14.8 |
| net.bytebuddy | byte-buddy-agent | 1.14.8 |
| org.objenesis | objenesis | 3.3 |

## 构建并运行

本次使用 Windows Docker Desktop 的 Linux 容器模式、Python 3.11 或以上、带 Node.js 和 JDK 17 的本地镜像 `secevo-java-js-baseplus-validator:current`。复用本次镜像 `cle-four-bank-go:20261124` 可跳过两步 Docker 构建。缺少历史本地基座时，可以基于 Debian Bookworm 的 Node.js 20 镜像安装 `openjdk-17-jdk-headless` 后打同名标签。替代基座的从零构建和结果等价性尚未验证。镜像构建依赖镜像仓库、APT、PyPI、npm 和 Go 模块源，依赖索引保留了浮动版本，跨时间复现建议保留已验证镜像。

```powershell
$PY = (Get-Command python).Source
docker build -t cle-external-bank:20261117 -f data/four_benchmark_validation/Dockerfile data/four_benchmark_validation
docker build -t cle-four-bank-go:20261124 -f data/four_benchmark_validation/Dockerfile.go data/four_benchmark_validation
& $PY -X utf8 data/four_benchmark_validation/prepare.py
& $PY -X utf8 data/four_benchmark_validation/go_deps.py
& $PY -X utf8 tools/vhdx_watchdog.py --label four_benchmark_replay --max-containers 1 -- $PY -X utf8 data/four_benchmark_validation/launch.py
```

准备阶段在联网时完成。回放阶段复用一个断网常驻容器，测试夹具生成后置于 `translation_work/`，Java JAR 只读挂载。不要同时在同一 checkout 启动两个回放。可在 `launch.py` 后加 `plt`、`codeseceval-base`、`codeseceval-plus`、`autosuit` 或 `cweval`，也可以用 `autosuit:cpp` 等语言选择。默认跑完整清单。复跑会覆盖当前 `replay.jsonl`，保留历史时先复制结果和相应 watchdog 报告。

逐题结果 `replay.jsonl` 和执行摘要 `replay_execution.json` 写入 `translation_work/validation_runs/four_benchmark_20261124/`。VHDX 报告写入 `translation_work/diagnostics/`。全量核验需确认 2,199 行的 `(group,id,language)` 与 `tasks.csv` 完全一致，并分别检查容器退出状态、VHDX 报告和题级状态。

## 下载已验证镜像和逐题结果

[GitHub Release](https://github.com/smallrabbit490/sct-security-generation/releases/tag/four-benchmark-replay-20261124) 提供实际回放镜像 `four-benchmark-image.tar` 以及归档的 `SHA256SUMS.txt`。镜像适用于 `linux/amd64`。下载后对照 SHA-256，再运行 `docker image load -i four-benchmark-image.tar`。加载后可跳过两步 Docker 构建，随后按上文准备数据、Java 依赖和 Go 模块缓存。

[逐题结果](task_outcomes.csv) 保留 1,241 条通过及 958 条未通过或缺测记录。[修复清单](REPAIR_QUEUE.md) 汇总待定位项、已知缺测及排查顺序，[逐题待处理表](repair_queue.csv) 给出任务键。上游快照通过固定版本下载，[SHA-256 清单](upstream_SHA256SUMS.txt) 用于核对本次用到的 354 个快照文件。

SeCodePLT 的 35 道安全侧失败题已补齐[原始逐用例回执及批次校验值](security_evidence_20261124/README.md)。
