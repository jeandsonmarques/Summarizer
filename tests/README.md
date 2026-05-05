# Testes do Summarizer

Executar localmente:

```powershell
python -m pip install -r requirements-dev.txt
python -m compileall plugin/Summarizer
pytest
ruff check tests plugin/Summarizer/utils/logging_utils.py plugin/Summarizer/utils/security_utils.py plugin/Summarizer/report_view/result_models.py plugin/Summarizer/report_view/charts
```

Quando o QGIS não estiver instalado, os testes `smoke` que dependem dele pulam com segurança.
