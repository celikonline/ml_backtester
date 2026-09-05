import {useEffect, useState} from 'react';
import {Bot, Copy, Plus, ArrowLeft, Play, LockKeyhole} from 'lucide-react';
import {request} from './platform-api';
import type {Experiment} from './platform-api';
import {useLang} from './i18n';
import './assistants.css';

type Config = {name:string;description:string;system_prompt:string;stage:string;permissions:string[]};
type Assistant = Config & {id:string;template:boolean;author:string};
type Task = {id:string;assistant_name:string;prompt:string;status:string;output:string;created_at:string};
type Catalog = {items:Assistant[];provider:{configured:boolean;model:string}};
const blank:Config = {name:'',description:'',system_prompt:'',stage:'research',permissions:['experiments','metrics']};

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
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const fail = (e:unknown)=>setError(e instanceof Error?e.message:String(e));
  async function load(){const [c,t]=await Promise.all([request<Catalog>('/assistants'),request<Task[]>('/assistant-tasks')]);setCatalog(c);setTasks(t);}
  useEffect(()=>{let active=true;Promise.all([request<Catalog>('/assistants'),request<Task[]>('/assistant-tasks')]).then(([c,t])=>{if(active){setCatalog(c);setTasks(t);}}).catch(e=>{if(active)fail(e);});return()=>{active=false;};},[]);
  async function perform(action:()=>Promise<void>){setBusy(true);setError('');try{await action();}catch(e){fail(e);}finally{setBusy(false);}}
  const readonly = !!editing && 'template' in editing && editing.template;
  function newTask(a:Assistant){setTarget(a);setPrompt('');setExperiment('');setEditing(null);}
  async function clone(a:Assistant){await perform(async()=>{const copy=await request<Assistant>(`/assistants/${a.id}/clone`,'POST');await load();setEditing(copy);});}
  return <section className="ai-assistants">
    <div className="panel-heading"><div><h2><Bot size={22}/> {tr('AI Asistanlar','AI Assistants')}</h2><p>{tr('Araştırma fikirlerini geliştirin, deneyleri inceleyin ve sonuçları değerlendirin.','Develop research ideas, inspect experiments and review results.')}</p></div><button className="primary" disabled={busy} onClick={()=>{setEditing({...blank,permissions:[...blank.permissions]});setTarget(null);}}><Plus size={15}/>{tr('Asistan ekle','Add assistant')}</button></div>
    <div className="research-tabs"><button className={tab==='assistants'?'chosen':''} onClick={()=>{setTab('assistants');setEditing(null);setTarget(null);}}>{tr('Asistanlar','Assistants')}</button><button className={tab==='tasks'?'chosen':''} onClick={()=>{setTab('tasks');setEditing(null);setTarget(null);void perform(load);}}>{tr('Görevler','Tasks')} ({tasks.length})</button></div>
    {error&&<p role="alert" className="ai-error">{error}</p>}
    {!catalog&&!error&&<p role="status">{tr('Yükleniyor…','Loading…')}</p>}
    {catalog&&<p className="inline-note">{catalog.provider.configured?`Ollama · ${catalog.provider.model}`:tr('Model bağlantısı gerekli: sunucuda REGIMELAB_AI_MODEL ayarlayın ve Ollama servisini başlatın.','Model connection required: set REGIMELAB_AI_MODEL on the server and start Ollama.')} · {tr('Araştırma ve analiz modu; işlem veya backtest başlatmaz.','Research and analysis mode; does not execute trades or backtests.')}</p>}
    {editing?<form className="panel ai-form" onSubmit={e=>{e.preventDefault();void perform(async()=>{const {name,description,system_prompt,stage,permissions}=editing;const id='id' in editing?editing.id:null;await request(id?`/assistants/${id}`:'/assistants',id?'PUT':'POST',{name,description,system_prompt,stage,permissions});await load();setEditing(null);});}}>
      <button type="button" className="text-button" onClick={()=>setEditing(null)}><ArrowLeft size={14}/>{tr('Listeye dön','Back to list')}</button>
      {readonly&&<div className="inline-note"><LockKeyhole size={16}/>{tr('Bu şablon salt okunurdur. Özelleştirmek için klonlayın.','This template is read-only. Clone it to customize.')}<button type="button" className="secondary" disabled={busy} onClick={()=>void clone(editing as Assistant)}>{tr('Klonla','Clone')}</button></div>}
      <fieldset disabled={readonly||busy}>
        <div className="form-grid"><label>{tr('Ad','Name')}<input required maxLength={120} value={editing.name} onChange={e=>setEditing({...editing,name:e.target.value})}/></label><label>{tr('Araştırma aşaması','Research stage')}<select value={editing.stage} onChange={e=>setEditing({...editing,stage:e.target.value})}>{['none','ideas','research','backtest'].map(s=><option key={s}>{s}</option>)}</select></label></div>
        <label>{tr('Açıklama','Description')}<input maxLength={1000} value={editing.description} onChange={e=>setEditing({...editing,description:e.target.value})}/></label>
        <label>{tr('Sistem talimatı','System prompt')}<textarea required rows={9} maxLength={16000} value={editing.system_prompt} onChange={e=>setEditing({...editing,system_prompt:e.target.value})}/></label>
        <h3>{tr('Okuma izinleri','Read permissions')}</h3><p>{tr('Yalnızca görevde seçtiğiniz deney paylaşılır.','Only the experiment selected for a task is shared.')}</p>
        {['experiments','metrics'].map(p=><label className="ai-check" key={p}><input type="checkbox" checked={editing.permissions.includes(p)} onChange={e=>setEditing({...editing,permissions:e.target.checked?[...editing.permissions,p]:editing.permissions.filter(v=>v!==p)})}/>{p==='experiments'?tr('Deney yapılandırması','Experiment configuration'):tr('Backtest metrikleri','Backtest metrics')}</label>)}
        {!readonly&&<button className="primary" disabled={busy||!editing.name.trim()||!editing.system_prompt.trim()}>{tr('Kaydet','Save')}</button>}
      </fieldset>
    </form>:target?<form className="panel ai-form" onSubmit={e=>{e.preventDefault();void perform(async()=>{await request<Task>('/assistant-tasks','POST',{assistant_id:target.id,prompt,experiment_id:experiment||null});await load();setTarget(null);setTab('tasks');});}}>
      <h3>{target.name} · {tr('Yeni görev','New task')}</h3><label>{tr('Deney bağlamı','Experiment context')}<select disabled={busy||!target.permissions.includes('experiments')} value={experiment} onChange={e=>setExperiment(e.target.value)}><option value="">{tr('Deney seçilmedi','No experiment selected')}</option>{experiments.map(e=><option value={e.id} key={e.id}>{e.code} · {e.name}</option>)}</select></label>
      <label>{tr('Asistanın ne yapmasını istiyorsunuz?','What should the assistant do?')}<textarea required autoFocus rows={5} maxLength={12000} disabled={busy} value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder={tr('Doğrulama planını ve aşırı uyum risklerini değerlendir.','Review the validation plan and overfitting risks.')}/></label>
      <div className="ai-actions"><button className="primary" disabled={busy||!catalog?.provider.configured||!prompt.trim()}><Play size={14}/>{busy?tr('Yanıt bekleniyor…','Waiting for response…'):tr('Görevi başlat','Start task')}</button><button type="button" className="secondary" disabled={busy} onClick={()=>setTarget(null)}>{tr('Vazgeç','Cancel')}</button></div>
    </form>:tab==='assistants'?<section className="panel table-wrap"><table><thead><tr><th>{tr('Ad','Name')}</th><th>{tr('Yazar / Aşama','Author / Stage')}</th><th>{tr('İşlemler','Actions')}</th></tr></thead><tbody>{catalog?.items.map(a=><tr key={a.id}><td><button className="text-button" onClick={()=>setEditing({...a})}><Bot size={18}/>{a.name}</button><small className="table-subline">{a.description}</small></td><td>{a.author}<small className="table-subline">{a.stage} · {a.template?tr('Şablon','Template'):tr('Özel asistan','Custom assistant')}</small></td><td><div className="ai-actions"><button className="text-button" disabled={busy} onClick={()=>void clone(a)}><Copy size={14}/>{tr('Klonla','Clone')}</button><button className="text-button" disabled={busy} onClick={()=>newTask(a)}><Plus size={14}/>{tr('Yeni görev','New task')}</button></div></td></tr>)}</tbody></table></section>:<section className="ai-task-list">{!tasks.length?<div className="panel small-empty"><Bot size={28}/>{tr('Henüz görev yok. Bir asistan seçerek başlayın.','No tasks yet. Choose an assistant to get started.')}</div>:tasks.map(task=><details className="panel ai-task" key={task.id} open={tasks[0].id===task.id}><summary><b>{task.assistant_name}</b><span className="badge">{task.status}</span><time>{new Date(task.created_at).toLocaleString(lang==='tr'?'tr-TR':'en-US')}</time></summary><p>{task.prompt}</p><pre>{task.output||tr('Görev çalışıyor. Görevler sekmesini açarak durumu yenileyin.','Task is running. Open the Tasks tab to refresh.')}</pre></details>)}</section>}
  </section>;
}
