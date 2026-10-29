# 题437按直接授权恢复

用户2026年10月27日明确要求“那题直接重跑了，后台我没有权限也没有账号”。这项授权取代该条请求等待服务端对账的条件，不再要求登录后台。原失败记录、未知用量及累计预算保留，不声称旧请求未执行或未计费。

恢复仅补发K0题437修复轮的那一条缺失选卡请求。63个完整结果重建Q并直接复用，437的六段已返回响应先重放，不整题重买。原学习入口、模型、提示、最多三卡、一次修复、奖励资格及逐题更新顺序不变。新发生的其他未决请求不在本次例外中。

零API恢复演练已通过：恢复63题和105张已获反馈卡，消费437的六段保存响应，准确停在缺失选卡边界，新增HTTP为0。39项恢复及共享评价入口测试通过。

在项目根目录使用既有Python环境运行：

```powershell
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_recovery_20261027.recover launch
```

该命令只在允许时段启动隐藏进程；已有学习进程时不重复启动。新段保留原成功前缀和失败现场，随后继续K0及K1/K2/K3。授权和演练证据在E盘运行根`FQ_LEARN/K0/authorized_reissue_20261027.json`及`authorized_prefix_probe_20261027/prefix_probe_result.json`。

工作日14:00至18:00不新发请求，当前计划18:00后恢复。可并行运行学习1个worker与FFS最多3个worker：FFS入口使用`launch --workers 3`；两者合计不超过4。FFS结束后再进入FG_LABELS，学习仍运行时同样使用3个评价worker。各包累计预算分开，不重置。
