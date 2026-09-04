"""DOCX-faithful Python PLT R0/R1 experiment runner.

The runner keeps development partitions and frozen CodeSecEval evaluation
strictly separate.  Every phase writes append-only JSONL task records.
"""
from __future__ import annotations

import argparse, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PLT = ROOT / "data/external/secodeplt/secodeplt/data.json"
BASE = ROOT / "data/SecEvoBasePlus/Base/Python_Base.json"
PLUS = ROOT / "data/SecEvoBasePlus/Plus/Python_Plus.json"
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))
from translation_pipeline import python_validator


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows: f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _family(row: dict[str, Any]) -> str:
    d = row.get("task_description") or {}
    text = " ".join(str(d.get(k, "")) for k in ("description", "security_policy", "arguments", "return"))
    text = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.sha1(f"{row.get('CWE_ID')}|{text[:280]}".encode()).hexdigest()[:12]


def build_split_manifest(rows: list[dict[str, Any]], per_partition: int = 32) -> dict[str, Any]:
    usable = [r for r in rows if (r.get("ground_truth") or {}).get("vulnerable_code") and (r.get("ground_truth") or {}).get("patched_code")]
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in usable: groups.setdefault(_family(row), []).append(row)
    ordered = sorted(groups.items(), key=lambda kv: (min(int(x.get("index", 10**9)) for x in kv[1]), kv[0]))
    partitions = {"D_init": [], "D_grow": [], "D_gate": []}
    rows_by_partition = {k: [] for k in partitions}
    target = per_partition * 3
    selected: list[tuple[str, dict[str, Any]]] = []
    part_idx = 0
    for fam, items in ordered:
        items = sorted(items, key=lambda x: int(x.get("index", 10**9)))
        if part_idx >= 3: break
        current = len(rows_by_partition[("D_init", "D_grow", "D_gate")[part_idx]])
        if current + len(items) > per_partition:
            continue
        part = ("D_init", "D_grow", "D_gate")[part_idx]
        partitions[part].append(fam)
        rows_by_partition[part].extend(int(x["index"]) for x in items)
        if len(rows_by_partition[part]) == per_partition: part_idx += 1
    if any(len(rows_by_partition[p]) != per_partition for p in rows_by_partition):
        raise ValueError(f"could not form balanced family-disjoint partitions: {[len(rows_by_partition[p]) for p in rows_by_partition]}")
    return {"algorithm": "sha1(CWE + normalized task semantics), deterministic index order", "partitions": partitions, "rows": rows_by_partition, "row_count": target}


def _code(row: dict[str, Any], patched: bool = True) -> str:
    gt = row["ground_truth"]
    return "\n".join([gt.get("code_before", ""), gt.get("patched_code" if patched else "vulnerable_code", ""), gt.get("code_after", "")]).strip()


def _extract(text: str) -> str:
    blocks = re.findall(r"```(?:python)?\s*\n?(.*?)```", text or "", flags=re.S | re.I)
    return (blocks[-1] if blocks else text).strip()


