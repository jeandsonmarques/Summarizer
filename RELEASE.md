# Release do Summarizer

O pacote distribuivel do plugin deve ser gerado fora do repositorio, em uma
pasta separada dentro de `Documents`, para evitar que ZIPs, staging e artefatos
temporarios fiquem dentro da arvore do projeto.

## Saida padrao

O comando abaixo gera o release em:

`$env:USERPROFILE\Documents\Summarizer_release`

```powershell
.\scripts\build_release.ps1
```

## Saida personalizada

Voce pode informar uma pasta de saida externa usando `-OutputDir`:

```powershell
.\scripts\build_release.ps1 -OutputDir "$env:USERPROFILE\Documents\Summarizer_release"
```

O ZIP final sera criado como:

`$env:USERPROFILE\Documents\Summarizer_release\Summarizer-qgis-release.zip`

## Estrutura esperada do ZIP

```text
Summarizer/
  __init__.py
  metadata.txt
  README.md
  CHANGELOG.md
  resources/
  i18n/
  model_view/
  report_view/
  utils/
  ui/
```

## O que nao deve entrar no ZIP

- `.git`
- `.github`
- `tests`
- `__pycache__`
- `*.pyc`
- `.pytest_cache`
- `.ruff_cache`
- `_release`
- `logs`
- `*.log`
- `*.tmp`
- arquivos temporarios
- senhas, tokens ou configs locais

## O que o script faz

1. valida `metadata.txt`;
2. valida o `icon.svg` referenciado no metadata e o `icon.png` usado como ativo auxiliar do pacote;
3. roda `compileall` em `plugin/Summarizer` e `tests`;
4. limpa caches e artefatos gerados;
5. monta o staging fora do repositorio;
6. cria o ZIP final em `Summarizer_release`;
7. verifica a estrutura interna do ZIP;
8. remove o staging temporario ao final.

## Icones

O `metadata.txt` aponta para `resources/icon.svg`, que e o icone principal usado pelo QGIS na instalacao do plugin.
O `scripts/build_release.ps1` tambem valida `resources/icon.png` porque o pacote de release mantem esse ativo auxiliar disponivel para o empacotamento.
Os dois arquivos sao mantidos de proposito para nao quebrar o carregamento do plugin nem o fluxo de distribuicao.

## Checklist rapido

1. Confirmar que o branch esta limpo.
2. Rodar o script de release.
3. Abrir o ZIP e verificar que a raiz e `Summarizer/`.
4. Confirmar que nao existem `tests/`, `.github/`, `__pycache__/` ou `*.pyc`.
5. Instalar o ZIP no QGIS e testar a abertura do plugin.
6. Publicar somente o ZIP final fora do repositorio.

## Observacao importante

O ZIP deve nascer sempre da pasta `plugin/Summarizer`. Nao compacte a raiz
inteira do repositorio, porque isso cria caminhos duplicados e dificulta a
instalacao limpa no QGIS.
