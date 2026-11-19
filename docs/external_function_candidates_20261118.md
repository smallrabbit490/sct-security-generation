# 新增函数粒度候选数据与 Docker 环境（2026-11-18）

本批不调用模型 API。第三方原始文件保留上游内容，快照在 `data/external/<名称>/upstream_20261118/`，版本和逐文件 SHA-256 在同级 manifest。外部数据不直接计入正式得分。

| 数据 | 已下载范围 | 评判方式与边界 |
|---|---|---|
| AutoSUIT | 951 题：Python 113、Java 365、C 277、C++ 196；官方自包含 JSONL、卡片和转换脚本 | 功能/安全测试分列；27 个 C 样本无安全测试；上游 secure_code 为空：Java 282、C 225、C++ 149（不影响题面与测试下载完整性）。含程序片段，不能一概称为严格单函数 |
| PythonSecurityEval | 470 题面、458 份单测；排除旧 LLMSecEval/SecurityEval 副本 | 12 题缺单测。测试含占位模块名，需要生成代码适配，不能直接把占位导入失败算为题目缺陷 |
| LSCBench Function | 150 个 Function 任务，含题面、环境、参考解与验证器；排除 File/Repo 与历史模型轨迹 | 有仓库上下文的函数重建，非独立函数生成。下载一套官方 Python 场景镜像用于 oracle 冒烟，未拉取全部任务镜像 |
| CodeLMSec | 280 提示：Python 200、C 80；Google Drive 原始 ZIP 与 104 个 .ql 查询；官方仓库材料 | CodeQL 静态 oracle，不具备同题功能/安全双动态测试 |
| SafeCoder | trained 24、trained-new 42、not-trained 15，共 81；评测代码与查询，不含训练语料 | 保留三组来源，不能与 SVEN/CodeGuard+ 当作完全独立数据；功能评测原属其他题库 |

## 环境入口

Dockerfile：`docker/external-bank-audit/Dockerfile.candidates`。基础为本地 `cle-external-bank:20261117`，增加固定 CodeQL 2.15.4、对应查询源码，以及 Go/Maven/Ruby/Babel 和 Python 测试依赖。

CodeQL 查询源码固定到 `e637eb720bb5d1061a8d99bc61d11dbe011d8b15`（上游 `codeql-cli-2.15.4` 分支快照）。该分支中的库版本与 SafeCoder setup 脚本另行下载的包版本存在差异，严格复现时需保留差异记录，不能宣称与论文环境完全相同。

```powershell
docker build -f docker/external-bank-audit/Dockerfile.candidates -t cle-candidates:20261118 translation_work/downloads/codeql
docker build -t cle-lscbench-verifier:cve-2024-5751 -f data/external/lscbench_function/upstream_20261118/tasks/cve-2024-5751_function/tests/Dockerfile data/external/lscbench_function/upstream_20261118/tasks/cve-2024-5751_function/tests
python tools/vhdx_watchdog.py --label candidates_20261118 --max-containers 1 --interval 2 -- python tools/external_bank_audit/candidate_environment.py
```

冒烟走常驻 ContainerPool；仅挂载 translation_work，测试输入只读、评测禁网。构建与下载不混入评测期 VHDX 判定。结果保存在 `translation_work/validation_runs/candidates_20261118/`。PythonSecurityEval 单题使用手写 plumbing control，仅验证测试接线，不能当成上游参考答案或安全通过证据。AutoSUIT 使用上游 secure_code，必须读取断言数而不能只看进程返回码。

LSCBench 仅 oracle 验证时合并参考解和隐藏测试；正式 agent 评测仍需分离 agent/verifier 环境，不允许把本冒烟入口用于生成并据此报正式分数。

## 上游

- https://huggingface.co/datasets/amazon/AutoSUIT
- https://github.com/Kamel773/LLM-code-refine
- https://github.com/alibaba/last-secure-code-benchmark
- https://github.com/codelmsec/codelmsec
- https://github.com/eth-sri/SafeCoder

下载核验：四个 GitHub 快照共 3,377 个文件的 SHA-256 已重新计算，无不一致。AutoSUIT 主版本自包含 JSONL 已下载，raw/ 冗余源文件未重复下载。LSCBench Function 语言分布：{"java": 35, "php": 22, "python": 22, "javascript": 22, "c": 23, "cpp": 6, "go": 20}。原始 dataset.toml 保留全 450 任务索引，实际只下载 150 Function，禁止按原始全量索引直接运行。

