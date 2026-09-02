from pathlib import Path


def get_project_root() -> Path:
    # ``src/translation_pipeline`` is two levels below the repository root.
    return Path(__file__).resolve().parents[2]


def get_work_dir() -> Path:
    return get_project_root() / "translation_work"


def ensure_work_dirs() -> dict[str, Path]:
    work_dir = get_work_dir()
    dirs = {
        "work": work_dir,
        "cache": work_dir / "cache",
        "temp": work_dir / "temp",
        "sandbox": work_dir / "sandbox",
        "logs": work_dir / "logs",
        "outputs": work_dir / "outputs",
        "downloads": work_dir / "downloads",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
