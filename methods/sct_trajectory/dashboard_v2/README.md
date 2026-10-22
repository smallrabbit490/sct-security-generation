# CLE 新版只读工作台

```powershell
cd D:\Agent\sct-security-generation
python methods/sct_trajectory/dashboard_v2/server.py --port 8771
```

- 新版：http://127.0.0.1:8771/
- 原站：http://127.0.0.1:8770/ （原 `dashboard` 目录保持不变）
- 运行输入：`translation_work/sct_runs/<run_name>/`，与原站相同。

保留原五页导航、SVG经验树、四态分布和代码对照。Phase 2、Phase 3、经验库共用轮次与历史快照；冷启动与收尾审计分别标明固定范围。任务、经验、审计记录可相互查看，关闭详情保留原列表。

没有真实运行时显示目录和文件清单；可主动进入标为“合成示例”的独立演示。示例由 `demo_data.py` 在内存生成，不写入运行目录，不代表实验结果。

页面只读取已有产物，不调用模型、不执行生成代码、不修改经验库。缺失轮次单独列出；缺失历史正文与门控代码不以其他阶段的内容补齐。候选门控以通过率及百分点显示，运行收尾审计不作为独立 Base/Plus 评测。
