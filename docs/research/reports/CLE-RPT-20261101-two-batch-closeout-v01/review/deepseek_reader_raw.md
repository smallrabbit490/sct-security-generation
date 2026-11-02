I reviewed only the supplied text. The report’s headline totals are largely arithmetically consistent, but a first-time reader cannot reliably reconstruct several central units, comparison sets, and statistical tests. The checklist below is ordered by impact.

**Checks that do hold (so the problems below are about meaning, not these sums):**

- 54 × 5 × 2 = 540; 82 × 5 × 2 = 820; 540 + 820 = 1,360.
- Q saved runs: 227 (1017) + 300 (non-1017) + 13 (mixed) = 540; measurable 225 + 297 + 13 = 535; 5 unmeasured.
- Memory saved runs: 247 + 570 + 3 = 820; measurable 247 + 569 + 3 = 819; 1 unmeasured.
- Q token total: 14,955,132 + 597,667 + 20,253,363 = 35,806,162.
- Memory token total: 9,121,876 + 671,862 + 22,245,515 = 32,039,253; grand total 67,845,415.
- Unknown-usage HTTP: 37 (Q) + 21 (memory) = 58.
- The 13 main pairs are 5 + 3 + 2 + 3; the 32 complete-label questions are 11 training + 21 development; 14 labeled + 18 unlabeled = 32.

## A. Terms, units, and scope

1. **Location:** Title, opening paragraph, R1.  
   **Excerpt:** “Q回测54题540次”; “Q明显改变选卡”.  
   **Why unclear:** “Q” is never defined. A first-time reader can easily read it as “question,” especially beside “54题.” The report later reveals only indirectly that Q is a learned scorer that reranks candidate experience cards.  
   **Minimal fix:** Add one sentence: “Q is the learned experience-card scorer; it reranks the candidate cards before the model selects them.”

2. **Location:** Q method and A2.  
   **Excerpt:** “沿用固定54题和1939张卡”; “三卡上限”; “blind卡”, “guard卡”, “hint卡”, “pitfall卡”.  
   **Why unclear:** “卡” is the central object of the Q experiment, but it is never defined. A reader may think it is a test case, a prompt card, or a UI card. The card-type prefixes are also undefined, so the case narratives cannot be interpreted.  
   **Minimal fix:** One glossary line: “卡 = a reusable experience/advice card with applicability conditions and modification instructions; blind/guard/hint/pitfall/cand are card subtypes.” Then distinguish “candidate card,” “selected card,” and “adopted card.”

3. **Location:** A1 main comparison and condition table.  
   **Excerpt:** “主要比较为最终K3对相似度Q1”; “Q2_K0”, “Q2_K3”.  
   **Why unclear:** Q1 is the similarity-only baseline, but its name sounds like a Q version. Q2 is never defined. A reader may think K3 vs Q1 compares two learned Q versions rather than Q versus no-Q.  
   **Minimal fix:** Rename the baseline “B0 (similarity only)” or state explicitly: “Q1 = similarity baseline, no learned Q; K0–K3 = four frozen learned-score snapshots; Q2_K* = the Q-scored conditions.”

4. **Location:** A1/A3 tables and statistical notes.  
   **Excerpt:** “95%题族区间”; “题族双侧检验”; “按真实题族整体重采样”.  
   **Why unclear:** “题族” is never defined, and the report never gives the number of families per experiment. The tables display pair counts (45, 59, 114) even though the claimed inference unit is the family. The reader cannot tell whether families are groups of related questions or each question is its own family.  
   **Minimal fix:** Define “题族” and report, for each analysis, the number of families and the number of questions per family. State whether the interval/test resamples questions or families.

5. **Location:** A1 and A3 comparison tables.  
   **Excerpt:** “救回／损失”; “净变化”.  
   **Why unclear:** Neither “救回” nor “损失” is defined. The entire sign of the result depends on them.  
   **Minimal fix:** Add a table note: “救回 = baseline fails and target passes; 损失 = baseline passes and target fails; 净变化 = 救回 − 损失.”

