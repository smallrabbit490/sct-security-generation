from __future__ import annotations

import os
import re
import shutil
import threading
import uuid
from pathlib import Path

from .models import ValidationResult, truncate_text
from .paths import ensure_work_dirs, get_work_dir
from .persistent_container import (
    ContainerSpec,
    implicit_pool,
    run_limited_command,
)


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
MAX_VALIDATOR_OUTPUT_CHARS = int(os.environ.get("SAFECODER_MAX_VALIDATOR_OUTPUT_CHARS", "2000"))
# 常驻容器里所有任务共用的挂载根。宿主 <translation_work>/... 对应 /work/...。
CONTAINER_WORK_ROOT = "/work"
# 不在挂载根内的任务目录 → 暂存目录的映射（见 stage_task_dir）。
_STAGED_DIRS: dict[Path, Path] = {}
_STAGE_LOCK = threading.Lock()
# 已废弃：``SAFECODER_CPP_DOCKER_ENTRYPOINT`` / ``SAFECODER_GO_DOCKER_ENTRYPOINT``
# 在常驻容器方案下不再有意义——容器必须以 ``--entrypoint tail`` 保活，
# 否则 porta-bench / safecoder 镜像自带的 docker_runner ENTRYPOINT 会立刻接管进程
# 并让容器退出。这两个变量原本也没有任何脚本设置过。


def _to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _truncate_output(value: object, limit: int = MAX_VALIDATOR_OUTPUT_CHARS) -> str:
    return truncate_text(value, limit)


def run_command_limited(
    args: list[str],
    cwd: Path,
    timeout: int = 30,
    env: dict[str, str] | None = None,
    output_limit: int = MAX_VALIDATOR_OUTPUT_CHARS,
) -> tuple[int | None, str, str, bool]:
    """运行外部命令，返回 ``(returncode, stdout, stderr, timed_out)``。

    实现已统一到 :mod:`translation_pipeline.persistent_container`，本函数只做转发，
    避免两份几乎相同的管道读取逻辑各自漂移（旧实现在循环里反复
    ``sum(len(item) for item in chunks)``，块数一多就是 O(n²)）。
    """
    return run_limited_command(args, cwd, timeout=timeout, env=env, output_limit=output_limit)


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


def _mount_root() -> Path:
    """常驻容器的宿主挂载根，挂载为容器内 ``/work``。

    为什么是 ``translation_work/`` 而不是 ``sandbox/``：任务目录不一定落在
    ``sandbox/`` 下。例如 ``run_full_docker_revalidation`` 会把 harness 复制到
    调用方指定的 ``output_root``（CLI 可指向 ``translation_work/`` 下任意位置）。
    只挂 ``sandbox/`` 时，容器内 ``/work/<任务名>`` 根本不存在，
    ``docker exec -w`` 会直接报 ``chdir to cwd ... no such file or directory``。

    用 ``translation_work/`` 作根后，任务目录按**相对路径**映射：
    ``translation_work/sandbox/<t>`` → ``/work/sandbox/<t>``，
    ``translation_work/temp/<run>/harnesses/...`` → ``/work/temp/<run>/harnesses/...``。

    安全边界：**只挂 ``translation_work/``**。绝不挂仓库根目录——``local_secrets/``
    与 ``.env.local`` 里有 API key，挂进去等于把密钥交给容器内运行的候选代码。

    不在此根下的目录由 :func:`stage_task_dir` 复制进 ``sandbox/_stage/`` 兜底。
    """
    return get_work_dir()


def stage_task_dir(temp_dir: Path) -> Path:
    """确保任务目录位于挂载根内；不在根内则复制到 ``sandbox/_stage/`` 并复用。

    同一源目录多次调用（编译阶段、运行阶段）返回同一个暂存目录，
    因此编译产物能在阶段之间保留，不会被重复复制覆盖。
    """
    root = _mount_root().resolve()
    resolved = temp_dir.resolve()
    try:
        resolved.relative_to(root)
        return temp_dir
    except ValueError:
        pass
    with _STAGE_LOCK:
        cached = _STAGED_DIRS.get(resolved)
        if cached is not None and cached.exists():
            return cached
        digest = uuid.uuid5(uuid.NAMESPACE_URL, str(resolved)).hex[:12]
        safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in resolved.name)
        staged = root / "sandbox" / "_stage" / f"{safe_name}_{digest}"
        shutil.copytree(resolved, staged, dirs_exist_ok=True)
        _STAGED_DIRS[resolved] = staged
        return staged


def _container_task_dir(temp_dir: Path) -> str:
    """宿主任务目录 → 容器内工作目录；不在挂载根内时自动暂存。

    调用方在构造命令前调用本函数，:func:`run_docker_task` 内部也会调用；
    由于 :func:`stage_task_dir` 带缓存且幂等，两处拿到的是同一个暂存目录，
    编译产物因此在编译阶段与运行阶段之间保留。
    """
    staged = stage_task_dir(temp_dir)
    root = _mount_root().resolve()
    relative = staged.resolve().relative_to(root)
    return f"{CONTAINER_WORK_ROOT}/{relative.as_posix()}"


