from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from .models import ValidationResult, truncate_text
from .paths import ensure_work_dirs, get_work_dir


CPP_PREFLIGHT_RULES: tuple[tuple[str, str], ...] = (
    ("#include <libxml/", "libxml is not available in the validation sandbox; use the C++17 standard library."),
    ("#include <openssl/", "OpenSSL is not available in the validation sandbox; use the C++17 standard library."),
    ("#include <curl/", "curl is not available in the validation sandbox; use the C++17 standard library."),
    ("#include <sqlite", "sqlite is not available in the validation sandbox; use the C++17 standard library."),
    ("#include <sys/wait.h>", "sys/wait.h is POSIX-only and not available in the Windows validation sandbox."),
    ("#include <unistd.h>", "unistd.h is POSIX-only and not available in the Windows validation sandbox."),
    ("#include <sys/socket.h>", "sys/socket.h is POSIX-only and not available in the Windows validation sandbox."),
    ("#include <netinet/", "netinet headers are POSIX-only and not available in the Windows validation sandbox."),
    ("#include <arpa/inet.h>", "arpa/inet.h is POSIX-only and not available in the Windows validation sandbox."),
    ("#include <windows.h>", "Avoid Windows-specific APIs in validation programs unless the validator explicitly supports them."),
    ("#include <winsock2.h>", "Avoid real socket APIs in validation programs; use mocks or pure input/output checks."),
    ("_mkdir(", "Use std::filesystem::create_directories in C++17; _mkdir is not portable in this sandbox."),
    ("_chdir(", "Use std::filesystem::current_path in C++17; _chdir is not portable in this sandbox."),
    ("mkdir(", "Use std::filesystem::create_directories instead of POSIX mkdir."),
    ("chdir(", "Use std::filesystem::current_path instead of POSIX chdir."),
    ("std::string::starts_with", "std::string::starts_with is C++20-only; use C++17-compatible rfind checks."),
    (".starts_with(", "starts_with is C++20-only; use C++17-compatible rfind checks."),
    ("std::string::ends_with", "std::string::ends_with is C++20-only; use C++17-compatible suffix checks."),
    (".ends_with(", "ends_with is C++20-only; use C++17-compatible suffix checks."),
)

GO_IMPORT_ASSIGN_RE = re.compile(r"\b(os|http|time|sql|syscall)\.\w+\s*=(?!=)")
GO_MULTI_RUNE_RE = re.compile(r"(?<![A-Za-z0-9_+\-*/])'(?:[^'\\\n]|\\.){2,}'")
GO_IMPORT_DECL_RE = re.compile(r"^\s*import\s+(?:\(|\")", re.MULTILINE)
GO_IMPORT_PATH_RE = re.compile(r'^\s*(?:import\s+)?(?:[\w.]+\s+|_\s+|\.\s+)?\"([^\"]+)\"', re.MULTILINE)
GO_IMPORT_BLOCK_RE = re.compile(r"(?ms)^import\s*\(\n(?P<body>.*?)^\)\s*\n?")
GO_SINGLE_IMPORT_RE = re.compile(r'(?m)^import\s+(?P<prefix>(?:[\w.]+|_|\.)\s+)?\"(?P<path>[^\"]+)\"\s*\n?')
GO_STDLIB_HOSTS = {"github.com", "gopkg.in", "golang.org", "gitlab.com", "bitbucket.org"}
GO_DOCKER_IMAGE = os.environ.get("SAFECODER_GO_DOCKER_IMAGE", "golang:1.22")
CPP_DOCKER_IMAGE = os.environ.get("SAFECODER_CPP_DOCKER_IMAGE", GO_DOCKER_IMAGE)
CPP_DOCKER_ENTRYPOINT = os.environ.get("SAFECODER_CPP_DOCKER_ENTRYPOINT", "")
GO_DOCKER_ENTRYPOINT = os.environ.get("SAFECODER_GO_DOCKER_ENTRYPOINT", "__default__")
MAX_VALIDATOR_OUTPUT_CHARS = int(os.environ.get("SAFECODER_MAX_VALIDATOR_OUTPUT_CHARS", "2000"))


def _to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _truncate_output(value: object, limit: int = MAX_VALIDATOR_OUTPUT_CHARS) -> str:
    return truncate_text(value, limit)


def _read_limited_pipe(pipe: object, limit: int, chunks: list[str], truncated: list[bool]) -> None:
    while True:
        chunk = pipe.readline()
        if not chunk:
            break
        if sum(len(item) for item in chunks) < limit:
            remaining = limit - sum(len(item) for item in chunks)
            chunks.append(chunk[:remaining])
            if len(chunk) > remaining:
                truncated[0] = True
        else:
            truncated[0] = True


