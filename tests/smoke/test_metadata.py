from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path


def test_metadata_txt_has_required_fields():
    repo_root = Path(__file__).resolve().parents[2]
    metadata_path = repo_root / "plugin" / "Summarizer" / "metadata.txt"
    parser = ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(metadata_path, encoding="utf-8")

    assert parser.has_section("general")
    general = parser["general"]
    assert general.get("name") == "Summarizer"
    assert general.get("version")
    assert general.get("qgisMinimumVersion")
    assert general.get("qgisMaximumVersion")
    assert general.get("repository")

