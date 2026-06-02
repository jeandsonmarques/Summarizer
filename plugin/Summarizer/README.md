# Summarizer QGIS Plugin Package

This folder contains the distributable QGIS plugin package used for publication.

## Package scope

The package includes the plugin code, metadata, and resources required for QGIS to load and run the extension locally.

## Distribution rules

- Ship only the `Summarizer/` folder at the root of the ZIP archive.
- Exclude development-only files, temporary artifacts, cached bytecode, and build outputs.
- Keep deployment-specific components outside the release ZIP.

## Included surface area

- plugin entry point
- plugin metadata
- summary, chart, dashboard, model, connection, visualization, and export components
- local resources and icons
- report-oriented helpers used by the QGIS client

## Release checklist

- confirm version, description, and compatibility in `metadata.txt`
- confirm repository, homepage, and issue tracker URLs
- verify that the archive root is `Summarizer/`
- verify that no generated files or hidden directories are present