6. **Location:** R1, R2, A1 condition table versus main comparison table.  
   **Excerpt:** “原模型来源净多2/45次”; condition table “Q1 … 最终Joint 17” versus “Q2_K3 … 最终Joint 20”.  
   **Why unclear:** The marginal counts differ by +3 (17/45 vs 20/46), but the paired comparison reports +2 on 45 pairs. A reader will see an apparent contradiction. The same happens for K2 (17/45 vs 18/44 but paired +2) and for the non-1017 K1 (27/60 vs 27/59 but paired +1). The report says only “分母分别计算,” which does not explain which runs are dropped.  
   **Minimal fix:** Add a reconciliation column: marginal passes, paired passes, unpaired passes, and net. For example: “Q1 17/45; K3 20/46; one K3 run has no Q1 partner and passed; paired set = 45, paired K3 = 19/45, net +2.” State explicitly that “净变化” is rescue minus loss, not the difference in marginal pass counts.

7. **Location:** Throughout, especially R1/R2 and the tables.  
   **Excerpt:** “题次表示一道题的一次运行”; “共同可测配对”; “540个唯一单元”; “42/45、50/59题次”.  
   **Why unclear:** “题,” “题次,” “配对,” and “运行单元” are used interchangeably in prose. A reader cannot tell whether 45 means 45 questions, 45 runs, or 45 pairs.  
   **Minimal fix:** Use one unit consistently: “题” = unique question; “运行单元” = one question × one condition × one repeat; “配对” = two conditions on the same question and repeat. Add a small unit table.

8. **Location:** R3 note and all condition tables.  
   **Excerpt:** “Joint表示同一份代码同时通过功能与安全测试.”  
   **Why unclear:** It does not say whether “通过” means all test cases in each category, or whether the count is runs or individual cases. The case narratives use “功能3/3、安全3/3,” which are case counts, while the tables use run counts.  
   **Minimal fix:** Define: “Joint = a run whose final code passes all functional cases and all safety cases; table counts are runs.” Then label case-level counts separately.

9. **Location:** A1/A3 condition tables.  
   **Excerpt:** “保存”, “可测”, “首次Joint”, “最终功能”, “最终安全”, “最终Joint”.  
   **Why unclear:** The tables give one “可测” column, but “首次Joint” may have a different denominator from “最终Joint.” For example, original K1 has saved 45, measurable 44, first Joint 17, final Joint 18; the reader cannot tell whether 17 is 17/45 or 17/44. The note “保存数包括未测记录；通过数只来自已经完成原验证的单元” does not say which columns use which denominator.  
   **Minimal fix:** Add per-column denominators, or a note: “首次Joint/保存; 最终功能、最终安全、最终Joint/可测.” Define “可测” as “final code exists and the original validator ran.”

10. **Location:** A2 cases and A5 tables.  
    **Excerpt:** “功能2/2、安全4/5”; “五档均无2/2成功档”; “最佳固定档Joint 13/22”; “58/113”.  
    **Why unclear:** The slash notation is overloaded: “3/3” means test cases passed; “2/2” can mean two repeats both passed; “13/22” means runs; “58/113” means passing runs out of measurable runs.  
    **Minimal fix:** Use words for repeats: “两次均通过”; use “13 of 22 runs”; use “58 of 113 measurable runs.” Avoid bare “2/2” for repeat success.

11. **Location:** Opening paragraph, R3, todo table, q_decision.  
    **Excerpt:** “Q回测54题”; “记忆标签82题”; “全273题固定回测”.  
    **Why unclear:** The relationship among the 54-question Q set, the 82-question memory set, and the 273-question full set is never stated. A reader cannot tell whether the two experiments overlap, or how either relates to the full benchmark.  
    **Minimal fix:** Add a sampling table: 54 Q questions, 82 memory questions, their overlap, and how each is drawn from the 273. State why different subsets were authorized.

12. **Location:** A1/A3 table rows and Q method step 3.  
    **Excerpt:** “原1017模型”; “无1017模型”; “混合旧前缀”; “按换模授权保留227次旧模型结果和成功请求前缀”.  
    **Why unclear:** “无1017模型” reads as “no model” rather than “the non-1017 flash model.” “混合旧前缀” is never defined. “模型来源” could mean the code-generation model, the Q scorer, or both.  
    **Minimal fix:** Use “1017 checkpoint,” “flash (non-1017),” and “mixed prefix (reused old successful request prefix + new model).” Define “model source” as the code-generation model, not the Q scorer.

## B. Q experiment: design, statistics, and conclusions

