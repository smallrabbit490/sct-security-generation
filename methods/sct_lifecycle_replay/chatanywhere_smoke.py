"""DeepSeek 3.2 最小连通性测试；只输出状态，不输出密钥和原始响应。"""

from __future__ import annotations

import os
from pathlib import Path


def load_key() -> str:
    """按仓库约定读取本地 key；绝不把 key 写入运行产物。"""
    value = os.environ.get("CHATANYWHERE_API_KEY")
    if value:
        return value.strip()
    path = Path(__file__).parents[2] / "local_secrets" / "chatanywhereapi使用" / "apikey.txt"
    return path.read_text(encoding="utf-8").strip().splitlines()[0]


def request_deepseek32(timeout: float = 30.0) -> dict:
    """发送一句短请求；模型名按 ChatAnywhere 配置尝试 deepseek-v3.2。"""
    # 使用标准库，避免骨架模块强制依赖 SDK；正式 runner 可注入 OpenAI 客户端。
    import json
    from urllib.request import Request, urlopen

    body = json.dumps({
        "model": "deepseek-v3.2",
        "messages": [{"role": "user", "content": "只回复：连接测试成功"}],
        "temperature": 0,
        "max_tokens": 16,
    }).encode("utf-8")
    request = Request(
        "https://api.chatanywhere.tech/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {load_key()}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return {"ok": bool(content.strip()), "model": "deepseek-v3.2", "content_length": len(content.strip())}
