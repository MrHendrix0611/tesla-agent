# Política de segurança e publicação

**Projeto:** Tesla Agent · **Criador:** Guilherme Hendrik

## Antes de publicar

- Nunca versionar `.env`, tokens, segredos, caches, logs, `.tesla/`, dados pessoais ou snapshots contendo credenciais.
- Usar `.env.example` com variáveis vazias para as credenciais.
- Rotacionar quaisquer chaves que tenham sido incluídas em ZIPs ou repositórios antigos, mesmo após excluí-las daqui.
- Conferir manualmente histórico Git, releases, issues e anexos: scanners não garantem ausência absoluta de segredos.
- Servidores MCP e ferramentas de terminal executam código com permissões locais; confiar apenas em provedores/servidores verificados.
- Consultar o log de mudanças e limitações da versão antes de uso em produção.

## Relato responsável

Para comunicar vulnerabilidades, prefira uma mensagem privada ao mantenedor por meio do perfil [GitHub](https://github.com/MrHendrix0611). Não publique exploits ou credenciais em issues públicas.

## Licença

Ainda não definida pelo mantenedor; nenhuma licença foi escolhida automaticamente neste pacote.