13. **Location:** Q introduction and method.  
    **Excerpt:** “四份评分来自此前1017模型的四轮学习；换模后继续冻结使用，未用新模型重新学习.”  
    **Why unclear:** The Q scores are old-model artifacts, while most runs use the new flash model. The experiment is therefore a cross-model transfer of Q, not a within-model estimate of Q’s effect. A reader may assume Q and the generator are the same model.  
    **Minimal fix:** State the Q training model, the generator model for each source, and label the comparison as “frozen old Q applied to the new model.” Discuss the transfer limitation.

14. **Location:** R2 and q_decision.  
    **Excerpt:** “增加反馈轮次持续提高正确率了吗？”; “四份评分 … 冻结使用.”  
    **Why unclear:** The experiment does not add feedback rounds; it compares four frozen score snapshots produced by prior learning. The conclusion “feedback more = better is not supported” is broader than the design.  
    **Minimal fix:** Limit the claim to “among these four frozen snapshots, no stable pairwise gain was observed.” If the original question is about incremental feedback, say that this design cannot test the process, only the final artifacts.

15. **Location:** R2 and Q exploratory table.  
    **Excerpt:** “K3相对K0”; “五项探索经Holm校正后均未过门”; “不支持‘反馈越多，正确率持续上升’.”  
    **Why unclear:** The five tests are pairwise comparisons (K0−Q1, K1−Q1, K2−Q1, K3−Q1, K3−K0). None is a monotonic trend test. The conclusion about “持续上升” is therefore broader than the analysis.  
    **Minimal fix:** Say “no pairwise comparison shows a stable gain; a formal monotonic trend was not tested,” or add a trend test.

16. **Location:** Q method and exploratory table.  
    **Excerpt:** “五项Holm校正”; the table has 5 rows for each of 3 sources.  
    **Why unclear:** The correction family is undefined. Are the five tests corrected within each source (three families of five), or are all 15 corrected together? The main K3−Q1 comparison also appears in the exploratory table, so it is unclear whether the primary p-value is raw or Holm-adjusted.  
    **Minimal fix:** List the five tests and state: “Holm is applied within each source; the primary K3−Q1 gate uses the unadjusted pre-registered p,” or “Holm is applied across all 15.” The same issue applies to A3’s “四项 … Holm4,” where the table shows 12 rows (four per source).

17. **Location:** A1 main table, p column.  
    **Excerpt:** “题族双侧检验p小于0.05”; p = 0.726562 for 5 rescues/3 losses; p = 1 for 2/3.  
    **Why unclear:** These values match an exact paired McNemar test on individual pairs (5/3 → 0.7265625; 2/3 → 1.0), not a test that resamples 题族. If the test is exact McNemar, the “题族” label is misleading; if it is cluster-adjusted, the coincidence needs explanation.  
    **Minimal fix:** Name the test and state whether it accounts for family clustering. If it is exact McNemar on pairs, say so and explain that the interval is the only family-adjusted part—or make both family-adjusted.

18. **Location:** A1/A3 interval columns.  
    **Excerpt:** “95%题族区间（百分点）”.  
    **Why unclear:** No interval method is stated. Some endpoints are exact multiples of 1/n (e.g., 5/3 on 45 gives −3/45 and +7/45), while others are not. A reader cannot tell whether the resampling unit is the pair or the family, nor whether the interval is percentile, BCa, or a simple Wald interval.  
    **Minimal fix:** State the resampling unit, number of families, bootstrap type, and whether the interval is two-sided 95%. If the family count is small, report it and warn that the interval is coarse.

19. **Location:** A1 three source rows and the gate definition.  
    **Excerpt:** “正收益门槛是净差为正、95%题族区间下界大于零、题族双侧检验p小于0.05.”  
    **Why unclear:** There are three source-specific tests (1017, non-1017, mixed), but the report does not say whether these are one pre-registered primary comparison (and how combined) or three separate tests with multiplicity control. The mixed row is descriptive only, but it sits in the same table.  
    **Minimal fix:** State the primary analysis set and the multiplicity rule across sources. If the conclusion is “neither of the two estimable sources passes,” say that explicitly and exclude the mixed row from testing.

