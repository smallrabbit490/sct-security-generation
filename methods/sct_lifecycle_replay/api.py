"""ChatAnywhere 请求适配；错误只保留类型，响应不落原始日志。"""
import json, os, time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

class ChatClient:
    """训练与冻结生成共用客户端；有限重试，不以 reasoning_content 替代答案。"""
    def __init__(self, model="deepseek-v3.2", timeout=60, retries=1, max_tokens=2048):
        self.model, self.timeout, self.retries, self.max_tokens = model, timeout, retries, max_tokens
        self.calls = []
        secret_dir = Path(__file__).resolve().parents[2] / "local_secrets/chatanywhereapi使用"
        path = secret_dir / "chatanywhere_test.env"
        settings = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    name, value = line.split("=", 1); settings[name.strip()] = value.strip().strip("\"'")
        key_file = secret_dir / "apikey.txt"
        file_key = key_file.read_text(encoding="utf-8").strip().splitlines()[0] if key_file.exists() else ""
        self.key = os.environ.get("CHATANYWHERE_API_KEY") or file_key or settings.get("INFRAMIG_API_KEY")
        if not self.key: raise ValueError("missing_test_api_key")
        self.base = os.environ.get("CHATANYWHERE_API_BASE") or settings.get("INFRAMIG_BASE_URL", "https://api.chatanywhere.tech/v1")

    def __call__(self, prompt):
        """输入提示，输出兼容响应；保存用量和终态，不写长期经验。"""
        error = "api_failed"
        for attempt in range(self.retries + 1):
            payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": self.max_tokens}
            request = Request(self.base.rstrip("/") + "/chat/completions", data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
            try:
                with urlopen(request, timeout=self.timeout) as response: result = json.loads(response.read())
                choice = result["choices"][0]
                if choice.get("finish_reason") == "length": raise ValueError("model_output_truncated")
                if not (choice.get("message", {}).get("content") or "").strip(): raise ValueError("empty_model_content")
                self.calls.append({"attempt": attempt, "usage": result.get("usage", {}), "error": None})
                return result
            except HTTPError as exc: error = f"http_{exc.code}"
            except (TimeoutError, URLError): error = "api_timeout_or_network"
            except (ValueError, KeyError, IndexError, TypeError) as exc: error = str(exc) if str(exc) in {"empty_model_content", "model_output_truncated"} else "invalid_api_response"
            self.calls.append({"attempt": attempt, "error": error})
            if error in {"http_401", "http_403"}: break
            if attempt < self.retries: time.sleep(2 ** attempt)
        raise RuntimeError(error)
