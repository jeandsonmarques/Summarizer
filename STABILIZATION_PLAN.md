# Stabilization Plan - Summarizer

## Objetivo

Esta fase existe para preparar o repositório do plugin **Summarizer** para correções seguras, com foco em estabilidade operacional, previsibilidade de release e redução de risco.  
O objetivo não é evoluir funcionalidade, e sim tornar o código mais confiável para manutenção contínua.

## Regras da fase

- Não adicionar features novas.
- Não mudar comportamento funcional de forma intencional.
- Priorizar correções que reduzam risco de runtime, falhas de empacotamento e regressões.
- Toda alteração deve ter escopo pequeno e verificável.
- Mudanças de UI só podem ocorrer se forem necessárias para corrigir bug, texto quebrado, segurança ou consistência de release.

## Foco de trabalho

1. Bugfixes.
2. Segurança e proteção de credenciais.
3. Limpeza técnica e redução de dívida.
4. Testes e validação automatizada.
5. Pipeline e empacotamento de release.

## Módulos mais críticos

- `plugin/Summarizer/data_summarizer.py`
- `plugin/Summarizer/pivot_table_widget.py`
- `plugin/Summarizer/model_tab.py`
- `plugin/Summarizer/integration_panel.py`
- `plugin/Summarizer/browser_integration.py`
- `plugin/Summarizer/report_view/reports_widget.py`
- `plugin/Summarizer/report_view/report_executor.py`
- `plugin/Summarizer/report_view/hybrid_query_interpreter.py`
- `plugin/Summarizer/report_view/chart_factory.py`
- `plugin/Summarizer/utils/i18n_runtime.py`

## Ordem de execução

1. Congelar a base atual com checkpoints claros de git.
2. Corrigir empacotamento de release e validar o conteúdo final do ZIP.
3. Corrigir problemas de encoding e texto quebrado.
4. Reduzir riscos de segurança ligados a senha, token, conexão e persistência local.
5. Substituir `except Exception: pass` em pontos críticos por tratamento com log ou erro explícito.
6. Criar testes mínimos de smoke/importação e validação de assets.
7. Só depois iniciar refatorações estruturais em módulos grandes.

## Checklist de validação manual no QGIS

- Abrir o plugin sem erro de carregamento.
- Verificar se a janela principal abre e fecha normalmente.
- Testar conexão com dados salvos e conexão nova.
- Confirmar que relatórios e tabelas continuam renderizando.
- Validar exportação básica.
- Conferir se textos exibidos ao usuário não têm caracteres quebrados.
- Verificar que credenciais não aparecem em logs, arquivos temporários ou telas indevidas.
- Testar o fluxo de abrir, editar e salvar um projeto.
- Confirmar que o ZIP de release contém os arquivos essenciais do plugin.
- Reiniciar o QGIS e repetir a abertura do plugin para garantir consistência.

## Critério de saída da estabilização

A fase só pode ser considerada concluída quando:

- o plugin carregar sem erros no QGIS;
- o pacote de release estiver consistente com o repositório;
- os principais fluxos forem validados manualmente;
- houver pelo menos uma base mínima de testes para impedir regressões triviais.
