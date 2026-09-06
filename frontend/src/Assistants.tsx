import {useEffect, useState} from 'react';
import {Bot, Copy, Plus, ArrowLeft, Play, LockKeyhole, ArrowUp, ArrowDown, X, Square} from 'lucide-react';
import {request} from './platform-api';
import type {Experiment} from './platform-api';
import {useLang} from './i18n';
import './app/styles/assistants.css';

type Config = {name:string;description:string;system_prompt:string;stage:string;permissions:string[];auto_backtest:boolean;chain:string[]};
type Assistant = Config & {id:string;template:boolean;author:string};
type Step = {assistant_id:string;config:Config;status:string;output:string;error?:string;run_id?:string};
type Task = {id:string;assistant_name:string;prompt:string;status:string;output:string;created_at:string;details:{steps?:Step[];index?:number;experiment_id?:string;run_id?:string;backtest_status?:string;run_backtest?:boolean}};
type Catalog = {items:Assistant[];provider:{configured:boolean;model:string}};
const blank:Config = {name:'',description:'',system_prompt:'',stage:'research',permissions:['experiments','metrics'],auto_backtest:false,chain:[]};
const active = (status:string)=>['QUEUED','RUNNING','WAITING_BACKTEST'].includes(status);

function executionPlan(root:Assistant|null,items:Assistant[]):Assistant[]{
  const seen=new Set<string>(),plan:Assistant[]=[];
  function visit(item:Assistant){if(seen.has(item.id))return;seen.add(item.id);plan.push(item);item.chain.forEach(id=>{const child=items.find(a=>a.id===id);if(child)visit(child);});}
  if(root)visit(root);
  return plan;
}

function TaskHistory({tasks,tr,lang,busy,statusLabel,cancel}:{tasks:Task[];tr:(a:string,b:string)=>string;lang:string;busy:boolean;statusLabel:(s:string)=>string;cancel:(id:string)=>void}){
  if(!tasks.length)return <div className="panel small-empty"><Bot size={28}/>{tr('Henüz görev yok. Bir asistan seçerek başlayın.','No tasks yet. Choose an assistant to get started.')}</div>;
  return <section className="ai-task-list">{tasks.map(task=><details className="panel ai-task" key={task.id} open={tasks[0].id===task.id}>
    <summary><b>{task.assistant_name}</b><span className="badge">{statusLabel(task.status)}</span><time>{new Date(task.created_at).toLocaleString(lang==='tr'?'tr-TR':'en-US')}</time></summary>
    <p>{task.prompt}</p>
    {task.details.experiment_id&&<p>{tr('Deney','Experiment')}: <code>{task.details.experiment_id}</code>{task.details.run_id&&<> · Backtest: <code>{task.details.run_id}</code></>}{task.details.backtest_status&&<> · {statusLabel(task.details.backtest_status)}</>}</p>}
    <ol className="ai-steps">{task.details.steps?.map((step,index)=><li key={`${step.assistant_id}-${index}`}><div className="ai-actions"><b>{step.config.name}</b><span className="badge">{statusLabel(step.status)}</span></div>{step.output&&<details><summary>{tr('Adım çıktısı','Step output')}</summary><pre>{step.output}</pre></details>}{step.error&&<p className="ai-error">{step.error}</p>}</li>)}</ol>
    <pre>{task.output||(active(task.status)?tr('Görev arka planda çalışıyor; durum otomatik güncellenir.','Task is running in the background; status updates automatically.'):tr('Henüz çıktı yok.','No output yet.'))}</pre>
    {active(task.status)&&<><button className="secondary" disabled={busy} onClick={()=>cancel(task.id)}><Square size={14}/>{tr('Zinciri durdur','Stop chain')}</button><p>{tr('Başlatılmış backtest çalışmaya devam eder; deney ekranından ayrıca durdurabilirsiniz.','An already started backtest continues; stop it separately from the experiment screen.')}</p></>}
  </details>)}</section>;
}

