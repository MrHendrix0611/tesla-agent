# Tesla V0.7.0 — Checklist Windows pós-correções

Abra o PowerShell na pasta do pacote, com Python instalado:

```powershell
py -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
py -m unittest discover -s tests -v
py -m web.main
```

Se já possui `.env` privado, copie-o somente para seu computador; jamais envie o arquivo ao GitHub.

## Testes manuais indispensáveis

1. **Marca:** acesse http://127.0.0.1:8765. Confirme que a barra lateral mostra somente o emblema orbital azul (sem a letra T e sem a palavra TESLA na imagem).
2. **Workspace:** selecione `F:\TeslaTestes\Projeto070`, reinicie o servidor e confirme que o workspace é restaurado.
3. **Chat:** solicite análise de um arquivo e confirme que retorna uma conclusão ou `incomplete` (e não marca interrupções como concluídas).
4. **Multiagentes:** crie e execute uma missão com Arquiteto, Dev, QA e Revisor. Confirme os contadores do QA e o `VEREDITO: APROVADO` estruturado. Simule também `AJUSTES` e confira `paused` com relatório completo e retry da revisão.
5. **CLI compartilhada:** durante uma pausa, abra outro terminal em `py -m cli.main`, execute `/project F:\TeslaTestes\Projeto070` e `/team`. Confira se exibe o mesmo plano, sem criar outro.
6. **Permissões:** negue uma escrita e confira que não foi aplicada. Autorize escrita e testes apenas em pasta de teste.
7. **Ferramentas:** abra a aba e confira cartões de ferramentas, consumo e histórico de execuções.
8. **VS Code:** com o servidor aberto, pressione F5 em `vscode-extension`, conecte usando token atual, teste `chat`, `write_file`, negação, `run_tests` e sincronização Web. Reinicie o servidor e confirme o fluxo de **Reconectar**.
9. **RAG:** salve uma nota, faça uma consulta e confirme a persistência depois de reiniciar.

**Critério de publicação:** se alguma dessas verificações falhar, registre o log e não publique a V0.7.0 ainda.