20. **Location:** A1 main table, mixed-prefix row.  
    **Excerpt:** “混合旧前缀 | 2 | 0／0 | +0 | +0.00至+0.00 | 1 | 仅2对的描述结果”.  
    **Why unclear:** A p-value and a 95% interval for 2 pairs are not meaningful, even if labeled descriptive. A reader may treat “p = 1” as evidence of no effect.  
    **Minimal fix:** Replace p and CI with “—” for fewer than 5 pairs; keep the row as a descriptive count only. Do the same for the A3 mixed rows.

21. **Location:** R1 and A1 selection table.  
    **Excerpt:** “共同候选中改选成员分别42/45、50/59题次”; “新成员被声明采用的题次 33/45, 36/59”; “声明采用仍需核对代码.”  
    **Why unclear:** “改选成员” (selection-set change), “声明采用” (the model says it used a card), and “采用” (code actually reflects the card) are different things. The table does not say whether 33/45 is a subset of 42/45, or whether “共同候选” means the same candidate pool or the same questions.  
    **Minimal fix:** Define three levels: selected, declared adopted, verified adopted. State that 42/45 and 50/59 are selection-set changes, and 33/45 and 36/59 are declarations not verified in code. Add whether the declaration count is a subset.

22. **Location:** Opening paragraph and q_decision.  
    **Excerpt:** “Q明显改变选卡”; “引入Q并检验选卡作用：已得到肯定回答.”  
    **Why unclear:** “肯定回答” does not specify the question. Read alone, it suggests Q improved accuracy, while R1 says accuracy improvement was not established. “明显” is also unquantified in the prose.  
    **Minimal fix:** Write: “Q changes which cards are selected (42/45 and 50/59 runs); it does not establish an accuracy gain.” Avoid “肯定回答” without naming the question.

## C. Memory-label experiment: labels, denominators, training

23. **Location:** R3, A3, A5.  
    **Excerpt:** “L0全程无卡”; “标签只在十格均可测、有卡片呈现、至少一个档两次Joint通过且输入成本已知时成立”; “L0 11题”.  
    **Why unclear:** Direct contradiction: L0 is defined as “no cards,” yet the label eligibility requires “有卡片呈现,” and L0 is the most common label (11 questions). A reader cannot tell whether L0 is eligible.  
    **Minimal fix:** Change to “the question has a usable card pool; the selected level may be L0 (no cards presented),” or delete “有卡片呈现.” State explicitly that L0 can be a label.

24. **Location:** A3 method step 1 and A5.  
    **Excerpt:** “训练61题、开发21题的原题族划分保持”; “其中训练11题、开发21题.”  
    **Why unclear:** The original split is 61 training / 21 development, but only 11 training questions have complete same-new-model labels. A reader may think the split changed or that the classifier was trained on 61 questions.  
    **Minimal fix:** Add the bridge: “Of the 61 training questions, 11 have complete same-new-model ten-cell labels; the other 50 are excluded because their runs are mixed-source. All 21 development questions are complete.”

25. **Location:** A5.  
    **Excerpt:** “换模后32题获得同一新模型的完整十格结果.”  
    **Why unclear:** “换模后32题” could be a contiguous block rather than a random subset. The 11 training questions may therefore differ systematically from the 50 excluded questions.  
    **Minimal fix:** State how the 32 were selected (contiguous vs random), whether the 11 are representative of the 61, and compare basic difficulty/features of included versus excluded questions.

26. **Location:** A3 and A4.  
    **Excerpt:** “L4不包含L3，五档不是逐级累计”; “更长的来源示例档”.  
    **Why unclear:** “更长” implies a cumulative dose, but the report explicitly says L4 does not contain L3. A reader may interpret L4 as “more memory” than L3.  
    **Minimal fix:** Use “L4 (source-example variant, not cumulative with L3)” consistently; avoid “更长/更短记忆.”

27. **Location:** A5 label rule and A4 case 461.  
    **Excerpt:** “在成功档中选平均P7输入Token最低者”; “拒绝全部经验的结果也会进入成本标签.”  
    **Why unclear:** The label is “cheapest successful presentation,” not “memory that caused success.” A level that rejects all cards can win the label. Training a classifier on such labels may learn cost, not memory benefit.  
    **Minimal fix:** State the construct explicitly: “label = cheapest successful presentation, not causal memory benefit.” Report card adoption for labeled runs; consider excluding all-reject successes or adding a sensitivity analysis.