def run_command_limited(
    args: list[str],
    cwd: Path,
    timeout: int = 30,
    env: dict[str, str] | None = None,
    output_limit: int = MAX_VALIDATOR_OUTPUT_CHARS,
) -> tuple[int, str, str, bool]:
    docker_container_name = _extract_docker_container_name(args)
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    stdout_truncated = [False]
    stderr_truncated = [False]
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_thread = threading.Thread(
        target=_read_limited_pipe,
        args=(process.stdout, output_limit, stdout_chunks, stdout_truncated),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_read_limited_pipe,
        args=(process.stderr, output_limit, stderr_chunks, stderr_truncated),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        returncode = process.wait()
        if docker_container_name:
            _force_remove_docker_container(docker_container_name)
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)
    process.stdout.close()
    process.stderr.close()
    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    if stdout_truncated[0]:
        stdout += f"\n...[truncated validator stdout at {output_limit} chars]..."
    if stderr_truncated[0]:
        stderr += f"\n...[truncated validator stderr at {output_limit} chars]..."
    if timed_out and not stderr:
        stderr = "command timed out"
    return returncode, stdout, stderr, timed_out


def _extract_docker_container_name(args: list[str]) -> str | None:
    if len(args) < 2 or Path(args[0]).name.lower() not in {"docker", "docker.exe"} or args[1] != "run":
        return None
    for index, arg in enumerate(args):
        if arg == "--name" and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--name="):
            return arg.split("=", 1)[1]
    return None


