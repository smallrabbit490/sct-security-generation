# SCT 安全代码生成实验仓库

本仓库用于复现“安全经验自进化 + 多语言安全代码生成”实验。推荐按下面的顺序阅读和执行，像阅读一本实验手册一样逐层深入。

## 目录：从入口到细节

1. **先了解项目**
   - [数据集说明](data/DATASET_CARD.md)：数据组成、数量、来源和限制。
   - [外部数据来源](docs/external_dataset_provenance.md)：经验提取所用外部数据及许可说明。
   - [当前限制](docs/limitations.md)：哪些语言和实验仍未完全冻结。
2. **再理解评测规则**
   - [评测协议](docs/evaluation_protocol.md)：Function、Secure、Function+Secure 指标和数据隔离要求。
   - [Baseline 忠实性说明](docs/baseline_fidelity.md)：四条 Prompt baseline 与五条 Agent baseline 的区别、阶段和判定标准。
   - [Baseline 执行审计](docs/baseline_execution_audit.md)：当前真实运行证据和已知阻断点。
3. **然后配置环境**
   - [复现实验指南](docs/reproduction_guide.md)：从安装到单任务 smoke test 的完整顺序。
   - [ChatAnywhere 配置](docs/chatanywhere-api.md)：本地 key、模型检查和脱敏输出位置。
   - [配置文件说明](configs/README.md)：哪些配置可以进入仓库。
4. **最后阅读方法差异**
   - [SCT 与 DOCX 差异审计](docs/sct_docx_gap_analysis.md)：当前实现与方法文档逐项对照。
   - [原始方法文档](docs/面向多语言安全代码生成的经验自进化方法.docx)：本项目的规范依据。

## 方法分组

| 分组 | 方法 | 特征 |
|---|---|---|
| Prompt baseline | Greedy、Greedy + Secure Prompt、Chain-of-Thought、CoT + Secure Prompt | 单次模型请求，仅提示词不同 |
| Agent baseline | AutoSafeCoder、AgentCoder、RA-Gen、SWE-Agent、SecAwareCoder | 多阶段生成、测试、反馈、修复或候选选择 |
| 本方法 | SCT-Agent | 经验卡、失败分析、门控晋升、冻结后最终评测 |

五条 Agent baseline 必须保留原始工作流阶段，不能把 Agent 名称包装成单个 prompt。详细阶段和 fidelity 判定见 [Baseline 忠实性说明](docs/baseline_fidelity.md)。

## 代码结构

```text
data/                         SecEvoBase/Plus 数据、数据卡和原生 harness
src/translation_pipeline/     Docker 验证器和质量指标
methods/prompting_baselines/  四条直接 Prompt baseline
methods/workflow_baselines/   五条真实多阶段 Agent workflow
methods/sct_agent/            SCT 经验记忆和门控进化入口
methods/legacy_prompt_adapters/历史兼容适配代码，仅用于回放
configs/                      不含密钥的运行配置
docker/                       Python/C++ 验证器镜像定义
results/curated/              可提交的精简结果摘要
docs/                         协议、审计、复现和数据说明
tests/                        离线回归测试
tools/                        数据清洗、key 检查和仓库检查工具
```

## 数据集

`data/SecEvoBasePlus/` 包含五种语言的 Base/Plus 数据：

| 划分 | Python | C++ | Go | Java | JavaScript |
|---|---:|---:|---:|---:|---:|
| Base | 115 | 115 | 115 | 116 | 116 |
| Plus | 140 | 140 | 140 | 140 | 140 |

当前完整 Docker 验证主要覆盖 Python、C++、Go；Java 和 JavaScript 的最终验证器仍在完善。Base/Plus 是最终评测集合，不能反向更新 SCT 经验记忆。

## 环境与验证器

在 Windows PowerShell 中运行，要求 Docker Desktop 已启动：

```powershell
python -m pip install -r requirements.txt
docker build -t safecoder-python-validator:local docker/python-validator
docker build -t safecoder-cpp-validator:local docker/cpp-validator
docker pull golang:1.22
```

离线检查：

```powershell
python -m compileall src methods tools
python -m unittest discover -s tests -v
python tools/check_repository.py
```

## Baseline 评测快速入口

结果统一写入被忽略的目录：

`translation_work/baseline_runs/<run-name>/<subset>/`

推荐先跑一个任务验证链路：

```powershell
$env:CHATANYWHERE_API_BASE = 'https://api.chatanywhere.tech/v1'
python methods/workflow_baselines/run_true_agent_workflows.py `
  --subsets Base --languages python --limit 1 `
  --model deepseek-v4-flash --max-tokens 1024 --temperature 0 `
  --retries 1 --workers 1
```

每条结果至少检查：真实模型请求、生成代码非空、`workflow_completed`、Agent 的 `fidelity_passed`、Docker Function/Secure 结果。模型生成了错误代码但流程到达终态，属于模型结果；API 超时、代码提取异常、缺阶段或 runner 崩溃，才属于运行失败。

## 结果管理规则

- `rows.jsonl`：逐任务代码、trace、fidelity 和验证结果。
- `summary.json`：按方法和语言汇总的指标。
- `true_agent_workflow_report.md`：面向人工阅读的运行报告。
- `translation_work/`：实验输出、Docker 临时目录和缓存，默认不提交。
- `results/curated/`：只放精简、标注清楚、可复核的最终摘要。

不要提交 API key、`.env.local`、原始长日志、Docker VHDX、构建缓存或未脱敏响应。

## 进一步阅读

如果你要复现实验，请按 [复现实验指南](docs/reproduction_guide.md)；如果你要判断某条 baseline 是否忠实，请按 [Baseline 忠实性说明](docs/baseline_fidelity.md)；如果你要理解 SCT 当前还缺什么，请按 [SCT 差异审计](docs/sct_docx_gap_analysis.md)。

代码采用 MIT 许可；外部 benchmark 数据仍受其原始许可证和再分发条件约束。
