# Manuscript comprehension checklist

source: reader
Reviewer input: manuscript only; no tools.

## R001 — A19, headline and table; top summary section on writing successful fixes into experience cards (term, main_chain)

> 两种新规则分别救回5次、损失0次

Obstacle: A19 lists three conditions (native, fixed action plus explanation, action only), and each new condition is 6/6 against native 1/6. That implies five rescues for each new condition, while the top summary reports five rescues in total. The same contrast is called “三种提炼方式” and “两类人工预设规则”. The reader cannot tell whether “five” is per condition or total, nor whether the two mechanisms are the two new conditions or two rule types.
Manuscript evidence: A19 table: native 1/6, fixed action plus explanation 6/6, action only 6/6. Top summary: five rescues, four from permission lists and one from numeric types.
Possible misreading: Reading the 83.3-point gain as one five-rescue comparison and applying it to both new conditions, or treating the two new conditions as one mechanism.
Missing explanation: Name the three conditions and give paired rescue/loss counts for each new condition against native; state whether five is per condition or total.
Proposed help: Report paired rescues separately: fixed action plus explanation vs native 5/0; action only vs native 5/0.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R002 — A11, final paragraph and per-family table (table, main_chain)

> 经验独有的4族全部属于车辆字段更新这一种机制

Obstacle: The table lists 21 question IDs and family hashes with counts but no task names or mechanism labels. The reader cannot identify the four experience-only families or verify that all four share the vehicle-field-update mechanism, so the conclusion that only one mechanism was found is not traceable to the table.
Manuscript evidence: A11 family table has only question IDs, hashes, and counts. The frozen family list, public statements, source cards, and mechanism labels are referenced externally.
Possible misreading: Treating the four family hashes as four independent mechanisms, or accepting the one-mechanism claim from the label alone.
Missing explanation: Map each family to its task name and mechanism; state the family-count threshold used for “经验覆盖的登记题族数量达到要求”.
Proposed help: Add a mechanism column or list the four family IDs with task names and the common vehicle-field-update label.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R003 — A26, first table row “原生卡跨六族”; A22, headline and table (structure, main_chain)

> 原生提炼与修改提炼各11/12次 Joint

Obstacle: A22 reports native Joint 2/12, source-verified 2/11, and public rules 2/12 on six families. A26 reports 11/12 Joint for native and modified extraction on “six families”. The manuscript does not state whether this is the same six-family run or a different dataset, so the reader cannot reconcile the two or know which result supports the natural-retrieval conclusion.
Manuscript evidence: A22 table gives native 2/12 Joint. A26 row gives 11/12 Joint for both native and modified extraction. The A26 link “跨数据集提炼” is not supplied.
Possible misreading: Assuming A22 and A26 are the same experiment and that Joint changed from 2/12 to 11/12, or treating the 11/12 row as the main six-family result.
Missing explanation: State whether the A26 row is A22 or a separate experiment; give the dataset and denominator.
Proposed help: Label the A26 row with its experiment ID or dataset; if it is A22, reconcile the Joint counts.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R004 — A24, headline, table, and paragraph beginning “队列题通过代码采纳的是旧背景卡”; top summary paragraph “接回正常流程后怎样？” (experiment, main_chain)

> 新版卡虽在8/12单元被选中，却没有进入实际采纳

Obstacle: The text distinguishes “选中” from “实际采纳” but never defines either. It also says the only rescue is distinguished by the code size threshold 65536 vs 1048576. Because the new cards were not adopted, the reader cannot tell whether the 3/11 result is a card-mediated effect, a prompt effect, or a code-constant effect; the threshold counterfactual is described only as “功能保持通过、安全转为失败” without stating which condition used which value or that it removes the rescue.
Manuscript evidence: A24 table: native 2/11, new version 3/11 Joint. Text: new cards selected in 8/12 units, adopted 0. Top summary: three new cards were not adopted.
Possible misreading: Reading 3/11 as evidence that the new extraction prompt improved card use, or reading the threshold change as the cause of the rescue rather than as a safety trade-off.
Missing explanation: Define selected and adopted; state the threshold value in each condition and show the per-unit counterfactual that removes the rescue.
Proposed help: Define “selected” and “adopted”; separate the card effect from the 65536/1048576 threshold effect.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R005 — A10, table (table, local)

> 240份输出中只有23份在至少一次代码生成请求中明确列出离线检查所用的来源卡

