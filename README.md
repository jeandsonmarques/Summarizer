# Summarizer

Summarizer is a QGIS plugin that helps turn spatial data into clean, report-ready outputs. It is designed for analysts who need to explore project layers, summarize results, prepare dashboard-style views, and move data into a streamlined reporting workflow without leaving QGIS.

## Highlights

- Summarize layers and tables into compact analytical outputs.
- Build report-friendly views and chart widgets inside QGIS.
- Export structured results for downstream reporting.
- Support local-first workflows with optional cloud integration.
- Keep the plugin focused on practical analysis rather than framework-heavy setup.

## Why this plugin

Many QGIS workflows stop at map exploration. Summarizer extends that process by helping you organize data into formats that are easier to review, share, and reuse in business reporting.

The plugin is built to stay lightweight from the user point of view:

- core workflows run locally in QGIS;
- cloud features are optional;
- the main package remains a QGIS plugin, not a backend application.

## Installation

### From a ZIP package

1. Open `Plugins > Manage and Install Plugins...` in QGIS.
2. Choose `Install from ZIP`.
3. Select a ZIP file whose root contains the `power_bi_summarizer/` folder.

### From this repository

The distributable package should contain only the `power_bi_summarizer/` directory at the root of the archive.

This layout matches the structure expected by QGIS plugin packaging.

## Compatibility

- QGIS 3.34 to 3.99
- Standard QGIS Python environment

The project is not currently positioned as QGIS 4 or Qt6 ready.

## Project structure

- `plugin/power_bi_summarizer/`: distributable QGIS plugin package
- `plugin/power_bi_summarizer/metadata.txt`: plugin metadata consumed by QGIS
- `plugin/power_bi_summarizer/__init__.py`: plugin entry point
- `plugin/power_bi_summarizer/README.md`: technical notes for the package

## What the plugin covers

- layer summaries and analytical views
- dashboard-style charting
- export of structured outputs for reporting
- optional cloud session and browser-assisted workflows
- optional AI-assisted interpretation for report generation

## Dependencies

Core functionality depends on QGIS.

Optional features may use:

- `pandas` for table-oriented processing;
- network access provided by the QGIS runtime;
- external services for cloud or AI-assisted workflows.

## Publishing notes

Before publishing the plugin, confirm that:

- `plugin/power_bi_summarizer/metadata.txt` contains real repository and issue tracker URLs;
- the release ZIP includes only the `power_bi_summarizer/` folder at the top level;
- no caches, build outputs, or temporary files are included in the package;
- the declared version matches the release being published.

## Support

- Repository: https://github.com/jeandsonmarques/PowerBISummarizer
- Issues: https://github.com/jeandsonmarques/PowerBISummarizer/issues
