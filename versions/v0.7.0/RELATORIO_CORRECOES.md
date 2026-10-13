# Tesla Agent V0.7.0 — Estabilização antes da publicação

**Responsável:** Guilherme Hendrik — https://github.com/MrHendrix0611

## Correções aplicadas

| Área | Correção | Evidência / verificação |
|---|---|---|
| Chat | Limites ampliados; interrupções retornam status `incomplete` e resumo conservador em vez de `completed` | Testes de regressão e serviço assíncrono |
| Multiagentes | Reconhecimento de `VEREDITO: APROVADO` e `VEREDITO: AJUSTES` também com formatação Markdown; respostas ambíguas ficam inconclusivas | Teste de parsing e fluxo existente |
| Multiagentes | Parecer do Revisor permanece disponível mesmo quando a etapa pausa; veredito e justificativa expostos separadamente | Testes da API / status |
| QA | Evidência `run_tests`, quantidade de testes e `exit_code` associadas ao plano; sem inferir aprovação de texto da LLM | Testes de execução real usando unittest |
| Sessões / CLI / Web | `PlanStore` por projeto + leitura da CLI + trava entre processos durante planos, retry/rework e cancelamento | Teste de exclusão, teste de restauração, testes antigos |
| Cancelamento | Verificação cooperativa entre ciclos de LLM e ferramentas, sem descartar arquivos alterados | Código e testes legados |
| Workspace | Último projeto restaurado do arquivo de preferências locais (somente caminho) | Teste de recriação do serviço |
| VS Code | Token testado contra `/api/status` antes de ser salvo, botão de reconexão | Revisão da integração, checagem sintática |
| Dashboard | Relatórios completos e expansíveis, indicadores de QA/veredito, ferramentas e uso formatados | Verificação dos ativos estáticos |
| Histórico | Metadados operacionais em `.tesla/web_jobs.jsonl` sem prompts ou conteúdo de ferramentas | Testes locais |
| Marca | Substituição do `T` pelo emblema orbital azul fornecido pelo autor, sem texto TESLA dentro da imagem | Imagem PNG RGBA 256×256, favicon e recurso VS Code |

## Limites ainda existentes

- **Validação offline não é homologação real.** A suíte Python foi executada com um *stub* temporário externo para `openai`, não incluído no pacote. Faça uma missão completa no Windows com sua credencial configurada.
- **Cancelamento cooperativo:** uma requisição à API da LLM já em andamento e processos de teste já iniciados não são interrompidos imediatamente.
- **Execuções concorrentes:** o bloqueio entre processos cobre geração, execução e alterações de controle dos planos. Edições manuais de CLI e chat em duas interfaces simultâneas ainda devem ser evitadas.
- **Histórico de execuções:** armazena metadados (tipo, status, horário e erro resumido), não prompts, código ou transcrições.
- **Token local:** gerado novamente após reiniciar o servidor por segurança; a extensão permite reconectar explicitamente. Não há reconexão automática baseada em segredo persistente.
- **UI visual:** a captura no navegador não pôde ser executada no ambiente de empacotamento por bloqueio de acesso localhost do navegador automatizado. Verifique no Windows.

## Verificações executadas

```text
python -m unittest discover -s tests -q
Ran 122 tests
OK

node --check web/static/app.js
node --check vscode-extension/extension.js
```

> O pacote inclui os testes, mas não contém os stubs de validação, credenciais reais ou diretórios privados de projeto. Execute `py -m pip install -r requirements.txt` antes dos testes no Windows.
