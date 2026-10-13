# Tesla Agent v0.7.0 — Notas de publicação

**Criador:** Guilherme Hendrik — [GitHub](https://github.com/MrHendrix0611), [LinkedIn](https://www.linkedin.com/in/guilherme-hendrik-59775326a/), [Instagram](https://www.instagram.com/hxtech_/).

## Escopo da release

Primeira interface visual Web, API local FastAPI e painel de desenvolvimento no VS Code, preservando CLI e harness Python. Inclui permissões explícitas, multiagentes, memória/RAG, consulta de ferramentas/MCP e melhorias de estabilidade.

## Homologação

O autor informou aprovação de **9/9 casos funcionais no Windows**, incluindo multiagentes, revisão, restauração de estado e reconexão VS Code.

Para repetir os testes automatizados com as dependências instaladas:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests -v
```

## Segurança e distribuição

O pacote público remove os logs de uso, o `.env` pessoal e os caches. Use seu próprio `.env` criado a partir de `.env.example`; nunca publique credenciais ou arquivos `.tesla/` de projetos reais.

**Atenção:** API Web exclusiva para uso local via loopback. Esta versão não deve ser exposta publicamente em um servidor acessível pela internet.

[Documentação da versão](README.md) · [Checklist Windows](VALIDACAO_WINDOWS.md) · [Licença MIT](LICENSE).
