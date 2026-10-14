# 架构与记忆共同进化（MASE 探索）

本目录是独立新方法，不要求沿用 CLE 四步，也不把旧 A7 的三种流程冒充自主架构搜索。

当前实现：流程设计、模型设计员、通用图执行器、真实模型/公开检查绑定、来源质量复核、记忆边界修订、训练搜索、版本记录与本地网页。网页中的人工“设计草案”没有实验分数；旧A7和新运行明确标注来源。完整60题对照与独立确认尚未完成，不能据此宣称效果提升。

- [流程与网页设计](design.md)：角色、信息边界、演化过程、记录、指标、实验安排与验收标准。
- [实施步骤](implementation_plan.md)：分阶段实现及验证检查点。
- [网页使用说明](dashboard/README.md)。

在仓库根目录运行：

```powershell
& D:/ANACONDA/python.exe -m methods.mase_evolution.import_history
& D:/ANACONDA/python.exe -m methods.mase_evolution.dashboard.server --port 8781
```

打开 `http://127.0.0.1:8781`。网页只读，刷新和筛选不会调用模型或启动实验。源码、设计、网页放在 `methods/mase_evolution/`；逐题代码、导入证据和运行记录放在 `translation_work/diagnostics/20261013/mase_evolution/`。

当前训练诊断入口：

```powershell
& D:/ANACONDA/python.exe -m methods.mase_evolution.run --run-id mase_new_run --limit 3 --proposals 2 --layer architecture
& D:/ANACONDA/python.exe -m methods.mase_evolution.exposure_audit
```

`--limit 0`表示旧60题全跑；`--layer`支持architecture、memory、joint；`--memory-kind`支持none、m1、m4；提案数可续跑追加，不是每题调用预算。当前运行都保存于上述diagnostics根；源码/记忆/检查签名变化必须使用新run ID。只在最终答案固定后评分，未完成流程记缺测。PLT本地python -I，无Docker；该隔离不是Docker级安全边界。

来源以真实source_id重新绑定family/CWE与漏洞/补丁代码并重测，其他训练family示例可用；目标答案/隐藏夹具不会传给解题或设计角色。净Joint提升择优，安全退步待用户审核。当前不提供人工审核自动接纳入口。模型仍使用仓库请求器与凭据解析顺序，不另存密钥，不写原CLE长期库。
