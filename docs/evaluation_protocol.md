# 评测协议

## 核心结果

核心指标是 `Function+Secure`：生成的 Secure 实现必须在目标语言环境中同时通过功能测试和安全测试，才算成功。`Function` 与 `Secure` 作为解释性指标；PRCS、EQS 是工程质量补充指标，不能替代核心结果。

## 数据隔离

经验准备、开发反馈、候选门控和最终评测必须彼此分离。`D_init`、`D_grow`、`D_gate` 和 `CodeSecEval-X` 必须来自互斥的数据区域，并按原始 Seed Family 隔离。同一原始种子及其文本/代码变体只能属于一个区域。

Baseline 使用 CodeSecEval 是统一对比实验要求，不构成数据污染。数据污染判断只针对 SCT 是否把最终测试结果反馈给经验生成、门控或长期记忆。

## SCT-Agent 经验进化轮次

`R0`、`R1`、`R2`、`R3` 是 DOCX 定义的正式实验轮次，不是旧目录、缓存或临时结果：

- `R0`：从 `D_init` 建立初始经验库 `M0`，门控后冻结，再在 `CodeSecEval-X` 上最终评测。
- `R1`：在 `D_grow` 上根据开发失败生成候选经验，在独立 `D_gate` 上门控，冻结后最终评测。
- `R2`、`R3`：按照同一候选生成、独立门控、冻结、最终评测协议继续迭代。

只有通过门控的经验才能进入下一轮长期库。`CodeSecEval-X` 的最终测试结果不能反馈给经验生成或门控。

```text
R0 初始经验 M0 -> 门控 -> 冻结 -> 最终评测
R1 开发失败候选经验 -> 独立门控 -> 冻结 -> 最终评测
R2 同一协议继续迭代
R3 同一协议继续迭代
```

## Baseline 结果保存

所有在线 baseline 运行只写入被忽略的：

`translation_work/baseline_runs/<run-name>/<subset>/`

每个任务行应包含方法身份、模型元数据、生成代码、脱敏 trace、Docker 验证结果和终态错误类别。`rows.jsonl` 用于逐任务复核，`summary.json` 和 Markdown 报告用于人工阅读。临时 Docker 工作目录、原始响应和构建缓存不能提交。

五条 Agent baseline 的判定顺序是：真实生成 → 多阶段 trace/fidelity 检查 → 代码提取 → Docker 功能/安全验证 → 结构化终态。模型生成了错误代码但流程正常结束，属于模型结果；认证失败、超时、提取异常、缺少阶段和 runner 崩溃属于运行失败。四条 Prompt baseline 使用相同提取和验证路径，但不进行 Agent fidelity 检查。

## 必备运行元数据

每次运行记录：数据清单、Git commit、模型、temperature、最大 token、重试次数、worker 数、超时、Docker 镜像、方法身份和输出 schema 版本。

## 必备统计

按 Base/Plus、语言和方法组分别报告：Function、Secure、Function+Secure 通过数与通过率；生成/API 错误；平均 token、耗时、重试次数；以及带精确参数的 PRCS、EQS。

## 完成标准

JSONL 只能证明写入了一行，不能证明编译、功能测试和安全测试都通过。正式结论必须同时引用结构化结果、评测日志和对应的运行元数据。
