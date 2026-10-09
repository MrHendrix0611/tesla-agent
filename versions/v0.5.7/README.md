# Tesla Agent V0.5.7 — Coding Agent: diff, rollback e testes

> **Versão histórica** · [Índice de versões](../../README.md) · **Criador:** Guilherme Hendrik  
> [GitHub](https://github.com/MrHendrix0611) · [LinkedIn](https://www.linkedin.com/in/guilherme-hendrik-59775326a/) · [Instagram](https://www.instagram.com/hxtech_/)

## 1. Descrição

Camada para evoluir projetos existentes com edição controlada, validação e recuperação.

## 2. Objetivo

Permitir alterações seguras de código com verificação real do resultado.

## 3. Funcionalidades e implementações desta versão

- `core/coding.py` implementa funcionalidades de edição, comparação e rollback de arquivos.
- Ferramentas de execução de `unittest` retornam evidência do resultado.
- Vinculação a um workspace explícito para operações sensíveis.
- CLI inclui `/workspace`, `/diff`, `/rollback`, `/test` e `/diagnose`.

### Principais arquivos e responsabilidades

- `core/coding.py` — edição e rollback
- `core/executor.py` — execução do plano
- `tools/terminal.py` — comandos e testes
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

**Observação:** comandos de barra só devem ser usados dentro da CLI do Tesla, após aparecer `Você:`. Mensagens comuns são encaminhadas ao modelo. Não execute comandos desconhecidos sem revisar permissões.

## 6. Fluxograma da arquitetura

```mermaid
flowchart TD
    CLI[CLI] --> EX[Planner e Executor]
    EX --> AG[Agent]
    AG --> C[Coding Workspace]
    C --> D[Diff e Patch]
    C --> B[Backup e Rollback]
    AG --> R[LLMRouter]
    AG --> T[Permissões e Tests]
    T --> C
```

## 7. Fluxograma de funcionamento

```mermaid
flowchart TD
    P[Selecionar workspace] --> R[Ler código atual]
    R --> M[Propor alteração]
    M --> D[Gerar diff]
    D --> A{Usuário aprova?}
    A -->|Sim| W[Aplicar alteração com backup]
    A -->|Não| X[Descartar]
    W --> T[Executar testes]
    T --> S{Falhou?}
    S -->|Sim| B[Corrigir ou rollback]
    S -->|Não| C[Confirmar execução]
```

## 8. Limitações e pontos de atenção

- A segurança de comandos depende das restrições do harness e da confirmação humana; não há isolamento completo por contêiner.

O código desta versão foi preservado como snapshot histórico. A documentação foi reescrita a partir dos arquivos fornecidos; não houve mudanças funcionais planejadas no snapshot.

## 9. Implementações e objetivos da próxima versão

**Próxima etapa:** [`v0.5.8`](../v0.5.8/README.md).

- Implementar memória explícita por projeto e recuperação lexical de código (RAG).
- Compactar o histórico de conversa e separar contexto entre projetos.

## 10. Segurança, autoria e contribuição

- **Criador e responsável pelo projeto:** **Guilherme Hendrik**.
- GitHub: https://github.com/MrHendrix0611
- LinkedIn: https://www.linkedin.com/in/guilherme-hendrik-59775326a/
- Instagram: https://www.instagram.com/hxtech_/
- Nunca publique `.env`, credenciais, logs de uso ou checkpoints pessoais.
- Versões históricas são disponibilizadas para estudo da evolução; não devem ser presumidas seguras para produção.
- Para informações sobre publicação e segurança, consulte [`SECURITY.md`](../../SECURITY.md).