Obstacle: The table has 24 question rows with values 0–8 and columns “经验分析” and “代码生成”, but no unit (output, request, or card mention) and no per-question denominator. The “代码生成” column sums to 23 and matches the headline; the “经验分析” column sums to 31 and is unexplained. The reader cannot tell what the 23/240 counts or why the table has 24 rows.
Manuscript evidence: A10 table: 24 rows; sum of code-generation entries is 23; sum of experience-analysis entries is 31; headline says 240 outputs.
Possible misreading: Treating each table cell as one question rather than a count of outputs, or treating the 23 as 23 questions.
Missing explanation: State the unit and denominator per row; explain what each column counts.
Proposed help: Add a table note: each cell is a count of outputs (10 per question), 240 outputs total; the two columns count explicit card mentions in experience-analysis and code-generation requests.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R006 — A8, table row “筛选前，所选检查与参考实现至少一次不一致的题族” (experiment, local)

> 筛选前，所选检查与参考实现至少一次不一致的题族 | 11 | 12

Obstacle: The denominator is not stated (57 registered families?) and the manuscript does not say how these inconsistencies were resolved before comparing the 32 warnings. If 11/12 families had at least one selected check disagree with the reference implementation, the equal 32/32 result may reflect the same invalid check in both arms rather than equivalent test strength.
Manuscript evidence: A8 table reports 11 and 12 families with at least one check-reference inconsistency; text says 65 questions, 57 families, and 591 comparable first codes, but gives no adjudication of those families.
Possible misreading: Accepting the 32/32 equality as evidence that experience checks add nothing, when both arms may share the same incorrect check.
Missing explanation: Give the denominator, summarize the inconsistent checks, and state whether they were corrected or excluded.
Proposed help: Report the inconsistent-check denominator and adjudication rule; add a sensitivity result excluding those families.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R007 — Section 2 “当周待做实验”; figure-album pages for Q scoring, round learning, memory detail, and retrieval (structure, local)

> 本周已登记的待做实验清单为空

Obstacle: Section 2 says the registered pending-experiment list is empty, while the figure album contains many “待做”, “外部待办”, “暂缓”, and “正在运行” labels. C01 appears as “已完成” in one page and “正在运行” in another. The note says statuses follow earlier archive times, but no date is attached to individual statuses, so the reader cannot tell which items are current.
Manuscript evidence: Section 2; figure-album textual statuses; note that statuses are read by earlier archive time.
Possible misreading: Reading the figure album’s “C02 待做” or “C01 正在运行” as current-week commitments, contrary to Section 2, or treating the album as a single current snapshot.
Missing explanation: Date each status or separate the current-week backlog from archived pages; explain why C01 has conflicting statuses.
Proposed help: Add an archive date to each album status and label the current-week backlog separately.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## Coverage

- Top summary “本周结论与下一步”: reviewed.
- Main text sections 一、本周实验主线; 二、当周待做实验; 三、实验与结果分析 preamble: reviewed.
- Experiment entries A1–A26: reviewed.
- Embedded tables in A1–A26: reviewed. Reviewed as text tables; no external per-unit data.
- Textual captions and status descriptions in “图2”, “摘要图文字”, and “横版图册”: reviewed. Reviewed as text only; no rendered figure was supplied.
- Rendered Figure 2 and rendered figure-album pages, including the nine prior pages and pages 10–12: not_reviewed. No image files or rendered pages were supplied; only captions and textual descriptions are available.
- Figures 图04, 图05, 图08, 图09 and other figure-album cross-references: not_reviewed. Only cross-references were provided; the figures themselves were not supplied.
- External appendices, reports, scripts, and data referenced as “完整报告”, “思路图册”, “逐项数据与实验记录”, “复现脚本”, etc.: not_reviewed. Not supplied; claims depending on them are listed in unresolved_evidence.
- Supplemental materials, code, and data: not_reviewed. None supplied.

## Unresolved evidence

A19/A20: per-unit paired records for the two new card-writing conditions are not supplied; needed to confirm whether “5 rescues” is per condition or total and to verify the “two additional passes” attribution.
A22/A26: the “跨数据集提炼” appendix and per-unit records are not supplied; needed to determine whether A26’s “11/12 Joint” row is the same six-family run as A22’s 2/12, 2/11, 2/12 table.
A11: the frozen 21-family list, task names, public statements, source cards, and mechanism labels are not supplied; needed to verify that the four experience-only families all share the vehicle-field-update mechanism.
A10/A24: original card texts, actual prompt logs, request-level records, and adoption judgments are not supplied; needed to verify the 23/240 count, the selected-versus-adopted distinction, and the 65536/1048576 counterfactual.
A8: per-family adjudication of selected checks against the reference implementation and the denominator for the 11/12 inconsistent families are not supplied; needed to judge whether the 32 matched warnings are valid.
Figure album: rendered images are not supplied; only textual status descriptions are available, so visual encodings and page-level status cannot be verified.

## Cross-section questions


