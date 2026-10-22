# ChatAnywhere embedding 选择诊断（2026-09-24）

## 固定设计与边界

先保存 `gold.json` 和含 SHA256 的 `preregistered.json`，再向三个模型发送文本。30 条人工自编查询、30 张目标经验卡及 8 张刻意错误的干扰卡，共 38 张卡；查询与卡片均为英文，未读取 PLT 或 Plus 任务、执行反馈或得分。覆盖 SQL 驱动和标识符、文件路径和归档、shell 参数和选项、HTML/URL/JavaScript 上下文、序列化、密码与完整性/加密/签名、令牌、SSRF、重定向、CSRF、对象授权、正则语义/资源、TLS 和错误披露。

预先固定排序规则是 Recall@3 → MRR → Top1；指标相同才比较官网输入价。数据和排序规则未根据向量结果修改。`run_benchmark.py` 支持复核，不允许覆盖 gold 或已有结果文件。

这是小规模领域健全性检查，单一作者定义的相关性标签不等于独立人工标注数据集，也不估计正式代码生成 JointPass。干扰卡故意含事实错误；向量相近不能证明事实正确。

## 实测

| 模型 | 维度 | Top1 | MRR | Recall@3 | 冷调用总秒数 | 请求数 | 输入/总 tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| text-embedding-3-large | 3072 | 21/30 = 70.00% | 0.836111 | 29/30 = 96.67% | 58.703 | 3 | 2156 |
| text-embedding-3-small | 1536 | 20/30 = 66.67% | 0.816667 | 30/30 = 100.00% | 25.797 | 3 | 2156 |
| text-embedding-ada-002 | 1536 | 16/30 = 53.33% | 0.747222 | 29/30 = 96.67% | 27.297 | 3 | 2156 |

三者各嵌入 68 条文本，均 0 API 失败、0 缺失 usage；总计 9 请求、6468 tokens。模型按固定顺序单次运行，延迟可能受网络、时间和服务端负载影响，不是可靠速度排名。

按预定规则选择 **text-embedding-3-small**：召回覆盖最高且价格更低；large 的 Top1 和 MRR 略高，但差距只有少数样例，不宜宣称任一模型具有统计显著优势。也不据此修改主实验的成功阈值或将诊断冒充任务得分提升。

## 官网价格核验

旧官方帮助页面 `https://docs.chatanywhere.tech/doc-2694962` 明确建议查看新价格页 `https://chatanywhere.tech/pricing`。新页面是前端应用，从其公开 JS 确认实际读接口为 **POST `https://chatanywhere.tech/api/public/models/prices`**，无需凭据。

保存了帮助页、前端页面与 JS、公开 API 完整响应及筛选的 embedding 条目。前端换算是 `prompt × ratio × 1,000,000`，本次三模型的 ratio 均 7，得到：

| 模型 | 官网输入价 CA / 百万 tokens | 本诊断按官网标价估算 CA |
|---|---:|---:|
| text-embedding-3-large | 0.91 | 0.00196196 |
| text-embedding-3-small | 0.14 | 0.00030184 |
| text-embedding-ada-002 | 0.70 | 0.00150920 |

官网说明无折扣时 1 CA = 1 RMB；以上仅模型公开标价估算，不是账户实际扣款核验。免费/付费模型分组均有 embedding 条目，具体账户权限以已认证调用为准，本次三者均实际成功。

## 错误模式与实施含义

- 全部模型对“路径 startswith 即可保证安全”和“数字 invoice ID 即授权”等错误卡具有很高相似度，均发生 Top1 误命中。embedding 负责语义召回，不能承担事实核验和最终适用性判断。
- large 在 PostgreSQL 驱动绑定题把错误的统一问号占位卡排第一，正确 psycopg 卡排第四。small 在该题正确目标排第一，说明不能仅按参数规模定优劣。
- 已使用 argv 仍遭选项注入、合法完整正则的资源耗尽等问题，模型往往召回相邻但不同问题的卡。后续选择必须理解当前已有防护、函数契约与剩余缺口。
- 真实 CLE 使用更宽的向量 top24 再结合词召回及 LLM 比较，本诊断只测原始向量排序。没有运行 LLM 选择、生成代码或动态测试，因此结果不能证明完整检索器有正向 JointPass 提升。

## 可复核产物

- 固定数据和哈希：`gold.json`、`preregistered.json`
- 执行与逐查询前五名：`run_benchmark.py`、`results.json`、三个 `*_result.json`
- 真实向量缓存：三个模型各自 `.sqlite`
- 当前官网证据：`current_pricing_api.json`、`current_embedding_prices.json`、`current_pricing_component.js`
- 历史帮助页证据：`official_pricing.html`、`official_pricing_evidence.json`

全部位于 `translation_work/diagnostics/20260924/retrieval_embedding_v2/model_benchmark/`，不提交运行区、不含凭据。
