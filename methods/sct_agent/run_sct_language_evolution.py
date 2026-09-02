"""Run language-specific SCT-Agent self-evolution for Python/C++/Go.

This wrapper keeps SCT-Agent separate from the 9 baselines. For each target
language it runs Ours only, summarizes failures, proposes small language-specific
rules with the configured LLM, gates the candidate rules on a micro sample, and
promotes only non-regressing rules.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
LEGACY_DIR = PROJECT_ROOT / "methods" / "legacy_prompt_adapters"
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))
import run_coset_eagle_experiment as sct
import run_language_method_matrix as matrix


SAME_TOPIC_RULE_LIMIT = 3
CANDIDATE_RULE_LIMIT = 10


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def language_rows(out_root: Path, subset: str, language: str) -> list[dict[str, Any]]:
    path = out_root / subset / "language_methods" / subset / language / "ours_sct_agent.jsonl"
    return read_jsonl(path)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)

    def count(key: str) -> int:
        return sum(1 for row in rows if (row.get("metrics") or {}).get(key))

    gen_errors = sum(int(row.get("generation_errors") or 0) for row in rows)
    return {
        "total": total,
        "functional": count("secure_functional"),
        "secure": count("secure_security"),
        "func_sec": count("secure_func_sec"),
        "generation_errors": gen_errors,
        "functional_rate": round(100 * count("secure_functional") / total, 2) if total else 0,
        "secure_rate": round(100 * count("secure_security") / total, 2) if total else 0,
        "func_sec_rate": round(100 * count("secure_func_sec") / total, 2) if total else 0,
    }


def failure_payload(rows: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        metrics = row.get("metrics") or {}
        if metrics.get("secure_func_sec") and not row.get("generation_errors"):
            continue
        secure = row.get("secure") or {}
        eval_result = secure.get("eval") or {}
        result = eval_result.get("result") or {}
        details = result.get("details") or {}
        failures.append(
            {
                "task_id": row.get("task_id"),
                "entry_point": row.get("entry_point"),
                "functional": bool(metrics.get("secure_functional")),
                "secure": bool(metrics.get("secure_security")),
                "func_sec": bool(metrics.get("secure_func_sec")),
                "generation_error": secure.get("error"),
                "validation_mode": eval_result.get("validation_mode"),
                "phase": details.get("phase"),
                "error_type": details.get("error_type"),
                "stderr_head": matrix.truncate_text(str(result.get("stderr") or ""), 900),
                "stdout_head": matrix.truncate_text(str(result.get("stdout") or ""), 500),
            }
        )
        if len(failures) >= limit:
            break
    return failures


def rules_to_markdown(rules: list[dict[str, Any]], language: str) -> str:
    lines = [
        f"SCT-Agent language-specific memory for {matrix.LANGUAGE_LABELS[language]}",
        "",
        "Use these rules only when they match the current task and harness contract.",
        "",
    ]
    for idx, rule in enumerate(rules, 1):
        name = rule.get("rule_name") or rule.get("name") or f"Rule {idx}"
        principle = rule.get("principle") or ""
        when = rule.get("when_to_apply") or ""
        hint = rule.get("implementation_hint") or rule.get("hint") or ""
        avoid = rule.get("avoid") or ""
        lines.append(f"{idx}. {name}")
        if principle:
            lines.append(f"   Principle: {principle}")
        if when:
            lines.append(f"   When to apply: {when}")
        if hint:
            lines.append(f"   Implementation hint: {hint}")
        if avoid:
            lines.append(f"   Avoid: {avoid}")
    return "\n".join(lines).strip() + "\n"


def write_active_rules(memory_root: Path, language: str, raw_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active_rules = select_active_rules(raw_rules)
    write_json(memory_root / f"{language}_active_rules.json", active_rules)
    write_json(memory_root / f"{language}_rules.json", active_rules)
    (memory_root / f"{language}_rules.md").write_text(rules_to_markdown(active_rules, language), encoding="utf-8")
    return active_rules


def load_language_rules(memory_root: Path, language: str) -> list[dict[str, Any]]:
    path = memory_root / f"{language}_rules.json"
    if path.exists():
        return read_json(path)
    return sct.load_final_gated_rules()


def rule_topic(rule: dict[str, Any]) -> str:
    explicit = rule.get("rule_topic") or rule.get("failure_type") or rule.get("topic")
    if explicit:
        return re.sub(r"\s+", "_", str(explicit).strip().lower())
    text = " ".join(
        str(rule.get(key) or "")
        for key in ("rule_name", "name", "principle", "when_to_apply", "implementation_hint", "avoid")
    ).lower()
    buckets = [
        ("harness_signature", ["harness", "signature", "entry point", "entry_point", "function name"]),
        ("imports_includes", ["import", "include", "unused import", "package"]),
        ("type_contract", ["type", "return", "parameter", "struct", "interface"]),
        ("path_filesystem", ["path", "file", "directory", "traversal", "filename"]),
        ("command_execution", ["command", "shell", "subprocess", "exec"]),
        ("deserialization", ["deserialize", "pickle", "yaml", "json load"]),
        ("resource_bounds", ["timeout", "loop", "memory", "size", "limit"]),
        ("error_handling", ["exception", "error", "panic", "raise"]),
        ("validation_sanitization", ["validate", "sanitize", "escape", "check"]),
    ]
    for bucket, needles in buckets:
        if any(needle in text for needle in needles):
            return bucket
    name = str(rule.get("rule_name") or rule.get("name") or "general").strip().lower()
    words = re.findall(r"[a-z0-9]+", name)
    return "_".join(words[:4]) or "general"


def propose_rules(
    *,
    language: str,
    current_rules: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    model: str,
    max_tokens: int,
    api_timeout: float,
    round_idx: int,
) -> list[dict[str, Any]]:
    if not failures:
        return []
    client = sct.make_client(api_timeout)
    prompt = f"""You are improving SCT-Agent for {matrix.LANGUAGE_LABELS[language]} secure code generation.

