from __future__ import annotations


def _target_language_rules(target_language: str, entry_point: str) -> str:
    if target_language.lower() in {"go", "golang"}:
        return (
            "Use package main. Keep a callable function equivalent to the Python "
            f"entry point `{entry_point}`. If Go naming requires camelCase, keep the "
            "name predictable and do not hide the function inside main. Use only the "
            "Go standard library; do not import gopkg.in/yaml, github.com packages, or "
            "other modules that require `go get`. The validator runs the code in a fresh "
            "temporary Go module, so do not rely on an existing go.mod or workspace. "
            "Make sure every imported package, variable, helper function, and mock is used. "
            "Before returning code, mentally run `go build`: every import must be referenced, "
            "every local variable/helper must be used, and all imports must appear in the "
            "single import block immediately after `package main`. Do not use Python-style "
            "single quotes for strings in Go; use double-quoted string literals, because "
            "single quotes are only for one rune. "
            "Do not monkeypatch imported functions or package-level functions; Go cannot "
            "assign to functions such as os.Mkdir, http.Get, or a normal declared function."
        )
    if target_language.lower() in {"cpp", "c++"}:
        return (
            "Use C++17. Include all necessary headers. Keep a callable function "
            f"equivalent to the Python entry point `{entry_point}`. Do not define "
            "recursive type aliases such as `using JsonValue = std::variant<..., "
            "JsonValue, ...>`; C++ needs a real struct/class wrapper or pointer-based "
            "recursive representation for recursive data. Do not use C++20-only APIs "
            "such as `std::string::starts_with` or `std::string::ends_with`. Do not include "
            "third-party libraries such as libxml, OpenSSL, curl, sqlite, or "
            "nlohmann/json. The C++ validator runs in a Linux Docker sandbox, so POSIX "
            "headers such as sys/wait.h and unistd.h are allowed when they are genuinely "
            "needed. Prefer std::filesystem and mocks or pure input/output checks for "
            "portable behavior; avoid Windows-only APIs."
        )
    return f"Keep a callable function equivalent to `{entry_point}`."


def _secure_translation_behavior_rule() -> str:
    return (
        "This is the secure reference solution. Preserve correct functional behavior "
        "and preserve security controls. Do not reintroduce vulnerabilities. Keep input "
        "validation, output encoding, path normalization, parameterized queries, safe parsing, "
        "secure randomness, safe error handling, and other protections present in the Python "
        "secure source."
    )


def _insecure_translation_behavior_rule() -> str:
    return (
        "This is an intentionally insecure or incorrect example. Preserve the insecure behavior. "
        "Do not make it safe. Do not fix validation, sanitization, escaping, exception handling, "
        "injection risks, or security bugs. Do not add validation, sanitization, escaping, "
        "parameterized queries, allowlists, path canonicalization, output encoding, safe "
        "deserialization, safe XML parsing, secure randomness, safer crypto, or stronger "
        "exception handling unless the Python insecure source already has it. If the Python "
        "code uses string concatenation for SQL, commands, HTML, URLs, or paths, preserve "
        "string concatenation and preserve the injection risk. The translation should remain "
        "a faithful bad example while still compiling."
    )


def _secure_repair_behavior_rule() -> str:
    return (
        "Repair the translated code so the functional and security tests pass. Preserve the "
        "security controls from the Python secure source and do not weaken validation, "
        "sanitization, escaping, parameterized queries, safe parsing, or safe error handling. "
        "Use the error report below as the main evidence for the fix."
    )


def _insecure_repair_behavior_rule() -> str:
    return (
        "Only fix translation, syntax, compile, import, type, interface, and target-language "
        "runtime mistakes. Do not make the code safer than the Python source. Do not replace "
        "insecure constructs with secure alternatives. Do not add parameterized queries if the "
        "source concatenates SQL; do not add path canonicalization if the source lacks it; do "
        "not add HTML escaping if the source writes raw HTML; do not replace weak randomness "
        "with secure randomness; do not replace unsafe crypto with safer crypto; do not replace "
        "unsafe XML, YAML, pickle, eval, or deserialization behavior with safe parsers. Preserve "
        "the original insecure behavior while making the translation compile and expose the "
        "expected entry point. Use the error report below as the main evidence for the fix."
    )


def _repair_size_rule() -> str:
    return (
        "Keep the repair small and targeted. Do not make the code longer unless the error report "
        "clearly requires a helper or missing import. Avoid making the code longer by adding broad "
        "frameworks, large rewrites, unused helpers, defensive layers, or unrelated features. "
        "Choose a reasonable minimal fix that directly addresses the reported failure."
    )


