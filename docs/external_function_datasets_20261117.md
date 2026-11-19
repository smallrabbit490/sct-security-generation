# 函数级安全代码数据下载清单（2026-11-17）

本次仅获取官方数据、测试及必要配套文件；未安装依赖、运行上游代码、启动 Docker、调用生成模型或评测。所有新增快照位于 `data/external/<名称>/upstream_20261117/`；原有 CWEval、PLT 和 CodeSecEval 文件保持原位。快照内上游文件保持原字节，不做脱敏替换或题面修订。

## 下载范围与实际计数

| 数据集 | 本地目录（相对 data/external） | 本次实际计数 | 任务粒度与 oracle |
|---|---|---|---|
| [CWEval](https://github.com/Co1lin/CWEval) | `cweval/upstream_20261117/` | 119 个 `_task` 文件：Python 25、C 31、C++ 21、JS 23、Go 19 | 函数/小代码任务；动态功能与安全测试；题面、参考代码、unsafe 对照和测试一起保留 |
| [SecurityEval](https://github.com/s2e-lab/SecurityEval) | `securityeval/upstream_20261117/` | `dataset.jsonl` 121 条，Python | 函数/代码补全片段，部分有 Web 框架上下文；原论文安全评估使用静态分析，不提供同等完整的动态双 oracle |
| [LLMSecEval](https://github.com/tuhh-softsec/LLMSecEval) | `llmseceval/upstream_20261117/` | `Dataset/LLMSecEval-Prompts_dataset.json` 150 条 | 语言可替换的自然语言代码场景，混有函数、程序与 Web 场景；不是全部严格单函数；保留上游 Dataset 和 CodeQL 分析材料 |
| [SALLM](https://github.com/s2e-lab/SALLM) | `sallm/upstream_20261117/` | 主 `Dataset/dataset.jsonl` 100 条，Python | 函数/小型 Web 代码任务；同时含 Assertion 动态测试与 Tainted 检测材料，不能归为纯静态标签集；`multi-dataset.jsonl` 不是额外独立题数 |
| [CodeGuard+](https://github.com/CodeGuardPlus/CodeGuardPlus) | `codeguard_plus/upstream_20261117/` | 当前 `data/base/**/info.json` 103 个，Python 71、C 32；`functional.py` 103 份 | 函数/代码补全任务；动态功能测试 + CodeQL/Sonar 安全检查，属于混合 oracle。README 写 91 题，与当前文件树不一致，后续按冻结 manifest 选题 |
| [CyberSecEval 代码子集](https://github.com/meta-llama/PurpleLlama) | `cyberseceval/upstream_20261117/` | instruct-v2 1,681 条（Python 282）；旧 instruct 和 autocomplete 各 1,916 条（各 Python 351） | instruct 是函数生成；autocomplete 是代码上下文续写，不能全算严格单函数；主要静态规则 oracle。三个文件是版本/任务形式关系，不可相加当独立题数 |
| [SecCodeBench-V2](https://github.com/alibaba/sec-code-bench) | `seccodebench_v2/upstream_20261117/` | 主语言清单去重 98 场景：Python 13、Java 53、C/C++ 15、Go 13、Node.js 4；4 种模式不当作独立场景 | 按指定函数/模块生成，但置于可运行项目与服务上下文，不能统称纯单函数；保留全部语言题面、模板、验证器和功能/安全测试，后续可选 Python 13 题。动态验证优先，部分配置也支持其它判断方式 |

SecCodeBench 原仓库 README 已声明后续迁移至 `alibaba/last-secure-code-benchmark`。本次仍冻结旧仓库的 V2 98 场景资产，不以新仓库的其它任务替代；没有下载旧仓库约 1.8 GB 的生成文档站点。

BaxBench 是后端应用生成，SecRepoBench 与 A.S.E 是仓库级，未纳入本次函数/小代码数据下载。PLT 与 CodeSecEval 已在现有 `data/external/secodeplt/`、`data/external/secodeplt_github/` 和 `data/SecEvoBasePlus/`，不重复下载或替换。

## 完整性与版本

每个快照根目录的 `DOWNLOAD_MANIFEST.json` 记录官方地址、固定 commit、下载日期、选择范围、文件数、大小，以及每份文件的 Git blob SHA-1 和 SHA-256。`data/external/function_dataset_downloads_20261117.json` 为汇总清单。下载按固定 commit 获取，逐文件验证 Git blob；再次从磁盘校验 SHA-256，主要题库 JSON/JSONL 逐条解析。校验结果见汇总清单；这不代表测试可运行或题库内容已经审计合格。

此次没有统一 schema、抽取严格单函数子集或去除跨数据集重复。SecurityEval、LLMSecEval、CodeGuard+ 等存在来源继承关系；跨基准比较前必须按代码/题面与来源去重，不能视为独立样本。

## 许可证及保存

保留上游提供的许可证与 README；SecurityEval 当前仓库没有独立 LICENSE，记录为未提供，不推定允许再分发。PurpleLlama 根 LICENSE 为 Llama 3.2 Community License，`CybersecurityBenchmarks/LICENSE` 与 `CodeShield/LICENSE` 为 MIT；本次三者均保留，实际使用按具体资产授权核对，不把根许可证简单套给所有子集。

这些原始快照加入本地忽略规则，避免批量提交第三方源码、测试、夹具及许可未明数据。后续归档保留固定 commit 与完整性清单。中文说明在本文维护，不改写第三方 README。

## 后续标注发布

本文件前述忽略规则描述最初下载状态。2026-11-18标签发布将许可明确的冻结快照上传GitHub，保留原始许可证与manifest；SecurityEval、LLMSecEval原文仍只在本地。当前标签及人工复核入口见[data审计发布](../data/audit_release_20261118/README.md)。
