from __future__ import annotations

import configparser
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = REPO_ROOT / "plugin" / "power_bi_summarizer"
DIST_DIR = REPO_ROOT / "dist"

REQUIRED_FILES = (
    "__init__.py",
    "metadata.txt",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
)

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".git",
    ".github",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

EXCLUDED_FILE_NAMES = {
    ".DS_Store",
    ".env",
    "relatorios_debug.log",
    "relatorios_memory.sqlite3",
    "relatorios_memory.sqlite3-shm",
    "relatorios_memory.sqlite3-wal",
    "Thumbs.db",
    "_tmp_orig.txt",
}

EXCLUDED_SUFFIXES = {
    ".bak",
    ".log",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
    ".tmp",
}


def read_plugin_version(metadata_path: Path) -> str:
    parser = configparser.ConfigParser()
    parser.read(metadata_path, encoding="utf-8")
    return parser.get("general", "version")


def validate_plugin_dir(plugin_dir: Path) -> None:
    missing = [name for name in REQUIRED_FILES if not (plugin_dir / name).exists()]
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Missing required plugin files: {joined}")


def should_include(path: Path) -> bool:
    if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
        return False
    if any(part.startswith(".") for part in path.parts):
        return False
    if path.name in EXCLUDED_FILE_NAMES:
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return True


def build_zip() -> Path:
    validate_plugin_dir(PLUGIN_DIR)

    version = read_plugin_version(PLUGIN_DIR / "metadata.txt")
    zip_name = f"power_bi_summarizer-{version}.zip"
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / zip_name
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PLUGIN_DIR.rglob("*")):
            if path.is_dir() or not should_include(path):
                continue
            relative_path = path.relative_to(PLUGIN_DIR.parent)
            archive.write(path, relative_path.as_posix())

    return zip_path


if __name__ == "__main__":
    print(build_zip())
