# 参考回放修复清单

[逐题结果](task_outcomes.csv) 覆盖全部 2,199 题，保留 1,241 条通过和 958 条未通过或缺测。 [待处理清单](repair_queue.csv) 收录这 958 条记录，按 `group`、`id` 与 [任务清单](tasks.csv) 对照。空白表示原记录中没有该项测量。修复分类用于安排排查，根因需要以定点复跑确认。

| `repair_bucket` | 题数 | 处理方式 |
|---|---:|---|
| `check_missing_dependency` | 1 | SeCodePLT 1391 的异常类别是 `ModuleNotFoundError`。先核对缺失模块、上游依赖声明和安装版本。 |
| `check_reference_load` | 1 | CodeSecEval Base 有一题参考实现加载失败。先取得加载诊断，区分语法、导入和入口问题。 |
| `check_native_compile` | 14 | AutoSUIT C++ 有 14 题归入此类。另有 3 道 C 题也有编译错误，同时缺安全套件，归入缺套件一类。按编译诊断归组，检查依赖、头文件及编译选项。 |
| `check_go_build_timeout` | 3 | CWEval 三题触及 Go 编译时限。固定资源配额、记录缓存状态和编译耗时，分别比较冷、热缓存。 |
| `check_reference_and_fixture_contract` | 124 | SeCodePLT 121 题、CodeSecEval Plus 3 题。核对参考实现和测试约定，保留有效断言与原始失败。 |
| `classify_suite_failures` | 140 | AutoSUIT 其余有参考且两套测试均存在的未通过题。需要进一步区分断言失败、用例发现、运行异常和超时。 |
| `classify_test_error` | 10 | CWEval 测试阶段错误。已有两批运行结果，优先确认两批之间发生状态变化的题。 |
| `upstream_reference_missing` | 656 | AutoSUIT 上游缺参考实现。登记上游缺测，在参考回放统计中单列。 |
| `upstream_test_missing` | 9 | AutoSUIT 有参考实现但缺安全套件。另外 18 题同时缺参考实现，归入上一行，安全套件缺测合计 27 题。 |

同题只分配一个 `repair_bucket`，功能和安全各自的状态及阶段仍保留在表中。以同一镜像、同一输入定点复跑，确认原因后每个改动只对应一个共同根因，同时保留通过样本用于回归校验。任何资产修订都应单独标版本，原回放结果继续作为对照。
