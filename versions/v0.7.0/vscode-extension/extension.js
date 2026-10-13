/* Tesla Agent 0.7 - VS Code panel. No external npm dependencies. */
'use strict';
const vscode = require('vscode');
const crypto = require('crypto');

function apiUrl() {
  const address = vscode.workspace.getConfiguration('tesla').get('apiUrl', 'http://127.0.0.1:8765');
  const url = new URL(address);
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) {
    throw new Error('O Tesla aceita apenas endereços HTTP locais.');
  }
  return url.origin;
}

async function request(context, path, method='GET', body, tokenOverride) {
  const token = tokenOverride || await context.secrets.get('tesla.local.token');
  if (!token) throw Error('Configure o token de acesso em "Tesla: Conectar ao agente local".');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 18000);
  try {
    const response = await fetch(apiUrl()+'/api'+path, {method, headers:{
      'X-Tesla-Token':token,
      ...(body !== undefined ? {'Content-Type':'application/json'}:{})},
      body: body !== undefined ? JSON.stringify(body):undefined, signal:controller.signal});
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || 'Erro HTTP '+response.status);
    return data;
  } finally {clearTimeout(timeout);}
}

function panelMarkup(nonce, logoUri, cspSource) {
  // User-provided strings never interpolated into HTML: all updates use textContent.
  return `<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${cspSource}; style-src 'nonce-${nonce}'; script-src 'nonce-${nonce}';"/>
  <style nonce="${nonce}">
    body{font:13px var(--vscode-font-family);color:var(--vscode-foreground);background:var(--vscode-editor-background);padding:16px;margin:0}
    h2{margin:0 0 14px}p{color:var(--vscode-descriptionForeground)}button,textarea{font:inherit;padding:10px;border:1px solid var(--vscode-input-border);color:var(--vscode-foreground);background:var(--vscode-input-background);border-radius:5px}
    button{cursor:pointer}button.main{background:var(--vscode-button-background);color:var(--vscode-button-foreground);border:none}button:disabled{opacity:.6}
    textarea{width:100%;box-sizing:border-box;min-height:100px;resize:vertical}
    .row{display:flex;align-items:center;gap:8px;margin:12px 0}.stream{height:48vh;overflow:auto;border:1px solid var(--vscode-input-border);padding:10px;border-radius:6px}
    .bubble{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0;padding:11px;background:var(--vscode-sideBar-background);border-radius:8px}
    .bubble.user{border-left:3px solid var(--vscode-button-background)}.bubble.assistant{border-left:3px solid #58c69f}
    .dialog{border:1px solid var(--vscode-focusBorder);padding:12px;margin:10px 0}.dialog pre{white-space:pre-wrap;max-height:120px;overflow:auto}
    .muted{opacity:.7}
  </style></head><body>
  <h2><img src="${logoUri}" alt="Tesla" style="width:37px;height:37px;vertical-align:middle;object-fit:contain;margin-right:6px"/> Tesla Agent</h2>
  <p id="status">Conectando ao agente local...</p><button id="reconnect">Reconectar ao servidor</button>
  <div class="row"><button id="openBrowser">Abrir dashboard</button><button id="chooseProject">Selecionar workspace</button></div>
  <div id="approvals"></div>
  <div class="stream" id="conversation"></div>
  <div class="row"><span class="muted">Mensagem para o Tesla</span></div>
  <textarea id="prompt" placeholder="Peça uma análise ou alteração..."></textarea>
  <div class="row"><button class="main" id="send">Enviar</button><button id="refresh">Atualizar</button></div>
  <script nonce="${nonce}">
  const vscode=acquireVsCodeApi();const $=id=>document.getElementById(id);
  $('send').onclick=()=>{const prompt=$('prompt').value.trim();if(prompt){vscode.postMessage({command:'chat',prompt});$('prompt').value='';}};
  $('refresh').onclick=()=>vscode.postMessage({command:'refresh'});
  $('reconnect').onclick=()=>vscode.postMessage({command:'reconnect'});
  $('chooseProject').onclick=()=>vscode.postMessage({command:'project'});
  $('openBrowser').onclick=()=>vscode.postMessage({command:'browser'});
  window.addEventListener('message',e=>{
    const m=e.data;if(m.command==='error'){$('status').textContent='Erro: '+m.message;return;}
    if(m.command!=='state')return;
    const s=m.status;
    $('status').textContent='Projeto: '+(s.workspace||'não selecionado')+(s.active_job?' · Executando...':'');
    $('send').disabled=!!s.active_job;
    const root=$('conversation');root.replaceChildren();
    for(const item of s.history||[]){const node=document.createElement('div');node.className='bubble '+(item.role==='user'?'user':'assistant');node.textContent=item.content||'';root.appendChild(node);}root.scrollTop=root.scrollHeight;
    const panel=$('approvals');panel.replaceChildren();
    for(const req of s.pending_approvals||[]){const card=document.createElement('div');card.className='dialog';
      const title=document.createElement('strong');title.textContent='Autorização: '+req.kind;
      const pre=document.createElement('pre');pre.textContent=JSON.stringify(req.details||{},null,2);
      const allow=document.createElement('button');allow.textContent='Permitir uma vez';allow.className='main';allow.onclick=()=>vscode.postMessage({command:'approval',id:req.id,approved:true});
      const deny=document.createElement('button');deny.textContent='Negar';deny.onclick=()=>vscode.postMessage({command:'approval',id:req.id,approved:false});
      card.append(title,pre,allow,deny);panel.appendChild(card);
    }
  });
  vscode.postMessage({command:'refresh'});
  </script></body></html>`;
}

