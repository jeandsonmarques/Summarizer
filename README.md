# Power BI Summarizer

Turn QGIS layers into reporting-ready tables, summaries, and dashboard inputs for Power BI without leaving QGIS.

> Main screenshot or GIF placeholder: add a product preview here, such as `docs/images/power-bi-summarizer-hero.gif`.

## About

Power BI Summarizer is a QGIS plugin built for analysts and GIS teams who need to move quickly from raw spatial layers to clean reporting outputs. It helps you explore project data, build summaries, create report-ready tables, prepare exports, and organize information for downstream Power BI workflows.

The plugin is designed to be useful on its own inside QGIS. Local workflows work without any cloud dependency. Optional cloud-connected features are available when your organization has a separately deployed backend, but that backend is not bundled into the QGIS plugin package.

## Features

- Summarize QGIS layers into tables and metrics ready for reporting.
- Build pivoted and report-style views for fast analysis.
- Prepare exports for Power BI-oriented workflows and downstream dashboards.
- Work with local layers and saved database connections from inside QGIS.
- Connect to optional cloud catalogs and remote delivery endpoints when configured.
- Use optional AI-assisted interpretation features when supporting services are available.

## Installation / Get the plugin

The plugin is being prepared for future publication in the official QGIS plugin repository. Until the first public listing is available, install it from a ZIP package built from this repository.

1. Build the plugin ZIP from the repository root:

   ```bash
   py -3 scripts/build_plugin_package.py
   ```

2. In QGIS, open `Plugins > Manage and Install Plugins...`.
3. Choose `Install from ZIP`.
4. Select the ZIP generated in `dist/`.

## Quick start

1. Enable `Power BI Summarizer` in QGIS.
2. Open the plugin from the `Plugins` menu.
3. Select a layer or dataset you want to analyze.
4. Generate summaries, pivoted views, charts, or exportable outputs.
5. Configure cloud access only if you need remote catalogs or backend-connected workflows.

## What works locally

You can use the plugin locally without any external backend for:

- summarizing local QGIS layers
- building report-style and pivoted views
- exporting local results to supported formats
- working with local or saved database connections
- testing non-production cloud UI screens with the sample mock catalog

## Optional cloud features

Cloud features are optional. The plugin remains useful as a local QGIS tool even when no backend is configured.

When cloud workflows are enabled, the plugin can provide:

- cloud sign-in and session handling
- configurable endpoint access
- remote catalog and layer browsing
- backend-connected data delivery workflows

The backend is a separate part of the product ecosystem and is not shipped inside the QGIS plugin ZIP. It may be deployed as a private internal service or as a public service, depending on how your organization operates it. In all cases, it must be installed and configured separately from the plugin.

## Documentation

- [Plugin README](plugin/power_bi_summarizer/README.md)
- [Repository layout](docs/repository-layout.md)
- [Publishing notes](docs/publishing-notes.md)
- Support and issues: `<ISSUES_URL>`

Replace the support placeholder with a real issue tracker URL before the first public release.

## Contributing

Contributions are welcome. Bug reports, workflow feedback, documentation improvements, UX suggestions, and carefully scoped code contributions all help move the project forward.

If you are planning a larger change, document the use case first so the implementation stays aligned with the plugin's user-facing goals.

## Development

Technical repository details live in the docs so this README can stay focused on users and product value.

- Start with [Repository layout](docs/repository-layout.md) for the split between plugin, backend, docs, scripts, and tests.
- Use [Publishing notes](docs/publishing-notes.md) for release-oriented checks and packaging guidance.
- See [Plugin README](plugin/power_bi_summarizer/README.md) for plugin-specific runtime notes and dependencies.

## License

Power BI Summarizer is distributed under the [GPL-3.0-or-later license](plugin/power_bi_summarizer/LICENSE).
