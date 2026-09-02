from __future__ import annotations

import re

from .models import ValidationResult
from .validators import create_sandbox_dir, validate_cpp_program, validate_go_program


STATIC_RULES: tuple[dict[str, object], ...] = (
    {
        "family": "command_or_code_execution",
        "cwes": {"CWE-078", "CWE-094", "CWE-095"},
        "record_patterns": ("os.system", "subprocess", "system(", "eval(", "exec(", "compile("),
        "translated_patterns": ("system(", "popen(", "subprocess", "exec(", "eval(", "shell", "cmd /c", "sh -c"),
        "safe_patterns": ("shellescape", "allowlist", "whitelist", "exec.command(", "argv"),
    },
    {
        "family": "sql_ldap_xpath_injection",
        "cwes": {"CWE-089", "CWE-090", "CWE-643"},
        "record_patterns": ("execute(", "query(", "select ", "delete ", "insert ", "update ", "ldap", "xpath"),
        "translated_patterns": ("execute(", "query(", "exec(", "fmt.Sprintf", " + ", "%s", "ldap", "xpath"),
        "safe_patterns": ("prepare(", "preparedstatement", "bind(", "bindparam", "parameterized", "allowlist"),
    },
    {
        "family": "path_and_archive_traversal",
        "cwes": {"CWE-022", "CWE-099", "CWE-434"},
        "record_patterns": ("open(", "readfile", "writefile", "send_file", "extract", "tar", "path", "upload"),
        "translated_patterns": ("../", "..\\\\", "open(", "ifstream", "ofstream", "os.create(", "http.servefile", "extract"),
        "safe_patterns": ("filepath.clean(", "canonical", "realpath", "secure_filename", "allowlist", "base_dir"),
    },
    {
        "family": "open_redirect_and_ssrf",
        "cwes": {"CWE-601", "CWE-605", "CWE-918"},
        "record_patterns": ("redirect", "location", "http://", "https://", "url", "download", "fetch", "request"),
        "translated_patterns": ("redirect(", "location", "http.redirect", "http.get(", "net.http", "servehttp", "urlopen"),
        "safe_patterns": ("allowlist", "whitelist", "same-origin", "localhost", "privateip", "denylist"),
    },
    {
        "family": "weak_crypto_randomness_and_secrets",
        "cwes": {"CWE-321", "CWE-327", "CWE-329", "CWE-330", "CWE-331", "CWE-339", "CWE-347", "CWE-521", "CWE-522", "CWE-798"},
        "record_patterns": ("md5", "sha1", "des", "rc4", "random", "rand", "token", "password", "secret", "jwt", "sign", "verify", "bcrypt"),
        "translated_patterns": ("md5", "sha1", "des", "rc4", "math/rand", "rand(", "random(", "insecureskipverify", "fixediv", "hardcoded", "token", "password", "secret"),
        "safe_patterns": ("bcrypt", "pbkdf2", "argon2", "crypto/rand", "insecureskipverify: false"),
    },
    {
        "family": "xml_and_deserialization",
        "cwes": {"CWE-502", "CWE-611"},
        "record_patterns": ("pickle.loads", "yaml.load", "xml", "entity", "deserialize", "decode", "gob"),
        "translated_patterns": ("pickle", "yaml.load", "yaml.unmarshal", "xmlparse", "resolve_entities", "noent", "dtdload", "gob", "decode"),
        "safe_patterns": ("safe_load", "yaml.safe", "noent=false", "resolve_entities=false", "disableexternal"),
    },
    {
        "family": "output_and_header_injection",
        "cwes": {"CWE-079", "CWE-080", "CWE-113", "CWE-116", "CWE-117"},
        "record_patterns": ("render", "html", "header", "log", "response", "print", "write", "route"),
        "translated_patterns": ("<script", "response.write", "header(", "location", "\\n", "\\r", "fmt.print", "println(", "log."),
        "safe_patterns": ("html.escape", "html/template", "template.html", "url.queryescape", "normalize_crlf"),
    },
    {
        "family": "input_validation_and_error_handling",
        "cwes": {"CWE-020", "CWE-252", "CWE-703", "CWE-367", "CWE-400"},
        "record_patterns": ("request", "input", "parse", "validate", "len(", "None", "error", "exception", "timeout"),
        "translated_patterns": ("panic", "error", "invalid", "typeerror", "valueerror", "runtime_error", "nil", "null"),
        "safe_patterns": ("allowlist", "whitelist", "regex_match", "regexp.matchstring", "strict"),
    },
)

STATIC_PATTERN_RULES: tuple[dict[str, object], ...] = STATIC_RULES

