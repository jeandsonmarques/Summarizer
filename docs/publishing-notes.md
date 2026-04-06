# Publishing Notes

## Before uploading to the official QGIS plugin repository

1. Replace placeholder URLs in `plugin/power_bi_summarizer/metadata.txt`.
2. Confirm the public repository contains the same plugin code shipped in the ZIP.
3. Re-run smoke tests and packaging from a clean tree.
4. Verify the final ZIP stays below repository size limits.
5. Confirm the plugin icon, metadata and README match the published branding.

## Current review-sensitive areas

- `plugin/power_bi_summarizer/cloud_session.py` uses `requests` for outbound HTTP calls.
- `plugin/power_bi_summarizer/report_view/ollama_fallback_service.py` uses `urllib.request`.
- The QGIS documentation recommends `QgsNetworkAccessManager` for network traffic so proxy handling follows QGIS settings.
- Remote GPKG downloads currently place the auth token in the query string for `/vsicurl/` access. Review whether the backend can support a safer pattern before public release.
- Mock/demo cloud behavior still exists for local development. Keep this clearly documented so users understand what is local demo behavior versus production cloud behavior.

## Scanner checklist

- No secrets or real deployment URLs should be committed in plugin metadata or README files.
- Keep real backend secrets only in local `.env` files that are ignored by git. Use `cloud-api/.env.example` as the committed template instead.
- Keep generated caches and runtime files out of git and out of the package.
- Review debug `print()` statements and migrate them to `QgsMessageLog` or a small internal logging helper before public submission.
- Keep optional AI integrations clearly marked as optional and disabled by default when not configured.