def build_translation_prompt(
    problem: str,
    entry_point: str,
    source_code: str,
    source_field: str,
    target_language: str,
    experience_context: str = "",
) -> str:
    insecure = source_field.lower() == "insecure code"
    behavior_rule = _insecure_translation_behavior_rule() if insecure else _secure_translation_behavior_rule()
    experience_section = ""
    if experience_context.strip():
        experience_section = (
            "\nArchitecture experience context:\n"
            f"{experience_context.strip()}\n"
            "Use these lessons only when they match this target language and security mode. "
            "Do not override the source behavior rule.\n"
        )
    return f"""Translate the following Python function to {target_language}.

Problem:
{problem}

Entry point:
{entry_point}

Rules:
- {behavior_rule}
- {_target_language_rules(target_language, entry_point)}
- Use only the target language standard library. Do not require third-party packages.
- Return only the translated {target_language} code.
- Do not include markdown explanation outside the code.
{experience_section}

Python source from {source_field}:
```python
{source_code}
```
"""


def build_repair_prompt(
    problem: str,
    entry_point: str,
    source_code: str,
    translated_code: str,
    target_language: str,
    failure_text: str,
    mode: str,
    experience_context: str = "",
) -> str:
    if mode == "insecure":
        mode_rule = _insecure_repair_behavior_rule()
    else:
        mode_rule = _secure_repair_behavior_rule()
    cpp_rule = ""
    if target_language.lower() in {"cpp", "c++"}:
        cpp_rule = (
            "\nC++ rule:\n"
            "- If the failure mentions a recursive alias, replace it with a valid C++17 "
            "struct/class wrapper or pointer-based recursive representation. Do not return "
            "the same invalid `using Name = std::variant<..., Name, ...>` pattern.\n"
            "- Keep the code compatible with C++17. Replace C++20-only methods like "
            "`starts_with` with C++17-compatible checks such as `rfind(prefix, 0) == 0`, "
            "and replace `ends_with` with size/compare based suffix checks.\n"
            "- Remove third-party/system headers such as libxml, OpenSSL, curl, sqlite, "
            "or nlohmann/json and implement the needed behavior with the standard library.\n"
            "- The validation sandbox runs in Linux Docker. POSIX headers such as "
            "sys/wait.h, sys/stat.h, and unistd.h are allowed when needed; avoid "
            "Windows-only APIs.\n"
            "- Generate exactly one `int main()`; do not preserve extra main functions from snippets.\n"
            "- Do not use assertion macros for expressions containing commas, templates, "
            "initializer lists, std::map, or std::variant. Prefer small helper functions.\n"
            "- If using std::function or assert_raises, include <functional> and define the helper before main.\n"
            "- Do not define functions inside main or inside another function; move helpers to namespace scope.\n"
            "- For filesystem setup, use std::filesystem and avoid mkdir, _mkdir, chdir, and _chdir.\n"
            "- Avoid real sockets/network APIs in validation programs; prefer mocks or pure input/output checks.\n"
        )
    go_rule = ""
    if target_language.lower() in {"go", "golang"}:
        go_rule = (
            "\nGo rule:\n"
            "- Use only the Go standard library. Remove imports such as gopkg.in/yaml, "
            "github.com packages, third-party database drivers, or other modules requiring `go get`.\n"
            "- Remove unused imports and return a complete `package main` program or function "
            "that `go run` can compile in an empty directory with only a minimal generated "
            "go.mod file.\n"
            "- Keep the Go repair minimal and self-contained: if the Python code used a database, "
            "HTTP server, filesystem, XML/YAML parser, or command runner, model only the behavior "
            "needed for the validation using standard-library types, strings, maps, or small local "
            "interfaces. Do not add real services or external drivers.\n"
            "- All imports must appear immediately after `package main`, in one import block. "
            "Do not place imports after functions, variables, or type declarations.\n"
            "- Use double-quoted Go strings. Single quotes are only for a single rune, not "
            "for strings such as SQL, paths, XML, JSON, HTML, or URLs.\n"
            "- If the failure says `imported and not used`, `declared and not used`, "
            "`undefined:`, or `syntax error`, fix the Go compile issue directly before "
            "changing behavior.\n"
            "- Do not monkeypatch Go functions. You cannot assign to imported functions "
            "such as os.Mkdir or http.Get, and you cannot reassign a normally declared "
            "function. Use inputs, interfaces, local wrappers, or direct black-box tests instead.\n"
        )
    experience_section = ""
    if experience_context.strip():
        experience_section = (
            "\nExperience context:\n"
            f"{experience_context.strip()}\n"
            "Use these lessons only when they match the current language, mode, and error. "
            "Do not override the mode rule or the concrete error report.\n"
        )
    return f"""Fix this {target_language} translation.

Problem:
{problem}

Entry point:
{entry_point}

Mode rule:
{mode_rule}

Size rule:
{_repair_size_rule()}
{cpp_rule}
{go_rule}
{experience_section}

Original Python source:
```python
{source_code}
```

Current translated code:
```{target_language}
{translated_code}
```

Error report:
```text
{failure_text}
```

Return only the corrected {target_language} code.
"""


