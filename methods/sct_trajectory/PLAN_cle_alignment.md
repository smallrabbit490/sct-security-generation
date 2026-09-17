# CLE（对比式经验自进化）对齐最终方案 DOCX 的实施计划

> 依据：`docs/面向安全代码生成的经验自进化方法（最终）.docx`
> 落点：`methods/sct_trajectory/`（本目录）
> 范围：Python 训练侧闭环（Phase 1 + 2 + 3），多语言/RQ 实验矩阵留待下一轮。
> 原则：凡涉及调 AI 之处一律真实调用 deepseek-v3.2；每阶段产出可验证结果。

## 已拍板决策（2026-09-15）

### 方向
1. **检索对齐**：保留 LLM 打分配序（与 DOCX"纯 TF-IDF"不同，按用户要求优先），
   但叠加 DOCX 效用分项 `α·(support+1)/(regression+1)`。
2. **HSK-Tree**：完整落地 4 层树（CWEFamilyNode → SecurityInvariantNode → LanguageLeaf）。
3. **范围**：只做 Python 训练侧闭环；多语言（C++/Go/Java）与 RQ 实验矩阵下一轮。

### 细节（全部照 DOCX）
4. Phase1 严格二分：达 A → M0(active)；否则单轮修复后仍不达 A → 错题本
   `seed_grounding_failure`，严禁入 M0。
5. Distillation = 独立 LLM 元认知 Agent（真实调 AI：细粒度归因 + 去特化 + 全状态无偏反思）。
6. 错题本完整实现 + 三大消费（回放偏置 / Analysis 预警 / 归并负向边界）。
7. Gate3：τ_sec 默认 1 + N=3 多数决。
8. 树拓扑演化完整实现：吸收(Overlap≥0.6) / 新建(<0.6) / 归并(>4条 LLM 离线) / 剪枝(效用<0.3)。
9. Seed Family 严格原子隔离（同族整体只入一池），重写 split 逻辑。
10. 检索公式叠加效用分。
11. LanguageLeaf 字段以正文为准：safe_constructs / prohibited_constructs / pattern_snippet。
12. Planning 输出 `{Preserved_Func, Patch_Scope, Avoidance_List}`。
13. CodeGen 局部补丁合成（Patch Synthesis）。

## 待实现模块（本目录新增/改写）

```
methods/sct_trajectory/
├── hsk_tree.py          # HSK-Tree 4 层节点结构 + 拓扑演化（吸收/新建/归并/剪枝/效用衰减）
├── error_ledger.py      # 错题本（结构 + 三消费：回放偏置/Analysis预警/归并负向边界）
├── distillation.py      # 独立 LLM 元认知总结 Agent（真实调 AI）
├── four_state.py        # 改写：8 类跃迁分类（对齐表 1）
├── agent_pipeline.py    # 改写：Analysis 输出合法输入边界；Planning 三键；CodeGen 局部补丁
├── retriever.py         # 改写：TF-IDF + LLM 打分 + 效用分；status=active 白名单 + language 过滤
├── closed_loop.py       # 改写：接 HSK-Tree + Distillation + 错题本 + 三池原子划分
├── run_closed_loop.py   # CLI：Phase1 冷启动 → Phase2 进化 → Phase3 门控拓扑
└── frozen.py            # 保留（已符合 DOCX Phase4 冻结协议）
```

## 分阶段实施（每阶段可验证产物）

### 阶段 A：HSK-Tree 数据结构（地基）
- 新增 `hsk_tree.py`：`CWEFamilyNode / SecurityInvariantNode / LanguageLeaf` dataclass
  + `HskTree` 容器（add/search/absorb/consolidate/prune）。
- status 枚举：`provisional | active | consolidated | retired`。
- 效用：`utility = (support_count+1)/(regression_count+1)`。
- **验证**：`tests/test_hsk_tree.py`（节点序列化、按 CWE 路由、吸收/新建/归并/剪枝）。

### 阶段 B：8 类跃迁分类（对齐表 1）
- 改写 `four_state.py`：`transition_kind` 返回 8 类精分类（A直出/B→A/B→C/B→B·B→D/C→A/C→C·C→D/D→A/D→B·C·D）。
- **验证**：`tests/test_four_state.py` 重写，覆盖表 1 全部 8 行 + A→C 不存在断言。

### 阶段 C：错题本 Error Ledger
- 新增 `error_ledger.py`：记录结构 + 三消费接口（replay_bias / analysis_warning / merge_negative_boundary）。
- **验证**：`tests/test_error_ledger.py`。

### 阶段 D：四步 Agent 改写（真实调 AI）
- 改写 `agent_pipeline.py`：
  - Analysis 输出「漏洞假设 + 功能不变量 + 合法输入边界」；
  - Planning 输出 `{Preserved_Func, Patch_Scope, Avoidance_List}` JSON；
  - CodeGen 局部补丁合成（Patch Synthesis）。
- **验证**：`tests/test_agent_pipeline.py` 重写 + 真实 AI smoke。

### 阶段 E：Distillation Agent（独立 LLM 元认知）
- 新增 `distillation.py`：真实调 AI，输入 4 Agent 中间输出 + code diff + 状态跃迁，
  输出结构化经验（归因 + 去特化 + 全状态无偏反思：增益/负例/错题本）。
- **验证**：`tests/test_distillation.py` + 真实 AI smoke。

### 阶段 F：检索器改写（LLM 打分 + 效用分 + 双层过滤）
- 改写 `retriever.py`：TF-IDF + LLM 打分 + `α·(support+1)/(regression+1)`；
  `status=active` 白名单 + `language` 过滤。
- **验证**：`tests/test_retriever_align.py` + 真实 LLM 打分 smoke。

### 阶段 G：三池原子划分 + 闭环整合
- 改写 `closed_loop.py` + `run_closed_loop.py`：Seed Family 原子划分（同族整体一池）；
  串联 Phase1(冷启动)→Phase2(四步+Distillation+错题本)→Phase3(Gate1/2/3 + 拓扑演化)。
- **验证**：真实端到端 smoke（Python 训练侧少量任务）+ 原子划分单测。

### 阶段 H：文档 + 全量回归
- 更新 `docs/sct_trajectory_contrastive.md` + README。
- 全量 pytest + 编译 + 敏感信息扫描。

## 待你后续拍板的剩余点（本轮实施不阻塞，但需你心里有数）
- 多语言 Java 验证器、RQ1-4 实验矩阵（下一轮范围）。
- 检索"LLM 打分"与 DOCX"纯 TF-IDF"的最终取舍（当前按你的选择保留 LLM）。
