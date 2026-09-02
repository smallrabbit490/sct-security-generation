"""The four direct prompting baselines; no Agent workflow is hidden here."""

PROMPTS = {
    "greedy": "Generate the requested callable directly. Output only code.",
    "greedy_secure": "Generate the requested callable directly. Apply secure coding practices and output only code.",
    "cot": "Briefly reason about the implementation, then output only the final callable code.",
    "cot_secure": "Briefly reason about functionality and security, then output only the final secure callable code.",
}


def build_prompt(method: str, language: str, problem: str, entry_point: str) -> str:
    if method not in PROMPTS:
        raise ValueError(f"unknown direct prompt method: {method}")
    return (
        f"Target language: {language}\n"
        f"Required entry point: {entry_point}\n"
        f"Task:\n{problem}\n\n"
        f"Instruction: {PROMPTS[method]}"
    )
