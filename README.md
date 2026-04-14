# Power BI Summarizer

Power BI Summarizer is a QGIS plugin for summarizing layers, preparing reporting-ready tables, and building dashboard-style outputs inside QGIS.

## Repository layout

- `plugin/power_bi_summarizer/`: the QGIS plugin package
- `plugin/power_bi_summarizer/metadata.txt`: plugin metadata used by QGIS
- `plugin/power_bi_summarizer/__init__.py`: plugin entry point

## QGIS plugin packaging

QGIS expects the release ZIP to contain only the `power_bi_summarizer/` folder at the root of the archive.

The plugin package already includes the mandatory files required by QGIS:

- `metadata.txt`
- `__init__.py`
- `resources/icon.svg`

## Development notes

- Keep the plugin package focused on the QGIS client-side code.
- Update `plugin/power_bi_summarizer/metadata.txt` with real repository and issue tracker URLs before publishing.
- Avoid committing generated files such as `__pycache__/`, build directories, and temporary archives.

## More information

- Plugin package README: `plugin/power_bi_summarizer/README.md`
- QGIS plugin metadata: `plugin/power_bi_summarizer/metadata.txt`
