# Summarizer QGIS Plugin Package

This folder contains the distributable QGIS plugin package used for publication.

## Package scope

This v0.5.1 package includes the plugin code, metadata, and resources required for QGIS to load and run the extension locally.

## Distribution rules

- Ship only the `Summarizer/` folder at the root of the ZIP archive.
- Exclude development-only files, temporary artifacts, cached bytecode, and build outputs.
- Use `Summarizer-qgis-release.zip`, generated with `scripts/build_release.ps1`, as the QGIS package.

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

## License and Branding

- Code: `GPL-3.0-or-later`.
- Brand, logo, name, and visual identity: see `TRADEMARKS.md`.
- Modified versions must use a different name if there is chance of confusion.
- Modified versions must preserve copyright notices and clearly mark changes.
