# 第432题的数据返回对象需要复核

## 已核实的问题

公开题面给出 `payload` 参数并要求签名验证成功后返回数据字典，同时提供 `get_data_packet(dev_id)` 辅助函数；题面没有明确返回传入的 `payload` 还是辅助函数返回的字典。原测试传入空 `payload`，期望返回辅助函数产生的非空字典。原S1分类将该题标为公开信息充分；应复核这一标签，暂时保留原分类表和原测试分数。

本轮两份代码均通过原安全测试。实际调用复核显示，一份先核对签名再调用辅助函数，另一份先调用辅助函数再核对签名；原测试检查返回值，没有检查辅助函数的调用顺序。是否允许验证前接收数据，需要明确辅助函数的具体语义。

## 待批准补查

复核公开题面对数据来源及操作次序的说明，再决定是否补充相应的独立测试；新增判断与原测试结果分开登记。

证据：[题面和原测试](E:/ResearchRuns/CLE/20261105_six_questions/minimal_s3_s4_s5_20261109/S3/confirmation/inputs/tasks.json) · [代码和调用核对](E:/ResearchRuns/CLE/20261105_six_questions/minimal_s3_s4_s5_20261109/S3/confirmation/analysis/early_case_review_432_rescue.json) · [原分类表](E:/ResearchRuns/CLE/20261105_six_questions/zero_api_closeout_20261109/S1_all874_coverage.csv)