export default function Assistants({experiments}:{experiments:Experiment[]}) {
  const {lang} = useLang();
  const tr = (a:string,b:string)=>lang==='tr'?a:b;
  const [catalog,setCatalog] = useState<Catalog|null>(null);
  const [tasks,setTasks] = useState<Task[]>([]);
  const [tab,setTab] = useState('assistants');
  const [editing,setEditing] = useState<Assistant|Config|null>(null);
  const [target,setTarget] = useState<Assistant|null>(null);
  const [prompt,setPrompt] = useState('');
  const [experiment,setExperiment] = useState('');
  const [runBacktest,setRunBacktest] = useState(false);
  const [chainChoice,setChainChoice] = useState('');
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const fail = (e:unknown)=>setError(e instanceof Error?e.message:String(e));
  async function load(){const [c,t]=await Promise.all([request<Catalog>('/assistants'),request<Task[]>('/assistant-tasks')]);setCatalog(c);setTasks(t);}
  useEffect(()=>{let active=true;Promise.all([request<Catalog>('/assistants'),request<Task[]>('/assistant-tasks')]).then(([c,t])=>{if(active){setCatalog(c);setTasks(t);}}).catch(e=>{if(active)fail(e);});return()=>{active=false;};},[]);
  const hasActive=tasks.some(task=>active(task.status));
  useEffect(()=>{
    if(!hasActive)return;
    let disposed=false;
    let timer:ReturnType<typeof setTimeout>;
    async function poll(){try{const next=await request<Task[]>('/assistant-tasks');if(!disposed)setTasks(next);}catch(e){if(!disposed)fail(e);}finally{if(!disposed)timer=setTimeout(poll,2000);}}
    timer=setTimeout(poll,1500);
    return()=>{disposed=true;clearTimeout(timer);};
  },[hasActive]);
  async function perform(action:()=>Promise<void>){setBusy(true);setError('');try{await action();}catch(e){fail(e);}finally{setBusy(false);}}
  const readonly = !!editing && 'template' in editing && editing.template;
  function newTask(a:Assistant){setTarget(a);setPrompt('');setExperiment('');setRunBacktest(false);setEditing(null);}
  const plan=executionPlan(target,catalog?.items||[]);
  const hasBacktest=plan.some(a=>a.auto_backtest);
  function moveChild(index:number,direction:number){if(!editing)return;const chain=[...editing.chain];[chain[index],chain[index+direction]]=[chain[index+direction],chain[index]];setEditing({...editing,chain});}
  const statusLabel=(s:string)=>({QUEUED:tr('Sırada','Queued'),RUNNING:tr('Çalışıyor','Running'),WAITING_BACKTEST:tr('Backtest bekleniyor','Waiting for backtest'),COMPLETED:tr('Tamamlandı','Completed'),FAILED:tr('Başarısız','Failed'),CANCELLED:tr('Durduruldu','Cancelled'),PENDING:tr('Bekliyor','Pending')}[s]||s);
  async function clone(a:Assistant){await perform(async()=>{const copy=await request<Assistant>(`/assistants/${a.id}/clone`,'POST');await load();setEditing(copy);});}
  return <section className="ai-assistants">
    <div className="panel-heading"><div><h2><Bot size={22}/> {tr('AI Asistanlar','AI Assistants')}</h2><p>{tr('Araştırma fikirlerini geliştirin, deneyleri inceleyin ve sonuçları değerlendirin.','Develop research ideas, inspect experiments and review results.')}</p></div><button className="primary" disabled={busy} onClick={()=>{setEditing({...blank,permissions:[...blank.permissions]});setTarget(null);}}><Plus size={15}/>{tr('Asistan ekle','Add assistant')}</button></div>
    <div className="research-tabs"><button className={tab==='assistants'?'chosen':''} onClick={()=>{setTab('assistants');setEditing(null);setTarget(null);}}>{tr('Asistanlar','Assistants')}</button><button className={tab==='tasks'?'chosen':''} onClick={()=>{setTab('tasks');setEditing(null);setTarget(null);void perform(load);}}>{tr('Görevler','Tasks')} ({tasks.length})</button></div>
    {error&&<p role="alert" className="ai-error">{error}</p>}
    {!catalog&&!error&&<p role="status">{tr('Yükleniyor…','Loading…')}</p>}
    {catalog&&<p className="inline-note">{catalog.provider.configured?`Ollama · ${catalog.provider.model}`:tr('Model bağlantısı gerekli: sunucuda REGIMELAB_AI_MODEL ayarlayın ve Ollama servisini başlatın.','Model connection required: set REGIMELAB_AI_MODEL on the server and start Ollama.')} · {tr('Sıralı asistan zincirleri ve izinli otomatik backtest.','Sequential assistant chains and authorized automatic backtests.')}</p>}
    {editing?<form className="panel ai-form" onSubmit={e=>{e.preventDefault();void perform(async()=>{const {name,description,system_prompt,stage,permissions,auto_backtest,chain}=editing;const id='id' in editing?editing.id:null;await request(id?`/assistants/${id}`:'/assistants',id?'PUT':'POST',{name,description,system_prompt,stage,permissions,auto_backtest,chain});await load();setEditing(null);});}}>
      <button type="button" className="text-button" onClick={()=>setEditing(null)}><ArrowLeft size={14}/>{tr('Listeye dön','Back to list')}</button>
      {readonly&&<div className="inline-note"><LockKeyhole size={16}/>{tr('Bu şablon salt okunurdur. Özelleştirmek için klonlayın.','This template is read-only. Clone it to customize.')}<button type="button" className="secondary" disabled={busy} onClick={()=>void clone(editing as Assistant)}>{tr('Klonla','Clone')}</button></div>}
      <fieldset disabled={readonly||busy}>
        <div className="form-grid"><label>{tr('Ad','Name')}<input required maxLength={120} value={editing.name} onChange={e=>setEditing({...editing,name:e.target.value})}/></label><label>{tr('Araştırma aşaması','Research stage')}<select value={editing.stage} onChange={e=>setEditing({...editing,stage:e.target.value})}>{['none','ideas','research','backtest'].map(s=><option key={s}>{s}</option>)}</select></label></div>
        <label>{tr('Açıklama','Description')}<input maxLength={1000} value={editing.description} onChange={e=>setEditing({...editing,description:e.target.value})}/></label>
        <label>{tr('Sistem talimatı','System prompt')}<textarea required rows={9} maxLength={16000} value={editing.system_prompt} onChange={e=>setEditing({...editing,system_prompt:e.target.value})}/></label>
        <h3>{tr('İzinler','Permissions')}</h3><p>{tr('Yalnızca görevde seçtiğiniz deney paylaşılır.','Only the experiment selected for a task is shared.')}</p>
        {['experiments','metrics','backtest_run'].map(p=><label className="ai-check" key={p}><input type="checkbox" checked={editing.permissions.includes(p)} onChange={e=>setEditing({...editing,auto_backtest:e.target.checked?editing.auto_backtest:false,permissions:e.target.checked?[...editing.permissions,p]:editing.permissions.filter(v=>v!==p)})}/>{p==='experiments'?tr('Deney yapılandırmasını oku','Read experiment configuration'):p==='metrics'?tr('Backtest metriklerini oku','Read backtest metrics'):tr('Backtest çalıştır','Run backtests')}</label>)}
        <h3>{tr('Otomatik backtest','Automatic backtest')}</h3>
        <label className="ai-check"><input type="checkbox" checked={editing.auto_backtest} disabled={!['experiments','metrics','backtest_run'].every(p=>editing.permissions.includes(p))} onChange={e=>setEditing({...editing,auto_backtest:e.target.checked})}/>{tr('Bu adımda backtest çalıştır, sonucu bekle ve analiz et.','Run the backtest at this step, wait for results and analyze them.')}</label>
        <p>{tr('Üç izin de gereklidir. Görev başlatılırken otomatik çalıştırma ayrıca seçilir. Tamamlanmış deneyin mevcut sonucu kullanılır.','All three permissions are required. Enable automatic execution when starting a task. Completed experiments reuse their existing result.')}</p>
        <h3>{tr('Alt asistan zinciri','Sub-assistant chain')}</h3>
        <p>{tr('Önce bu asistan, ardından aşağıdaki asistanlar sırayla çalışır. Her asistanın kendi alt zinciri de aynı sırada açılır; toplam en fazla 8 adım.','This assistant runs first, followed by the assistants below. Each assistant’s own chain runs in sequence too; up to 8 steps in total.')}</p>
        <ol className="ai-chain">{editing.chain.map((id,index)=><li key={id}><span>{catalog?.items.find(a=>a.id===id)?.name||id}</span><div className="ai-actions"><button type="button" className="text-button" aria-label={tr('Yukarı taşı','Move up')} disabled={index===0} onClick={()=>moveChild(index,-1)}><ArrowUp size={14}/></button><button type="button" className="text-button" aria-label={tr('Aşağı taşı','Move down')} disabled={index===editing.chain.length-1} onClick={()=>moveChild(index,1)}><ArrowDown size={14}/></button><button type="button" className="text-button" aria-label={tr('Zincirden çıkar','Remove from chain')} onClick={()=>setEditing({...editing,chain:editing.chain.filter(v=>v!==id)})}><X size={14}/></button></div></li>)}</ol>
        <div className="ai-actions"><label>{tr('Alt asistan','Sub-assistant')}<select value={chainChoice} onChange={e=>setChainChoice(e.target.value)}><option value="">{tr('Asistan seçin','Choose an assistant')}</option>{catalog?.items.filter(a=>!editing.chain.includes(a.id)&&(!('id' in editing)||a.id!==editing.id)).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label><button className="secondary" type="button" disabled={!chainChoice||editing.chain.includes(chainChoice)||('id' in editing&&editing.id===chainChoice)||editing.chain.length>=7} onClick={()=>{setEditing({...editing,chain:[...editing.chain,chainChoice]});setChainChoice('');}}><Plus size={14}/>{tr('Zincire ekle','Add to chain')}</button></div>
        {!readonly&&<button className="primary" disabled={busy||!editing.name.trim()||!editing.system_prompt.trim()}>{tr('Kaydet','Save')}</button>}
      </fieldset>
    </form>:target?<form className="panel ai-form" onSubmit={e=>{e.preventDefault();void perform(async()=>{await request<Task>('/assistant-tasks','POST',{assistant_id:target.id,prompt,experiment_id:experiment||null,run_backtest:runBacktest});await load();setTarget(null);setTab('tasks');});}}>
      <h3>{target.name} · {tr('Yeni görev','New task')}</h3><label>{tr('Deney bağlamı','Experiment context')}<select disabled={busy||!target.permissions.includes('experiments')} value={experiment} onChange={e=>setExperiment(e.target.value)}><option value="">{tr('Deney seçilmedi','No experiment selected')}</option>{experiments.map(e=><option value={e.id} key={e.id}>{e.code} · {e.name}</option>)}</select></label>
      <div className="inline-note">{plan.map((a,i)=><span key={a.id}>{i>0?' → ':''}{a.name}{a.auto_backtest?' + backtest':''}</span>)}</div>
      {hasBacktest&&<><label className="ai-check"><input type="checkbox" disabled={busy} checked={runBacktest} onChange={e=>setRunBacktest(e.target.checked)}/>{tr('Bu görevde otomatik backtest çalıştır.','Run automatic backtests for this task.')}</label><p>{tr('Taslak deney çalıştırılır; devam eden veya tamamlanmış deney tekrar başlatılmaz. Hesaplama bütçesi ve kilitli test kuralları geçerlidir. Seçilmezse yalnızca analiz yapılır.','Draft experiments are executed; active or completed experiments are not rerun. Compute budgets and locked-test rules apply. Leave unchecked for analysis only.')}</p></>}
      <label>{tr('Asistanın ne yapmasını istiyorsunuz?','What should the assistant do?')}<textarea required autoFocus rows={5} maxLength={12000} disabled={busy} value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder={tr('Doğrulama planını ve aşırı uyum risklerini değerlendir.','Review the validation plan and overfitting risks.')}/></label>
      <div className="ai-actions"><button className="primary" disabled={busy||!catalog?.provider.configured||!prompt.trim()||(runBacktest&&!experiment)}><Play size={14}/>{busy?tr('Sıraya alınıyor…','Queuing…'):tr('Görevi başlat','Start task')}</button><button type="button" className="secondary" disabled={busy} onClick={()=>setTarget(null)}>{tr('Vazgeç','Cancel')}</button></div>
    </form>:tab==='assistants'?<section className="panel table-wrap"><table><thead><tr><th>{tr('Ad','Name')}</th><th>{tr('Yazar / Aşama','Author / Stage')}</th><th>{tr('İşlemler','Actions')}</th></tr></thead><tbody>{catalog?.items.map(a=><tr key={a.id}><td><button className="text-button" onClick={()=>setEditing({...a})}><Bot size={18}/>{a.name}</button><small className="table-subline">{a.description}</small></td><td>{a.author}<small className="table-subline">{a.stage} · {a.template?tr('Şablon','Template'):tr('Özel asistan','Custom assistant')}</small></td><td><div className="ai-actions"><button className="text-button" disabled={busy} onClick={()=>void clone(a)}><Copy size={14}/>{tr('Klonla','Clone')}</button><button className="text-button" disabled={busy} onClick={()=>newTask(a)}><Plus size={14}/>{tr('Yeni görev','New task')}</button></div></td></tr>)}</tbody></table></section>:<TaskHistory tasks={tasks} tr={tr} lang={lang} busy={busy} statusLabel={statusLabel} cancel={id=>void perform(async()=>{await request(`/assistant-tasks/${id}/cancel`,'POST');await load();})}/>}

  </section>;
}
