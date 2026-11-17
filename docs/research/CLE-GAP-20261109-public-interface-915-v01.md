# 第915题公开参数名与测试调用不一致

## 已核实的问题

第915题的公开参数只写“字典”，没有给出参数名；原功能与安全测试均使用 `request=` 关键字调用。当前完整分类表将该题的功能、安全和同时通过均列为“可按公开信息实现”，需要复核公开接口信息是否充分。

本轮开发对照中，`request` 参数的代码可接受该测试调用，`request_dict` 参数的代码会在进入函数前产生 `TypeError`。这两种参数名均符合公开题面中的“字典”描述。对应代码没有采用来源卡，故这次成绩差异不能归因于经验提炼。

## 补齐步骤

1. 对照第915题原始公开题面、测试调用和既有分类依据，确定功能、安全及同时通过三个标签。
2. 检查其他题是否存在公开题面未给参数名、测试却使用关键字调用的同类问题；记录实际影响的题号和标签。
3. 在独立修订版中重算三个数据集的分类数量，保留原表及逐题变更理由。以上范围较大，按用户要求等待批准后执行。

## 证据

- 原分类：[S1_all874_coverage.csv](E:/ResearchRuns/CLE/20261105_six_questions/zero_api_closeout_20261109/S1_all874_coverage.csv)
- 已保存差异：[S3开发集案例审阅](E:/ResearchRuns/CLE/20261105_six_questions/minimal_s3_s4_s5_20261109/S3/development/analysis/case_reviews.json)
- 本轮固定题目与原测试：[tasks.json](E:/ResearchRuns/CLE/20261105_six_questions/minimal_s3_s4_s5_20261109/S3/development/inputs/tasks.json)
