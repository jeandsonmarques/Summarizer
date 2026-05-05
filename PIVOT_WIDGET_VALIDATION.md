# Pivot Table Widget Validation

## Manual checklist in QGIS

1. Open the Summarizer plugin.
2. Open the pivot table view.
3. Add at least one field to rows.
4. Add at least one field to columns.
5. Add at least one field to values.
6. Apply a filter and confirm the table updates.
7. Save the dashboard.
8. Close and reopen the dashboard.
9. Export the pivot table.
10. Confirm the exported file opens and the table structure matches the UI.

## Local validation commands

```powershell
py -3 -m compileall plugin/Summarizer tests
py -3 -m pytest
py -3 -m ruff check plugin/Summarizer/pivot tests/unit/test_pivot_calculations.py tests/unit/test_pivot_filters.py tests/unit/test_pivot_formatting.py tests/unit/test_pivot_models.py tests/smoke/test_pivot_package.py
```
