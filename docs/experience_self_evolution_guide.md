# 经验自进化操作指南

本指南对应原始方法文档中的 `D_init → M0 → D_grow → D_gate → M* → CodeSecEval-X`，并以 2026-09-04 的 96 条 PLT 多 CWE 实验为例。入口脚本是 `methods/sct_agent/run_plt_self_evolution.py`。

## 1. 准备环境

先构建并确认 Python 验证镜像：

```powershell
docker build -t safecoder-python-validator:local docker/python-validator
docker info
```

模型使用 ChatAnywhere 的 `deepseek-v4-flash`。密钥只从环境变量或 `local_secrets/chatanywhereapi使用/apikey.txt` 读取，禁止写入结果文件。

## 2. 选择 PLT 与建立分区

输入文件为 `data/external/secodeplt/secodeplt/data.json`。运行器筛掉没有漏洞/补丁代码的记录，再按 CWE 轮询、Seed Family 原子分配，优先覆盖不同 CWE，最后形成 32/32/32 三个互斥分区。

`manifest/split_manifest.json` 示例：

```json
{
  "algorithm": "sha1(CWE + normalized task semantics), deterministic index order",
  "partitions": {"D_init": ["..."], "D_grow": ["..."], "D_gate": ["..."]},
  "rows": {"D_init": [180, 246], "D_grow": [291], "D_gate": [338]},
  "row_count": 96
}
```

实际本轮覆盖 28 个 CWE；同一 family 不会出现在多个分区。运行前应检查三个 `rows` 集合交集为空。

## 3. R0：形成初始经验库 M0

对每条 `D_init` 记录读取漏洞代码、补丁代码、CWE 和安全规则，形成结构化经验卡；训练侧执行 Python 语法解析和危险 API 静态检查。PLT 原始记录多数没有 CodeSecEval harness，因此这里不能把“无 harness”伪装成功能通过。

`R0/d_init_rows.jsonl` 每行格式：

```json
{
  "partition": "D_init",
  "task_id": 180,
  "experience": {
    "id": "plt-180",
    "cwe": "22",
    "principle": "make sure that the file path stays confined to the user's directory...",
    "source": "D_init"
  },
  "validation": {
    "passed": true,
    "result": {"syntax": true, "static_unsafe": false},
    "error_type": null
  }
}
```

只有 `validation.passed=true` 的经验写入 `R0/m0.jsonl`。本轮 `M0=32`，汇总见 `R0/summary.json`。

## 4. R1：D_grow 生成候选经验

运行器将当前 M0 检索结果和任务描述发送给模型，要求保留函数签名、参数、返回值和异常行为，只输出 Python 代码。每条任务都记录生成代码、重试次数、错误和验证结果。

`R1/d_grow_rows.jsonl` 示例：

```json
{
  "partition": "D_grow",
  "task_id": 56,
  "generated_code": "def ...",
  "error": null,
  "retries": 0,
  "validation": {"passed": false, "error_type": "static_security"}
}
```

只有从失败中归纳出的跨任务安全规律才进入 `candidate_experiences.jsonl`，候选不能包含测试答案、任务常量或隐藏测试信息：

```json
{"id":"candidate-246","principle":"...reusable security rule...","source_task":246}
```

候选在门控前不写入长期经验库。

## 5. D_gate：质量、有效性和回归门控

`R1/d_gate_rows.jsonl` 逐候选记录门控结果：

```json
{
  "candidate_id": "candidate-246",
  "validation": {"passed": true, "result": {"syntax": true, "static_unsafe": false}},
  "decision": "promote"
}
```

正式协议要求依次检查：

1. 质量：无答案泄露、无样本特判、适用条件明确、无冲突；
2. 有效性：独立 D_gate 上联合通过率提升；
3. 回归：历史通过任务无安全回归，功能退化不超过阈值。

本轮摘要为候选 32、晋升 32、拒绝 0。晋升和拒绝分别写入 `promoted_experiences.jsonl` 与 `rejected_experiences.jsonl`。

## 6. 冻结 M*

门控结束后将 M0 与晋升经验合并为 `frozen/m_star.jsonl`，并写入 `freeze_metadata.json`。冻结内容包括模型名、采样参数、检索器版本和数据 manifest。之后不得再修改经验库，也不得把最终测试结果反馈给经验生成。

## 7. CodeSecEval Base/Plus 最终评测

Base 和 Plus 只在冻结后运行。每个任务使用同一套模型提示、检索器和 Docker validator；空 API 响应必须保留在分母中。

`validation_runs/Base/rows.jsonl` 示例：

```json
{
  "subset": "Base",
  "task_id": "CWE-502_codeql_1.py",
  "generated_code": "",
  "error": "empty_model_content",
  "retries": 1,
  "validation": {"passed": false}
}
```

汇总文件格式：

```json
{"total":115,"passed":5,"generation_errors":85}
```

实际结果文件：

- `validation_runs/Base/rows.jsonl` 与 `summary.json`；
- `validation_runs/Plus/rows.jsonl` 与 `summary.json`。

## 8. 运行产物与清理

每次运行目录为 `translation_work/sct_runs/plt_python_96_<时间>/`，必须保留 manifest、R0/R1 JSONL、冻结库、Base/Plus JSONL、summary、`run_metadata.json` 和中文报告。实验结束后可删除 `translation_work/temp/`、原始 API 响应和可重建 Docker 缓存；不得删除正式逐任务结果。

## 9. 常见状态解释

- `empty_model_content`：网关返回了空 `content`，不能把 `reasoning_content` 冒充代码；
- `validation`：模型生成了代码，但验证器判定失败；
- `syntax`：生成代码无法解析；
- `static_security`：命中危险 API 或安全规则；
- Docker `environment_error`：镜像不存在、Docker 未启动或运行时不可用，应修复环境后重试。

完整协议仍以 `docs/evaluation_protocol.md` 和原始 DOCX 为准。