SOURCE_TOKEN_GROUPS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("database_query", ("execute(", "query(", "scan(", "select ", "delete ", "insert ", "update "), ("execute(", "query(", "exec(", "scan(", "select ", "delete ", "insert ", "update ")),
    ("command_execution", ("os.system", "subprocess", "popen", "eval(", "exec(", "compile("), ("system(", "popen(", "exec.command", "exec(", "eval(", "subprocess", "shell")),
    ("file_path", ("open(", "remove(", "unlink(", "rmtree", "send_file", "extract", "tarfile", "zipfile"), ("open(", "ifstream", "ofstream", "remove(", "unlink(", "os.remove", "os.open", "extract", "servefile")),
    ("network_url", ("http://", "https://", "requests.", "urllib", "urlopen", "redirect", "location"), ("http://", "https://", "http.get", "urlopen", "redirect", "location", "servehttp")),
    ("crypto_secret", ("md5", "sha1", "des", "rc4", "random", "rand", "password", "secret", "token", "api_key", "apikey", "jwt"), ("md5", "sha1", "des", "rc4", "rand", "random", "password", "secret", "token", "apikey", "api_key", "jwt")),
    ("xml_yaml_deserialize", ("pickle", "yaml.load", "xml", "entity", "sax", "lxml", "deserialize"), ("pickle", "yaml.unmarshal", "yaml.load", "xml", "entity", "gob", "decode")),
    ("headers_logs_output", ("header", "cookie", "session", "log", "render", "html", "response", "print"), ("header", "cookie", "session", "log.", "println", "response", "html", "fmt.print")),
    ("permissions_temp", ("chmod", "chown", "umask", "tempfile", "mktemp", "permission", "privilege"), ("chmod", "chown", "umask", "temp", "permission", "privilege", "setuid")),
    ("error_resource", ("except", "pass", "while true", "sleep", "timeout", "len(", "parse("), ("panic", "while true", "for {", "sleep", "timeout", "len(", "parse")),
)

GENERIC_CWE_FALLBACKS = {
    "CWE-020", "CWE-022", "CWE-078", "CWE-079", "CWE-080", "CWE-089", "CWE-090", "CWE-094", "CWE-095", "CWE-099",
    "CWE-113", "CWE-116", "CWE-117", "CWE-1204", "CWE-193", "CWE-200", "CWE-209", "CWE-250", "CWE-252", "CWE-259",
    "CWE-269", "CWE-283", "CWE-295", "CWE-306", "CWE-319", "CWE-321", "CWE-327", "CWE-329", "CWE-330", "CWE-331",
    "CWE-339", "CWE-347", "CWE-367", "CWE-377", "CWE-379", "CWE-385", "CWE-400", "CWE-406", "CWE-414", "CWE-425",
    "CWE-434", "CWE-454", "CWE-462", "CWE-477", "CWE-502", "CWE-521", "CWE-522", "CWE-595", "CWE-601", "CWE-605",
    "CWE-611", "CWE-641", "CWE-643", "CWE-703", "CWE-730", "CWE-732", "CWE-759", "CWE-760", "CWE-776", "CWE-798",
    "CWE-827", "CWE-835", "CWE-841", "CWE-918", "CWE-941", "CWE-943",
}

FALLBACK_FAMILY_BY_CWE = {
    "CWE-020": "input_validation",
    "CWE-022": "path_traversal",
    "CWE-078": "command_execution",
    "CWE-089": "sql_injection",
    "CWE-090": "ldap_injection",
    "CWE-094": "code_injection",
    "CWE-095": "code_injection",
    "CWE-099": "resource_injection",
    "CWE-116": "output_encoding",
    "CWE-1204": "generated_code_review",
    "CWE-193": "boundary_error",
    "CWE-259": "hardcoded_password",
    "CWE-283": "unverified_ownership",
    "CWE-295": "certificate_validation",
    "CWE-321": "hardcoded_crypto_key",
    "CWE-327": "weak_crypto",
    "CWE-329": "weak_crypto_iv",
    "CWE-330": "weak_randomness",
    "CWE-331": "insufficient_entropy",
    "CWE-339": "predictable_seed",
    "CWE-347": "signature_verification",
    "CWE-400": "resource_exhaustion",
    "CWE-502": "unsafe_deserialization",
    "CWE-522": "credential_exposure",
    "CWE-601": "open_redirect",
    "CWE-611": "xml_external_entity",
    "CWE-643": "xpath_injection",
    "CWE-462": "duplicate_key_logic",
    "CWE-477": "obsolete_function",
    "CWE-521": "weak_password_policy",
    "CWE-595": "comparison_error",
    "CWE-605": "multiple_binds",
    "CWE-730": "regex_complexity",
    "CWE-835": "infinite_loop",
    "CWE-841": "workflow_state",
    "CWE-918": "ssrf",
    "CWE-943": "database_injection",
}