28. **Location:** A4 cases 461/1321 and A5 label rule.  
    **Excerpt:** “P7输入包含该档分析、规划、代码生成与修复请求，公共初析、检索和材料制作另外计费.”  
    **Why unclear:** “P7” is undefined. “计费” suggests money, but only token counts are reported. The label excludes common analysis/retrieval/material costs, so it is an incremental cost, not total cost.  
    **Minimal fix:** Define P7 as the per-run level-specific input-token stage; state that common costs are excluded and do not affect the within-question ranking; distinguish tokens from currency.

29. **Location:** A5.  
    **Excerpt:** “十格”.  
    **Why unclear:** “十格” is not defined. A reader may think ten questions or ten test cases.  
    **Minimal fix:** Define “十格 = 5 levels × 2 repeats per question.”

30. **Location:** A5 training table.  
    **Excerpt:** “最佳固定档Joint 13/22”; “事后逐题选档Joint上限 13/22”.  
    **Why unclear:** The denominator 22 is not explained (it is 11 questions × 2 repeats). The “best fixed” level is not named. Both the best fixed level and the oracle are chosen on the same 11 questions, so both are in-sample.  
    **Minimal fix:** State “best fixed level = Lx; 13 of 22 runs (11 questions × 2 repeats); selected post hoc on the same training questions.” State that the oracle gap is an in-sample upper-bound gap, not an out-of-sample estimate.

31. **Location:** A5 training table.  
    **Excerpt:** “各档两次结果完全相同”; “档位差异伴随重复波动”; “两次均体现同向档位差异”.  
    **Why unclear:** The three categories are undefined. “完全相同” could mean all five levels agree, or each level’s two repeats agree. A reader cannot map the counts to the 11 questions.  
    **Minimal fix:** Define each category with one concrete example and state the comparison unit (e.g., “all five levels have the same pass/fail in both repeats”).

32. **Location:** A5 development table.  
    **Excerpt:** “fixed | 42 | 20 | 30 | 15 | L4=42”; “rule | 42 | … | L2=12；L3=30”.  
    **Why unclear:** “fixed” is actually “always L4,” but the name suggests a generic fixed policy. “rule” is never defined, so the reader cannot interpret its L2/L3 routing. The “42” is 21 questions × 2 repeats, not 42 questions. The choice of fixed_L1 as the comparator is also unexplained.  
    **Minimal fix:** Rename “fixed” to “fixed_L4”; define the rule’s decision logic; add “42 = 21 development questions × 2 repeats”; state that fixed_L1 is the strongest fixed baseline or the reference L1.

33. **Location:** A5 development comparison table.  
    **Excerpt:** “classifier−fixed_L1 | 42 | 0／2 | -2 | -11.90至+0.00”; “classifier−rule | 42 | 0／1 | -1 | -7.50至+0.00”.  
    **Why unclear:** Every upper bound is exactly 0.00, which looks like a one-sided or truncated interval, not a two-sided 95% interval. A reader cannot tell whether the interval is one-sided, or whether a cluster bootstrap with few families produced a coarse upper bound.  
    **Minimal fix:** State the interval method and whether it is one-sided or two-sided. If one-sided, label it. If two-sided, explain why the upper bound is exactly 0.00.

34. **Location:** A5 gate table, “分类器不能是常量” row.  
    **Excerpt:** “分类器不能是常量 | multinomial_logistic”.  
    **Why unclear:** The criterion is “not constant,” but the evidence is a model class. A multinomial logistic model can still predict one class for every question. The dev routing (L0/L1/L4) is the actual evidence of non-constancy.  
    **Minimal fix:** Change the actual entry to “predicts L0/L1/L4 (three levels), not constant; model = multinomial logistic.”

35. **Location:** A5 gate table, “至少两类各有5个训练题族” row.  
    **Excerpt:** “至少两类各有5个训练题族 | L0=2族；L4=1族；L1=2族”.  
    **Why unclear:** The requirement implies at least 10 labeled families across two classes, while the actual total is 5. The table does not state the total, so the reader must add 2 + 1 + 2.  
    **Minimal fix:** Add “total labeled families = 5; requirement = at least 10 across at least two classes; no class reaches 5.”