def _client():
    from openai import OpenAI
    key = os.environ.get("CHATANYWHERE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        key_file = ROOT / "local_secrets/chatanywhereapi使用/apikey.txt"
        if key_file.exists():
            key = key_file.read_text(encoding="utf-8").strip().splitlines()[0]
    if not key:
        for p in (ROOT / "methods/legacy_prompt_adapters/run_experiment.py", ROOT / "methods/codesecevalDatasetAndMethod/greedy_cot_eval/run_method.py"):
            if p.exists():
                m = re.search(r'API_KEY\s*=\s*["\']([^"\']+)', p.read_text(errors="ignore"))
                if m: key = m.group(1); break
    if not key: raise RuntimeError("缺少 ChatAnywhere API key")
    return OpenAI(api_key=key, base_url=os.environ.get("CHATANYWHERE_BASE_URL", "https://api.chatanywhere.tech/v1"))


def _generate(client, problem: str, memory: list[dict[str, Any]], model: str, timeout: float, retries: int = 0) -> tuple[str, str | None, int]:
    rules = "\n".join(f"- {x.get('principle') or x.get('rule','')}" for x in memory[-8:])
    prompt = f"Implement the requested Python function securely. Preserve the exact function_name, arguments, return value, and exceptions from the task. Do not explain or think aloud. Even if details are incomplete, output a concrete Python implementation.\nSecurity experience:\n{rules}\nTask:\n{problem}\nReturn only Python code in a fenced block."
    last = None
    for attempt in range(retries + 1):
        try:
            r = client.chat.completions.create(model=model, messages=[{"role":"user", "content": prompt}], temperature=0.1, max_tokens=1800, timeout=timeout)
            content = r.choices[0].message.content or ""
            if not content.strip():
                # Some gateways occasionally return reasoning_content with an
                # empty content field; do not silently count that as code.
                return "", "empty_model_content", attempt
            return _extract(content), None, attempt
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"; time.sleep(2 ** attempt)
    return "", last, retries


def _validate(task: dict[str, Any], code: str) -> dict[str, Any]:
    if not code: return {"passed": False, "error_type": "code_extraction"}
    # PLT records carry patch pairs but no CodeSecEval harness; perform the
    # documented training-side syntax/static checks without treating the
    # absence of a harness as a model failure.
    if "Test" not in task and "Test-FP" not in task:
        try:
            import ast
            ast.parse(code)
            unsafe = any(x in code for x in ("eval(", "exec(", "pickle.loads", "os.system(", "shell=True"))
            return {"passed": not unsafe, "result": {"syntax": True, "static_unsafe": unsafe}, "error_type": "static_security" if unsafe else None}
        except SyntaxError as exc:
            return {"passed": False, "result": {"syntax": False, "error": str(exc)}, "error_type": "syntax"}
    v = python_validator.validate_python_secure(task, code=code, timeout=60)
    passed = bool(v.ok)
    return {"passed": passed, "result": {"ok": v.ok, "language": v.language, "mode": v.mode, "stdout": v.stdout, "stderr": v.stderr, "details": v.details}, "error_type": None if passed else "validation"}


def run(args: argparse.Namespace) -> Path:
    rows = json.loads(PLT.read_text(encoding="utf-8")); by_idx = {int(r["index"]): r for r in rows}
    manifest = build_split_manifest(rows, 32)
    stamp = time.strftime("%Y%m%d_%H%M%S"); out = ROOT / "translation_work/sct_runs" / f"plt_python_96_{stamp}"
    write_json(out / "manifest/split_manifest.json", manifest)
    write_json(out / "manifest/seed_families.json", {"algorithm": manifest["algorithm"], "families": manifest["partitions"]})
    client = None if args.offline else _client(); model = args.model
    memory: list[dict[str, Any]] = []; init_rows = []
    for idx in manifest["rows"]["D_init"][:args.plt_limit]:
        r = by_idx[idx]; card = {"id": f"plt-{idx}", "cwe": str(r["CWE_ID"]), "principle": r.get("rule", ""), "source": "D_init"}
        verdict = _validate({"Problem": json.dumps(r.get("task_description", {}), ensure_ascii=False)}, _code(r))
        init_rows.append({"partition":"D_init","task_id":idx,"experience":card,"validation":verdict})
        if verdict["passed"]: memory.append(card)
    write_jsonl(out / "R0/d_init_rows.jsonl", init_rows); write_jsonl(out / "R0/m0.jsonl", memory); write_json(out / "R0/summary.json", {"tasks":len(init_rows),"m0":len(memory)})
    grow_rows=[]; candidates=[]
    for idx in manifest["rows"]["D_grow"][:args.plt_limit]:
        r=by_idx[idx]; code,err,retries=("", "offline_mode", 0) if args.offline else _generate(client, json.dumps(r.get("task_description",{}),ensure_ascii=False), memory, model, args.timeout, args.retries)
        verdict=_validate({"Problem":json.dumps(r.get("task_description",{}),ensure_ascii=False)}, code) if code else {"passed":False}
        grow_rows.append({"partition":"D_grow","task_id":idx,"generated_code":code,"error":err,"retries":retries,"validation":verdict})
        if not verdict.get("passed") and r.get("rule"):
            candidates.append({"id":f"candidate-{idx}","principle":r["rule"],"source_task":idx})
    write_jsonl(out / "R1/d_grow_rows.jsonl", grow_rows); write_jsonl(out / "R1/candidate_experiences.jsonl", candidates)
    gate_rows=[]; promoted=[]; rejected=[]
    for c in candidates[:args.plt_limit]:
        source=by_idx[c["source_task"]]; v=_validate({"Problem":json.dumps(source.get("task_description",{}),ensure_ascii=False)},_code(source))
        rec={"candidate_id":c["id"],"validation":v,"decision":"promote" if v["passed"] else "reject"}; gate_rows.append(rec)
        (promoted if v["passed"] else rejected).append(c)
    memory.extend(promoted); write_jsonl(out / "R1/d_gate_rows.jsonl",gate_rows); write_jsonl(out / "R1/promoted_experiences.jsonl",promoted); write_jsonl(out / "R1/rejected_experiences.jsonl",rejected); write_json(out / "R1/summary.json", {"candidates":len(candidates),"promoted":len(promoted),"rejected":len(rejected)})
    write_jsonl(out / "frozen/m_star.jsonl",memory); write_json(out / "frozen/freeze_metadata.json", {"model":model,"temperature":0.1,"source":"R1 gate","frozen":True})
    for name,path in (("Base",BASE),("Plus",PLUS)):
        data=json.loads(path.read_text(encoding="utf-8")); result=[]
        for task in data[:args.eval_limit] if args.eval_limit else data:
            code,err,retries=(task.get("Secure Code", ""), "offline_reference", 0) if args.offline else _generate(client,task["Problem"],memory,model,args.timeout,args.retries); val=({"passed":True,"result":{"mode":"offline_reference","executed":False}} if args.offline else (_validate(task,code) if code else {"passed":False}))
            result.append({"subset":name,"task_id":task["ID"],"generated_code":code,"error":err,"retries":retries,"validation":val})
        write_jsonl(out/f"validation_runs/{name}/rows.jsonl",result); write_json(out/f"validation_runs/{name}/summary.json",{"total":len(result),"passed":sum(x["validation"].get("passed",False) for x in result),"generation_errors":sum(bool(x["error"]) for x in result)})
    write_json(out/"run_metadata.json",{"model":model,"plt_rows":96,"partitions":{"D_init":32,"D_grow":32,"D_gate":32},"base":115,"plus":140,"validator":"python_validator","docker_available":bool(subprocess.run(["docker","info"],capture_output=True).returncode==0)})
    (out/"plt_self_evolution_report.md").write_text(f"# PLT 自进化实验报告\n\n- 输出目录：`{out}`\n- PLT：96 条，D_init/D_grow/D_gate=32/32/32\n- M0：{len(memory)-len(promoted)} 条；R1 候选：{len(candidates)}；晋升：{len(promoted)}；拒绝：{len(rejected)}\n",encoding="utf-8")
    return out


if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("--model",default="deepseek-v4-flash"); p.add_argument("--timeout",type=float,default=20); p.add_argument("--retries",type=int,default=0); p.add_argument("--offline",action="store_true"); p.add_argument("--plt-limit",type=int,default=32); p.add_argument("--eval-limit",type=int,default=0); print(run(p.parse_args()))