def _docker_task_env(container_dir: str) -> dict[str, str]:
    """任务级临时目录指向该任务自己的挂载目录，与旧行为保持一致。

    为什么不改指容器内 tmpfs ``/tmp``：``g++``/``go`` 编译大源文件时中间文件可能
    超过 ``--tmpfs`` 的 128m 上限，会把"编译成功"变成"环境失败"，属于行为回归。
    指回任务目录后临时文件仍在宿主盘，但随任务目录一起清理，不写容器可写层。
    这些变量必须按任务传入（容器级 ENV 是固定的，无法区分任务目录）。
    """
    tmp = f"{container_dir}/.tmp"
    return {"TMPDIR": tmp, "TEMP": tmp, "TMP": tmp, "GOTMPDIR": tmp}


def cpp_docker_spec(network: str | None = "none") -> ContainerSpec:
    """CodeSecEval C++ harness 的容器规格。

    ``network`` 必须按阶段区分：编译固定 ``"none"``；运行阶段由调用方决定，
    因为部分 harness 需要回环网络才能验证网络相关缺陷
    （见 ``run_full_docker_revalidation._cpp_run_network_for_source``）。
    不同 ``network`` 会得到不同的池，互不干扰。
    """
    return ContainerSpec(
        image=CPP_DOCKER_IMAGE,
        mounts=((_docker_mount_path(_mount_root()), CONTAINER_WORK_ROOT),),
        network=network,
    )


def go_docker_spec(
    network: str | None = "none",
    *,
    cache_root: Path | None = None,
) -> ContainerSpec:
    """CodeSecEval Go harness 的容器规格。

    模块缓存与构建缓存挂到宿主 ``translation_work/cache/go/``：镜像
    ``golang:1.22`` 只设 ``GOPATH=/go``，不设 ``GOCACHE``/``GOMODCACHE``，
    因此默认路径 ``/go/pkg/mod`` 与 ``/root/.cache/go-build`` 正好落在挂载点上，
    缓存可以跨任务复用。``docker/go-validator/Dockerfile`` 里那组
    ``GOCACHE=/work/.cache/...`` 属于**未被使用**的旧镜像定义
    （``SAFECODER_GO_DOCKER_IMAGE`` 实际指向 ``golang:1.22``），不影响当前路径。
    """
    root = cache_root or (get_work_dir() / "cache" / "go")
    mod_cache = root / "mod"
    build_cache = root / "build"
    for path in (mod_cache, build_cache):
        path.mkdir(parents=True, exist_ok=True)
    return ContainerSpec(
        image=GO_DOCKER_IMAGE,
        mounts=(
            (_docker_mount_path(_mount_root()), CONTAINER_WORK_ROOT),
            (_docker_mount_path(mod_cache), "/go/pkg/mod"),
            (_docker_mount_path(build_cache), "/root/.cache/go-build"),
        ),
        env=(
            ("GOPROXY", "https://goproxy.cn,direct"),
            ("GO111MODULE", "on"),
            ("GOWORK", "off"),
        ),
        network=network,
    )


def docker_environment_error(
    stderr: str,
    cwd: Path,
    *,
    language: str = "go",
    mode: str = "run",
    phase: str = "docker_check",
    extra: dict[str, object] | None = None,
) -> ValidationResult:
    """构造 ``environment_error``：环境事故，不得折算成方法失败或方法得分。"""
    details: dict[str, object] = {
        "phase": phase,
        "sandbox_dir": str(cwd),
        "error_type": "environment_error",
    }
    if extra:
        details.update(extra)
    return ValidationResult(
        ok=False,
        language=language,
        mode=mode,
        stderr=(
            "Docker validation environment failed. Start Docker Desktop or switch "
            "SAFECODER_*_BACKEND back to local.\n"
            f"{stderr}"
        ).strip(),
        details=details,
    )


