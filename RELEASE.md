# Summarizer Release

The QGIS plugin package must be generated outside the repository in a separate
folder under `Documents`. This keeps ZIP files, staging folders, and temporary
artifacts out of the project tree.

## Default Output

Run the release script from the repository root:

```powershell
.\scripts\build_release.ps1
```

The final ZIP is created as:

`$env:USERPROFILE\Documents\Summarizer_release\Summarizer-qgis-release.zip`

## Custom Output

You can provide an external output folder with `-OutputDir`:

```powershell
.\scripts\build_release.ps1 -OutputDir "$env:USERPROFILE\Documents\Summarizer_release"
```

## Expected ZIP Structure

```text
Summarizer/
  __init__.py
  metadata.txt
  LICENSE
  README.md
  CHANGELOG.md
  resources/
  i18n/
  model_view/
  report_view/
  utils/
  ui/
```

The ZIP root must contain only `Summarizer/`. Do not upload GitHub's automatic
Source Code ZIP to the QGIS plugin repository.

## Excluded Files

- `.git`
- `.github`
- `tests`
- `__pycache__`
- `*.pyc`
- `*.pyo`
- `.pytest_cache`
- `.ruff_cache`
- `_release`
- `_release_stage`
- `__MACOSX`
- `logs`
- `*.log`
- `*.tmp`
- temporary files
- passwords, tokens, or local configs

## What The Script Does

1. Validates `metadata.txt`.
2. Validates the icon referenced by `metadata.txt` and the raster `icon.png`.
3. Runs `compileall` for `plugin/Summarizer`.
4. Removes caches and generated artifacts.
5. Copies only `plugin/Summarizer` into a temporary staging folder.
6. Creates `Summarizer-qgis-release.zip` with `Summarizer/` at the archive root.
7. Blocks repository, test, cache, bytecode, generated, and hidden platform files from the ZIP.
8. Audits the release package for prohibited references.
9. Removes temporary staging files at the end.

## Icons

The `metadata.txt` file points to `resources/icon.png`, which is the QGIS
plugin icon used for publication. The SVG companion can remain as a local
resource, but the release script validates the raster icon used by metadata.

## Quick Checklist

1. Confirm the branch is clean.
2. Run `scripts/build_release.ps1`.
3. Open the ZIP and verify the root is only `Summarizer/`.
4. Confirm there are no `tests/`, `.github/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `*.pyc`, or `*.pyo` files.
5. Install the ZIP in QGIS and test that the plugin opens correctly.
6. Publish only `Summarizer-qgis-release.zip`.

## Important Note

The ZIP must always be generated from `plugin/Summarizer`. Do not compress the
repository root, because that creates extra paths and prevents a clean QGIS
installation.
