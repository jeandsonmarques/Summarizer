# Power BI Summarizer

Power BI Summarizer é um plugin para QGIS voltado à análise, resumo e preparação de dados geoespaciais para uso em relatórios, painéis e fluxos de trabalho inspirados no Power BI.

O foco do projeto é oferecer uma experiência sólida dentro do QGIS para:

- resumir camadas vetoriais e tabelas;
- gerar tabelas prontas para relatório;
- criar visões analíticas e gráficos;
- apoiar a organização de dados para consumo externo;
- manter os fluxos principais funcionando localmente, sem depender de backend para uso básico.

## Visão geral

O repositório está organizado para separar claramente o pacote do plugin QGIS de eventuais componentes auxiliares. O código distribuído ao usuário final fica em `plugin/power_bi_summarizer/`, enquanto a raiz do repositório serve como ponto de documentação e manutenção do projeto.

## Estrutura do repositório

- `plugin/power_bi_summarizer/`: pacote principal do plugin QGIS
- `plugin/power_bi_summarizer/metadata.txt`: metadados exigidos pelo QGIS
- `plugin/power_bi_summarizer/__init__.py`: ponto de entrada do plugin
- `plugin/power_bi_summarizer/README.md`: documentação técnica do pacote do plugin

## Compatibilidade

- QGIS 3.34 até 3.99
- Ambiente Python fornecido pelo QGIS

O projeto ainda não é apresentado como compatível com QGIS 4 ou Qt6.

## Instalação

### Pela interface do QGIS

1. Abra `Plugins > Manage and Install Plugins...`.
2. Use a opção `Install from ZIP`.
3. Selecione um arquivo ZIP que contenha a pasta `power_bi_summarizer/` na raiz do pacote.

### A partir deste repositório

O pacote final do plugin deve ser montado de forma que o ZIP contenha apenas a pasta `power_bi_summarizer/` no nível superior.

Isso é importante porque o QGIS espera encontrar os arquivos do plugin diretamente dentro dessa pasta.

## O que o plugin faz

O plugin reúne funcionalidades para:

- explorar camadas carregadas no projeto;
- produzir resumos e tabelas derivadas;
- criar visualizações para análise e apresentação;
- exportar resultados para uso posterior em relatórios ou integrações;
- apoiar fluxos opcionais de conectividade com serviços externos.

## Dependências e observações

O funcionamento básico depende apenas do QGIS.

Alguns recursos adicionais podem exigir:

- `pandas` para processamento tabular;
- conexão de rede do próprio QGIS para integração com serviços remotos;
- serviços externos opcionais para recursos de IA ou backend.

Essas dependências adicionais não são necessárias para carregar o plugin nem para os fluxos locais principais.

## Publicação no QGIS

Antes de publicar o plugin no repositório oficial do QGIS, verifique:

- se `plugin/power_bi_summarizer/metadata.txt` contém URLs reais de repositório e rastreador de problemas;
- se o arquivo ZIP de distribuição contém somente a pasta `power_bi_summarizer/`;
- se não há arquivos temporários, caches ou artefatos de build no pacote final;
- se a versão declarada no `metadata.txt` corresponde à versão pretendida para publicação.

## Documentação complementar

- [README técnico do pacote do plugin](plugin/power_bi_summarizer/README.md)
- [Metadados do plugin](plugin/power_bi_summarizer/metadata.txt)