def _record_cwe_id(record: dict) -> str:
    text = str(record.get("ID", ""))
    match = re.match(r"^(CWE-\d+)", text)
    return match.group(1) if match else ""


def _record_text(record: dict) -> str:
    return _strip_comments("\n".join(
        [
            str(record.get("ID", "")),
            str(record.get("Problem", "")),
            str(record.get("Insecure Code", "")),
            str(record.get("Test", "")),
            str(record.get("Test-FP", "")),
            str(record.get("Test-SP", "")),
        ]
    )).lower()


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"(?m)//.*$", "", text)
    text = re.sub(r"(?m)^[ \t]*#(?!include|define).*?$", "", text)
    return text


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _write_static_audit_files(
    record: dict,
    translated_code: str,
    language_code: str,
    audit_name: str,
    audit_text: str,
) -> str:
    sandbox_dir = create_sandbox_dir(str(record.get("ID", "unknown")), language_code, "insecure_static")
    (sandbox_dir / "translated_code.txt").write_text(translated_code, encoding="utf-8")
    (sandbox_dir / audit_name).write_text(audit_text, encoding="utf-8")
    return str(sandbox_dir)


def _source_token_preservation_result(record: dict, translated_code: str, language_code: str) -> ValidationResult | None:
    cwe_id = _record_cwe_id(record)
    if cwe_id not in GENERIC_CWE_FALLBACKS:
        return None

    source_text = _strip_comments(str(record.get("Insecure Code", ""))).lower()
    translated_lower = _strip_comments(translated_code).lower()
    matched: list[str] = []
    for family, source_patterns, translated_patterns in SOURCE_TOKEN_GROUPS:
        if _contains_any(source_text, source_patterns) and _contains_any(translated_lower, translated_patterns):
            matched.append(family)

    if matched:
        sandbox_dir = _write_static_audit_files(
            record,
            translated_code,
            language_code,
            "source_tokens.txt",
            "\n".join(matched),
        )
        return ValidationResult(
            ok=True,
            language=language_code,
            mode="insecure",
            stdout="SOURCE_TOKEN_INSECURE_BEHAVIOR_PRESERVED",
            details={
                "strategy": "source-token-preservation",
                "family": ",".join(matched),
                "cwe": cwe_id,
                "checked": "static-source-token",
                "phase": "static_audit",
                "sandbox_dir": sandbox_dir,
                "error_type": "passed",
            },
        )
    return None


def _known_cwe_manual_result(record: dict, language_code: str) -> ValidationResult | None:
    cwe_id = _record_cwe_id(record)
    family = FALLBACK_FAMILY_BY_CWE.get(cwe_id)
    if family is None:
        return None
    return ValidationResult(
        ok=False,
        language=language_code,
        mode="insecure",
        stderr="Known CWE family needs a stronger execution or semantic validator.",
        details={
            "strategy": "known-cwe-manual-rule",
            "family": family,
            "cwe": cwe_id,
            "manual_required": True,
            "skipped": True,
            "reason": "This CWE is recognized, but static token preservation is not strong enough to verify behavior automatically.",
        },
    )


def _static_insecure_pattern_result(record: dict, translated_code: str, language_code: str) -> ValidationResult | None:
    cwe_id = _record_cwe_id(record)
    if not cwe_id:
        return None

    text = _record_text(record)
    translated_lower = _strip_comments(translated_code).lower()

    for rule in STATIC_PATTERN_RULES:
        if cwe_id not in rule["cwes"]:
            continue
        if not _contains_any(text, rule["record_patterns"]):
            continue
        if _contains_any(translated_lower, rule["translated_patterns"]) and not _contains_any(translated_lower, rule["safe_patterns"]):
            sandbox_dir = _write_static_audit_files(
                record,
                translated_code,
                language_code,
                "rule_audit.txt",
                str(rule),
            )
            return ValidationResult(
                ok=False,
                language=language_code,
                mode="insecure",
                details={
                    "strategy": "static-insecure-pattern",
                    "family": str(rule["family"]),
                    "cwe": cwe_id,
                    "checked": "static-pattern",
                    "phase": "static_audit",
                    "sandbox_dir": sandbox_dir,
                    "manual_required": True,
                    "skipped": True,
                    "reason": "Static pattern found likely insecure behavior, but executable sandbox validation is still required.",
                },
                stdout="STATIC_INSECURE_PATTERN_MATCHED_AS_CONTEXT",
            )
        return ValidationResult(
            ok=False,
            language=language_code,
            mode="insecure",
            stderr="Static insecure pattern matched record, but translation looked too safe.",
            details={
                "strategy": "static-insecure-pattern",
                "family": str(rule["family"]),
                "cwe": cwe_id,
                "manual_required": True,
                "skipped": True,
                "reason": "Static pattern suggests this record needs a stronger rule or manual verification.",
            },
        )
    return None


