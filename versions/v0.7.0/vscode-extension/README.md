# Tesla Agent — extensão inicial VS Code

A extensão abre um **painel nativo de chat** integrado ao Tesla local, apresenta aprovações de ferramentas/modelos pagos e permite selecionar a pasta aberta no VS Code. A área principal de planos, diffs e MCP fica no Dashboard Web.

## Instalação de desenvolvimento (sem publicar na Marketplace)

1. No diretório `versions/v0.7.0`, instale as dependências Python, configure seu `.env` e execute `py -m web.main`.
2. Anote o token gerado e exibido no terminal (não coloque esse token no código nem no Git).
3. Abra `vscode-extension/` no VS Code. Pressione `F5` para iniciar uma janela **Extension Development Host**.
4. Na janela de desenvolvimento, execute `Ctrl+Shift+P` → **Tesla: Conectar ao agente local**, e informe o token.
5. Execute **Tesla: Abrir painel Agent**. Abra uma pasta de projeto e clique em **Selecionar workspace**.

O token é armazenado no `SecretStorage` do VS Code. É um token **temporário**: a cada reinício do servidor, informe o novo token. Não são necessários `npm install` nem TypeScript para executar esta extensão inicial.

O painel requer VS Code moderno com `fetch` disponível no Extension Host (VS Code ^1.90). O processo do dashboard e do VS Code devem rodar na mesma máquina; acesso remoto não está contemplado.


### Reconexão e token

1. Execute `py -m web.main` e mantenha o servidor aberto.
2. No Extension Development Host, use `Tesla: Conectar ao agente local` e informe o token **da execução atual**.
3. A extensão verifica o token em `/api/status` **antes de salvá-lo**. Caso o token esteja incorreto, mostra o erro sem substituir a credencial válida anterior.
4. Se o servidor reiniciar, clique em **Reconectar ao servidor** no painel ou execute o mesmo comando de conexão novamente.

A nova identidade visual usa `media/tesla-mark.png`, sem o nome na imagem.
