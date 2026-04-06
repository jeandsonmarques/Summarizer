# Publishing Notes

## Before uploading to the official QGIS plugin repository

1. Replace placeholder URLs in `plugin/power_bi_summarizer/metadata.txt`.
2. Confirm the public repository contains the same plugin code shipped in the ZIP.
3. Re-run smoke tests and packaging from a clean tree.
4. Verify the final ZIP stays below repository size limits.
5. Confirm the plugin icon, metadata and README match the published branding.

## Current review-sensitive areas

- The plugin-side cloud client is now aligned with the QGIS network stack where available so proxy handling follows QGIS settings.
- Remote GPKG downloads currently place the auth token in the query string for `/vsicurl/` access. Review whether the backend can support a safer pattern before public release.
- Mock/demo cloud behavior still exists for local development. Keep this clearly documented so users understand what is local demo behavior versus production cloud behavior.
- Saved database credentials should still be reviewed carefully before public publication. Prefer QGIS authentication storage when possible.

## Scanner checklist

- No secrets or real deployment URLs should be committed in plugin metadata or README files.
- Keep real backend secrets only in local `.env` files that are ignored by git. Use `cloud-api/.env.example` as the committed template instead.
- Keep generated caches and runtime files out of git and out of the package.
- Review new code for debug `print()` statements and prefer the plugin logging helper or `QgsMessageLog`.
- Keep optional AI integrations clearly marked as optional and disabled by default when not configured.