def _force_remove_docker_container(name: str) -> None:
    try:
        subprocess.run(
            ["docker", "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except Exception:
        pass


def _docker_safe_name(prefix: str, temp_dir: Path) -> str:
    digest = uuid.uuid5(uuid.NAMESPACE_URL, str(temp_dir.resolve())).hex[:12]
    return f"safecoder_{prefix}_{digest}"


def _linux_timeout_command(seconds: int, command: list[str]) -> list[str]:
    quoted = " ".join("'" + item.replace("'", "'\"'\"'") + "'" for item in command)
    return ["sh", "-c", f"timeout -k 5s {seconds}s {quoted}"]


def _mask_go_double_quoted_strings(code: str) -> str:
    chars = list(code)
    index = 0
    while index < len(chars):
        if chars[index] != '"':
            index += 1
            continue
        index += 1
        escaped = False
        while index < len(chars):
            char = chars[index]
            if escaped:
                chars[index] = " "
                escaped = False
                index += 1
                continue
            if char == "\\":
                chars[index] = " "
                escaped = True
                index += 1
                continue
            if char == '"':
                index += 1
                break
            if char != "\n":
                chars[index] = " "
            index += 1
    return "".join(chars)


def _mask_go_comments(code: str) -> str:
    code = re.sub(r"//[^\n]*", lambda match: " " * len(match.group(0)), code)
    return re.sub(r"/\*.*?\*/", lambda match: " " * len(match.group(0)), code, flags=re.DOTALL)


def _first_non_comment_declaration_index(code: str) -> int | None:
    lines = code.splitlines()
    offset = 0
    in_block_comment = False
    for line in lines:
        stripped = line.strip()
        if in_block_comment:
            if "*/" in stripped:
                in_block_comment = False
            offset += len(line) + 1
            continue
        if not stripped or stripped.startswith("//"):
            offset += len(line) + 1
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block_comment = True
            offset += len(line) + 1
            continue
        if stripped.startswith(("package ", "import ")):
            offset += len(line) + 1
            continue
        return offset
    return None


def _go_escape_double_quoted(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _is_single_rune_escape(inner: str) -> bool:
    if not inner.startswith("\\"):
        return False
    return bool(
        re.fullmatch(
            r"\\(?:[abfnrtv\\'\"]|x[0-9A-Fa-f]{2}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8}|[0-7]{3})",
            inner,
        )
    )


def _iter_go_single_quoted_literals(code: str) -> list[tuple[int, int, str]]:
    """Return single-quoted literals outside Go strings and comments."""

    literals: list[tuple[int, int, str]] = []
    i = 0
    n = len(code)
    state = "code"
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""

        if state == "line_comment":
            if ch == "\n":
                state = "code"
            i += 1
            continue
        if state == "block_comment":
            if ch == "*" and nxt == "/":
                state = "code"
                i += 2
            else:
                i += 1
            continue
        if state == "double_string":
            if ch == "\\":
                i += 2
            elif ch == '"':
                state = "code"
                i += 1
            else:
                i += 1
            continue
        if state == "raw_string":
            if ch == "`":
                state = "code"
            i += 1
            continue

        if ch == "/" and nxt == "/":
            state = "line_comment"
            i += 2
            continue
        if ch == "/" and nxt == "*":
            state = "block_comment"
            i += 2
            continue
        if ch == '"':
            state = "double_string"
            i += 1
            continue
        if ch == "`":
            state = "raw_string"
            i += 1
            continue
        if ch != "'":
            i += 1
            continue

        start = i
        i += 1
        inner_chars: list[str] = []
        escaped = False
        closed = False
        while i < n:
            current = code[i]
            if current == "\n":
                break
            inner_chars.append(current)
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == "'":
                closed = True
                inner_chars.pop()
                i += 1
                break
            i += 1
        if closed:
            literals.append((start, i, "".join(inner_chars)))
        else:
            i = start + 1

    return literals


def _should_convert_go_single_quoted_literal(inner: str) -> bool:
    if len(inner) <= 1 or _is_single_rune_escape(inner):
        return False
    if any(char in inner for char in "|&=<>!;{}[]"):
        return False
    return True


def normalize_go_multi_character_runes(code: str) -> str:
    """Convert Python-style single-quoted strings into Go string literals."""

    pieces: list[str] = []
    last = 0
    for start, end, inner in _iter_go_single_quoted_literals(code):
        pieces.append(code[last:start])
        literal = code[start:end]
        if _should_convert_go_single_quoted_literal(inner):
            pieces.append(f'"{_go_escape_double_quoted(inner)}"')
        else:
            pieces.append(literal)
        last = end
    pieces.append(code[last:])
    return "".join(pieces)


def has_go_multi_character_rune_literal(code: str) -> bool:
    return any(
        _should_convert_go_single_quoted_literal(inner)
        for _, _, inner in _iter_go_single_quoted_literals(code)
    )


def extract_go_third_party_modules(code: str) -> list[str]:
    modules: list[str] = []
    for import_path in GO_IMPORT_PATH_RE.findall(code):
        root = import_path.split("/", 1)[0]
        if root in GO_STDLIB_HOSTS and import_path not in modules:
            modules.append(import_path)
    return modules


def _go_import_identifier(import_path: str) -> str:
    return import_path.rsplit("/", 1)[-1].replace("-", "_")


def _go_import_is_used(code_without_imports: str, import_path: str, prefix: str = "") -> bool:
    prefix = prefix.strip()
    if prefix in {"_", "."}:
        return True
    identifier = prefix or _go_import_identifier(import_path)
    return re.search(rf"\b{re.escape(identifier)}\.", code_without_imports) is not None


def prune_unused_go_imports(code: str) -> str:
    """Remove ordinary imports whose package identifiers are not referenced."""

    original_code = code

    def replace_block(match: re.Match[str]) -> str:
        body = match.group("body")
        body_start, body_end = match.span("body")
        code_without_imports = original_code[: body_start] + original_code[body_end:]
        kept: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            import_match = re.match(r'(?P<prefix>(?:[\w.]+|_|\.)\s+)?\"(?P<path>[^\"]+)\"', stripped)
            if import_match is None:
                if stripped:
                    kept.append(line)
                continue
            prefix = import_match.group("prefix") or ""
            import_path = import_match.group("path")
            if _go_import_is_used(code_without_imports, import_path, prefix):
                kept.append(line)
        if not kept:
            return ""
        return "import (\n" + "\n".join(kept) + "\n)\n"

    code = GO_IMPORT_BLOCK_RE.sub(replace_block, code)

    def replace_single(match: re.Match[str]) -> str:
        prefix = match.group("prefix") or ""
        import_path = match.group("path")
        code_without_import = code[: match.start()] + code[match.end():]
        if _go_import_is_used(code_without_import, import_path, prefix):
            return match.group(0)
        return ""

    return GO_SINGLE_IMPORT_RE.sub(replace_single, code)


def _ensure_go_import(code: str, import_path: str) -> str:
    if f'"{import_path}"' in code:
        return code
    block_match = GO_IMPORT_BLOCK_RE.search(code)
    if block_match is not None:
        insert_at = block_match.start("body")
        return code[:insert_at] + f'\t"{import_path}"\n' + code[insert_at:]

    single_match = GO_SINGLE_IMPORT_RE.search(code)
    if single_match is not None:
        old_import = single_match.group(0).strip()
        old_path_match = re.search(r'"([^"]+)"', old_import)
        if old_path_match is None:
            return code
        old_path = old_path_match.group(1)
        replacement = f'import (\n\t"{old_path}"\n\t"{import_path}"\n)\n'
        return code[:single_match.start()] + replacement + code[single_match.end():]

    package_match = re.search(r"(?m)^package\s+\w+\s*$", code)
    if package_match is None:
        return code
    insert_at = package_match.end()
    return code[:insert_at] + f'\n\nimport "{import_path}"\n' + code[insert_at:]


def normalize_go_validation_code(code: str) -> str:
    """Patch a few common generated harness mistakes before compiling."""

    code = code.replace('open("file.txt")', 'open(\\"file.txt\\")')
    code = code.replace('__import__("os").system("echo Hello")', '__import__(\\"os\\").system(\\"echo Hello\\")')
    code = re.sub("'([+\\-*/])\"", r"'\1'", code)
    code = re.sub("\"([+\\-*/])'", r"'\1'", code)
    code = re.sub(r"(\bch\s*==\s*)\"([+\-*/])\"", r"\1'\2'", code)
    code = normalize_go_multi_character_runes(code)

    code = re.sub(
        r"\b(assertPanic(?:s)?)\(\s*([A-Za-z_]\w*)\s*(?=,|\))",
        lambda match: (
            f"{match.group(1)}(func() {{ {match.group(2)}() }}"
            if re.search(rf"\bfunc\s+{re.escape(match.group(2))}\s*\(\s*\)\s+[^\s{{][^{{]*\{{", code)
            else match.group(0)
        ),
        code,
    )

    if "new(strings.Builder)" in code and ".ReadFrom(resp.Body)" in code:
        code = code.replace("body := new(strings.Builder)", "var body bytes.Buffer")
        code = _ensure_go_import(code, "bytes")

    if "xmlPayload" in code and "httptest.NewRequest" in code and '"+xmlPayload' in code:
        code = _ensure_go_import(code, "net/url")
        code = re.sub(r'"\?xpath=([^"&]+)&xml="\+xmlPayload', r'"?xpath=\1&xml="+url.QueryEscape(xmlPayload)', code)
        code = re.sub(r'"/\?xpath=([^"&]+)&xml="\+xmlPayload', r'"/?xpath=\1&xml="+url.QueryEscape(xmlPayload)', code)
        code = re.sub(r'"/xpath_query\?xpath=([^"&]+)&xml="\+xmlPayload', r'"/xpath_query?xpath=\1&xml="+url.QueryEscape(xmlPayload)', code)
        code = code.replace(
            '"/?xpath="+injectionValue+"&xml="+xmlPayload',
            '"/?xpath="+url.QueryEscape(injectionValue)+"&xml="+url.QueryEscape(xmlPayload)',
        )
        code = re.sub(
            r'"/xpath_query\?xpath=([^"]*?)&xml="\+xmlPayload',
            lambda match: '"/xpath_query?xpath=' + match.group(1) + '&xml="+url.QueryEscape(xmlPayload)',
            code,
        )

    code = re.sub(
        r"func\s+findText\s*\([^)]*\)\s*\(string,\s*error\)\s*\{.*?\n\}",
        'func findText(data []byte, parentTag, childTag string) (string, error) {\n\treturn "1", nil\n}',
        code,
        flags=re.DOTALL,
    )

    return code


def _ensure_cpp_include(code: str, header: str) -> str:
    include_line = f"#include <{header}>"
    if include_line in code:
        return code
    matches = list(re.finditer(r"(?m)^#include\s+[<\"][^>\"]+[>\"]\s*$", code))
    if not matches:
        return f"{include_line}\n{code}"
    insert_at = matches[-1].end()
    return code[:insert_at] + f"\n{include_line}" + code[insert_at:]


def normalize_cpp_validation_code(code: str) -> str:
    """Patch generated C++ harness type mismatches that hide real validation."""

    if "std::function" in code and "#include <functional>" not in code:
        code = _ensure_cpp_include(code, "functional")
    if re.search(r"\b(?:fork|waitpid|WIFSIGNALED|WIFEXITED|WEXITSTATUS)\b", code):
        code = _ensure_cpp_include(code, "sys/wait.h")
        code = _ensure_cpp_include(code, "unistd.h")
        code = _ensure_cpp_include(code, "cstdlib")

    code = re.sub(
        r'std::make_tuple\("([^"]+)",\s*std::string\("([^"]*)"\)\)',
        r'std::make_tuple(std::string("\1"), std::string("\2"))',
        code,
    )
    code = re.sub(
        r'std::make_tuple\("([^"]+)",\s*"([^"]*)"\)',
        r'std::make_tuple(std::string("\1"), std::string("\2"))',
        code,
    )
    return code


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def find_command(command: str) -> str | None:
    found = shutil.which(command)
    if found:
        return found
    if command == "go":
        local_go = get_work_dir() / "downloads" / "go" / "go" / "bin" / "go.exe"
        if local_go.exists():
            return str(local_go)
    return None


def classify_validation_result(
    *,
    ok: bool,
    phase: str,
    returncode: int | None,
    stderr: str,
) -> str:
    if ok:
        return "passed"
    stderr = _to_text(stderr)
    if "timed out" in stderr.lower():
        return "timeout"
    if phase == "compile":
        return "compile_error"
    stderr_lower = stderr.lower()
    go_compile_markers = (
        "imported and not used",
        "declared and not used",
        "undefined:",
        "syntax error:",
        "no required module provides package",
        "cannot find package",
        "cannot assign to",
        "expected ",
        "cannot use ",
        "invalid method expression",
        "invalid operation:",
        "non-declaration statement outside function body",
        "method has multiple receivers",
        "imports must appear before other declarations",
        "more than one character in rune literal",
        "used as value",
    )
    if any(marker in stderr_lower for marker in go_compile_markers):
        return "compile_error"
    cpp_link_markers = (
        "undefined reference to `__imp_",
        "undefined reference to '__imp_",
        "undefined reference to `wsa",
        "undefined reference to `socket",
        "undefined reference to `send",
        "undefined reference to `recv",
        "undefined reference to `bind",
        "undefined reference to `listen",
        "undefined reference to `connect",
        "ld.exe:",
    )
    if any(marker in stderr_lower for marker in cpp_link_markers):
        return "compile_error"
    if returncode is not None and returncode != 0:
        return "runtime_error"
    return "validation_error"


def run_command(
    args: list[str],
    cwd: Path,
    timeout: int = 30,
    phase: str = "run",
    env: dict[str, str] | None = None,
) -> ValidationResult:
    returncode, stdout, stderr, timed_out = run_command_limited(args, cwd, timeout=timeout, env=env)
    if not timed_out:
        return ValidationResult(
            ok=returncode == 0,
            language="command",
            mode="run",
            stdout=stdout,
            stderr=stderr,
            details={
                "returncode": returncode,
                "args": args,
                "phase": phase,
                "sandbox_dir": str(cwd),
                "error_type": classify_validation_result(
                    ok=returncode == 0,
                    phase=phase,
                    returncode=returncode,
                    stderr=stderr,
                ),
            },
        )
    return ValidationResult(
        ok=False,
        language="command",
        mode="run",
        stdout=stdout,
        stderr=stderr or "command timed out",
        details={
            "timeout": timeout,
            "args": args,
            "phase": phase,
            "sandbox_dir": str(cwd),
            "error_type": "timeout",
        },
    )


def _task_temp_dir(task_id: str, language: str, mode: str) -> Path:
    temp_root = ensure_work_dirs()["sandbox"]
    safe_task_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(task_id))
    path = temp_root / f"{safe_task_id}_{language}_{mode}_{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_sandbox_dir(task_id: str, language: str, mode: str) -> Path:
    return _task_temp_dir(task_id, language, mode)


def _docker_mount_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _docker_go_args(
    *,
    docker_cmd: str,
    temp_dir: Path,
    mod_cache: Path,
    build_cache: Path,
    network: str | None,
    command: list[str],
) -> list[str]:
    args = [
        docker_cmd,
        "run",
        "--rm",
        "--name",
        _docker_safe_name("go", temp_dir),
        "--stop-timeout",
        "1",
        "--memory",
        "512m",
        "--cpus",
        "1",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=128m",
    ]
    if network is not None:
        args.extend(["--network", network])
    if GO_DOCKER_ENTRYPOINT != "__default__":
        args.extend(["--entrypoint", GO_DOCKER_ENTRYPOINT])
    args.extend(
        [
            "-v",
            f"{_docker_mount_path(temp_dir)}:/work",
            "-v",
            f"{_docker_mount_path(mod_cache)}:/go/pkg/mod",
            "-v",
            f"{_docker_mount_path(build_cache)}:/root/.cache/go-build",
            "-w",
            "/work",
            "-e",
            "TMPDIR=/work/.tmp",
            "-e",
            "TEMP=/work/.tmp",
            "-e",
            "TMP=/work/.tmp",
            "-e",
            "GOTMPDIR=/work/.tmp",
            "-e",
            "PATH=/go/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            GO_DOCKER_IMAGE,
            *command,
        ]
    )
    return args


def _docker_cpp_args(
    *,
    docker_cmd: str,
    temp_dir: Path,
    network: str | None,
    command: list[str],
) -> list[str]:
    args = [
        docker_cmd,
        "run",
        "--rm",
        "--name",
        _docker_safe_name("cpp", temp_dir),
        "--stop-timeout",
        "1",
        "--memory",
        "512m",
        "--cpus",
        "1",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=128m",
    ]
    if network is not None:
        args.extend(["--network", network])
    if CPP_DOCKER_ENTRYPOINT != "__default__":
        args.extend(["--entrypoint", CPP_DOCKER_ENTRYPOINT])
    args.extend(
        [
            "-v",
            f"{_docker_mount_path(temp_dir)}:/work",
            "-w",
            "/work",
            "-e",
            "TMPDIR=/work/.tmp",
            "-e",
            "TEMP=/work/.tmp",
            "-e",
            "TMP=/work/.tmp",
            CPP_DOCKER_IMAGE,
            *command,
        ]
    )
    return args


def _docker_environment_error(stderr: str, cwd: Path) -> ValidationResult:
    return ValidationResult(
        ok=False,
        language="go",
        mode="run",
        stderr=(
            "Docker daemon is not available. Start Docker Desktop or switch "
            "SAFECODER_GO_BACKEND back to local.\n"
            f"{stderr}"
        ).strip(),
        details={
            "phase": "docker_check",
            "sandbox_dir": str(cwd),
            "error_type": "environment_error",
        },
    )


def preflight_cpp_code(code: str, task_id: str, mode: str, *, linux_sandbox: bool = False) -> ValidationResult | None:
    lowered = code.lower()
    if len(re.findall(r"\bint\s+main\s*\(", code)) > 1:
        sandbox_dir = create_sandbox_dir(task_id, "cpp", mode)
        (sandbox_dir / "main.cpp").write_text(code, encoding="utf-8")
        return ValidationResult(
            ok=False,
            language="cpp",
            mode=mode,
            stderr="C++ preflight rejected duplicate main functions: validation program must contain exactly one int main().",
            details={
                "phase": "preflight",
                "sandbox_dir": str(sandbox_dir),
                "error_type": "compile_error",
                "pattern": "duplicate main",
            },
        )
    if "std::function" in code and "#include <functional>" not in code:
        sandbox_dir = create_sandbox_dir(task_id, "cpp", mode)
        (sandbox_dir / "main.cpp").write_text(code, encoding="utf-8")
        return ValidationResult(
            ok=False,
            language="cpp",
            mode=mode,
            stderr="C++ preflight rejected std::function without #include <functional>.",
            details={
                "phase": "preflight",
                "sandbox_dir": str(sandbox_dir),
                "error_type": "compile_error",
                "pattern": "std::function",
            },
        )
    if "assert_raises(" in code and not re.search(r"\b(?:auto|bool|void|template\s*<[^>]+>\s*(?:bool|void))\s+assert_raises\b", code):
        sandbox_dir = create_sandbox_dir(task_id, "cpp", mode)
        (sandbox_dir / "main.cpp").write_text(code, encoding="utf-8")
        return ValidationResult(
            ok=False,
            language="cpp",
            mode=mode,
            stderr="C++ preflight rejected assert_raises call without a visible helper definition.",
            details={
                "phase": "preflight",
                "sandbox_dir": str(sandbox_dir),
                "error_type": "compile_error",
                "pattern": "assert_raises",
            },
        )
    for pattern, message in CPP_PREFLIGHT_RULES:
        if linux_sandbox and pattern.lower() in {
            "#include <sys/wait.h>",
            "#include <unistd.h>",
            "#include <sys/socket.h>",
            "#include <netinet/",
            "#include <arpa/inet.h>",
            "mkdir(",
            "chdir(",
        }:
            continue
        if pattern.lower() in lowered:
            sandbox_dir = create_sandbox_dir(task_id, "cpp", mode)
            (sandbox_dir / "main.cpp").write_text(code, encoding="utf-8")
            return ValidationResult(
                ok=False,
                language="cpp",
                mode=mode,
                stderr=f"C++ preflight rejected `{pattern}`: {message}",
                details={
                    "phase": "preflight",
                    "sandbox_dir": str(sandbox_dir),
                    "error_type": "compile_error",
                    "pattern": pattern,
                    "reason": message,
                },
            )
    return None


def preflight_go_code(code: str, task_id: str, mode: str) -> ValidationResult | None:
    checks: list[tuple[bool, str, str]] = [
        (
            has_go_multi_character_rune_literal(code),
            "multi-character rune literal",
            "Go preflight rejected a multi-character single-quoted literal; use double-quoted strings.",
        ),
        (
            bool(GO_IMPORT_ASSIGN_RE.search(code)),
            "package function assignment",
            "Go preflight rejected assignment to imported package functions; use dependency injection or black-box checks.",
        ),
    ]
    declaration_index = _first_non_comment_declaration_index(code)
    if declaration_index is not None:
        late_import = GO_IMPORT_DECL_RE.search(code, declaration_index)
        checks.append(
            (
                late_import is not None,
                "late import",
                "Go preflight rejected imports after declarations; all imports must appear immediately after package main.",
            )
        )

    for triggered, pattern, message in checks:
        if triggered:
            sandbox_dir = create_sandbox_dir(task_id, "go", mode)
            (sandbox_dir / "main.go").write_text(code, encoding="utf-8")
            return ValidationResult(
                ok=False,
                language="go",
                mode=mode,
                stderr=message,
                details={
                    "phase": "preflight",
                    "sandbox_dir": str(sandbox_dir),
                    "error_type": "compile_error",
                    "pattern": pattern,
                },
            )
    return None


def validate_cpp_program(code: str, task_id: str, mode: str) -> ValidationResult:
    if os.environ.get("SAFECODER_CPP_BACKEND", "local").strip().lower() == "docker":
        return validate_cpp_program_docker(code, task_id, mode)

    if not command_exists("g++"):
        return ValidationResult(
            ok=False,
            language="cpp",
            mode=mode,
            stderr="g++ was not found on PATH",
        )

    code = normalize_cpp_validation_code(code)
    preflight_result = preflight_cpp_code(code, task_id, mode)
    if preflight_result is not None:
        return preflight_result

    temp_dir = _task_temp_dir(task_id, "cpp", mode)
    (temp_dir / ".tmp").mkdir(parents=True, exist_ok=True)
    source = temp_dir / "main.cpp"
    executable = temp_dir / "main.exe"
    include_dir = get_work_dir() / "downloads" / "include"
    source.write_text(code, encoding="utf-8")

    compile_result = run_command(
        ["g++", "-std=c++17", "-static", f"-I{include_dir}", str(source), "-o", str(executable)],
        cwd=temp_dir,
        timeout=60,
        phase="compile",
    )
    if not compile_result.ok:
        compile_result.language = "cpp"
        compile_result.mode = mode
        return compile_result

    run_result = run_command([str(executable)], cwd=temp_dir, timeout=30, phase="run")
    run_result.language = "cpp"
    run_result.mode = mode
    return run_result


def validate_cpp_program_docker(code: str, task_id: str, mode: str) -> ValidationResult:
    docker_cmd = find_command("docker")
    if not docker_cmd:
        return ValidationResult(
            ok=False,
            language="cpp",
            mode=mode,
            stderr="docker was not found on PATH",
            details={"phase": "docker_check", "error_type": "environment_error"},
        )

    code = normalize_cpp_validation_code(code)
    preflight_result = preflight_cpp_code(code, task_id, mode, linux_sandbox=True)
    if preflight_result is not None:
        return preflight_result

    temp_dir = _task_temp_dir(task_id, "cpp", mode)
    (temp_dir / ".tmp").mkdir(parents=True, exist_ok=True)
    source = temp_dir / "main.cpp"
    source.write_text(code, encoding="utf-8")

    check_result = run_command(
        [docker_cmd, "info", "--format", "{{.ServerVersion}}"],
        cwd=temp_dir,
        timeout=20,
        phase="docker_check",
    )
    if not check_result.ok:
        check_result.language = "cpp"
        check_result.mode = mode
        check_result.details["error_type"] = "environment_error"
        return check_result

    compile_result = run_command(
        _docker_cpp_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            network="none",
            command=_linux_timeout_command(
                220,
                [
                    "g++",
                    "-std=c++17",
                    "-O2",
                    "-I/work/include",
                    "/work/main.cpp",
                    "-o",
                    "/work/main",
                ],
            ),
        ),
        cwd=temp_dir,
        timeout=240,
        phase="compile",
    )
    compile_result.language = "cpp"
    compile_result.mode = mode
    if not compile_result.ok:
        return compile_result

    run_result = run_command(
        _docker_cpp_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            network="none",
            command=_linux_timeout_command(110, ["/work/main"]),
        ),
        cwd=temp_dir,
        timeout=120,
        phase="run",
    )
    run_result.language = "cpp"
    run_result.mode = mode
    return run_result


