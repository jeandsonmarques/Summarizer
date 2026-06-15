# Changelog

## 0.5.7

- Added database-backed Model panels discovered from PostgreSQL/PostGIS connections.
- Added `.pbsdash` import into PostgreSQL tables from the Model database menu.
- Restricted Model edit mode for database panels to users with PostgreSQL `UPDATE` permission on the panel table.
- Saved editable database panels directly back to PostgreSQL instead of prompting for a local file.
- Kept compatibility with QGIS 3.34 to 3.99.

## 0.5.6

- First stable QGIS 3.x release.
- Removed experimental plugin status.
- Kept compatibility with QGIS 3.34 to 3.99.
- Kept QGIS 4 compatibility not declared.
- No breaking workflow changes.

## [0.5.5] - 2026-06-03

- Fixed QGIS 3.44 compatibility for the Summarizer Browser provider capabilities return type.
- Kept compatibility with QGIS 3.34+.
- Kept plugin functionality unchanged.

## [0.5.4] - 2026-06-03

- Fixed the final Flake8 E306 informational finding reported by the QGIS Plugin Repository validation.
- Kept plugin functionality unchanged.

## [0.5.3] - 2026-06-02

- Cleaned remaining Flake8 W504 informational findings reported by the QGIS Plugin Repository validation.
- Reworked long boolean expressions using intermediate variables, all(), any(), and fallback helpers to avoid W503/W504 conflicts.
- Kept plugin functionality unchanged.

## [0.5.2] - 2026-06-02

- Cleaned Python code style issues reported by the QGIS Plugin Repository validation.
- Fixed Flake8 W503, W391, E302, and F811 findings where applicable.
- Kept the release focused on local QGIS summaries, charts, dashboards, model, connections, visualizations, and exports.

## [0.5.1] - 2026-06-02

- Fixed the plugin icon displayed by the QGIS Plugin Manager by shipping `icon.png` at the plugin root.
- Improved metadata text for the experimental QGIS repository submission.
- Kept the release focused on local QGIS summaries, charts, dashboards, model, connections, visualizations, and exports.

## [0.5.0] - 2026-06-02

- Prepared the first experimental public release for the QGIS plugin repository.
- Kept the focus on layer summaries, charts, dashboards, model, connections, visualizations, and exports.
- Packaged the release for local QGIS workflows and report-ready analytical outputs.

## [0.5.0-beta.2] - 2026-05-04

- Hardened credential handling to avoid saving passwords when `authcfg` is available.
- Replaced silent exception swallowing with safe logging in the main runtime paths.
- Added a minimal test base with smoke checks, utility tests, and release validation.
- Standardized release ZIP generation so the archive root is a clean `Summarizer/` folder.
- Began incremental refactors for charts, pivot, reports, and model tabs without changing public behavior.

## [0.1.0] - 2026-04-24

- Finalized the public release branding as `Summarizer`.
- Standardized the distributable package so the ZIP root contains only `Summarizer/`.
- Kept the plugin logic and QGIS runtime flow unchanged for release publication.
