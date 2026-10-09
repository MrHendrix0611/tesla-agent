# Tesla Agent V0.6.0 — Orquestração multiagentes

> **Versão histórica** · [Índice de versões](../../README.md) · **Criador:** Guilherme Hendrik  
> [GitHub](https://github.com/MrHendrix0611) · [LinkedIn](https://www.linkedin.com/in/guilherme-hendrik-59775326a/) · [Instagram](https://www.instagram.com/hxtech_/)

## 1. Descrição

Coordenação sequencial de papéis especializados no ciclo de desenvolvimento de software.

## 2. Objetivo

Separar responsabilidades de arquitetura, implementação, teste e revisão, com critérios explícitos de aceite.

## 3. Funcionalidades e implementações desta versão

- `core/multiagent.py` define papéis de Arquiteto, Desenvolvedor, QA e Revisor.
- Fluxo sequencial com handoffs e restrição de ferramentas por papel.
- QA exige testes reais e Revisor emite veredito explícito.
- CLI inclui `/team roles`, `/team create`, `/team run`, `/team retry` e `/team rework`.

### Principais arquivos e responsabilidades

- `core/multiagent.py` — papéis e orquestração
- `core/planner.py` e `core/executor.py` — planos
- `core/plan_store.py` — progresso
- `core/agent.py` — execução
- `tools/` — ferramentas restritas por papel

## 4. Instalação e execução

Requisitos: Python 3 e acesso ao provedor configurado (se for remoto). Execute os comandos a partir desta pasta de versão, não da raiz do repositório:

```powershell
py -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edite .env apenas em sua máquina e preencha as chaves necessárias.
py -m cli.main
```

O arquivo `.env.example` contém somente exemplos sem credenciais reais. Para modelos locais, configure o Ollama quando a versão o permitir. Identificadores de modelos antigos podem não estar disponíveis hoje.

## 5. Comandos disponíveis

| Comando | Finalidade |
|---|---|
| `/skills` | Lista Skills. |
| `/skill <nome>` | Ativa Skill. |
| `/skill off` | Desativa Skill. |
| `/tools` | Lista as famílias de ferramentas. |
| `/sair` | Encerra. |
| `/router` | Mostra a decisão do roteador. |
| `/usage` | Exibe o uso local. |
| `/paid` | Exibe modo de uso pago e orçamento. |
| `/stats` | Relatório agregado de uso e falhas. |
| `/audit` | Histórico de eventos do roteador. |
| `/project <caminho>` | Seleciona pasta do projeto. |
| `/map` | Resume o repositório. |
| `/find <texto>` | Localiza ocorrências no código. |
| `/symbols [termo]` | Lista funções/classes ou filtra por nome. |
| `/plan create <objetivo>` | Gera plano. |
| `/plan` | Consulta o plano. |
| `/steps` | Consulta etapas. |
| `/resume` | Executa/retoma etapas. |
| `/retry <id>` | Libera etapa pausada/falha. |
| `/cancel` | Cancela o plano. |
| `/workspace` | Exibe projeto ativo. |
| `/diff <arquivo>` | Mostra diferenças de arquivo. |
| `/rollback <arquivo>` | Restaura alterações anteriores. |
| `/test [módulo|all|discover]` | Executa testes reais. |
| `/diagnose` | Diagnóstico local sem credenciais. |
| `/index` | Atualiza índice lexical do projeto. |
| `/recall <tema>` | Busca fontes e notas. |
| `/remember <nota>` | Salva memória explícita. |
| `/memories` | Lista memórias. |
| `/forget <id>` | Exclui nota. |
| `/context` | Estatísticas de contexto. |
| `/clearcontext` | Limpa o histórico temporário. |
| `/mcp` | Servidores configurados/conectados. |
| `/mcp config` | Local da configuração. |
| `/mcp connect <nome>` | Conecta servidor. |
| `/mcp tools <nome>` | Ferramentas do servidor. |
| `/mcp call <nome> <tool> <json>` | Chama ferramenta. |
| `/mcp disconnect <nome>` | Desconecta. |
| `/team roles` | Lista os papéis de agentes. |
| `/team create <objetivo>` | Cria plano com papéis. |
| `/team` | Mostra plano e evidências. |
| `/team run` | Executa plano. |
| `/team retry <id>` | Retoma etapa. |
| `/team rework` | Abre ciclo de correções. |

**Observação:** comandos de barra só devem ser usados dentro da CLI do Tesla, após aparecer `Você:`. Mensagens comuns são encaminhadas ao modelo. Não execute comandos desconhecidos sem revisar permissões.

## 6. Fluxograma da arquitetura

```mermaid
flowchart TD
    CLI[CLI] --> O[TeamOrchestrator]
    O --> A[Arquiteto]
    A --> D[Desenvolvedor]
    D --> Q[QA - unittest real]
    Q --> RV[Revisor - veredito]
    RV --> O
    O --> E[Planner e Executor]
    E --> L[Agent e LLMRouter]
    E --> T[Tools - Coding - MCP]
    O --> ST[PlanStore checkpoints]
```

## 7. Fluxograma de funcionamento

```mermaid
flowchart TD
    G[Criar plano /team create] --> A[Arquiteto inspeciona]
    A --> D[Desenvolvedor implementa]
    D --> Q[QA executa unittest real]
    Q --> V{Testes aprovados?}
    V -->|Não| R[Retrabalho /team rework]
    R --> D
    V -->|Sim| RV[Revisor avalia e emite veredito]
    RV --> AP{Aprovado?}
    AP -->|Sim| OK[Plano completed]
    AP -->|Não| R
```

## 8. Limitações e pontos de atenção

- Os agentes são papéis coordenados sequencialmente, não processos autônomos paralelos.
- O fluxo de QA foi validado com `unittest`, mas não substitui revisão humana de segurança para produção.

O código desta versão foi preservado como snapshot histórico. A documentação foi reescrita a partir dos arquivos fornecidos; não houve mudanças funcionais planejadas no snapshot.

## 9. Implementações e objetivos da próxima versão

**Próxima etapa:** [Roadmap V0.7.0](../../ROADMAP.md).

- Disponibilizar API local para reutilizar o harness fora do terminal.
- Criar Dashboard Web com chat, planos, permissões e diffs.
- Iniciar integração do Tesla ao VS Code preservando a CLI.

## 10. Segurança, autoria e contribuição

- **Criador e responsável pelo projeto:** **Guilherme Hendrik**.
- GitHub: https://github.com/MrHendrix0611
- LinkedIn: https://www.linkedin.com/in/guilherme-hendrik-59775326a/
- Instagram: https://www.instagram.com/hxtech_/
- Nunca publique `.env`, credenciais, logs de uso ou checkpoints pessoais.
- Versões históricas são disponibilizadas para estudo da evolução; não devem ser presumidas seguras para produção.
- Para informações sobre publicação e segurança, consulte [`SECURITY.md`](../../SECURITY.md).
