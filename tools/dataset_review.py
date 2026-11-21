"""构建可选择题包的人工复核离线页面；不调用 API，不运行题包代码。"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent / "dataset_review"
REVIEW = ROOT / "data/audit_release_20261118/human_review_150"


def json_lines(path: Path) -> list[dict]:
    """读取冻结题包，仅解析 JSON，材料中的代码始终作为字符串处理。"""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def public_material(material: dict) -> object:
    """译文仅对应公开题面，不读取测试或参考答案补全缺失契约。"""
    if "public" in material:
        return material["public"]
    return [s for s in material.get("sources", []) if s["role"] == "public"]


def public_hash(material: dict) -> str:
    raw = json.dumps(public_material(material), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def safe_inline_json(value: object) -> str:
    """阻止材料内的 HTML 结束标签脱离 JSON script 容器。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def build(output: Path, review: Path | None = None) -> dict:
    """将只读题包、带哈希译文和源码内联为无需网络的 HTML；生成物限运行区。"""
    output = output.resolve()
    work = (ROOT / "translation_work").resolve()
    if not output.is_relative_to(work):
        raise ValueError("生成页面必须保存在 translation_work/ 内")
    review = (review or REVIEW).resolve()
    qualified = review != REVIEW.resolve()
    packets = json_lines(review / "blinded_tasks.jsonl")
    models = {r["review_id"]: r for r in json_lines(review / "model_labels.jsonl")}
    if qualified and any(m.get("review_kind") != "qualified_risk" for m in models.values()):
        raise ValueError("自定义题包必须明确为 qualified_risk，不能误用默认缺陷候选比较规则")
    translations = {"tasks": {}} if qualified else json.loads((ASSETS / "translations.zh-CN.json").read_text(encoding="utf-8"))
    if not packets or len({p["review_id"] for p in packets}) != len(packets) or (not qualified and len(packets) != 150):
        raise ValueError("题包数量或 review_id 唯一性不符")
    if set(models) != {p["review_id"] for p in packets} or (not qualified and set(translations["tasks"]) != set(models)):
        raise ValueError("题包、机器标签与译文编号不一致")
    tasks = []
    for packet in packets:
        rid, material = packet["review_id"], packet["material"]
        translation = ({"public_sha256": public_hash(material), "text": "本题未提供中文译文，请阅读完整公开原文。"}
                       if qualified else translations["tasks"][rid])
        if translation["public_sha256"] != public_hash(material) or not translation["text"].strip():
            raise ValueError(f"{rid}：公开材料变更或译文缺失，需重新核对译文")
        if "reference" in material or any(s["role"].startswith("reference") for s in material.get("sources", [])):
            raise ValueError(f"{rid}：盲审材料含参考答案")
        search_text = json.dumps(public_material(material), ensure_ascii=False) + translation["text"] + rid + material.get("key", "") + material["bank"]
        tasks.append({**packet, "translation": translation["text"], "model": models[rid], "search_text": search_text.lower()})
    digest = hashlib.sha256((review / "blinded_tasks.jsonl").read_bytes()).hexdigest()
    payload = {"version": 1, "dataset_hash": digest, "tasks": tasks,
               "review_kind": "qualified_risk" if qualified else "defect_candidates",
               "review_path": review.relative_to(ROOT).as_posix()}
    html = (ASSETS / "index.template.html").read_text(encoding="utf-8")
    replacements = {"/*__STYLES__*/": (ASSETS / "style.css").read_text(encoding="utf-8"), "/*__CORE__*/": (ASSETS / "core.js").read_text(encoding="utf-8"), "/*__APP__*/": (ASSETS / "app.js").read_text(encoding="utf-8"), "/*__DATA__*/": safe_inline_json(payload)}
    # 一次替换，避免题面内恰好含占位符时被二次当成源码处理。
    import re
    html = re.sub(r"/\*__(?:STYLES|CORE|APP|DATA)__\*/", lambda m: replacements[m.group()], html)
    if qualified:
        html = html.replace("0 / 150", f"0 / {len(tasks)}").replace('max="150"', f'max="{len(tasks)}"')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return {"output": str(output), "tasks": len(tasks), "translations": len(translations["tasks"]), "dataset_hash": digest}


class ReviewHandler(BaseHTTPRequestHandler):
    """预览仅暴露生成的单个 HTML，不提供目录浏览或仓库文件访问。"""
    def __init__(self, *args, page: Path, **kwargs):
        self.page = page
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path.split("?", 1)[0] not in ("/", "/index.html"):
            self.send_error(404)
            return
        content = self.page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "translation_work/diagnostics" / datetime.now().strftime("%Y%m%d") / "dataset_review_ui/index.html")
    parser.add_argument("--open", action="store_true", help="在默认浏览器打开生成页面")
    parser.add_argument("--serve", action="store_true", help="在 127.0.0.1 提供本地预览；Ctrl+C 退出")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--review-dir", type=Path, default=REVIEW, help="选择另一个人工复核题包；旧150题为默认")
    args = parser.parse_args()
    result = build(args.out, review=args.review_dir)
    print(json.dumps(result, ensure_ascii=True), flush=True)
    if args.serve:
        handler = partial(ReviewHandler, page=args.out.resolve())
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
        url = f"http://127.0.0.1:{server.server_port}/"
        print(f"Local: {url}", flush=True)
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    elif args.open:
        webbrowser.open(args.out.resolve().as_uri())


if __name__ == "__main__":
    main()