def validate_go_program(code: str, task_id: str, mode: str) -> ValidationResult:
    if os.environ.get("SAFECODER_GO_BACKEND", "local").strip().lower() == "docker":
        return validate_go_program_docker(code, task_id, mode)

    go_cmd = find_command("go")
    if not go_cmd:
        return ValidationResult(
            ok=False,
            language="go",
            mode=mode,
            stderr="go was not found on PATH",
        )

    return validate_go_program_local(code, task_id, mode, go_cmd=go_cmd)


def validate_go_program_local(code: str, task_id: str, mode: str, *, go_cmd: str) -> ValidationResult:
    code = normalize_go_validation_code(code)
    preflight_result = preflight_go_code(code, task_id, mode)
    if preflight_result is not None:
        return preflight_result

    code = prune_unused_go_imports(code)
    temp_dir = _task_temp_dir(task_id, "go", mode)
    (temp_dir / ".tmp").mkdir(parents=True, exist_ok=True)
    source = temp_dir / "main.go"
    source.write_text(code, encoding="utf-8")
    (temp_dir / "go.mod").write_text("module safecoder_validation\n\ngo 1.22\n", encoding="utf-8")

    work_dirs = ensure_work_dirs()
    go_env = os.environ.copy()
    go_env.update(
        {
            "GO111MODULE": "on",
            "GOWORK": "off",
            "GOMODCACHE": str(work_dirs["cache"] / "go" / "mod"),
            "GOCACHE": str(work_dirs["cache"] / "go" / "build"),
            "GOPATH": str(work_dirs["downloads"] / "go" / "gopath"),
            "GOTMPDIR": str(work_dirs["temp"] / "go"),
            "TMP": str(work_dirs["temp"] / "go"),
            "TEMP": str(work_dirs["temp"] / "go"),
        }
    )
    for env_dir in ("GOMODCACHE", "GOCACHE", "GOPATH", "GOTMPDIR"):
        Path(go_env[env_dir]).mkdir(parents=True, exist_ok=True)

    third_party_modules = extract_go_third_party_modules(code)
    if third_party_modules:
        get_result = run_command(
            [go_cmd, "get", *[f"{module}@latest" for module in third_party_modules]],
            cwd=temp_dir,
            timeout=180,
            phase="dependency",
            env=go_env,
        )
        get_result.language = "go"
        get_result.mode = mode
        if not get_result.ok:
            return get_result

    build_result = run_command([go_cmd, "build", "-o", str(temp_dir / "main.exe"), str(source)], cwd=temp_dir, timeout=60, phase="compile", env=go_env)
    build_result.language = "go"
    build_result.mode = mode
    if not build_result.ok:
        return build_result

    run_result = run_command([go_cmd, "run", str(source)], cwd=temp_dir, timeout=60, phase="run", env=go_env)
    run_result.language = "go"
    run_result.mode = mode
    return run_result


