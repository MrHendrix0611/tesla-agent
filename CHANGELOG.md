# Histórico das versões — Tesla Agent

> Evolução documentada a partir de snapshots fornecidos, sem atribuir datas de commits originais.

## v0.6.0 — Orquestração multiagentes

- `core/multiagent.py` define papéis de Arquiteto, Desenvolvedor, QA e Revisor.
- Fluxo sequencial com handoffs e restrição de ferramentas por papel.
- QA exige testes reais e Revisor emite veredito explícito.
- CLI inclui `/team roles`, `/team create`, `/team run`, `/team retry` e `/team rework`.

## v0.5.9 — Integração MCP via stdio

- `tools/mcp.py` implementa cliente MCP via stdio.
- Conexão, descoberta de tools, chamada e desconexão de servidores configurados.
- Exemplo de servidor em `examples/mcp_echo_server.py`.
- CLI inclui `/mcp`, `/mcp config`, `/mcp connect`, `/mcp tools`, `/mcp call` e `/mcp disconnect`.

## v0.5.8 — Memória de projeto e RAG lexical

- `core/memory.py` armazena notas explícitas do projeto.
- `core/knowledge.py` constrói índice lexical dos arquivos permitidos.
- Indexação incremental, recuperação de trechos e histórico compacto.
- CLI inclui `/index`, `/recall`, `/remember`, `/memories`, `/forget`, `/context` e `/clearcontext`.

## v0.5.7 — Coding Agent: diff, rollback e testes

- `core/coding.py` implementa funcionalidades de edição, comparação e rollback de arquivos.
- Ferramentas de execução de `unittest` retornam evidência do resultado.
- Vinculação a um workspace explícito para operações sensíveis.
- CLI inclui `/workspace`, `/diff`, `/rollback`, `/test` e `/diagnose`.

## v0.5.6 — Planner, Executor e checkpoints

- `core/planner.py` cria planos e controla estados e dependências.
- `core/executor.py` executa etapas com confirmação e evidência de ferramentas.
- `core/plan_store.py` persiste checkpoints localmente.
- CLI adiciona `/plan create`, `/plan`, `/steps`, `/resume`, `/retry` e `/cancel`.

## v0.5.5 — Repository Intelligence — Tesla

- `tools/repository.py` implementa mapeamento de repositório e pesquisa de código.
- Busca por símbolos (funções e classes) e por ocorrências com números de linha.
- CLI inclui `/project`, `/map`, `/find` e `/symbols`.
- O registro passa a expor operações de escrita de arquivo na variante presente neste snapshot.

## v0.5.4 — Observabilidade e auditoria

- `llm/observability.py` inclui registros de auditoria e relatórios.
- Identificadores de requisição, falhas e eventos de fallback.
- Comandos `/stats` e `/audit`.
- Persistência de eventos em JSONL local.

## v0.5.3 — Aprovação de modelos pagos

- Política `PAID_USAGE_MODE=never|ask|auto` com tratamento conservador de valores inválidos.
- O modo `ask` solicita autorização antes da chamada.
- `MONTHLY_PAID_BUDGET_USD` e `BudgetGuard` para limites locais estimados.
- Comando `/paid` para consultar a configuração.

## v0.5.2 — Smart Router e controle de uso

- `llm/intelligence.py` reúne `ModelSelector`, `UsageTracker` e `BudgetGuard`.
- Classificação heurística de tarefas de programação, arquitetura, dados e uso geral.
- Fallback entre provedores, cooldown e limites locais opcionais.
- CLI ganha `/router` e `/usage`.

## v0.5.1 — Multi-LLM e fallback

- Provedores `Groq`, `Gemini`, `OpenRouter` e `Ollama` no diretório `llm/providers/`.
- Configuração por `.env.example` com ordem de fallback.
- Roteador aceita modo automático com sequência configurável de provedores.
- Tools e permissões são preservadas da base anterior.

## v0.5 — Tools, permissões e execução

- `tools/registry.py` registra leitura de arquivo, listagem, pesquisa, Git e terminal.
- `core/permission_manager.py` classifica operações permitidas e sujeitas a confirmação.
- `core/agent.py` processa chamadas de ferramentas e envia seus retornos para a LLM.
- O CLI fornece `/tools` e mantém os comandos de Skills.

## v0.4 — Skills especializadas

- `core/skill_manager.py` lista e carrega instruções de Skills.
- As pastas `skills/architecture`, `skills/coding` e `skills/qa` contêm instruções.
- O agente injeta o texto da Skill ativa no contexto.
- Comandos de CLI para listar, ativar e desativar Skills.

## v0.3 — Contexto conversacional

- `core/context.py` introduz `ContextManager`.
- Mensagens do usuário e do assistente são acumuladas na sessão.
- `core/agent.py` envia `system` e histórico ao roteador.
- Método `clear_context()` para limpeza programática do contexto.

## v0.2 — Seleção de provedores

- `llm/router.py` lê `LLM_PROVIDER` do ambiente com `python-dotenv`.
- Suporte à seleção explícita de `openrouter` e `ollama`.
- Erros são apresentados para provedores não suportados.
- O CLI e o agente permanecem essencialmente iguais aos da V0.1.

## v0.1 — Fundação do agente e CLI

- `cli/main.py` mantém um ciclo de leitura de mensagens e saída no console.
- `core/agent.py` monta um prompt inicial e solicita a resposta ao `LLMRouter`.
- `llm/router.py` utiliza o provedor OpenRouter como rota única.
- `core/context.py` define uma estrutura simples de mensagens, ainda não integrada à execução do agente.