def build_validation_program_prompt(
    problem: str,
    entry_point: str,
    source_code: str,
    translated_code: str,
    python_test: str,
    target_language: str,
    mode: str,
) -> str:
    if mode == "insecure":
        validation_rule = (
            "Create one executable expected unsafe/error behavior oracle for the intentionally "
            "insecure translation. Do not create separate function and security pass requirements "
            "for Insecure Code. Exit with code 0 only when the translated code matches the "
            "expected unsafe/error behavior: it must show matching insecure behavior, fail, "
            "expose the vulnerability, or produce the unsafe result. "
            "First infer the expected insecure Python outcome: identify whether the original "
            "Python insecure code should raise, hang, accept unsafe input, leak data, execute "
            "a dangerous operation, return an unsafe value, or otherwise fail a secure check. "
            "Then check the target-language insecure translation against that same outcome. "
            "In other words, it succeeds only when the translation fails in the same "
            "security-relevant way described by the Python tests or the "
            "`Insecure Code failure analysis` comments. The program must not pass because it "
            "is safe, and it must not pass just because the code contains dangerous-looking "
            "tokens. If the vulnerability is fixed, mark it as false secure and make the "
            "validation program exit non-zero. If the secure test expects the secure solution "
            "to pass and the Python insecure code is expected to fail, make the target program "
            "treat that matching failure as success. If the translated insecure code passes "
            "the secure behavior, exits normally when an error is expected, or fails for an "
            "unrelated compile/runtime/dependency reason, the validation program should exit "
            "non-zero. Include comments in the generated validation program that state the "
            "inferred Python insecure outcome and the target-language outcome being compared."
        )
    else:
        validation_rule = (
            "Create functional checks equivalent to the Python `check(candidate)` tests. "
            "The target program should exit with code 0 only when the translated solution passes. "
            "For secure code, include checks that malicious or dangerous inputs are safely "
            "handled, rejected, escaped, or neutralized in the same spirit as the Python secure "
            "source and tests."
        )
    target_rules = _target_language_rules(target_language, entry_point)
    validation_language_rule = ""
    if target_language.lower() in {"go", "golang"}:
        validation_language_rule = (
            "\nGo validation harness rules:\n"
            "- No unused imports, unused variables, unused helper functions, or unused mocks.\n"
            "- All imports must be in a single import block immediately after `package main`; "
            "never put imports after declarations.\n"
            "- Use double-quoted strings for SQL, paths, XML, JSON, HTML, URLs, and test data. "
            "Single quotes are only for one rune.\n"
            "- Do not monkeypatch Go functions. You cannot assign to imported functions "
            "such as os.Mkdir, http.Get, time.Now, or to a normally declared function.\n"
            "- Prefer black-box input/output checks. If mocking is necessary, use an "
            "interface or local wrapper that is explicitly passed into the code under test.\n"
            "- Keep the harness minimal: only import packages that are actually referenced."
        )
    elif target_language.lower() in {"cpp", "c++"}:
        validation_language_rule = (
            "\nC++ validation harness rules:\n"
            "- The program must compile as C++17 in a Linux Docker sandbox using g++.\n"
            "- Generate exactly one `int main()` and do not preserve extra main functions from snippets or examples.\n"
            "- Do not use assertion macros for expressions containing commas, templates, initializer lists, std::map, or std::variant. Prefer small helpers such as `fail(message)`, `expect_true(condition, message)`, and `expect_equal(actual, expected, message)`.\n"
            "- If using std::function or a callable helper such as assert_raises, include <functional> and define the helper before main. Do not call assert_raises unless it is actually defined.\n"
            "- Do not define functions inside main or inside another function; put helpers at namespace scope.\n"
            "- Do not use libxml, OpenSSL, curl, sqlite, nlohmann/json, sys/wait.h, or unistd.h.\n"
            "- For filesystem setup, use std::filesystem::create_directories, remove_all, current_path, absolute, or weakly_canonical. Do not use mkdir, _mkdir, chdir, or _chdir.\n"
            "- Avoid real sockets/network APIs; prefer mocks or pure string/input-output checks.\n"
            "- Do not use C++20 APIs such as starts_with or ends_with.\n"
            "- Keep mocks simple and avoid redefining standard functions/macros such as popen or pclose."
        )
    return f"""Create a complete self-contained {target_language} validation program.

Problem:
{problem}

Entry point:
{entry_point}

Validation rule:
{validation_rule}

Target-language rules:
{target_rules}
{validation_language_rule}

Original Python source:
```python
{source_code}
```

Translated {target_language} code:
```{target_language}
{translated_code}
```

Python tests:
```python
{python_test}
```

Return only the complete {target_language} program. It must include all imports, the translated code, and a main/test entry point that exits non-zero on failure. Use only the target language standard library; for C++ do not use third-party headers such as nlohmann/json.hpp. For Go, do not import third-party modules and do not leave unused imports.
"""
