# Repository Layout

This repository uses a split layout so the QGIS plugin can be distributed cleanly without bundling backend infrastructure or development-only assets.

## Overview

The user-facing QGIS plugin lives in its own package directory, while backend services, maintenance scripts, documentation, and tests stay outside the final plugin ZIP. This keeps the publication boundary clear and makes future QGIS repository uploads easier to maintain.

## Main directories

| Path | Purpose |
| --- | --- |
| `plugin/power_bi_summarizer/` | Distributable QGIS plugin source and runtime files. This is the folder that becomes the plugin package. |
| `cloud-api/` | Separate backend service and deployment assets used by optional cloud workflows. Not included in the plugin ZIP. |
| `docs/` | Technical and publication-oriented repository documentation. |
| `scripts/` | Local automation for packaging, synchronization, and maintenance. |
| `tests/` | Smoke tests and development-only validation helpers. |

## Plugin packaging boundary

Only the contents of `plugin/power_bi_summarizer/` belong in the final QGIS plugin ZIP.

The final archive should contain the plugin folder with its runtime code, metadata, documentation, resources, and bundled assets required by QGIS.

The following stay out of the ZIP:

- `cloud-api/`
- `docs/`
- `scripts/`
- `tests/`
- `.github/`
- `.git/`
- `dist/`
- caches, logs, temporary files, and local runtime databases

## Stable naming

- Visible plugin name: `Power BI Summarizer`
- Plugin folder and package name: `power_bi_summarizer`

The folder name is ASCII-only and stable for future publication in the official QGIS plugin repository.

## Common workflows

### Build the plugin ZIP

Run from the repository root:

```bash
py -3 scripts/build_plugin_package.py
```

This creates a distributable ZIP in `dist/` containing only the plugin package.

### Sync the current plugin revision to a local QGIS profile

Run from the repository root:

```powershell
.\scripts\sync_qgis_plugin.cmd
```

This copies the current `plugin/power_bi_summarizer/` contents into the local QGIS plugin directory used for manual testing.

### Run smoke tests

Run from the repository root:

```bash
py -3 tests/test_plugin_open_smoke.py
py -3 tests/test_report_view_smoke.py
```

These smoke tests help validate that the plugin package still imports and that key report-view paths remain healthy in the current development environment.
