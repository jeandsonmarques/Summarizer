from __future__ import annotations

import zipfile
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_release_files_have_minimum_package_surface():
    repo_root = _repo_root()
    plugin_root = repo_root / "plugin" / "Summarizer"

    required_files = [
        plugin_root / "__init__.py",
        plugin_root / "metadata.txt",
        plugin_root / "README.md",
        plugin_root / "resources" / "icon.svg",
    ]
    for path in required_files:
        assert path.exists(), f"Missing required release file: {path}"


def test_release_zip_if_present_contains_expected_files():
    repo_root = _repo_root()
    zip_candidates = list(repo_root.rglob("*release*.zip"))
    if not zip_candidates:
        return

    required_members = {
        "Summarizer/__init__.py",
        "Summarizer/metadata.txt",
        "Summarizer/README.md",
    }

    for zip_path in zip_candidates:
        with zipfile.ZipFile(zip_path) as archive:
            members = set(archive.namelist())
            assert required_members <= members
            assert all(not name.endswith((".pyc", ".pyo")) for name in members)