Read the sanitized failure signals. Propose 6 to 10 short, reusable rules when there are enough distinct failure themes.

Requirements:
- Rules must be language-specific when the failure is caused by syntax, harness, imports/includes, type signatures, package structure, or compiler behavior.
- Do not create a rule tied to one exact task ID or one exact CWE.
- Keep rules short. Do not make generated code longer than necessary.
- Prefer different failure themes over repeating the same theme.
- Add a compact rule_topic field such as harness_signature, imports_includes, type_contract, path_filesystem, resource_bounds, or error_handling.
- Return only a JSON array.

Each rule object must have:
- rule_name
- rule_topic
- principle
- when_to_apply
- implementation_hint
- avoid
- source

Current rules:
```json
{json.dumps([sct.compact_rule(rule) for rule in current_rules[:20]], ensure_ascii=False, indent=2)}
```

Failure signals:
```json
{json.dumps(failures, ensure_ascii=False, indent=2)}
```
"""
    raw, _tokens, error = sct.call_model(client, prompt, model, max_tokens, retries=3)
    if error:
        return []
    try:
        updates = sct.extract_json_array(raw)
    except Exception:
        return []
    cleaned = []
    for update in updates[:CANDIDATE_RULE_LIMIT]:
        if not isinstance(update, dict):
            continue
        update["source"] = update.get("source") or f"{language}_round_{round_idx}_self_evolution"
        update["rule_topic"] = rule_topic(update)
        cleaned.append(update)
    return cleaned


def merge_rules(current: list[dict[str, Any]], updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    topic_counts: dict[str, int] = {}
    seen: set[tuple[str, str]] = set()

    def add_rule(rule: dict[str, Any]) -> None:
        if not isinstance(rule, dict) or not sct.is_generic_rule(rule):
            return
        topic = rule_topic(rule)
        if topic_counts.get(topic, 0) >= SAME_TOPIC_RULE_LIMIT:
            return
        name = str(rule.get("rule_name") or rule.get("name") or "").strip().lower()
        principle = str(rule.get("principle") or rule.get("rule") or "").strip().lower()
        key = (topic, name or principle[:120])
        if key in seen:
            return
        normalized = dict(rule)
        normalized["rule_topic"] = topic
        seen.add(key)
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        merged.append(normalized)

    for rule in current:
        add_rule(rule)
    for rule in updates:
        add_rule(rule)
    return merged


def _rule_identity(rule: dict[str, Any]) -> tuple[str, str, str]:
    topic = rule_topic(rule)
    name = str(rule.get("rule_name") or rule.get("name") or "").strip().lower()
    principle = str(rule.get("principle") or rule.get("rule") or "").strip().lower()
    return topic, name, principle[:180]


def merge_raw_memory(current: list[dict[str, Any]], updates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for rule in current + updates:
        if not isinstance(rule, dict) or not sct.is_generic_rule(rule):
            continue
        normalized = dict(rule)
        normalized["rule_topic"] = rule_topic(normalized)
        key = _rule_identity(normalized)
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def select_active_rules(raw_rules: list[dict[str, Any]], same_topic_limit: int = SAME_TOPIC_RULE_LIMIT) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    topic_counts: dict[str, int] = {}
    seen: set[tuple[str, str, str]] = set()
    for rule in raw_rules:
        if not isinstance(rule, dict) or not sct.is_generic_rule(rule):
            continue
        normalized = dict(rule)
        topic = rule_topic(normalized)
        normalized["rule_topic"] = topic
        if topic_counts.get(topic, 0) >= same_topic_limit:
            continue
        key = _rule_identity(normalized)
        if key in seen:
            continue
        seen.add(key)
        topic_counts[topic] = topic_counts.get(topic, 0) + 1
        active.append(normalized)
    return active


def full_summary_is_better(candidate: dict[str, Any], incumbent: dict[str, Any] | None) -> bool:
    if incumbent is None:
        return True
    candidate_key = (
        int(candidate.get("func_sec", 0)),
        int(candidate.get("secure", 0)),
        int(candidate.get("functional", 0)),
        -int(candidate.get("generation_errors", 0)),
    )
    incumbent_key = (
        int(incumbent.get("func_sec", 0)),
        int(incumbent.get("secure", 0)),
        int(incumbent.get("functional", 0)),
        -int(incumbent.get("generation_errors", 0)),
    )
    return candidate_key > incumbent_key


def gate_accepts(before: dict[str, Any], after: dict[str, Any]) -> tuple[bool, str]:
    if after["generation_errors"] > before["generation_errors"]:
        return False, "rejected: generation errors increased"
    if after["func_sec"] < before["func_sec"]:
        return False, "rejected: Function+Secure regressed"
    if after["functional"] < before["functional"]:
        return False, "rejected: Function regressed"
    if after["secure"] < before["secure"]:
        return False, "rejected: Secure regressed"
    return True, "accepted: no negative regression on micro gate"


def run_matrix_subprocess(
    *,
    out_name: str,
    subset: str,
    language: str,
    limit: int,
    model: str,
    max_tokens: int,
    retries: int,
    workers: int,
    memory_root: Path,
    force: bool,
) -> None:
    out_dir = HERE / "out" / out_name / subset / "language_methods" / subset / language / "ours_sct_agent.jsonl"
    if force and out_dir.exists():
        out_dir.unlink()
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(PROJECT_ROOT / "DatasetAndMethod" / "SecAwareCoder"))
    env.setdefault("SAFECODER_CPP_DOCKER_IMAGE", "safecoder-cpp-validator:local")
    env.setdefault("SAFECODER_GO_DOCKER_IMAGE", "golang:1.22")
    env["SCT_LANGUAGE_MEMORY_ROOT"] = str(memory_root)
    cmd = [
        sys.executable,
        str(LEGACY_DIR / "run_language_method_matrix.py"),
        "--dataset-root",
        str(PROJECT_ROOT / "data" / "SecEvoBasePlus"),
        "--subsets",
        subset,
        "--languages",
        language,
        "--limit",
        str(limit),
        "--include-ours",
        "--only-ours",
        "--out-name",
        out_name,
        "--model",
        model,
        "--max-tokens",
        str(max_tokens),
        "--temperature",
        "0",
        "--retries",
        str(retries),
        "--workers",
        str(workers),
    ]
    subprocess.run(cmd, cwd=LEGACY_DIR, env=env, check=True)


def run_language_evolution(args: argparse.Namespace, language: str) -> dict[str, Any]:
    memory_root = HERE / "out" / args.out_name / "sct_language_memory"
    memory_root.mkdir(parents=True, exist_ok=True)
    raw_rules = merge_raw_memory(load_language_rules(memory_root, language), [])
    active_rules = write_active_rules(memory_root, language, raw_rules)
    write_json(memory_root / f"{language}_raw_rules_r0.json", raw_rules)
    write_json(memory_root / f"{language}_rules_r0.json", active_rules)

    records: list[dict[str, Any]] = []
    current_summary: dict[str, Any] | None = None
    best_summary: dict[str, Any] | None = None
    best_round: int | None = None
    for round_idx in range(0, args.evolution_rounds + 1):
        round_name = f"{args.out_name}_{language}_micro_r{round_idx}"
        run_matrix_subprocess(
            out_name=round_name,
            subset=args.micro_subset,
            language=language,
            limit=args.micro_limit,
            model=args.model,
            max_tokens=args.max_tokens,
            retries=args.retries,
            workers=args.workers,
            memory_root=memory_root,
            force=args.force,
        )
        rows = language_rows(HERE / "out" / round_name, args.micro_subset, language)
        summary = summarize_rows(rows)
        micro_payload = failure_payload(rows)
        write_json(memory_root / f"{language}_round_{round_idx}_micro_summary.json", summary)

        if round_idx == 0:
            current_summary = summary
            records.append({
                "round": 0,
                "summary": summary,
                "active_rules": len(active_rules),
                "raw_rules": len(raw_rules),
                "decision": "seed",
            })
        else:
            assert current_summary is not None
            accepted, reason = gate_accepts(current_summary, summary)
            records.append({
                "round": round_idx,
                "summary": summary,
                "active_rules": len(active_rules),
                "raw_rules": len(raw_rules),
                "decision": reason,
            })
            if accepted:
                current_summary = summary
            else:
                raw_rules = read_json(memory_root / f"{language}_raw_rules_r{round_idx - 1}.json")
                active_rules = write_active_rules(memory_root, language, raw_rules)

        full_name = f"{args.out_name}_{language}_full_r{round_idx}"
        for subset in args.subsets:
            run_matrix_subprocess(
                out_name=full_name,
                subset=subset,
                language=language,
                limit=args.limit,
                model=args.model,
                max_tokens=args.max_tokens,
                retries=args.retries,
                workers=args.workers,
                memory_root=memory_root,
                force=args.force,
            )
        full_rows: list[dict[str, Any]] = []
        for subset in args.subsets:
            full_rows.extend(language_rows(HERE / "out" / full_name, subset, language))
        full_summary = summarize_rows(full_rows)
        full_payload = failure_payload(full_rows)
        write_json(memory_root / f"{language}_round_{round_idx}_full_summary.json", full_summary)
        write_json(memory_root / f"{language}_round_{round_idx}_micro_failure_payload.json", micro_payload)
        write_json(memory_root / f"{language}_round_{round_idx}_failure_payload.json", full_payload)
        if full_summary_is_better(full_summary, best_summary):
            best_summary = full_summary
            best_round = round_idx
            write_json(memory_root / f"{language}_best_summary.json", best_summary)
            write_json(memory_root / f"{language}_best_raw_rules.json", raw_rules)
            write_json(memory_root / f"{language}_best_active_rules.json", active_rules)
            (memory_root / f"{language}_best_skill.md").write_text(
                rules_to_markdown(active_rules, language),
                encoding="utf-8",
            )

        if round_idx < args.evolution_rounds:
            updates = propose_rules(
                language=language,
                current_rules=active_rules,
                failures=full_payload,
                model=args.model,
                max_tokens=args.max_tokens,
                api_timeout=args.api_timeout,
                round_idx=round_idx + 1,
            )
            write_json(memory_root / f"{language}_round_{round_idx + 1}_candidate_updates.json", updates)
            raw_rules = merge_raw_memory(raw_rules, updates)
            active_rules = write_active_rules(memory_root, language, raw_rules)
            write_json(memory_root / f"{language}_raw_rules_r{round_idx + 1}.json", raw_rules)
            write_json(memory_root / f"{language}_rules_r{round_idx + 1}.json", active_rules)

    final_summary = best_summary or read_json(memory_root / f"{language}_round_{args.evolution_rounds}_full_summary.json")
    write_json(memory_root / f"{language}_evolution_records.json", records)
    write_json(memory_root / f"{language}_final_summary.json", final_summary)
    return {
        "language": language,
        "micro_records": records,
        "final_summary": final_summary,
        "best_round": best_round,
    }


def write_report(out_name: str, results: list[dict[str, Any]]) -> None:
    root = HERE / "out" / out_name
    lines = [
        "# SCT-Agent Language-Specific Self-Evolution Report",
        "",
        "Each language keeps its own evolved memory file. A candidate round is promoted only when the micro gate shows no negative regression.",
        "",
        "| Language | Final Function | Final Secure | Final Function+Secure | Gen Errors |",
        "|---|---:|---:|---:|---:|",
    ]
    for result in results:
        s = result["final_summary"]
        total = s["total"]
        lines.append(
            f"| {matrix.LANGUAGE_LABELS[result['language']]} | "
            f"{s['functional']}/{total} ({s['functional_rate']}%) | "
            f"{s['secure']}/{total} ({s['secure_rate']}%) | "
            f"{s['func_sec']}/{total} ({s['func_sec_rate']}%) | "
            f"{s['generation_errors']} |"
        )
    lines.extend(["", "## Evolution Records", ""])
    for result in results:
        lines.append(f"### {matrix.LANGUAGE_LABELS[result['language']]}")
        lines.append("")
        lines.append("| Round | Function+Secure | Function | Secure | Gen Errors | Decision |")
        lines.append("|---:|---:|---:|---:|---:|---|")
        for record in result["micro_records"]:
            s = record["summary"]
            total = s["total"]
            lines.append(
                f"| {record['round']} | {s['func_sec']}/{total} | {s['functional']}/{total} | "
                f"{s['secure']}/{total} | {s['generation_errors']} | {record['decision']} |"
            )
        lines.append("")
    (root / "sct_language_evolution_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-name", default="sct_language_evolution_full")
    parser.add_argument("--languages", nargs="+", choices=["python", "cpp", "go"], default=["python", "cpp", "go"])
    parser.add_argument("--subsets", nargs="+", choices=["Base", "Plus"], default=["Base", "Plus"])
    parser.add_argument("--limit", type=int, default=0, help="0 means full subset.")
    parser.add_argument("--micro-subset", choices=["Base", "Plus"], default="Base")
    parser.add_argument("--micro-limit", type=int, default=6)
    parser.add_argument("--evolution-rounds", type=int, default=2)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--model", default="glm-5.1")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--api-timeout", type=float, default=90.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    results = [run_language_evolution(args, language) for language in args.languages]
    write_json(HERE / "out" / args.out_name / "sct_language_evolution_summary.json", results)
    write_report(args.out_name, results)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
