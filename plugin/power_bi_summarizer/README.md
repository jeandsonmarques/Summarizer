# Power BI Summarizer

Power BI Summarizer is a QGIS plugin for summarizing project layers, preparing reporting-ready tables, and supporting Power BI-oriented analysis workflows from inside QGIS.

## Overview

The plugin combines local QGIS data exploration, report-style summaries, dashboard helpers, export utilities, and optional cloud connectivity in a single client package. It is designed so the QGIS plugin remains installable on its own while cloud infrastructure is deployed separately.

## Features

- Summarize vector layer content into tables and metrics ready for reporting.
- Build dashboard-oriented views and chart widgets inside QGIS.
- Export datasets and derived outputs for downstream Power BI workflows.
- Connect to optional cloud catalogs and remote layer delivery endpoints.
- Support optional AI-assisted question interpretation for report generation.

## Installation

### Install from a ZIP package

1. Build or obtain a ZIP that contains only the `power_bi_summarizer/` folder.
2. In QGIS, open `Plugins > Manage and Install Plugins...`.
3. Use `Install from ZIP` and select the generated package.

### Build the ZIP from this repository

From the repository root:

```bash
py -3 scripts/build_plugin_package.py
```

The generated archive will be written to `dist/`.

## Basic usage

1. Enable the plugin in QGIS.
2. Open `Power BI Summarizer` from the Plugins menu.
3. Select project layers or imported datasets.
4. Generate summaries, pivoted views, charts, or exportable outputs.
5. Optionally configure cloud settings if you want remote catalog features.

## Cloud features

Some workflows depend on a separately deployed backend service and are not bundled in the plugin package.

Cloud features may require:

- a reachable HTTPS API endpoint
- a deployment-specific account
- deployment-specific permissions for upload or administration
- additional backend storage or database configuration

If cloud features are not configured, the local plugin can still be used for local summarization workflows.

## External dependencies

### Required runtime environment

- QGIS 3.34 to 3.99
- Standard QGIS Python environment

### Optional Python or service dependencies

- `pandas` for table-oriented processing used by several UI and reporting flows
- `requests` for current cloud HTTP communication
- `langchain-openai` plus an OpenAI API key for optional LangChain-based interpretation
- a local Ollama service for optional local fallback interpretation

Optional dependencies are not required for the core plugin UI to load, but related features will remain unavailable until configured.

## Limitations

- The plugin is currently scoped to QGIS 3 and is not yet declared ready for QGIS 4 / Qt6.
- Cloud features depend on an external backend that must be deployed and operated separately.
- Some network calls currently use Python HTTP libraries instead of `QgsNetworkAccessManager`; this should be revisited before public publication.
- Optional AI features depend on services that may introduce cost, latency, network, or policy requirements.

## Support and issues

- Project page: `<README_OR_PROJECT_PAGE_URL>`
- Source repository: `<PUBLIC_REPOSITORY_URL>`
- Issue tracker: `<ISSUES_URL>`

Replace the placeholders above before publishing the repository or uploading a release to the official QGIS plugin repository.
