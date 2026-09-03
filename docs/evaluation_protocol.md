# 评测协议

## 核心结果

核心结果是 `Function+Secure`：生成的 Secure 实现必须在目标语言环境中同时通过功能测试和安全测试，才算成功。

`Function` 和 `Secure` 仍作为解释性指标；PRCS、EQS 是工程质量补充指标，不能替代核心结果。

## Baseline Evaluation Storage

Live baseline runs write only below the ignored
`translation_work/baseline_runs/<run-name>/<subset>/` directory. Each task row
contains method identity, model metadata, generated code, sanitized workflow
trace, Docker validation result, and terminal error class. `summary.json` and
the Markdown report are the human-facing outputs; retain `rows.jsonl` when
per-task auditability is needed.

For the five workflow baselines, the evaluation order is: live generation →
original multi-stage trace/fidelity check → code extraction → Docker
functional/security validation → structured terminal row. The four prompt
baselines use the same extraction and validation path without Agent fidelity.
Do not classify a model-generated failing candidate as a runner failure.

## 数据隔离

经验准备、开发反馈和门控必须与最终评测分离。Base、Plus 只用于最终评测，其失败不能更新 prompt、memory、micro gate 或后续规则。

## 必备运行元数据

每次运行都记录数据清单、commit、模型、temperature、最大 token、重试次数、worker 数、超时、Docker 镜像、方法身份和输出 schema 版本。

## 必备统计表

按 Base/Plus、语言和方法组分别报告：

- Function pass count and rate.
- Secure pass count and rate.
- Function+Secure count and rate.
- Generation/API errors.
- Average tokens, time, and retries.
- PRCS and EQS with the exact warning and growth settings.

## SCT-Agent 轮次

```text
R0 initial memory -> gate -> freeze -> final evaluation
R1 candidate rules from training/development failures -> gate -> freeze -> final evaluation
R2 same protocol
R3 same protocol
```

最终报告必须展示每一轮。只完成部分 micro-gate，或把 Base/Plus 失败反馈回 memory 的运行，只能作为诊断结果。
