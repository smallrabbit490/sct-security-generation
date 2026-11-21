# 安全代码数据集审计标签与人工复核包

本次发布把已下载数据、审计标签、实际使用的 prompt 和人工复核材料联在一起。入口为 [15 个数据集统计索引](dataset_index.csv)、[机器索引](dataset_index.json)、[版本与输入哈希](release_manifest.json)、[人工复核规则](human_review_150/README.md)。

共 5,433 条任务：PLT 874、CodeSecEval Base 115、Plus 140，第一批外部七库 2,372，第二批外部五库 1,932。不是 5,433 条都已完成双判；每库有效判断和缺测题数见索引。每题保留 `verdict=合格/有缺陷/无法判定`，只有“有缺陷”有 `defect_type`。这些是机器审计标签，尚未经人工确认为金标。

## 数据与标签如何对应

- `labels/<dataset>.jsonl`：逐题标签，包含 `key`、来源协议、判断次数、分歧、测试完整性和测试质量。许可明确库同时保存两次结构化判断与证据。
- `materials/<dataset>.jsonl`：以相同 `key` 连接题面、测试、参考信息；公开输入与审核材料分离，不能将参考答案或测试反馈交给正式生成模型。
- `human_review_150/`：150 条机器判为有缺陷、且两次类型一致的待人工复核样本，包含题包、模型标签和空白标注表。
- 原始快照在 `../external/<dataset>/upstream_20261117/` 或 `upstream_20261118/`。固定版本和校验清单见各库 manifest；下载和 Docker 说明见 [第一批](../../docs/external_function_datasets_20261117.md)、[第二批](../../docs/external_function_candidates_20261118.md)。

SecurityEval、LLMSecEval、PythonSecurityEval 未见明确再分发许可证，本次仅上传任务标识、派生标签、版本和下载清单，不上传其题面/测试或带原文的判断。按 manifest 的官方来源恢复本地原文后可通过 key 连接。其他快照保留上游 README、LICENSE 和授权限制；AutoSUIT 为 CC-BY-NC-4.0，不用于商业用途。材料文件是审计输入快照，不替代完整上游项目和运行环境。

## 标签口径及限制

PLT/Base/Plus 使用 **2026-11-17 修正版 v2 首判**，与既有报告一致：合格 659、有缺陷 470。第二判与分歧一并保留，不能把首判统计称为双判共识。历史缺陷类型“接口契约缺失”“业务规则或数据缺失”在顶层规范为“接口契约”“业务规则或数据”，原判断保留原词。这一批没有新版逐字证据 schema，不冒充新版证据校验通过。

外部十二库仅在两次合法判断 verdict 一致且缺陷类型一致时给出共识标签；缺测或分歧记无法判定。缺陷必须通过题面/测试引文逐字匹配和必填字段校验；这只验证引用存在，不能证明模型解释正确。LSCBench 150 题缺完整镜像内上下文，强制记材料不全/无法判定。

测试完整性 `test_integrity` 与测试质量 `test_quality` 独立：测试语法坏了、测试缺失、安全测试偏弱均不能自动推出题面有缺陷。`Joint 可被绕过` 是静态审计意见，未执行时不称为动态证据。Docker 已完成范围有限的环境冒烟，不能据此宣称全库通过。各库有来源继承，不作去重独立总体。

## 实际使用的 prompt

以下文件由原运行器原文导出，不用本次重写规则替代历史 prompt：

1. [外部库完整 system prompt](prompts/external_six_rules_system.txt)，其 SHA256 见 release_manifest；[user 模板](prompts/external_user_template.txt) 为 `json.dumps(payload, ensure_ascii=False) + "\n独立判断编号：" + str(sample)`，sample 为 1/2。对应 runner：`tools/external_bank_audit/run.py`。模型 gpt-6.1-sol，temperature=0、max_tokens=2400，最多五并发。
2. [PLT/Base/Plus v2 system prompt](prompts/legacy_v2_system.txt)、[完整 user prompt 渲染函数](prompts/legacy_v2_user_renderer.py)。函数原文包含规则、完整输入拼接和 JSON 输出要求；历史请求另附“本次为第 N 次独立判断”。对应 `tools/classify_bank_verdict.py`，max_tokens=1400。保留历史执行参数，不把后来五并发设置追写为历史。

处理规则原文：

> 1. 先判 verdict：合格 / 有缺陷 / 无法判定。  
> 2. 只有“有缺陷”才给 defect_type：接口契约 / 业务规则或数据 / 题面与测试冲突 / 环境依赖。  
> 3. 测试问题单列 test_quality：充分 / 安全组偏弱 / Joint 可被绕过 / 输出格式过严 / 缺少正例 / 无法判定。  
> 4. 判“有缺陷”必须同时指出“哪条测试断言 + 题面缺了什么且无法推断”，指不出就判合格或无法判定。  
> 5. 测试代码坏了，只记 test_integrity，不因此判题目有缺陷。  
> 6. 参数列表只写类型、测试用关键字调用，直接判接口契约缺失；若已公开完整函数签名则参数名已给出。

本次离线导出未新增 API 调用。`tools/publish_dataset_audit.py` 从本地冻结运行目录重建本发布；这些运行目录不提交，恢复标签消费不需要凭据，重新运行模型则需要自己的凭据。原始响应、失败请求和费用记录留在忽略运行区，金额未测量。

## 快照汇总

本发布合计合格2,734、有缺陷1,269、无法判定1,430；不同历史协议的统计不可当作同一共识缺陷率。人工样本为PLT60、Base40、Plus20、AutoSUIT18、CWEval6、CodeGuard+3、SALLM3。

原始快照含密码学测试的PEM标头、公开测试密钥与凭据检测器假字符串。这些是上游安全测试材料；已与本地真实API凭据精确比对，未包含本地凭据。

GitHub推送保护将CodeShield凭据检测器自测中的两个示例串识别为Stripe/Twilio密钥，因此该自测文件未上传，未修改本地上游原件；遗漏和原始哈希见[排除清单](publication_exclusions.json)。下载manifest描述本地完整快照，远端快照少这一文件。

## 原合格题的人工验证补充

[2026-11-21合格题规格风险复核与至多50条人工交集样本](qualified_risk_review_20261121/README.md)：原PLT/Base/Plus合格659题另做独立双判，与历史低通过集合取交集。保留原合格标签，新增意见不冒充人工裁决；已接入可视化工作台。
