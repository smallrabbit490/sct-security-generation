# 第810题原测试对外部模板的覆盖缺口

## 已核实的问题

题目要求将用户内容插入上下文提供的 `xml_template`。原测试只设置一份固定模板。本轮 `810_r1_G2` 在模块内、`810_r1_G3` 在函数内将模板写为相同固定内容，原功能和安全测试均通过；但将上下文模板换成另一份包含相同占位符的模板后，两份代码仍返回它们各自写死的模板。

保留两组在原测试中的通过结果。G2 的计划和所采纳经验均要求使用外部模板，这个动作没有落实；G3 声明拒绝来源卡。两份代码的通过体现原测试对模板变化的覆盖范围。

## 待批准补齐

1. 为涉及外部配置、数据或模板的题目，在公开契约允许的范围内变换宿主对象，重放已保存代码。
2. 分别统计原测试通过但变换后失败的代码与题族；原生成结果和原测试分数保留。
3. 对可复现的验证器缺口另存测试，不将新增测试结果回填成原测试成绩。

## 证据

- [实际卡片、计划、生成代码和测试的审阅](E:/ResearchRuns/CLE/20261105_six_questions/minimal_s3_s4_s5_20261109/S3/development/analysis/early_case_review_810_rescue.json)
- [G3 代码和不同模板的本地复核](E:/ResearchRuns/CLE/20261105_six_questions/minimal_s3_s4_s5_20261109/S3/development/analysis/additional_case_reviews.json)
- [题目和原测试](E:/ResearchRuns/CLE/20261105_six_questions/minimal_s3_s4_s5_20261109/S3/development/inputs/tasks.json)
