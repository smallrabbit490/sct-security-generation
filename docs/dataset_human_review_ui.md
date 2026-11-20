# 数据集人工复核可视化工作台

本工具用于 `data/audit_release_20261118/human_review_150/` 的 150 条候选人工复核。显示公开题面中文译文、原文、审核测试和全部 13 个 CSV 字段；原始数据保持只读，不调用模型 API，不执行题包代码，不修改经验库。

## 打开

在仓库根目录执行，无需安装额外依赖：

```powershell
python tools/dataset_review.py --open
```

生成的单文件页面默认位于 `translation_work/diagnostics/<日期>/dataset_review_ui/index.html`。也可双击该 HTML，用 Chrome、Edge 或 Firefox 打开；无需联网或启动 Docker。

Windows 用户也可在仓库中双击 `tools/start_dataset_review.cmd`，自动构建并打开页面。

如希望使用固定本地地址，可执行：

```powershell
python tools/dataset_review.py --serve --open --port 8765
```

只监听 `127.0.0.1`，只提供构建出的页面，不提供仓库目录浏览。按 Ctrl+C 停止服务。文件打开和 HTTP 打开属于不同的浏览器存储空间；更换打开方式前先导出 JSON，再在新页面导入。

## 标注顺序

1. 填写标注人，在左侧选择题目；可按数据集、进度、编号、函数名或中英文题面筛选。
2. 中间先读公开题面；可切换“中文与原文 / 中文优先 / 仅原文”。再切换“审核用测试”，逐条核对。
3. 右侧选择合格、有缺陷或无法判定。有缺陷必须填写首要类型、具体断言或调用、缺失要求、无法推断理由。无法判定必须在补充说明写明材料缺口。
4. 测试完整性和测试质量独立填写。测试损坏或未提供时，测试质量为无法判定。没有执行动态验证时，Joint 绕过只能写静态推测。
5. 填写信心，点击“提交独立判断并查看标签”。页面保存此时的独立判断快照，再显示机器结论。随后选择一致性；人工判合格或修改机器类型时，必须写分歧理由。
6. 点击“完成并继续”，或按 Ctrl+Enter。校验通过后计入完成并进入当前筛选范围的下一条待完成题。任何后续编辑都会将该题恢复为待完成，需再次确认。

左下角和“判定规则”页保留规范摘要，详细边界以 [人工复核规则](../data/audit_release_20261118/human_review_150/README.md) 为准。多个标注者分别保留自己的导出文件；不要共用同一浏览器进度冒充独立双人标注。

## 保存、导入、导出

- 自动保存使用当前浏览器的 localStorage，不会写回仓库 CSV。保存失败时显示提示；关闭页面前请下载备份。
- “导出 CSV”可导出已完成记录，或全部 150 行（含空白和草稿）。UTF-8 BOM 编码便于 Excel 识别中文，逗号、引号和换行按 CSV 规则保留。
- CSV 列及顺序与 `annotation_template.csv` 完全一致：`review_id, annotator, human_verdict, human_defect_type, assertion_or_call, missing_requirement, why_not_inferable, human_test_integrity, human_test_quality, type_consistency, disagreement_reason, confidence, notes`。
- JSON 备份另含查看标签状态、独立判断快照和完成状态，可完整恢复。CSV 不含该历史；导入 CSV 仅恢复字段值，并依据校验结果恢复完成状态。
- 导入前显示覆盖数量并下载当前进度的 JSON 备份；只覆盖文件内有填写内容的题目。空白模板不覆盖工作。未知编号、重复编号、无效选项或不匹配题包会被拒绝。
- 本地浏览器数据可能被清理、被无痕模式丢弃，换浏览器也不会自动迁移。因此定期导出 JSON 和 CSV。

## 译文与材料边界

`tools/dataset_review/translations.zh-CN.json` 为全部 150 条公开自然语言的辅助中文译文。代码、签名、参数标识符、精确字符串及完整调用示例保留原文，引用证据应回到原始字段。译文不以隐藏测试、参考答案或机器意见补全公开契约，不提供自动缺陷判断；没有经过独立人工翻译审定。

每条译文绑定相应公开材料的 SHA-256。若题包公开字段变化，构建失败并要求重新核对译文，不会静默展示过期翻译。生成页面也保留原始盲审材料，构建时拒绝混入参考答案。

机器标签默认在页面中折叠，只有独立判断通过必填校验后才显示。这是工作流层面的盲审提示，不是加密或访问控制；需要严格实验盲法时，应给标注人分发不含机器标签的独立材料。

审核材料通过文本节点呈现，HTML 和脚本不运行；页面不依赖外部脚本或网络。测试展示没有编译、功能、安全或静态分析执行，动态项目均为未测量。Plus 快照中的 `Test-FP/Test-SP` 与当前验证器从总 `Test` 拆分的实际套件需要分别核实。

150 条都是机器缺陷候选，不能估计全库缺陷率或标签召回率。Base/Plus 的人工发现不得用于 SCT 经验生成、门控或长期记忆更新，详见 [评测协议](evaluation_protocol.md)。

## 源码和离线检查

入口为 `tools/dataset_review.py`，页面源码在 `tools/dataset_review/`，生成物限于忽略的 `translation_work/`。

```powershell
python -m unittest discover -s tests -p test_dataset_review.py -v
node --test tests/test_dataset_review_core.cjs tests/test_dataset_review_ui.cjs
```

检查覆盖 150 条材料与译文完整对应、原始材料不变、脚本容器转义、CSV 往返、判定举证、分歧字段和导入边界。轻量 DOM 适配器执行实际页面脚本，检查表单门控、独立判断快照、完成后跳题、恢复和按钮导出，不运行 benchmark 测试或在线模型请求。

2026-11-20 检查结果：Python 4 项、Node 12 项通过。真实浏览器预览未完成：执行环境不允许访问本机监听端口，浏览器控制策略禁止导航 `file://`。因此未声称已实测实际浏览器布局、点击或下载对话框；事件流程检查使用上述 DOM 适配器。生成页面和启动入口保存在本地，供正常浏览器打开。
