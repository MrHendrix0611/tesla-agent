# Hefesto Agent V0.5 — Tools, permissões e execução

> **Versão histórica** · [Índice de versões](../../README.md) · **Criador:** Guilherme Hendrik  
> [GitHub](https://github.com/MrHendrix0611) · [LinkedIn](https://www.linkedin.com/in/guilherme-hendrik-59775326a/) · [Instagram](https://www.instagram.com/hxtech_/)

## 1. Descrição

Primeiro ciclo de tool calling do Hefesto, com ferramentas locais e confirmação humana.

## 2. Objetivo

Permitir que a LLM solicite ações reais no sistema sem execução irrestrita.

## 3. Funcionalidades e implementações desta versão

- `tools/registry.py` registra leitura de arquivo, listagem, pesquisa, Git e terminal.
- `core/permission_manager.py` classifica operações permitidas e sujeitas a confirmação.
- `core/agent.py` processa chamadas de ferramentas e envia seus retornos para a LLM.
- O CLI fornece `/tools` e mantém os comandos de Skills.

### Principais arquivos e responsabilidades

- `tools/registry.py` — definição e despacho de tools
- `core/permission_manager.py` — regras de autorização
- `tools/filesystem.py`, `tools/git.py`, `tools/search.py`, `tools/terminal.py` — ferramentas locais

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

**Observação:** comandos de barra só devem ser usados dentro da CLI do Hefesto, após aparecer `Você:`. Mensagens comuns são encaminhadas ao modelo. Não execute comandos desconhecidos sem revisar permissões.

## 6. Fluxograma da arquitetura

```mermaid
flowchart TD
    U[Usuário] --> CLI[CLI]
    CLI --> A[Agent]
    A --> S[SkillManager]
    A --> C[ContextManager]
    A --> L[LLMRouter]
    L --> P[LLM]
    P --> T[ToolRegistry]
    T --> PM[PermissionManager]
    PM --> FS[Filesystem]
    PM --> G[Git e Pesquisa]
    PM --> TM[Terminal confirmado]
    FS --> A
    G --> A
    TM --> A
```

## 7. Fluxograma de funcionamento

```mermaid
flowchart TD
    P[Pedido] --> L[LLM gera resposta ou tool call]
    L --> T{Chamou ferramenta?}
    T -->|Não| O[Responder]
    T -->|Sim| PM{Permissão?}
    PM -->|Permitida| X[Executar tool]
    PM -->|Confirmar| H{Usuário autoriza?}
    H -->|Sim| X
    H -->|Não| N[Negar operação]
    PM -->|Negada| N
    X --> R[Retornar resultado à LLM]
    R --> L
```

## 8. Limitações e pontos de atenção

- `write_file()` aparece no código do filesystem, mas o registro desta versão não o expõe como tool calling.
- Operações de terminal exigem confirmação; a implementação ainda não possui sandbox de processos.

O código desta versão foi preservado como snapshot histórico. A documentação foi reescrita a partir dos arquivos fornecidos; não houve mudanças funcionais planejadas no snapshot.

## 9. Implementações e objetivos da próxima versão

**Próxima etapa:** [`v0.5.1`](../v0.5.1/README.md).

- Integrar Groq e Gemini, além dos provedores existentes.
- Introduzir fallback entre provedores e configuração uniforme.

## 10. Segurança, autoria e contribuição

- **Criador e responsável pelo projeto:** **Guilherme Hendrik**.
- GitHub: https://github.com/MrHendrix0611
- LinkedIn: https://www.linkedin.com/in/guilherme-hendrik-59775326a/
- Instagram: https://www.instagram.com/hxtech_/
- Nunca publique `.env`, credenciais, logs de uso ou checkpoints pessoais.
- Versões históricas são disponibilizadas para estudo da evolução; não devem ser presumidas seguras para produção.
- Para informações sobre publicação e segurança, consulte [`SECURITY.md`](../../SECURITY.md).
