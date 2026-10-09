# Tesla Agent V0.5.6 — Planner, Executor e checkpoints

> **Versão histórica** · [Índice de versões](../../README.md) · **Criador:** Guilherme Hendrik  
> [GitHub](https://github.com/MrHendrix0611) · [LinkedIn](https://www.linkedin.com/in/guilherme-hendrik-59775326a/) · [Instagram](https://www.instagram.com/hxtech_/)

## 1. Descrição

Planejamento de atividades e execução sequencial controlada.

## 2. Objetivo

Permitir que tarefas complexas sejam divididas em passos dependentes e retomáveis.

## 3. Funcionalidades e implementações desta versão

- `core/planner.py` cria planos e controla estados e dependências.
- `core/executor.py` executa etapas com confirmação e evidência de ferramentas.
- `core/plan_store.py` persiste checkpoints localmente.
- CLI adiciona `/plan create`, `/plan`, `/steps`, `/resume`, `/retry` e `/cancel`.

### Principais arquivos e responsabilidades

- `core/planner.py` — dependências e estados
- `core/executor.py` — execução sequencial
- `core/plan_store.py` — checkpoints
- `core/agent.py` — ferramentas e LLM

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

**Observação:** comandos de barra só devem ser usados dentro da CLI do Tesla, após aparecer `Você:`. Mensagens comuns são encaminhadas ao modelo. Não execute comandos desconhecidos sem revisar permissões.

## 6. Fluxograma da arquitetura

```mermaid
flowchart TD
    CLI[CLI] --> PL[Planner]
    PL --> PS[PlanStore local]
    PL --> EX[PlanExecutor]
    EX --> AG[Agent]
    AG --> LLM[LLMRouter]
    AG --> TR[Tools e Permissions]
    EX --> PS
    EX --> CLI
```

## 7. Fluxograma de funcionamento

```mermaid
flowchart TD
    P[Definir objetivo] --> PL[Gerar etapas e dependências]
    PL --> C[Salvar checkpoint]
    C --> N{Etapa disponível?}
    N -->|Sim| U{Usuário autoriza?}
    U -->|Sim| X[Executar ferramentas]
    X --> V{Evidência suficiente?}
    V -->|Sim| OK[Marcar concluída]
    V -->|Não| PA[Registrar pausa ou falha]
    OK --> C
    PA --> C
    N -->|Não| F[Encerrar ou aguardar]
```

## 8. Limitações e pontos de atenção

- A versão histórica apresentou problemas de caminhos no Windows e etapas marcadas como falhas apesar de gravações realizadas.
- Os checkpoints pessoais foram removidos da distribuição pública.

O código desta versão foi preservado como snapshot histórico. A documentação foi reescrita a partir dos arquivos fornecidos; não houve mudanças funcionais planejadas no snapshot.

## 9. Implementações e objetivos da próxima versão

**Próxima etapa:** [`v0.5.7`](../v0.5.7/README.md).

- Criar edição por patches, diffs e rollback.
- Melhorar validação de caminhos e execução de testes de código.

## 10. Segurança, autoria e contribuição

- **Criador e responsável pelo projeto:** **Guilherme Hendrik**.
- GitHub: https://github.com/MrHendrix0611
- LinkedIn: https://www.linkedin.com/in/guilherme-hendrik-59775326a/
- Instagram: https://www.instagram.com/hxtech_/
- Nunca publique `.env`, credenciais, logs de uso ou checkpoints pessoais.
- Versões históricas são disponibilizadas para estudo da evolução; não devem ser presumidas seguras para produção.
- Para informações sobre publicação e segurança, consulte [`SECURITY.md`](../../SECURITY.md).
