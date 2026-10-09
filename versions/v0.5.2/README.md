# Hefesto Agent V0.5.2 — Smart Router e controle de uso

> **Versão histórica** · [Índice de versões](../../README.md) · **Criador:** Guilherme Hendrik  
> [GitHub](https://github.com/MrHendrix0611) · [LinkedIn](https://www.linkedin.com/in/guilherme-hendrik-59775326a/) · [Instagram](https://www.instagram.com/hxtech_/)

## 1. Descrição

O roteamento passa a considerar o tipo da tarefa e limites locais de uso.

## 2. Objetivo

Escolher modelos de forma mais adequada e reduzir chamadas desnecessárias ou indisponíveis.

## 3. Funcionalidades e implementações desta versão

- `llm/intelligence.py` reúne `ModelSelector`, `UsageTracker` e `BudgetGuard`.
- Classificação heurística de tarefas de programação, arquitetura, dados e uso geral.
- Fallback entre provedores, cooldown e limites locais opcionais.
- CLI ganha `/router` e `/usage`.

### Principais arquivos e responsabilidades

- `llm/intelligence.py` — seletor, uso e orçamento
- `llm/router.py` — roteamento e fallback
- `tools/registry.py` — ferramentas

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

**Observação:** comandos de barra só devem ser usados dentro da CLI do Hefesto, após aparecer `Você:`. Mensagens comuns são encaminhadas ao modelo. Não execute comandos desconhecidos sem revisar permissões.

## 6. Fluxograma da arquitetura

```mermaid
flowchart TD
    CLI[CLI] --> A[Agent]
    A --> R[Smart LLMRouter]
    R --> MS[ModelSelector]
    R --> UT[UsageTracker]
    R --> BG[BudgetGuard]
    MS --> P[Groq - Gemini - OpenRouter - Ollama]
    P --> R
    A --> TR[ToolRegistry e Permissions]
```

## 7. Fluxograma de funcionamento

```mermaid
flowchart TD
    U[Solicitação] --> C[Classificar tarefa]
    C --> S[Selecionar provedor]
    S --> Q{Disponível e dentro do limite?}
    Q -->|Sim| G[Gerar resposta]
    Q -->|Não| F[Tentar fallback]
    F --> S
    G --> T[Registrar consumo e escolha]
    T --> R[Responder]
```

## 8. Limitações e pontos de atenção

- As estimativas locais não substituem dados oficiais de faturamento dos provedores.

O código desta versão foi preservado como snapshot histórico. A documentação foi reescrita a partir dos arquivos fornecidos; não houve mudanças funcionais planejadas no snapshot.

## 9. Implementações e objetivos da próxima versão

**Próxima etapa:** [`v0.5.3`](../v0.5.3/README.md).

- Introduzir política explícita de aprovação para uso pago.
- Controlar orçamento e solicitação de consentimento por chamada.

## 10. Segurança, autoria e contribuição

- **Criador e responsável pelo projeto:** **Guilherme Hendrik**.
- GitHub: https://github.com/MrHendrix0611
- LinkedIn: https://www.linkedin.com/in/guilherme-hendrik-59775326a/
- Instagram: https://www.instagram.com/hxtech_/
- Nunca publique `.env`, credenciais, logs de uso ou checkpoints pessoais.
- Versões históricas são disponibilizadas para estudo da evolução; não devem ser presumidas seguras para produção.
- Para informações sobre publicação e segurança, consulte [`SECURITY.md`](../../SECURITY.md).
