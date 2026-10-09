# Hefesto Agent V0.3 — Contexto conversacional

> **Versão histórica** · [Índice de versões](../../README.md) · **Criador:** Guilherme Hendrik  
> [GitHub](https://github.com/MrHendrix0611) · [LinkedIn](https://www.linkedin.com/in/guilherme-hendrik-59775326a/) · [Instagram](https://www.instagram.com/hxtech_/)

## 1. Descrição

O Hefesto passa a armazenar o histórico da conversa durante a sessão.

## 2. Objetivo

Responder considerando mensagens anteriores, não apenas a pergunta atual.

## 3. Funcionalidades e implementações desta versão

- `core/context.py` introduz `ContextManager`.
- Mensagens do usuário e do assistente são acumuladas na sessão.
- `core/agent.py` envia `system` e histórico ao roteador.
- Método `clear_context()` para limpeza programática do contexto.

### Principais arquivos e responsabilidades

- `core/context.py` — histórico de mensagens
- `core/agent.py` — composição de contexto
- `llm/router.py` — envio à LLM

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
| `sair` / `exit` / `quit` | Encerra o CLI. |
| `<mensagem>` | Conversa com histórico da sessão. |

**Observação:** comandos de barra só devem ser usados dentro da CLI do Hefesto, após aparecer `Você:`. Mensagens comuns são encaminhadas ao modelo. Não execute comandos desconhecidos sem revisar permissões.

## 6. Fluxograma da arquitetura

```mermaid
flowchart TD
    U[Usuário] --> CLI[CLI]
    CLI --> A[Agent]
    A <--> CT[ContextManager]
    A --> R[LLMRouter]
    R --> OR[OpenRouter]
    R --> OL[Ollama]
    OR --> A
    OL --> A
```

## 7. Fluxograma de funcionamento

```mermaid
flowchart TD
    P[Mensagem do usuário] --> H[Adicionar ao ContextManager]
    H --> M[Montar system + histórico]
    M --> R[Enviar ao provedor]
    R --> S[Salvar resposta no histórico]
    S --> O[Mostrar no CLI]
```

## 8. Limitações e pontos de atenção

- A memória é somente em processo e não persiste após encerrar.
- O CLI não expõe um comando específico para limpar o contexto.

O código desta versão foi preservado como snapshot histórico. A documentação foi reescrita a partir dos arquivos fornecidos; não houve mudanças funcionais planejadas no snapshot. Nesta fase, os módulos têm escopo pequeno e alguns arquivos são apenas scaffolding.

## 9. Implementações e objetivos da próxima versão

**Próxima etapa:** [`v0.4`](../v0.4/README.md).

- Introduzir Skills especializadas e seus arquivos de instruções.
- Criar comandos de gerenciamento de Skills no CLI.

## 10. Segurança, autoria e contribuição

- **Criador e responsável pelo projeto:** **Guilherme Hendrik**.
- GitHub: https://github.com/MrHendrix0611
- LinkedIn: https://www.linkedin.com/in/guilherme-hendrik-59775326a/
- Instagram: https://www.instagram.com/hxtech_/
- Nunca publique `.env`, credenciais, logs de uso ou checkpoints pessoais.
- Versões históricas são disponibilizadas para estudo da evolução; não devem ser presumidas seguras para produção.
- Para informações sobre publicação e segurança, consulte [`SECURITY.md`](../../SECURITY.md).