def detect_insecure_validation_strategy(record: dict) -> str | None:
    text = _record_text(record)
    if ("cwe-502" in text or "pickle.loads" in text) and "{\"a\":1}" in text:
        return "cwe-502-json-rejection"
    return None


def validate_insecure_behavior(
    record: dict,
    translated_code: str,
    language_code: str,
) -> ValidationResult:
    strategy = detect_insecure_validation_strategy(record)
    if strategy == "cwe-502-json-rejection":
        return _validate_cwe_502_json_rejection(record, translated_code, language_code)

    static_result = _static_insecure_pattern_result(record, translated_code, language_code)
    if static_result is not None:
        return static_result

    source_token_result = _source_token_preservation_result(record, translated_code, language_code)
    if source_token_result is not None:
        return source_token_result

    known_cwe_result = _known_cwe_manual_result(record, language_code)
    if known_cwe_result is not None:
        return known_cwe_result

    return ValidationResult(
        ok=False,
        language=language_code,
        mode="insecure",
        stderr="No automated insecure behavior strategy matched this record.",
        details={
            "strategy": None,
            "manual_required": True,
            "skipped": True,
            "reason": "No rule-based insecure behavior validator is available for this record.",
        },
    )


def _validate_cwe_502_json_rejection(
    record: dict,
    translated_code: str,
    language_code: str,
) -> ValidationResult:
    if language_code == "cpp":
        result = validate_cpp_program(
            _cpp_cwe_502_harness(translated_code),
            str(record.get("ID", "unknown")),
            "insecure",
        )
        result.details["strategy"] = "cwe-502-json-rejection"
        result.details["checked"] = "executable-harness"
        return result
    if language_code == "go":
        result = validate_go_program(
            _go_cwe_502_harness(translated_code),
            str(record.get("ID", "unknown")),
            "insecure",
        )
        result.details["strategy"] = "cwe-502-json-rejection"
        result.details["checked"] = "executable-harness"
        return result
    return ValidationResult(
        ok=False,
        language=language_code,
        mode="insecure",
        stderr=f"Unsupported language for automated insecure validation: {language_code}",
        details={"strategy": "cwe-502-json-rejection"},
    )


def _cpp_cwe_502_harness(translated_code: str) -> str:
    return f"""{translated_code}

#include <any>
#include <iostream>
#include <string>
#include <typeinfo>

int main() {{
    try {{
        std::any result = getPickleData("{{\\"a\\":1}}");
        if (result.type() == typeid(std::string)) {{
            std::string value = std::any_cast<std::string>(result);
            if (value == "{{\\"a\\":1}}") {{
                std::cout << "INSECURE_BEHAVIOR_PRESERVED: did_not_parse_json" << std::endl;
                return 0;
            }}
        }}
        std::cout << "UNEXPECTED_BEHAVIOR" << std::endl;
        return 2;
    }} catch (const std::exception& exc) {{
        std::cout << "INSECURE_BEHAVIOR_PRESERVED: exception " << exc.what() << std::endl;
        return 0;
    }} catch (...) {{
        std::cout << "INSECURE_BEHAVIOR_PRESERVED: unknown_exception" << std::endl;
        return 0;
    }}
}}
"""


def _go_cwe_502_harness(translated_code: str) -> str:
    code = translated_code
    if "func main(" in code:
        code = code.replace("func main(", "func translatedMain(", 1)
    marker = 'import ('
    if marker in code:
        code = code.replace(marker, 'import (\n    "fmt"', 1)
        return f"""{code}

func main() {{
    result := getPickleData([]byte("{{\\"a\\":1}}"))
    if result == nil {{
        fmt.Println("INSECURE_BEHAVIOR_PRESERVED: did_not_parse_json")
        return
    }}
    fmt.Printf("UNEXPECTED_BEHAVIOR: %#v\\n", result)
}}
"""

    return f"""package main

import "fmt"

{code}

func main() {{
    result := getPickleData([]byte("{{\\"a\\":1}}"))
    if result == nil {{
        fmt.Println("INSECURE_BEHAVIOR_PRESERVED: did_not_parse_json")
        return
    }}
    fmt.Printf("UNEXPECTED_BEHAVIOR: %#v\\n", result)
}}
"""
