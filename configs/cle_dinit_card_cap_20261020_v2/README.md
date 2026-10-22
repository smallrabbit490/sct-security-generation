# D_init不限三张：选择器长度门续跑

入口：`python -B -X utf8 -m configs.cle_dinit_card_cap_20261020.continue_after_prompt_budget <prepare|smoke|pilot|full|report>`。

原v1在L3/1350修复轮超过180000字符，停止后保留。v2两组统一许可420000字符；候选与提示正文、4096生成预算和256选择器输出预算不变。15条未触发长度门的正常记录复用，原受阻P7不作为主记录，成本累计。

2题技术门、12题对照已通过；full接续Lall剩余291题，数值Q不排序，Joint不作继续门。不运行D_gate。最终报告由原配置目录的finalize模块生成；cost中包含v1及3条补生成初析。

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