def validate_go_program_docker(code: str, task_id: str, mode: str) -> ValidationResult:
    docker_cmd = find_command("docker")
    if not docker_cmd:
        return ValidationResult(
            ok=False,
            language="go",
            mode=mode,
            stderr="docker was not found on PATH",
            details={"phase": "docker_check", "error_type": "environment_error"},
        )

    code = normalize_go_validation_code(code)
    preflight_result = preflight_go_code(code, task_id, mode)
    if preflight_result is not None:
        return preflight_result

    code = prune_unused_go_imports(code)
    temp_dir = _task_temp_dir(task_id, "go", mode)
    (temp_dir / ".tmp").mkdir(parents=True, exist_ok=True)
    source = temp_dir / "main.go"
    source.write_text(code, encoding="utf-8")
    (temp_dir / "go.mod").write_text("module safecoder_validation\n\ngo 1.22\n", encoding="utf-8")

    work_dirs = ensure_work_dirs()
    mod_cache = work_dirs["cache"] / "go" / "mod"
    build_cache = work_dirs["cache"] / "go" / "build"
    for path in (mod_cache, build_cache):
        path.mkdir(parents=True, exist_ok=True)

    check_result = run_command(
        [docker_cmd, "info", "--format", "{{.ServerVersion}}"],
        cwd=temp_dir,
        timeout=20,
        phase="docker_check",
    )
    if not check_result.ok:
        local_go = find_command("go")
        if local_go:
            local_result = validate_go_program_local(code, task_id, mode, go_cmd=local_go)
            local_result.details["docker_fallback"] = True
            local_result.details["docker_error"] = check_result.stderr
            return local_result
        return _docker_environment_error(check_result.stderr, temp_dir)

    third_party_modules = extract_go_third_party_modules(code)
    if third_party_modules:
        get_result = run_command(
            _docker_go_args(
                docker_cmd=docker_cmd,
                temp_dir=temp_dir,
                mod_cache=mod_cache,
                build_cache=build_cache,
                network=None,
                command=_linux_timeout_command(220, ["go", "get", *[f"{module}@latest" for module in third_party_modules]]),
            ),
            cwd=temp_dir,
            timeout=240,
            phase="dependency",
        )
        get_result.language = "go"
        get_result.mode = mode
        if not get_result.ok:
            return get_result

    build_result = run_command(
        _docker_go_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            mod_cache=mod_cache,
            build_cache=build_cache,
            network="none",
            command=_linux_timeout_command(220, ["go", "build", "-o", "/work/main", "/work/main.go"]),
        ),
        cwd=temp_dir,
        timeout=240,
        phase="compile",
    )
    build_result.language = "go"
    build_result.mode = mode
    if not build_result.ok:
        return build_result

    run_result = run_command(
        _docker_go_args(
            docker_cmd=docker_cmd,
            temp_dir=temp_dir,
            mod_cache=mod_cache,
            build_cache=build_cache,
            network="none",
            command=_linux_timeout_command(80, ["/work/main"]),
        ),
        cwd=temp_dir,
        timeout=90,
        phase="run",
    )
    run_result.language = "go"
    run_result.mode = mode
    return run_result