36. **Location:** R3 and A5.  
    **Excerpt:** “本次不发布分类器”; “下面保留该候选的开发诊断.”  
    **Why unclear:** The report says no classifier is released, then presents a full classifier development table. A reader may think a classifier was trained and deployed, or that the “no classifier” statement is contradicted.  
    **Minimal fix:** Distinguish “offline diagnostic candidate (trained but not released)” from “formal classifier (not qualified, not released, no paid evaluation).”

37. **Location:** A5.  
    **Excerpt:** “正则参数仅在训练题族三折上按Joint选取，再看21道开发题.”  
    **Why unclear:** With only 5 training families, 3-fold CV has very small folds; the report does not give fold sizes, the selected regularization value, or the CV Joint scores. A reader cannot assess overfitting or stability.  
    **Minimal fix:** Report fold sizes, selected regularization, CV Joint, and confirm that the 21 development questions were used once.

## D. Case narratives

38. **Location:** A2 introduction and summary.  
    **Excerpt:** “13个主要配对”; “13例”.  
    **Why unclear:** The 13 pairs cover only 11 distinct questions: 1218 and 1152 each appear twice (different repeats). A reader may think there are 13 distinct questions.  
    **Minimal fix:** Say “13 pairs across 11 distinct questions; 1218 and 1152 each contribute two pairs.”

39. **Location:** A2 introduction.  
    **Excerpt:** “另用原数据驱动验证器完成16次零API诊断” versus 13 pairs.  
    **Why unclear:** The extra three diagnostics are unexplained. A reader cannot tell whether some pairs received two diagnostics or whether three cases were rechecked for another reason.  
    **Minimal fix:** State which pairs received two diagnostics and why (e.g., both repeats).

40. **Location:** A2 cases 1152/2, 497/2, and elsewhere.  
    **Excerpt:** “原功能失败、安全通过”; “原safety明确要求”; “原成绩”; “原生诊断”.  
    **Why unclear:** “原” is overloaded: it can mean the original 1017 model, the first attempt, the original validator, or “native/local.” In “原功能失败,” the reader cannot tell whose result is meant (first attempt or final K3).  
    **Minimal fix:** Use “首次功能失败” for the first attempt, “原验证器功能失败” for the validator, “1017模型” for the model, and “本地诊断” for the native replay. Avoid bare “原功能” and “原safety.”

41. **Location:** A2 case 1112.  
    **Excerpt:** “两组首次功能失败、安全通过”; “K3 … 最终Joint通过.”  
    **Why unclear:** The similarity group’s final result is never stated. The case is counted as a rescue, so it must have failed, but the reader has to infer that.  
    **Minimal fix:** In every case, give a final line for both arms: final functional, final safety, final Joint.

42. **Location:** A4 case 110.  
    **Excerpt:** “公开题面允许点号并禁止目录穿越，未明示拒绝所有点号开头文件；原验证测试将.hidden_file设为拒绝.”  
    **Why unclear:** This admits the test may be under-specified. The report excludes 110 from labels but still counts its pass/fail in the five-level tables. A reader cannot tell whether the failures are model errors or test artifacts.  
    **Minimal fix:** State explicitly that 110 is excluded from training labels because the requirement is under-specified, and whether it remains in the 82-question performance tables. If it remains, flag the test-validity caveat.

43. **Location:** A4 case 1012 and case 497.  
    **Excerpt:** “更长的来源示例档”; “模板中只绑定headers/body或通用操作.”  
    **Why unclear:** “更长” implies cumulative memory, which the report elsewhere denies. “模板” could mean the L3 presentation template or a code template; “绑定headers/body” is opaque.  
    **Minimal fix:** Say “L4 (source-example variant, not cumulative with L3)” and “L3’s operation template contained only headers/body placeholders or generic operations, not an explicit media-type allowlist.”

44. **Location:** A2 cases 1152/2, 1160/1, 974/1.  
    **Excerpt:** “不能解释为算术安全原理无效”; “不能把所有功能损失统称为过度防御”; “不能据此宣称存在XSS注入.”  
    **Why unclear:** These are rebuttals to interpretations that are not stated in the report. A first-time reader does not know who claimed “over-defense” or “XSS,” so the caveats are unanchored.  
    **Minimal fix:** Either state the alternative interpretation being rebutted, or phrase as “this case does not establish X.”

