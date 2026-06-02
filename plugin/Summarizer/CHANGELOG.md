# Changelog

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