已实测：LSCBench `cve-2024-5751_function` 上游参考解，禁网常驻容器内 12 功能 + 9 安全测试通过，functional=1、secure=1、reward=1。证据 `translation_work/validation_runs/candidates_20261118/lscbench_initial_smoke.json`；不是全 150 任务验证。

空间检查：本批 CodeQL 下载/解压目录约 2.44 GiB，为在用镜像构建输入与恢复压缩包，暂保留；未执行清理、prune 或永久删除。构建期间空间增长不视为评测期通过证据。

## 首轮冒烟与修正

- AutoSUIT Python：功能 3/3、安全 5/5；C 功能/安全断言均通过；C++ 功能通过，安全套件缺 `<climits>` 导致编译失败，记录 test_integrity，不据此判题面缺陷。
- Java 上游 secure_code 的功能测试 4/6：两项空值测试触发 NullPointerException，属于已测量断言失败。安全套件首轮遇到默认 ASCII 编码，runner 已加 `javac -encoding UTF-8`。
- CodeQL 2.15.4 和 CodeLMSec 原始命令注入查询均完成建库/编译/分析；首轮 stdin 控制无告警，后续换用显式 Flask 请求源检查告警。
- 首轮 watchdog FAIL：VHDX 增长 128 MiB（阈值64 MiB），容器峰值1，收尾0，无残留；原始失败报告保留。查询源码缓存改为挂载 translation_work 后复验；Maven 临时原生库改到 /work/jansi。

## 最终配置与验证状态

镜像 `cle-candidates:20261118` 已构建：`sha256:0b29a43916cca760a18d2b60747ba3adc392342ecce726471bd8d3ed5e7a49df`，约 6.98 GB（Docker 逻辑大小）。本地镜像含 Python、GCC/G++、Java17、Node20、Go1.22、Maven、Ruby、Babel、CodeQL2.15.4；依赖版本保存在运行记录。仅配置评测工具，不安装训练模型或恢复付费队列。

| 数据 | 最终冒烟状态 | 尚未验证/上游限制 |
|---|---|---|
| AutoSUIT | Python 功能3/3、安全5/5；C功能7/7、安全10/10；C++功能6/6；Java功能4/6、安全8/9且两套正常运行 | C++安全套件缺climits，未测量安全；Java失败是参考实现空值断言，不是环境失败；未全量跑951题 |
| PythonSecurityEval | 1题手写控制实现通过单测，常用依赖已安装 | 470题未全量适配/执行；12题缺单测；占位模块导入需逐题适配 |
| LSCBench Function | 官方参考解1场景12功能+9安全全通过 | 其余149场景镜像未下载/验证；未配置全语言全部任务 |
| CodeLMSec | 原始命令注入查询对Flask控制代码产生1条预期告警 | 其余103个查询及C链路未逐一验证；非同题双动态oracle |
| SafeCoder | 上游使用的Python命令注入查询对控制代码产生1条告警；各语言工具链可用 | 81场景未全量评估，其他语言CodeQL分析未验证；包版本与上游setup差异保留 |

最终 watchdog **PASS**：VHDX增量0字节、容器峰值1、收尾0，无残留。原首轮FAIL（128MiB增长）保留。报告 `translation_work/diagnostics/vhdx_watchdog_candidates_20261118_fixed.json`；结构化摘要 `translation_work/validation_runs/candidates_20261118/summary.json`。这说明环境与列出的样例可运行，不代表全部数据题目合格或全量验证通过。

后续复跑使用上文命令，但watchdog标签建议另起批次以保留旧报告。静态查询源码目录写入缓存，挂载来自translation_work，不包含仓库根或凭据。原始上游文件未修改；C++缺头文件未偷偷修复。未发起付费模型请求。

## 后续审计发布

上文“未发起付费模型请求”只描述环境配置阶段；后续审计另有用户授权。已发布[逐题标签、实际prompt与人工复核包](../data/audit_release_20261118/README.md)，双判缺测单列。许可明确快照已纳入发布，PythonSecurityEval原文因许可未明确继续保留本地。
