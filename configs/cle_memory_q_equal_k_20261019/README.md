# 冻结Q等量选卡诊断

本轮按用户“按推荐完成下一轮实验”授权执行，详细规则见[实验规格](../../docs/CLE_Q等量选卡与接口约束实验规格_20261019.md)。

输入为20261018完整观察学习后的冻结1939卡Q库；取固定48题名单前8题，K取旧Q1首次选择数量，三组重复两次共48次P7。不训练新Q，不运行Base/Plus。

```powershell
python -X utf8 -m methods.cle_ablation.run_memory_q_equal_k prepare
python -X utf8 -m methods.cle_ablation.run_memory_q_equal_k label
python -X utf8 -m methods.cle_ablation.run_memory_q_equal_k run --tasks 2 --repeats 1
python -X utf8 -m methods.cle_ablation.run_memory_q_equal_k run
python -X utf8 -m methods.cle_ablation.run_memory_q_equal_k report
python -X utf8 configs/cle_memory_q_equal_k_20261019/analyze.py
python -X utf8 configs/cle_memory_q_equal_k_20261019/diagnose_cases.py
python -X utf8 configs/cle_memory_q_equal_k_20261019/finalize.py
```

生成进程只处理尚未落盘的任务/组/重复组合，不重跑已保存失败。人工在运行区`human_review.csv`的副本中审定后，使用`import-review --labels <真人填写的CSV>`导入。未审定时仅输出模型估计，不阻断已锁定且不依赖标签的48次生成。

已完成48/48：Q1/Q2/Q3 Joint为10/16、9/16、10/16。AI初标222/222，人工0/222。完整分析及停止决定见[结果报告](../../docs/CLE_Q等量选卡与接口约束实验结果_20261019.md)。`analyze.py`复算原生结果及不变量；`diagnose_cases.py`只用原验证器重放重点代码；`finalize.py`最后生成含逐题解释的终稿。后两步均不调用API，不重新生成代码。
