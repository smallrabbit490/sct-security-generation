# 全D_gate四臂，原CLE P7与每次最多三张

全部298题/217题族，Q0原候选顺序、Q1相似度、Q2学习Q、Q3同CWE打乱Q，全部原LLM选卡最多3张，再走原复析/采用/规划/生成/动态验证/最多一次修复。

共同状态是2026-10-18不限量273题D_grow观察学习末的1939卡冻结库，466卡有Q；后续测试未更新。三张是本次推理限制，不切回旧297卡Q库。详见 `state_sources.json`。

- [完整实验规格](../../docs/CLE_Dgate全量四臂三张上限实验规格_20261019.md)。
- `manifest.design.json`：完整298题，不按成绩筛题，附历史数据质量与暴露标记。
- `inventory.json`：零API池规模、历史预检和暴露核对。
- `protocol.json`：统一参数、实际入口和统计要求；实际运行状态另记运行区metadata。

用户后续要求按CLE完整要求执行，实施时必须复用原P7和验证器。原48题结果保持只读，不混入新1192条主表。

本次预检已完成，模型新结果产生前锁定174题诊断子集；四题探针为1256、1341、1013、1055，16条包含在1192条中。主表始终保留全部298题。

执行已完成，协议为`cle-q-full-dgate-four-arm-cap3-v4-environment-repaired`，详见`protocol.v4.json`。主表1192条齐全，Q0/Q1/Q2/Q3的Joint分别为97/104/102/100（计划分母均298）；Q2两条F/S缺测另列。预定三项配对统计门未通过，本次冻结Q探索收口，不自动追加实验。完整解释见[结果报告](../../docs/CLE_Dgate全量四臂三张上限实验结果_20261019.md)与[Word版](../../docs/CLE_Dgate全量四臂三张上限实验结果_20261019.docx)。

v1/v2记录问题与v3在175条时检测到的缺PyYAML环境停止全部保留。已按原镜像依赖在既有虚拟环境安装PyYAML6.0.3；零API复验280个代码版本和全298题参考，只有1402反馈改变。41道完整题164条经反馈不变认证复用，1402/472/639三题四组恢复；原P7、模型、排序、卡库、Q和三张参数不变。旧10条未落盘用量未知，已知16条排除记录成本单列；实际总执行1218次P7，主表1192条。已知LLM用量85,017,538 Token为下界，不是账单金额。

当前执行命令（项目根目录，使用既有`translation_work/temp/cle_memory_q_env/Scripts/python.exe -X utf8`）：

```text
python -X utf8 -m methods.cle_ablation.run_memory_q_full_gate_v4 prepare
python -X utf8 -m methods.cle_ablation.run_memory_q_full_gate_v4 run --probe
python -X utf8 -m methods.cle_ablation.run_memory_q_full_gate_v4 run
python -X utf8 configs/cle_memory_q_full_gate_cap3_20261019/analyze.py
```

`prepare`不覆盖旧目录；已有逐题结果包含失败均不会由`run`重跑。最终统计只在1192条齐全后运行；中途状态以`translation_work/diagnostics/20261019/cle_memory_q/full_gate_cap3_v4/run_metadata.json`为准。v1–v3入口保留历史，不再续跑。工作线程原子保存`task_rows/<id>/<arm>.json`；主汇总未消费的结果可由`run`无API恢复。

Word由`build_report_docx.py`从最终Markdown生成，使用Codex附带Python；本机无附带LibreOffice，采用`render_report_word.ps1`调用隐藏的Word实例导出PDF，再用附带Poppler生成逐页PNG供版面检查。中间文件只保存在运行区。

环境修复命令：`uv pip install --python translation_work/temp/cle_memory_q_env/Scripts/python.exe --only-binary :all: --index-url https://pypi.org/simple -r configs/cle_memory_q_full_gate_cap3_20261019/requirements.recovery.txt`。只补齐原Dockerfile已有的实际缺失依赖；原始数据、验证器源码和锁定174题诊断子集未改。反馈复验认证位于v3运行区`environment_recovery/`并已在v4归档。