function activate(context) {
  const configure = vscode.commands.registerCommand('tesla.configure', async () => {
    const token = await vscode.window.showInputBox({prompt:'Token exibido ao executar py -m web.main',password:true,ignoreFocusOut:true});
    if (!token) return;
    try {
      const status = await request(context, '/status', 'GET', undefined, token.trim());
      if (!status || !Object.hasOwn(status, 'engine_ready')) throw Error('Resposta inesperada do servidor Tesla');
      await context.secrets.store('tesla.local.token', token.trim());
      vscode.window.showInformationMessage('Tesla conectado e token validado com sucesso.');
    } catch (error) {
      vscode.window.showErrorMessage('Tesla: token recusado ou servidor indisponível. '+String(error.message||error));
    }
  });
  const browser = vscode.commands.registerCommand('tesla.openDashboard', () => vscode.env.openExternal(vscode.Uri.parse(apiUrl())));
  const panelCmd = vscode.commands.registerCommand('tesla.openPanel', () => {
    const mediaRoot = vscode.Uri.joinPath(context.extensionUri, 'media');
    const panel = vscode.window.createWebviewPanel('tesla', 'Tesla Agent', vscode.ViewColumn.Beside, {enableScripts:true,retainContextWhenHidden:true,localResourceRoots:[mediaRoot]});
    const nonce=crypto.randomBytes(16).toString('hex');
    const logo = panel.webview.asWebviewUri(vscode.Uri.joinPath(mediaRoot, 'tesla-mark.png'));
    panel.webview.html=panelMarkup(nonce, logo.toString(), panel.webview.cspSource);
    let busy=false;
    const refresh=async()=>{if(busy)return;busy=true;try{panel.webview.postMessage({command:'state',status:await request(context,'/status')});}catch(e){panel.webview.postMessage({command:'error',message:String(e.message||e)});}finally{busy=false;}};
    const timer=setInterval(refresh,1500);
    panel.onDidDispose(()=>clearInterval(timer));
    panel.webview.onDidReceiveMessage(async msg=>{
      try{
        if(msg.command==='reconnect'){await vscode.commands.executeCommand('tesla.configure');}
        else if(msg.command==='chat'){await request(context,'/chat','POST',{prompt:String(msg.prompt||'')});}
        else if(msg.command==='approval'){await request(context,'/approvals/'+encodeURIComponent(msg.id),'POST',{approved:msg.approved===true});}
        else if(msg.command==='project'){
          const folder=vscode.workspace.workspaceFolders?.[0];
          if(!folder){vscode.window.showWarningMessage('Abra uma pasta no VS Code antes.');return;}
          await request(context,'/project','POST',{path:folder.uri.fsPath});
        }
        else if(msg.command==='browser') await vscode.env.openExternal(vscode.Uri.parse(apiUrl()));
        await refresh();
      }catch(e){vscode.window.showErrorMessage('Tesla: '+String(e.message||e));await refresh();}
    });
    refresh();
  });
  context.subscriptions.push(configure,browser,panelCmd);
}
function deactivate(){}
module.exports={activate,deactivate};
