from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any

import requests

from .paths import ensure_work_dirs, get_project_root


DEFAULT_MODEL = "glm-5.1"
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


def load_zhipu_keys(env_path: Path | None = None) -> dict[str, str]:
    if env_path is None:
        env_path = get_project_root() / "质朴api使用" / "质朴.env"
    if not env_path.exists():
        return {}

    keys: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            keys[name.strip()] = value
    return keys


def select_api_key(keys: dict[str, str]) -> str:
    if "lzhkey" in keys:
        return keys["lzhkey"]
    if keys:
        return next(iter(keys.values()))
    raise RuntimeError("No Zhipu API key found in 质朴api使用\\质朴.env")


def make_cache_key(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ZhipuTranslationClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        env_path: Path | None = None,
        cache_dir: Path | None = None,
        base_url: str = DEFAULT_BASE_URL,
        request_timeout: int = 180,
        max_tokens: int = 65536,
        disable_thinking: bool = True,
        max_retries: int = 6,
        retry_delay_seconds: float = 12.0,
    ) -> None:
        self.model = model
        self.api_key = select_api_key(load_zhipu_keys(env_path))
        self.cache_dir = cache_dir or ensure_work_dirs()["cache"]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout
        self.max_tokens = max_tokens
        self.disable_thinking = disable_thinking
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    def translate(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": self.max_tokens,
            "disable_thinking": self.disable_thinking,
        }
        cache_path = self.cache_dir / f"{make_cache_key(payload)}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return cached["content"]

        content = self._call_api(prompt)
        cache_path.write_text(
            json.dumps({"content": content}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return content

    def _call_api(self, prompt: str) -> str:
        return self._call_openai_compatible(prompt)

    def _call_openai_compatible(self, prompt: str) -> str:
        json_body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": self.max_tokens,
        }
        if self.disable_thinking:
            json_body["thinking"] = {"type": "disabled"}
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=json_body,
                    timeout=self.request_timeout,
                )
                response.raise_for_status()
                break
            except requests.HTTPError as exc:
                last_error = exc
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code not in {408, 409, 425, 429, 500, 502, 503, 504} or attempt >= self.max_retries:
                    raise
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise
            retry_after = None
            if isinstance(last_error, requests.HTTPError) and last_error.response is not None:
                retry_after_header = last_error.response.headers.get("Retry-After")
                if retry_after_header:
                    try:
                        retry_after = float(retry_after_header)
                    except ValueError:
                        retry_after = None
            delay = retry_after if retry_after is not None else self.retry_delay_seconds * (2 ** attempt)
            time.sleep(delay + random.uniform(0.0, 1.5))
        else:
            raise RuntimeError(f"Zhipu API request failed after retries: {last_error}")
        data = response.json()
        return data["choices"][0]["message"]["content"]
