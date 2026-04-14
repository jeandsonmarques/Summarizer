# Power BI Summarizer - Plugin Package

Este diretório contém o pacote distribuído do plugin QGIS Power BI Summarizer.

## Conteúdo esperado pelo QGIS

O pacote do plugin deve incluir, no mínimo:

- `metadata.txt`
- `__init__.py`
- o código Python do plugin
- os recursos referenciados pelo plugin, como ícones e arquivos de interface

## Finalidade

O plugin foi estruturado para executar os fluxos principais dentro do QGIS:

- resumo de camadas e tabelas;
- preparação de saídas analíticas;
- geração de visualizações e componentes de dashboard;
- integração opcional com serviços externos.

## Empacotamento

Ao criar a versão final para distribuição:

1. compacte apenas a pasta `power_bi_summarizer/`;
2. mantenha a pasta na raiz do ZIP;
3. evite incluir diretórios de desenvolvimento, testes ou backend;
4. confirme que `metadata.txt` contém URLs válidos antes da publicação.

## Publicação

Antes de enviar o plugin para o repositório oficial do QGIS, revise:

- compatibilidade declarada em `metadata.txt`;
- descrição e resumo do plugin;
- URL do repositório;
- URL do rastreador de problemas;
- versão de publicação.

## Observação

Os recursos de backend e integrações remotas não fazem parte do pacote principal do plugin e devem ser mantidos fora do ZIP de distribuição do QGIS.
