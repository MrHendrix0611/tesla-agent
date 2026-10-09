# Publicação no GitHub — Tesla Agent

**Perfil:** https://github.com/MrHendrix0611

## Conferência prévia

1. Abra esta pasta em seu computador e revise o código-fonte.
2. Execute `python scripts/verificar_publicacao.py` para examinar os arquivos e potenciais segredos.
3. Não copie `.env` dos projetos antigos; configure as chaves apenas em instalações locais.
4. Se chaves já foram incluídas em outros ZIPs, **revogue-as e gere novas** antes da publicação.
5. A licença ainda não foi definida; adicione `LICENSE` antes de apresentar o projeto como open source licenciado.

## Git

O pacote vem organizado por pastas `versions/v0.x/` e inclui o código correspondente a cada versão.

Se o ZIP já incluir `.git`, não faça `git init` novamente:

```powershell
git status
git tag --list
git remote add origin https://github.com/MrHendrix0611/tesla-agent.git
git push -u origin main
git push origin --tags
```

Crie antes um repositório **vazio**, sem README inicial, em `https://github.com/new`, caso ainda não exista.

> Os commits e tags foram reconstruídos para apresentar snapshots históricos. Não representam datas de commits originais. As tags apontam para a adição de cada pasta-versionada, e não para uma raiz de código correspondente a cada versão.
