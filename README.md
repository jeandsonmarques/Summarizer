# Summarizer

Summarizer v0.5.0 is an experimental QGIS plugin release for summarizing layers and generating charts, dashboards, and reports from geospatial data.

It is designed for analysts who need to inspect QGIS project data, build visual summaries, organize dashboard views, and export structured results without leaving QGIS.

## What It Does

- Summarizes QGIS vector layers and attribute tables.
- Builds charts and dashboard-ready visualizations.
- Supports model, connection, visualization, and export workflows.
- Generates report-oriented outputs from geospatial datasets.
- Runs as a local QGIS plugin using the standard QGIS Python environment.

## Requirements

- QGIS 3.34 or later.
- Standard QGIS Python environment.

## Installation

1. Open **Plugins > Manage and Install Plugins...** in QGIS.
2. Select **Install from ZIP**.
3. Choose `Summarizer-qgis-release.zip`, generated with `scripts/build_release.ps1`.

For QGIS publication, the final ZIP must contain only the `Summarizer/` folder at the archive root. Do not upload GitHub's automatic Source Code ZIP as the QGIS plugin package.

## Support

- Repository: https://github.com/jeandsonmarques/Summarizer
- Issues: https://github.com/jeandsonmarques/Summarizer/issues

## License and Branding

- Code: `GPL-3.0-or-later`. See [LICENSE](LICENSE).
- Brand, logo, name, and visual identity: see [TRADEMARKS.md](TRADEMARKS.md).
- Modified versions must preserve copyright notices and clearly mark changes.
