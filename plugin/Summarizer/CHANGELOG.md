# Changelog

## [0.5.0-beta.2] - 2026-05-04

- Hardened credential handling to avoid saving passwords when `authcfg` is available.
- Replaced silent exception swallowing with safe logging in the main runtime paths.
- Added a minimal test base with smoke checks, utility tests, and release validation.
- Standardized release ZIP generation so the archive root is a clean `Summarizer/` folder.
- Began incremental refactors for charts, pivot, reports, and model tabs without changing public behavior.

## [0.1.0] - 2026-04-24

- Finalized the public release branding as `Summarizer`.
- Standardized the distributable package so the ZIP root contains only `Summarizer/`.
- Clarified optional AI-assisted dependencies in the public documentation.
- Kept the plugin logic and QGIS runtime flow unchanged for release publication.
