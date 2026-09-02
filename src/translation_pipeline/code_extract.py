from __future__ import annotations

import re


_FENCE_RE = re.compile(r"```(?P<lang>[A-Za-z0-9_+#.-]*)\s*\n(?P<code>.*?)```", re.DOTALL)


def _language_aliases(language: str) -> set[str]:
    normalized = language.lower().strip()
    if normalized in {"cpp", "c++", "gnu c++17"}:
        return {"cpp", "c++", "cc", "cxx"}
    if normalized in {"go", "golang"}:
        return {"go", "golang"}
    return {normalized}


def extract_code_block(response: str | None, language: str) -> str:
    if not isinstance(response, str) or not response.strip():
        raise ValueError("Model response was empty; cannot extract translated code.")

    matches = list(_FENCE_RE.finditer(response))
    if not matches:
        return response.strip()

    aliases = _language_aliases(language)
    for match in matches:
        fence_lang = match.group("lang").lower().strip()
        if fence_lang in aliases:
            return match.group("code").strip()

    return matches[0].group("code").strip()
