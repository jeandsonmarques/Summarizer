from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_include_nulls_switch_defaults_on_for_loaded_summary_data():
    widget_source = (ROOT / "plugin" / "Summarizer" / "pivot_table_widget.py").read_text(
        encoding="utf-8"
    )

    assert "self.include_nulls_check.setChecked(True)" in widget_source
    assert "_pivot_restore_saved_configuration_for_metadata(self, metadata)" in widget_source
    assert (
        "_pivot_restore_saved_configuration_for_metadata(self, metadata)\n"
        "            self.include_nulls_check.setChecked(True)"
    ) in widget_source
    assert "self.include_nulls_check.toggled.connect(self._maybe_refresh)" in widget_source
