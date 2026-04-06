# Power BI Summarizer Repository

This repository is organized so the QGIS plugin can be packaged and released independently from the cloud backend and other development assets.

## Repository layout

- `plugin/power_bi_summarizer/`: distributable QGIS plugin package
- `cloud-api/`: optional backend service used by cloud workflows
- `docs/`: repository and publishing notes
- `scripts/`: packaging and maintenance helpers
- `tests/`: development-only tests and smoke checks

## Packaging

The QGIS plugin ZIP must contain only the `power_bi_summarizer/` folder.

Use:

```bash
py -3 scripts/build_plugin_package.py
```

This creates a ZIP in `dist/` containing only the plugin folder and required runtime files.

## Backend separation

The `cloud-api/` directory is part of the product ecosystem, but it is not part of the QGIS plugin package and must not be included in the ZIP uploaded to the QGIS plugin repository.
