# Summarizer QGIS Plugin Package

This folder contains the distributable QGIS plugin package used by QGIS.

Summarizer helps users create layer summaries, charts, dashboards, and report-ready analytical outputs from QGIS project data. Main workflows run locally inside QGIS.

For the public project overview, screenshots, installation notes, compatibility table, feedback links, and license details, see the repository [README](../../README.md).

## Package scope

- QGIS plugin entry point.
- Plugin metadata and resources.
- Layer summary, chart, dashboard, model, connection, visualization, and export components.
- Local icons and runtime assets required by the QGIS client.

## Distribution notes

- The package remains experimental while public testing continues.
- Release compatibility and version metadata are defined in `metadata.txt`.
- ZIP archives for QGIS publication must contain the `Summarizer/` folder at the archive root.
- Development-only files, temporary artifacts, cached bytecode, and build outputs should stay out of release archives.
