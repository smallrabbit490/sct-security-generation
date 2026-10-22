# 32道D_grow网址题修复与独立补测

协议：`cle-dgrow-url-source-restoration-public-contract-v2`。

范围固定为旧奖励资格表中CWE601的8题和CWE918的24题。原始`data.json`、旧资格表、旧Q库和历史成绩不改。

## 修复内容

- 对照官方SeCodePLT固定提交`1f3da9ee48e0046359903cba0cc48d03665f96d5`，恢复32题的原生URL测试以及1399的公开安全说明。
- 上游与本地逐题核对index、CWE、参考代码、初始化配置和依赖一致。没有自行编造网址或标准答案。
- 24题公开context补充外部配置的名称、类型和运行时提供关系；公开新增部分不含测试网址、配置常量或参考补丁。
- `repaired_tasks.json`是完整的独立32题修订集；`public_task_descriptions.json`仅含可向生成器提供的公开字段；`repair_manifest.json`列逐题修改。

## 实际补测

使用现有实验解释器和原`validate_and_state`验证器，128次本地验证：32份参考代码、32份漏洞版对照、两批历史末次交付代码各32份。没有重新生成代码、调用LLM/Embedding、更新Q或重跑D_gate。

|对象|功能通过|安全通过|Joint通过|
|---|---:|---:|---:|
|参考代码|32/32|32/32|32/32|
|漏洞版对照|32/32|0/32|0/32|
|历史观察组末次代码|2/32|31/32|1/32|
|历史学习Q回测末次代码|2/32|30/32|0/32|

旧生成代码没有读过本次补齐后的公开context，也曾收到旧测试反馈，因此这两组只用于诊断，不能当成修订题面下的新生成成绩或Q收益对照。新协议下32题通过当前奖励资格检查；旧资格表仍保留原状态，不追补旧Q奖励。

## 重跑

下面的入口故意不覆盖已存在的运行目录；重跑时先在脚本中指定新的独立OUT和CURATED目录及协议版本，再执行：

```powershell
$cleRepairPython = 'D:/Agent/sct-security-generation/translation_work/temp/cle_memory_q_env/Scripts/python.exe'
& $cleRepairPython -B -X utf8 configs/cle_dgrow_url_repair_20261019/repair_and_retest.py prepare
& $cleRepairPython -B -X utf8 configs/cle_dgrow_url_repair_20261019/repair_and_retest.py retest --workers 4
& $cleRepairPython -B -X utf8 -m pytest -q -p no:cacheprovider tests/test_cle_dgrow_url_repair.py
```

v1由系统默认Python执行，1405的四类验证遇到缺少requests。原始回执和测量勘误保留；v2改用项目已有、已安装requests的解释器，并修复环境故障误计有效测量的问题。

原生运行：`translation_work/diagnostics/20261019/cle_dgrow_url_repair_v2/`。
精简结果：`results/curated/cle_dgrow_url_repair_20261019/`。
中文报告：`docs/CLE_Dgrow网址题修复与独立补测_20261019.md`。