45. **Location:** A2 end and A4 summary.  
    **Excerpt:** “自动生成的73条探索案例队列不等于全部已审”; “来源示例在权限修改题救回，也在资料访问题损失；目标模板仍可能遗漏媒体类型规则.”  
    **Why unclear:** The reader cannot map the 73 flagged cases to the 13 reviewed pairs, or the summary descriptions to case numbers (1023, 1012, 497).  
    **Minimal fix:** Add a mapping table: 73 auto-flagged candidates; 13 main discordant pairs manually reviewed; the other 60 not reviewed and not used for causal claims. Add case numbers to the A4 summary.

## E. Replay, cost, delivery, and decisions

46. **Location:** Q method step 5 and A6 table.  
    **Excerpt:** “540次一致、差异0、新HTTP为0”; “可测535，未测5”.  
    **Why unclear:** The table says 5 runs are unmeasured, yet replay is “540/540 consistent.” A reader cannot tell what is replayed for a truncated output with no final code.  
    **Minimal fix:** Define replay as “re-run saved final code through the original validator, no model calls.” State that consistency includes reproducing the “unmeasured/truncated” status, and give a breakdown: 535 measurable verdicts reproduced + 5 statuses reproduced.

47. **Location:** Q cost section and A6.  
    **Excerpt:** “5次最终结果未测”; “主比较受影响的是新模型683题第二次K3输出截断”; “未测 … 不计作已经验证失败.”  
    **Why unclear:** The missing runs are not mapped to conditions, and there is no sensitivity analysis. A reader cannot tell whether the missing run would have changed the main comparison, or whether missingness is related to performance.  
    **Minimal fix:** Map each missing run to question/condition/repeat; state the first-attempt result if known; give a worst-case and best-case inclusion for the main comparison; say whether missingness is plausibly random.

48. **Location:** A6 cost tables and Q cost section.  
    **Excerpt:** “物理HTTP”; “已报告Token”; “未知用量HTTP”; “未知费用没有记作零.”  
    **Why unclear:** “物理HTTP” is jargon; “费用” suggests money, but only tokens and HTTP counts are reported. The unknown share (58 of 10,078 HTTP, about 0.6%) is not stated.  
    **Minimal fix:** Define “physical HTTP = actual network requests, excluding cache reuse.” State that the budget is measured in tokens/HTTP, not currency, or provide prices. Give the unknown share and whether it could change the cost conclusion.

49. **Location:** Q cost section and A6.  
    **Excerpt:** “原累计上限8100万Token、21600次HTTP及8640次Embedding HTTP保持不变”; “独立长选卡控制测试26,527 Token另行登记.”  
    **Why unclear:** It is unclear whether the caps apply to these two batches or the whole project, and whether the 26,527-token control test counts toward them.  
    **Minimal fix:** State the scope of the cap and the remaining budget; say whether the 26,527-token control test is inside or outside the cap.

50. **Location:** Opening paragraph, q_decision, todo table.  
    **Excerpt:** “排队全量继续跳过”; “稳定提分门未通过.”  
    **Why unclear:** The report does not state whether skipping the full run is a pre-registered consequence of the failed gate or a separate budget/authorization decision. “Not established” is being treated as “no effect,” even though the confidence intervals are wide.  
    **Minimal fix:** State the decision rule that links a failed gate to skipping the full 273-question run. If the skip is a budget/authorization choice, say so. Distinguish “no stable gain demonstrated” from “no effect.”

51. **Location:** Todo table and q_decision.  
    **Excerpt:** “付费分类器评价”; “不启动付费评价.”  
    **Why unclear:** “付费评价” is undefined. A reader cannot tell whether the current development diagnostic was paid, or what a future paid evaluation would add (new API runs, human review, etc.).  
    **Minimal fix:** Define what a paid evaluation would consist of and state that the current development diagnostic reuses completed runs with no new API cost.

52. **Location:** Todo table.  
    **Excerpt:** “57题检索与人工复核”; “新库、影响半径与Base/Plus.”  
    **Why unclear:** These are separate workstreams introduced without context. “检索” of what, “影响半径,” and “Base/Plus” are not explained, so the rows are uninterpretable to a first-time reader.  
    **Minimal fix:** Add one clause per row defining the task and why it is out of scope, or move these rows to an appendix.
