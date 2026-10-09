# Tesla Agent V0.5.9 — Integração MCP via stdio

> **Versão histórica** · [Índice de versões](../../README.md) · **Criador:** Guilherme Hendrik  
> [GitHub](https://github.com/MrHendrix0611) · [LinkedIn](https://www.linkedin.com/in/guilherme-hendrik-59775326a/) · [Instagram](https://www.instagram.com/hxtech_/)

## 1. Descrição

Adição de cliente MCP para integrar servidores de ferramentas externas.

## 2. Objetivo

Permitir descoberta e execução supervisionada de ferramentas externas.

## 3. Funcionalidades e implementações desta versão

- `tools/mcp.py` implementa cliente MCP via stdio.
- Conexão, descoberta de tools, chamada e desconexão de servidores configurados.
- Exemplo de servidor em `examples/mcp_echo_server.py`.
- CLI inclui `/mcp`, `/mcp config`, `/mcp connect`, `/mcp tools`, `/mcp call` e `/mcp disconnect`.

### Principais arquivos e responsabilidades

- `tools/mcp.py` — cliente MCP
- `tools/registry.py` — despacho
- `examples/mcp_echo_server.py` — exemplo
- `core/agent.py` — chamadas MCP da LLM

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

**Observação:** comandos de barra só devem ser usados dentro da CLI do Tesla, após aparecer `Você:`. Mensagens comuns são encaminhadas ao modelo. Não execute comandos desconhecidos sem revisar permissões.

## 6. Fluxograma da arquitetura

```mermaid
flowchart TD
    CLI[CLI] --> AG[Agent]
    AG --> REG[ToolRegistry]
    REG --> MCP[Cliente MCP stdio]
    MCP --> SV[Servidor MCP externo]
    MCP --> P[Permissões e Aprovação]
    AG --> RAG[Memória e RAG]
    AG --> EX[Planner e Coding]
    AG --> LLM[LLMRouter]
```

## 7. Fluxograma de funcionamento

```mermaid
flowchart TD
    C[Configurar servidor MCP] --> A{Autorizar conexão?}
    A -->|Sim| S[Iniciar processo via stdio]
    A -->|Não| X[Cancelar]
    S --> D[Descobrir ferramentas]
    D --> L[LLM escolhe chamada ou CLI call]
    L --> P{Autorizar tool?}
    P -->|Sim| E[Executar no servidor MCP]
    P -->|Não| X
    E --> R[Retornar resultado]
    R --> F[Desconectar quando necessário]
```

## 8. Limitações e pontos de atenção

- Integração MCP desta versão prioriza stdio; não é uma implementação completa de todos os transportes.
- Processos MCP externos possuem as permissões de sistema do processo que os executa.

O código desta versão foi preservado como snapshot histórico. A documentação foi reescrita a partir dos arquivos fornecidos; não houve mudanças funcionais planejadas no snapshot.

## 9. Implementações e objetivos da próxima versão

**Próxima etapa:** [`v0.6.0`](../v0.6.0/README.md).

- Adicionar papéis especializados de agentes e orquestração.
- Exigir QA real e parecer do Revisor antes de concluir tarefas.

## 10. Segurança, autoria e contribuição

- **Criador e responsável pelo projeto:** **Guilherme Hendrik**.
- GitHub: https://github.com/MrHendrix0611
- LinkedIn: https://www.linkedin.com/in/guilherme-hendrik-59775326a/
- Instagram: https://www.instagram.com/hxtech_/
- Nunca publique `.env`, credenciais, logs de uso ou checkpoints pessoais.
- Versões históricas são disponibilizadas para estudo da evolução; não devem ser presumidas seguras para produção.
- Para informações sobre publicação e segurança, consulte [`SECURITY.md`](../../SECURITY.md).
