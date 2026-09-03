# 数据集说明卡

## 内容

`SecEvoBasePlus` 包含 Python、C++、Go、Java、JavaScript 的 Secure/Insecure 配对记录。正式公开评测只使用 Secure 轨；Insecure 字段仅用于来源追溯和训练侧安全差异分析。

## 数量

| 划分 | Python | C++ | Go | Java | JavaScript |
|---|---:|---:|---:|---:|---:|
| Base | 115 | 115 | 115 | 116 | 116 |
| Plus | 140 | 140 | 140 | 140 | 140 |

## 来源

- Python：CodeSecEval/SecEvaBase 与 Plus。
- C++、Go：项目内翻译并检查的结果。
- Java、JavaScript：准备好的数据归档，最终 Docker 复现仍在完善。

## 隐私与复现清理

公开副本不得包含 API key 或机器绝对路径。使用 `tools/sanitize_dataset.py` 将本地路径替换为可移植占位符；清洗器保持 JSON 结构，不改变代码、任务描述或测试语义。

## 限制

数据文件包含上游 benchmark 内容，使用者需自行核对许可证和再分发条件。历史验证报告不代表每条方法都已按当前协议重新运行。
