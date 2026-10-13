'use strict';
const state = { seq:0, activeApproval:null, lastHistory:'', view:'agent', events:[], renderedJobs:new Set(), socket:null };
const $ = selector => document.querySelector(selector);
const api = async (path, method='GET', data) => {
  const response = await fetch('/api' + path, { method,
    headers:{'X-Tesla-Token':window.TESLA_TOKEN, ...(data !== undefined ? {'Content-Type':'application/json'} : {})},
    body: data === undefined ? undefined : JSON.stringify(data) });
  const body = await response.json().catch(() => ({}));
  if(!response.ok) throw new Error(body.detail || 'Falha ao acessar a API (' + response.status + ')');
  return body;
};
function notice(message, error=false){ const toast=$('#toast'); toast.textContent=String(message); toast.style.borderColor=error?'#dd7185':'#4c5470'; toast.classList.add('show'); clearTimeout(notice.timer); notice.timer=setTimeout(()=>toast.classList.remove('show'),5000); }
async function action(f){try{await f();}catch(e){notice(e.message||String(e),true);}}
function showView(name){state.view=name; document.querySelectorAll('.view').forEach(node=>node.classList.toggle('active',node.id==='view-'+name)); document.querySelectorAll('.rail-button').forEach(node=>node.classList.toggle('active',node.dataset.view===name)); if(name==='knowledge')loadMemory();if(name==='tools')loadTools();}
for(const button of document.querySelectorAll('.rail-button')) button.addEventListener('click',()=>showView(button.dataset.view));
function renderHistory(messages){ const normalized=JSON.stringify(messages||[]); if(normalized===state.lastHistory)return;state.lastHistory=normalized; const root=$('#chat-history');root.replaceChildren(); if(!messages||!messages.length){root.innerHTML='<div class="intro-chat"><div class="intro-icon">✧</div><strong>Seu parceiro de desenvolvimento</strong><p>Selecione uma pasta e descreva o que você deseja construir, corrigir ou analisar.</p></div>';return;}for(const entry of messages){const bubble=document.createElement('div');bubble.className='bubble '+(entry.role==='user'?'user':'assistant');bubble.textContent=entry.content||'';root.appendChild(bubble);}root.scrollTop=root.scrollHeight;}
function renderTeam(team){
  $('#team-status').textContent=team.status||'Sem plano';
  const overview=$('#team-summary');overview.replaceChildren();
  for(const [label,value] of [['QA verificado',team.qa_verified],['Revisor aprovado',team.review_approved],['Ciclo',team.revisions ?? 0]]){
    if(!team.roles)break;
    const chip=document.createElement('span');chip.className='pill-detail';chip.textContent=label+': '+(typeof value==='boolean'?(value?'Sim':'Não'):value);overview.append(chip);
  }
  const root=$('#role-steps');const previousScroll=root.scrollTop;
  const expanded=new Set([...root.querySelectorAll('details[open]')].map(x=>x.dataset.step));root.replaceChildren();
  if(!team.roles){root.textContent=team.message||'Nenhum plano multiagentes ativo.';return;}
  for(const step of team.roles){
    const item=document.createElement('article');item.className='role-step';
    const head=document.createElement('div');head.className='role-step-head';
    const title=document.createElement('strong');title.textContent='#'+step.id+' · '+step.role.toUpperCase();
    const status=document.createElement('span');status.className='status';status.dataset.state=step.status;status.textContent=step.status;
    head.append(title,status);item.append(head);
    const description=document.createElement('p');description.textContent=step.description;item.append(description);
    const toolCount=document.createElement('p');toolCount.className='role-tools';toolCount.textContent=`Ferramentas: ${step.tools} · Tentativas: ${step.attempts}`;item.append(toolCount);
    if(step.verdict){const v=document.createElement('strong');v.className='pill-detail';v.textContent='Veredito: '+step.verdict;item.append(v);}
    if(step.verdict_reason){const msg=document.createElement('p');msg.textContent=step.verdict_reason;item.append(msg);}
    if(step.qa_evidence?.verified){const qa=document.createElement('p');qa.textContent=`QA real: ${step.qa_evidence.test_count} testes, exit_code ${step.qa_evidence.exit_code}`;item.append(qa);}
    if(step.result){
      const details=document.createElement('details');details.dataset.step=String(step.id);details.open=expanded.has(String(step.id)) || ['paused','failed'].includes(step.status);
      const summary=document.createElement('summary');summary.textContent='Ver relatório completo';
      const report=document.createElement('div');report.className='rich-report';report.textContent=String(step.result);
      const copy=document.createElement('button');copy.className='secondary small';copy.textContent='Copiar relatório';
      copy.onclick=()=>navigator.clipboard.writeText(String(step.result)).then(()=>notice('Relatório copiado')).catch(()=>notice('Não foi possível copiar',true));
      details.append(summary,report,copy);item.append(details);
    }
    root.append(item);
  }
  root.scrollTop=previousScroll;
}
function renderModels(model){const control=$('#model-select');const prior=control.value;control.replaceChildren();for(const name of (model.available||[])){const opt=document.createElement('option');opt.value=name;opt.textContent=name.toUpperCase();control.appendChild(opt);}if(model.selected)control.value=model.selected;control.disabled=!(model.available||[]).length;}
function renderStatus(data){const ready=data.engine_ready;const oldWorkspace=state.currentWorkspace;state.currentWorkspace=data.workspace;$('#connection').textContent=ready?'Agente pronto':'Configure o .env';$('#connection').style.color=ready?'#63d6ae':'#ffc475';$('#workspace').value=data.workspace||$('#workspace').value;$('#project-indicator').textContent=data.workspace?'Ativo':'Nenhum projeto';$('#activity-project').textContent=data.workspace?data.workspace.split(/[\\/]/).pop():'Não selecionado';state.activeJob=data.active_job;renderModels(data.model||{});renderTeam(data.team||{});renderHistory(data.history||[]);if(data.workspace && oldWorkspace!==data.workspace)loadFiles().catch(()=>{});for(const job of data.jobs||[]){if(['completed','failed','cancelled','paused','incomplete'].includes(job.status)){if(!state.renderedJobs.has(job.id)){state.renderedJobs.add(job.id);if(job.error)notice(job.error,true);if(job.kind!=='chat'&&job.result)activity('Resultado · '+job.kind+' ('+job.status+')',job.result.slice(0,800));if(job.status==='incomplete')notice('Execução incompleta; confira alterações e retome a tarefa.',true);if(job.status==='paused')notice('Missão pausada; consulte a etapa e seu parecer.',true);}}}const busy=!!data.active_job;$('#job-cancel').disabled=!busy;$('#chat-send').disabled=busy;$('#team-run').disabled=busy;$('#model-select').disabled=busy||!ready;for(const approval of data.pending_approvals||[]){if(state.activeApproval===null){displayApproval(approval);break;}}if(!data.pending_approvals?.some(a=>a.id===state.activeApproval?.id)&&state.activeApproval){$('#approval-dialog').close();state.activeApproval=null;}}
async function refresh(){try{renderStatus(await api('/status'));}catch(e){$('#connection').textContent='Sem conexão';}}
state.selectedFile=null;state.selectedContent='';
async function loadFiles(){const data=await api('/files');const root=$('#file-tree');root.replaceChildren();if(!data.files.length){root.textContent='Projeto vazio.';return;}for(const item of data.files){const button=document.createElement('button');button.className='file-item';button.textContent=item.path;button.title=item.path;button.addEventListener('click',()=>action(async()=>{const file=await api('/file?path='+encodeURIComponent(item.path));state.selectedFile=file.path;state.selectedContent=file.content;$('#code-view').textContent=file.content;$('#selected-file').textContent=file.path;document.querySelectorAll('.file-item').forEach(x=>x.classList.remove('selected'));button.classList.add('selected');}));root.appendChild(button);}}
function activity(title,detail){const root=$('#activity-list');if(root.querySelector('.muted'))root.replaceChildren();const el=document.createElement('div');el.className='event-item';const when=document.createElement('div');when.className='when';when.textContent=new Date().toLocaleTimeString('pt-BR');const label=document.createElement('strong');label.textContent=title;const text=document.createElement('p');text.textContent=detail;el.append(when,label,text);root.prepend(el);while(root.children.length>35)root.lastChild.remove();}
function displayApproval(a){state.activeApproval=a;const titles={tool:'Autorizar ferramenta?',paid:'Autorizar chamada paga?',step:'Executar etapa do time?'};$('#approval-title').textContent=titles[a.kind]||'Autorizar ação?';const d=a.details||{};$('#approval-description').textContent=[d.tool,d.path,d.role,d.workspace,d.description].filter(Boolean).join(' · ');$('#approval-preview').textContent=d.preview||JSON.stringify(d,null,2);$('#approval-dialog').showModal();}
function processEvent(e){if(e.id<=state.seq)return;state.seq=e.id;const d=e.data||{};if(e.type==='approval_requested'){activity('Autorização solicitada',d.kind+' · '+(d.details?.tool||d.details?.role||''));if(!state.activeApproval)displayApproval(d);}else if(e.type==='team_step'){activity('Etapa de agente',d.role+' · '+d.description);}else if(e.type==='job_finished'){activity('Execução '+d.status,d.job.slice(0,8));refresh();loadFiles().catch(()=>{});}else if(e.type==='job_started'){activity('Execução iniciada',d.kind);}else if(e.type==='project_selected'){activity('Projeto selecionado',d.path);}else if(e.type==='approval_resolved'){activity('Autorização respondida',d.approved?'Permitida':'Negada');refresh();}else if(e.type==='model_selected'){activity('Modelo alterado',d.provider);}}
function connect(){const proto=location.protocol==='https:'?'wss:':'ws:';const ws=new WebSocket(proto+'//'+location.host+'/ws?token='+encodeURIComponent(window.TESLA_TOKEN));state.socket=ws;ws.onmessage=ev=>{try{processEvent(JSON.parse(ev.data));}catch(e){console.warn('Event decode failed',e);}};ws.onclose=()=>{setTimeout(connect,2000);};}
$('#approval-allow').addEventListener('click',ev=>{ev.preventDefault();resolveApproval(true);});$('#approval-deny').addEventListener('click',ev=>{ev.preventDefault();resolveApproval(false);});$('#approval-dialog').addEventListener('cancel',ev=>{ev.preventDefault();resolveApproval(false);});
async function resolveApproval(approved){const current=state.activeApproval;if(!current)return;$('#approval-dialog').close();state.activeApproval=null;await action(()=>api('/approvals/'+current.id,'POST',{approved}));refresh();}
$('#project-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{const path=$('#workspace').value.trim();await api('/project','POST',{path});await loadFiles();await refresh();notice('Projeto selecionado.');});});
$('#refresh-files').addEventListener('click',()=>action(loadFiles));
$('#file-diff').addEventListener('click',()=>action(async()=>{if(!state.selectedFile)throw Error('Selecione primeiro um arquivo.');const data=await api('/diff?path='+encodeURIComponent(state.selectedFile));$('#code-view').textContent=typeof data.diff==='string'?data.diff:JSON.stringify(data.diff,null,2);}));
$('#show-file').addEventListener('click',()=>{$('#code-view').textContent=state.selectedContent||'Selecione um arquivo.';});
$('#chat-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{const prompt=$('#chat-input').value.trim();if(!prompt)return;await api('/chat','POST',{prompt});$('#chat-input').value='';await refresh();});});
$('#chat-input').addEventListener('keydown',ev=>{if(ev.key==='Enter'&&(ev.ctrlKey||ev.metaKey)){ev.preventDefault();$('#chat-form').requestSubmit();}});
$('#model-select').addEventListener('change',ev=>action(async()=>{await api('/models','POST',{provider:ev.target.value});await refresh();}));
$('#team-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{const objective=$('#team-objective').value.trim();await api('/team/plan','POST',{objective});notice('Planejamento iniciado.');refresh();});});
$('#team-run').addEventListener('click',()=>action(async()=>{await api('/team/run','POST');notice('Execução iniciada. Aguarde as aprovações.');refresh();}));
$('#team-cancel').addEventListener('click',()=>action(async()=>{if(!confirm('Cancelar o plano atual?'))return;await api('/team/cancel','POST');refresh();}));
$('#job-cancel').addEventListener('click',()=>action(async()=>{if(!state.activeJob)throw Error('Nenhuma execução ativa.');const info=await api('/jobs/'+state.activeJob+'/cancel','POST');notice(info.note||'Cancelamento solicitado.');}));
$('#team-rework').addEventListener('click',()=>action(async()=>{await api('/team/rework','POST');refresh();}));
$('#team-retry').addEventListener('click',()=>action(async()=>{const id=Number($('#retry-step').value);if(!Number.isInteger(id)||id<1)throw Error('Informe o número de uma etapa.');await api('/team/retry/'+id,'POST');refresh();}));
$('#recall-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{renderRecall(await api('/recall','POST',{query:$('#recall-query').value}));});});
$('#remember-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{await api('/remember','POST',{query:$('#remember-note').value});$('#remember-note').value='';await loadMemory();notice('Nota salva no projeto.');});});
async function loadMemory(){await action(async()=>{const data=await api('/memory');const root=$('#memory-list');root.replaceChildren();for(const note of data.notes||[]){const item=document.createElement('div');item.className='memory-note';item.textContent=note.text||'';root.appendChild(item);}if(!root.children.length)root.textContent='Nenhuma nota salva.';});}
async function loadTools(){await action(async()=>{renderTools(await api('/tools'));await loadJobHistory();});}
$('#refresh-tools').addEventListener('click',loadTools);
$('#test-form').addEventListener('submit',ev=>{ev.preventDefault();action(async()=>{await api('/test','POST',{target:$('#test-target').value||'all'});notice('Teste aguardando autorização.');});});
refresh().then(()=>api('/events?after=0').then(d=>d.events.forEach(processEvent)).catch(()=>{}));connect();setInterval(refresh,2200);

function renderRecall(data){
  const root=$('#recall-result');root.replaceChildren();
  for(const note of data.notes||[]){const card=document.createElement('div');card.className='recall-card';const title=document.createElement('strong');title.textContent='Memória do projeto';const body=document.createElement('pre');body.textContent=note.text||'';card.append(title,body);root.append(card);}
  for(const hit of data.sources||[]){const card=document.createElement('div');card.className='recall-card';const title=document.createElement('strong');title.textContent=`${hit.file||'Código'} · linhas ${hit.start_line||'?'}–${hit.end_line||'?'}`;const body=document.createElement('pre');body.textContent=hit.snippet||'';card.append(title,body);root.append(card);}
  if(!root.children.length)root.textContent='Nenhuma memória ou trecho relacionado encontrado.';
}
function renderTools(data){
  const root=$('#tools-info');root.replaceChildren();
  const heading=(text)=>{const h=document.createElement('div');h.className='tool-heading';h.textContent=text;root.append(h);};
  heading('Ferramentas disponíveis');const chips=document.createElement('div');chips.className='tool-chips';
  for(const name of data.tools||[]){const c=document.createElement('span');c.className='tool-chip';c.textContent=name;chips.append(c);}root.append(chips);
  heading('Consumo e provedores');const metrics=document.createElement('div');metrics.className='metrics';
  const usage=data.usage||{};for(const [key,val] of Object.entries(usage)){
    if(typeof val==='object'||val===null)continue;
    const item=document.createElement('div');item.className='metric';const amount=document.createElement('strong');amount.textContent=String(val);const label=document.createElement('span');label.textContent=key.replaceAll('_',' ');item.append(amount,label);metrics.append(item);
    if(metrics.children.length>=8)break;
  }if(!metrics.children.length){const e=document.createElement('span');e.textContent='Sem métricas disponíveis';metrics.append(e);}root.append(metrics);
  heading('Servidores MCP');const mcp=document.createElement('div');mcp.className='tool-chips';
  const servers=Array.isArray(data.mcp)?data.mcp:Object.entries(data.mcp||{});
  for(const server of servers){const c=document.createElement('span');c.className='tool-chip';c.textContent=typeof server==='string'?server:Array.isArray(server)?server[0]:String(server.name||'Servidor');mcp.append(c);}
  if(!mcp.children.length)mcp.textContent='Nenhum servidor MCP conectado';root.append(mcp);
  const more=document.createElement('details');more.className='tool-details';const summary=document.createElement('summary');summary.textContent='Dados técnicos e última evidência';const dump=document.createElement('pre');dump.textContent=JSON.stringify({mcp:data.mcp,usage:data.usage,last_evidence:data.last_evidence},null,2);more.append(summary,dump);root.append(more);
}
$('#activity-clear').addEventListener('click',()=>{$('#activity-list').replaceChildren();notice('Eventos visuais limpos (sem excluir logs de auditoria).');});

async function loadJobHistory(){
  const root=$('#job-history');if(!root)return;
  const data=await api('/jobs/history');root.replaceChildren();
  for(const job of (data.jobs||[]).slice(-20).reverse()){
    const card=document.createElement('div');card.className='history-row';
    const headline=document.createElement('strong');headline.textContent=`${job.kind} · ${job.status}`;
    const details=document.createElement('span');details.textContent=new Date(job.timestamp*1000).toLocaleString('pt-BR');
    card.append(headline,details);if(job.error){const e=document.createElement('p');e.textContent=job.error;card.append(e);}
    root.append(card);
  }
  if(!root.children.length)root.textContent='Nenhuma execução registrada.';
}
