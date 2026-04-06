# Repository Layout

This repository uses a split layout so the QGIS plugin remains publishable without bundling backend infrastructure.

## Main directories

- `plugin/power_bi_summarizer/`: QGIS plugin source to be packaged and zipped
- `cloud-api/`: backend API and deployment assets
- `docs/`: repository notes, publishing guidance and support files
- `scripts/`: local automation such as plugin packaging
- `tests/`: smoke tests and development-only validation

## Packaging boundary

Only the contents of `plugin/power_bi_summarizer/` belong in the final QGIS plugin ZIP.

The following must stay out of the ZIP:

- `cloud-api/`
- `.github/`
- `docs/`
- `scripts/`
- `tests/`
- `.git/`
- caches, logs and local runtime files

## Stable package name

- Visible plugin name: `Power BI Summarizer`
- Plugin folder/package name: `power_bi_summarizer`

The folder name is ASCII-only and stable for future publication in the official QGIS plugin repository.
