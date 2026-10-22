# D_init三张/不限量观察学习

协议 cle-dinit-card-cap-v1；先离线验证，再按 prepare → smoke → pilot → full → report 执行。

入口：`methods/cle_ablation/run_memory_q_dinit_card_cap.py`，使用现有 cle_memory_q_env 的Python。

smoke为前2题×两组，包含在pilot的12题×两组中；full只补Lall剩余291题。每一步读取上一技术门，不检查正确率。原始数据与旧结果只读，禁止启动D_gate。

完整规格：`docs/CLE_Dinit不限三张代码生成与Q覆盖学习方案_20261020.md`。

## 本次实际执行顺序

使用 `translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8`。原v1先 prepare、smoke、pilot，遇到已记录的长度门后使用续跑入口。

```powershell
python -B -X utf8 -m configs.cle_dinit_card_cap_20261020.continue_after_prompt_budget smoke
python -B -X utf8 -m configs.cle_dinit_card_cap_20261020.continue_after_prompt_budget pilot
python -B -X utf8 -m configs.cle_dinit_card_cap_20261020.prepare_missing_initials
python -B -X utf8 -m configs.cle_dinit_card_cap_20261020.continue_after_prompt_budget full
python -B -X utf8 -m configs.cle_dinit_card_cap_20261020.finalize
```

补初析入口只处理没有可复用有效初析的127、671、105，已落盘后跳过，不重复付费。full接续12题记录；report/finalize为零API复算。v1的受阻记录与费用保留，v2输出不得和v1简单合并计数。
