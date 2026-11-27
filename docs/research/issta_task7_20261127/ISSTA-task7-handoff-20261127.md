# ISSTA 第 7 项 · 本机补验与学长交接

2026-11-27 已补齐三道 CWEval Go 题的原普通功能验收。第 7 项剩两类事项，一类需要作者确认题意，一类需要与修订版对应的完整测试回执。

## 可直接转发的说明

学长，第 7 项本机已补完三道原先编译超时的 CWEval Go 题，原普通功能共 9/9 通过，同组通过题也保持 4/4。还需要帮忙确认两件事。

1. **SeCodePLT 76 的判定口径。** 原普通功能 4/4 通过。题面写了最低 8 字符，未写上限，同一参考实现接受符合格式的 100 字符普通样例，拒绝同类 101 字符样例。请确认 **100 字符是否为题目约定的硬上限**，以及**原安全断言的布尔期望对应格式判定还是正则性能，应该按什么规则判定通过**。答复时请写明确切规则和需同步的题面或测试条目。[普通样例回执][plt76]
2. **138 道目标题仍缺完整回执。** 所需题键与修订版本见附件，覆盖 SeCodePLT 122 道、CodeSecEval Plus 3 道、CWEval 13 道。如果手头已经有对应修订版的完整功能和安全结果，请提供已有的脱敏回执或来源链接。每道题至少保留以下内容。若未执行或未留存，请在对应题键标注。 [138 道待验收题键][gaps]

   | 信息 | 具体要求 |
   | --- | --- |
   | 题与版本 | `group,id,language`，附件中的 `revision`，实际提交或修订资产哈希，功能和安全夹具各自的版本或哈希。 |
   | 运行身份 | 实际批次 ID，runner 版本或提交，镜像 ID 或可核对的环境清单。功能和安全须能匹配到同一修订、参考实现和环境。 |
   | 两侧结果 | 功能和安全分开给出通过数、总数、执行状态，标记超时、异常或未执行。已有失败细节时可提供失败序号、阶段、错误类别和来源定位。 |
   | 证据定位 | 链接或文件相对路径加行号、记录号。未执行填 `not_run`，执行过但原记录未留存填 `not_retained`。保留结果元数据即可。 |

此前已上传的 **35 道、38 条**已逐条对上原批次回执。原回执保留的是未通过用例序号和结果码，具体返回值或异常细节未随回执留存。它们可以用来查原回放；修订后的 Joint 要等对应版本的功能与安全两侧证据齐备。[38 条历史回执与修订版映射][trace]

## 本地验收记录

在原 Docker 镜像、Go 1.23.3、2 CPU、4 GB 和断网条件下，核对原参考实现、测试和离线模块的资产校验值。先做有时限的构建缓存准备，再以原 40 秒上限重新编译并执行核阅过的原普通用例。

| 题键 | 准备后编译 | 原普通功能 |
| --- | ---: | ---: |
| `cwe_643_0_go_task.go` | 0.974 秒 | 4/4 |
| `cwe_760_0_go_task.go` | 0.134 秒 | 1/1 |
| `cwe_943_0_go_task.go` | 0.304 秒 | 4/4 |
| `cwe_020_0_go_task.go`，原通过对照 | 0.101 秒 | 4/4 |

`760` 另用三组虚构账号检查派生输出长度和盐值互异，均通过。[Go 回执][go] · [本机产物 SHA-256 清单][manifest]

完整安全套件含用于触发漏洞行为的用例，本轮本机范围完成到普通功能、构建与证据核验。未取得修订版完整双套件回执的目标保留 `not_measured`。139 道当前适用队列题中，1 道 CodeSecEval Base 目标题已有原离线夹具完整双套件和 Joint 结果。另有 1 道 Base 通过对照。AutoSUIT 继续暂缓。[155 条统一回归表][regression] · [原任务清单](ISSTA-master-20261125.md)

[gaps]: ../../../../../sct-security-generation/_worktrees/issta-replay-diagnostics-20261125/translation_work/validation_runs/issta_task7_followup_20261127/joint_evidence_gaps.csv
[trace]: ../../../../../sct-security-generation/_worktrees/issta-replay-diagnostics-20261125/translation_work/validation_runs/issta_task7_followup_20261127/plt_security_traceability.csv
[go]: ../../../../../sct-security-generation/_worktrees/issta-replay-diagnostics-20261125/translation_work/validation_runs/issta_task7_followup_20261127/go_functional_receipt.json
[manifest]: ../../../../../sct-security-generation/_worktrees/issta-replay-diagnostics-20261125/translation_work/validation_runs/issta_task7_followup_20261127/followup_manifest.json
[regression]: ../../../../../sct-security-generation/_worktrees/issta-replay-diagnostics-20261125/translation_work/validation_runs/issta_task7_followup_20261127/repair_regression.csv
[plt76]: ../../../../../sct-security-generation/_worktrees/issta-replay-diagnostics-20261125/translation_work/validation_runs/issta_task7_final_20261126/plt76_ordinary_contract.json
