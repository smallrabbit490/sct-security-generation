# ChatAnywhere API 本地配置与检查

本项目支持用 ChatAnywhere 的 OpenAI-compatible 接口进行本地实验。密钥文件只放在本机的 `local_secrets/chatanywhereapi使用/`，该目录已被 `.gitignore` 忽略，不应提交到仓库。

## 接口

官方文档：

- [ChatAnywhere API 帮助文档](https://docs.chatanywhere.tech/)
- [列出模型](https://docs.chatanywhere.tech/api-92222074)
- [聊天接口](https://docs.chatanywhere.tech/api-92222076)
- [查询用量详情（小时粒度）](https://docs.chatanywhere.tech/api-165664739)

当前确认的接口：

| 用途 | 方法和路径 |
|---|---|
| 模型列表 | `GET /v1/models` |
| 聊天生成 | `POST /v1/chat/completions` |
| 小时用量详情（文档接口） | `POST /v1/query/usage_details` |

官方文档中的用量接口返回小时粒度的 token、调用次数和费用记录，它不是余额接口。当前官方公开文档没有确认一个直接返回余额的 API；余额应以 ChatAnywhere 官网账户页面为准。

## 本地检查

在仓库根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\check_chatanywhere_keys.ps1
```

脚本对每个非空 key 发送一次最小请求，结果写入：

```text
translation_work/chatanywhere_key_check/chatanywhere_key_check.json
```

该结果目录已被忽略。输出只包含 key 编号、HTTP 状态、错误类型、延迟和模型名，不保存 key 内容。

错误分类：

- `401/403`: `invalid_or_unauthorized`
- `429`: `rate_limited_or_quota`
- 超时: `timeout`
- `5xx`: `provider_error`
- 其他: `request_error`