def run_docker_task(
    *,
    spec: ContainerSpec,
    temp_dir: Path,
    command: list[str],
    phase: str,
    language: str,
    mode: str,
    container_timeout: int,
    host_timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> ValidationResult:
    """在常驻容器里执行一条任务级命令，返回与旧 ``run_command`` 兼容的结果。

    与旧实现的区别：不再每个阶段 ``docker run --rm`` 新建容器，而是从容器池里
    借一个常驻容器做 ``docker exec``；容器在整轮评测中复用，只有评测结束才删除。

    超时用两层：``container_timeout`` 交给容器内 ``timeout``（正常路径，Linux
    自己杀干净），``host_timeout`` 是宿主侧兜底（默认比容器内多 30 秒）。

    未测量项：本函数不判断编译/功能/安全语义，只负责"命令跑没跑完"。
    判定仍由各 harness 的 ``returncode`` 与 ``classify_validation_result`` 决定。
    """
    staged_dir = stage_task_dir(temp_dir)
    container_dir = _container_task_dir(staged_dir)
    if host_timeout is None:
        host_timeout = container_timeout + 30
    task_env = _docker_task_env(container_dir)
    if env:
        task_env.update(env)
    try:
        pool = implicit_pool(spec)
        with pool.acquire() as container:
            result = container.exec_argv(
                command,
                workdir=container_dir,
                env=task_env,
                timeout=host_timeout,
                container_timeout=container_timeout,
                cwd=staged_dir,
            )
            # 只在异常信号出现时才做一次 docker inspect，避免给每个任务增加固定开销。
            container_alive = True
            if result.timed_out or result.returncode != 0:
                container_alive = container.is_running()
    except RuntimeError as exc:
        # 池启动失败 / 池耗尽 / 容器重建失败：都属于环境事故。
        return docker_environment_error(str(exc), temp_dir, language=language, mode=mode, phase=phase)

    common_details = {
        "args": result.argv,
        "phase": phase,
        "sandbox_dir": str(staged_dir),
        "source_dir": str(temp_dir),
        "container_dir": container_dir,
        **result.as_details(),
    }
    if not container_alive:
        # 容器在任务执行期间消失（OOM 被杀、daemon 重启、镜像被删）。
        # 必须记成 environment_error：否则环境事故会被当成方法失败，污染得分。
        return docker_environment_error(
            f"container {result.container} stopped during phase '{phase}'",
            temp_dir,
            language=language,
            mode=mode,
            phase=phase,
            extra=common_details,
        )
    if result.timed_out:
        return ValidationResult(
            ok=False,
            language=language,
            mode=mode,
            stdout=result.stdout,
            stderr=result.stderr or "command timed out",
            details={"timeout": container_timeout, "error_type": "timeout", **common_details},
        )
    return ValidationResult(
        ok=result.returncode == 0,
        language=language,
        mode=mode,
        stdout=result.stdout,
        stderr=result.stderr,
        details={
            "returncode": result.returncode,
            "error_type": classify_validation_result(
                ok=result.returncode == 0,
                phase=phase,
                returncode=result.returncode,
                stderr=result.stderr,
            ),
            **common_details,
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
    """用常驻容器验证 C++ harness：编译 + 运行两个阶段。

    与旧实现的差异：两阶段复用同一个常驻容器（``docker exec``），而不是各自
    ``docker run --rm`` 起一个新容器。命令路径从 ``/work/xxx`` 变为
    ``/work/<task_dir>/xxx``，因为宿主沙盒根整体挂载到 ``/work``。
    """
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

    container_dir = _container_task_dir(temp_dir)
    compile_result = run_docker_task(
        spec=cpp_docker_spec("none"),
        temp_dir=temp_dir,
        command=[
            "g++",
            "-std=c++17",
            "-O2",
            "-I/work/include",
            f"{container_dir}/main.cpp",
            "-o",
            f"{container_dir}/main",
        ],
        phase="compile",
        language="cpp",
        mode=mode,
        container_timeout=220,
        host_timeout=240,
    )
    if not compile_result.ok:
        return compile_result

    return run_docker_task(
        spec=cpp_docker_spec("none"),
        temp_dir=temp_dir,
        command=[f"{container_dir}/main"],
        phase="run",
        language="cpp",
        mode=mode,
        container_timeout=110,
        host_timeout=120,
    )


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
        return docker_environment_error(check_result.stderr, temp_dir, language="go", mode=mode)

    container_dir = _container_task_dir(temp_dir)
    third_party_modules = extract_go_third_party_modules(code)
    if third_party_modules:
        # 依赖下载需要网络：用放开网络的池。模块缓存挂载在两套池之间共享，
        # 所以后面的离线构建阶段能直接命中已下载的模块。
        get_result = run_docker_task(
            spec=go_docker_spec(None, cache_root=work_dirs["cache"] / "go"),
            temp_dir=temp_dir,
            command=["go", "get", *[f"{module}@latest" for module in third_party_modules]],
            phase="dependency",
            language="go",
            mode=mode,
            container_timeout=220,
            host_timeout=240,
        )
        if not get_result.ok:
            return get_result

    build_result = run_docker_task(
        spec=go_docker_spec("none", cache_root=work_dirs["cache"] / "go"),
        temp_dir=temp_dir,
        command=["go", "build", "-o", f"{container_dir}/main", f"{container_dir}/main.go"],
        phase="compile",
        language="go",
        mode=mode,
        container_timeout=220,
        host_timeout=240,
    )
    if not build_result.ok:
        return build_result

    return run_docker_task(
        spec=go_docker_spec("none", cache_root=work_dirs["cache"] / "go"),
        temp_dir=temp_dir,
        command=[f"{container_dir}/main"],
        phase="run",
        language="go",
        mode=mode,
        container_timeout=80,
        host_timeout=90,
    )
