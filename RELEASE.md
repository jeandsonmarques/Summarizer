# Release do Summarizer

Este repositório usa a pasta `plugin/Summarizer` como fonte do pacote publicável.
O ZIP final precisa abrir como `Summarizer/...` na raiz, sem o prefixo extra
`Summarizer-main/`.

## Estrutura esperada do ZIP

```
Summarizer/
  __init__.py
  metadata.txt
  README.md
  CHANGELOG.md
  LICENSE
  resources/
  i18n/
  model_view/
  report_view/
  utils/
  ui/
  ...
```

## O que não deve entrar no ZIP

- `.git`
- `.github`
- `tests`
- `__pycache__`
- `*.pyc`
- `.pytest_cache`
- `.ruff_cache`
- arquivos temporários
- logs
- ZIPs antigos
- segredos locais, tokens, chaves ou configs de desenvolvimento

## Script de release

Use o script:

```powershell
.\scripts\build_release.ps1
```

Ele faz:

1. valida `metadata.txt`;
2. valida `resources/icon.png` e o ícone referenciado no metadata;
3. roda `compileall`;
4. limpa caches e artefatos gerados;
5. cria o ZIP em `_release/`;
6. verifica a estrutura final do ZIP.

## Checklist de publicação

1. Confirmar que o branch está limpo e com as correções desejadas.
2. Rodar `.\scripts\build_release.ps1`.
3. Abrir o ZIP gerado e confirmar que a raiz é `Summarizer/`.
4. Confirmar que não existem `tests/`, `.github/`, `__pycache__/` ou `*.pyc`.
5. Instalar o ZIP no QGIS e testar a abertura do plugin.
6. Confirmar que o ícone aparece e que `metadata.txt` está válido.
7. Publicar apenas o ZIP final de `_release/`.

## Observação importante

O pacote público deve nascer da pasta `plugin/Summarizer`. Evite compactar a
raiz inteira do repositório, porque isso cria caminhos duplicados como
`Summarizer-main/Summarizer/...` e quebra a instalação limpa no QGIS.
