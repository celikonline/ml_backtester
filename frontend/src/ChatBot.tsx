import { useEffect, useMemo, useState } from 'react';
import { Bot, Check, Clipboard, Download, Maximize2, Minimize2, Pin, PinOff, Plus, Search, Send, Sparkles, X } from 'lucide-react';
import { request } from './platform-api';
import type { Experiment } from './platform-api';
import { useLang } from './i18n';
import './app/styles/chatbot.css';

type Assistant = { id:string; name:string; description:string; permissions:string[]; template:boolean; author:string };
type Task = { id:string; assistant_name:string; prompt:string; status:string; output:string; error?:string; created_at:string };

const preparedQuestions = [
  ['Bu deneyde aşırı uyum riski var mı?','Does this experiment show overfitting risk?'],
  ['Validation ve test sonuçlarını karşılaştır.','Compare the validation and test results.'],
  ['Bu sonuçları maliyet ve drawdown açısından değerlendir.','Evaluate these results for costs and drawdown.'],
  ['Bir sonraki araştırma adımlarını öner.','Suggest the next research steps.'],
  ['En iyi adayın seçilme nedenini açıkla.','Explain why the best candidate was selected.'],
  ['Feature seçiminde kararsız veya zayıf özellikleri bul.','Find unstable or weak features in the selection.'],
  ['Modelin farklı piyasa rejimlerindeki performansını incele.','Review model performance across market regimes.'],
  ['İşlem maliyetleri iki katına çıkarsa sonuç nasıl etkilenir?','How would the result change if trading costs doubled?'],
  ['Test performansındaki düşüşü ve olası nedenlerini açıkla.','Explain the test performance decline and possible causes.'],
  ['Bu stratejinin risklerini yatırımcıya sade bir dille anlat.','Explain this strategy’s risks in plain language.'],
  ['Pozisyon değişiklikleri ve turnover makul mü?','Are the position changes and turnover reasonable?'],
  ['Sonuçları benchmark ile karşılaştır ve farkı açıkla.','Compare the results with the benchmark and explain the difference.'],
  ['En güvenilir üç metriği seç ve yorumla.','Choose and interpret the three most reliable metrics.'],
  ['Bu deney için daha sağlam bir validation planı öner.','Suggest a more robust validation plan for this experiment.'],
  ['Aynı sonucu doğrulamak için hangi yeni deneyi kurmalıyım?','What new experiment should I run to verify this result?'],
  ['Kullanılan veri ve snapshot bütünlüğü hakkında rapor hazırla.','Report on the integrity of the data and snapshot used.'],
  ['Final testin sealed test kurallarına uygunluğunu kontrol et.','Check whether the final test follows sealed-test rules.'],
  ['Bu modeli üretime almadan önce hangi kontroller yapılmalı?','What checks are needed before deploying this model?'],
  ['En kötü senaryoyu ve maksimum kayıp riskini özetle.','Summarize the worst-case scenario and maximum loss risk.'],
  ['Bu backtest sonucuna ne kadar güvenebiliriz? Gerekçelendir.','How much confidence should we place in this backtest? Explain why.'],
  ['İndikatörler arasında yüksek korelasyon veya tekrar eden bilgi var mı?','Are indicators highly correlated or redundant?'],
  ['Daha az özellik kullanarak benzer performans mümkün mü?','Can similar performance be achieved with fewer features?'],
  ['Walk-forward fold sonuçlarının tutarlılığını incele.','Review the consistency of walk-forward fold results.'],
  ['Bu deneyin sonuçlarını kısa bir yönetici özetine dönüştür.','Turn this experiment’s results into a short executive summary.'],
  ['Dış kaynak gerekiyorsa hangi verileri aramalıyız ve neden?','If external research is needed, what data should we look for and why?'],
].map(([tr,en])=>({tr,en}));
const activeStatuses = new Set(['QUEUED','RUNNING','WAITING_BACKTEST']);

export default function ChatBot({ experiments: initialExperiments = [] }: { experiments?: Experiment[] }) {
  const { lang } = useLang();
  const text=(tr:string,en:string)=>lang==='tr'?tr:en;
  const [open,setOpen] = useState(false);
  const [fullscreen,setFullscreen] = useState(false);
  const [pinned,setPinned] = useState(()=>localStorage.getItem('regimelab-chat-pinned')==='true');
  const [catalog,setCatalog] = useState<Assistant[]>([]);
  const [experiments,setExperiments] = useState<Experiment[]>(initialExperiments);
  const [assistantId,setAssistantId] = useState('');
  const [experimentId,setExperimentId] = useState('');
  const [question,setQuestion] = useState('');
  const [promptSearch,setPromptSearch] = useState('');
  const [customQuestions,setCustomQuestions] = useState<string[]>(()=>{try{return JSON.parse(localStorage.getItem('regimelab-chat-prompts')||'[]');}catch{return [];}});
  const [newPrompt,setNewPrompt] = useState('');
  const [tasks,setTasks] = useState<Task[]>([]);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const assistant = useMemo(()=>catalog.find(item=>item.id===assistantId)||catalog[0], [catalog,assistantId]);
  const allQuestions=useMemo(()=>[...preparedQuestions.map(item=>lang==='tr'?item.tr:item.en),...customQuestions],[customQuestions,lang]);
  const visibleQuestions=useMemo(()=>allQuestions.filter(item=>item.toLocaleLowerCase(lang==='tr'?'tr-TR':'en-US').includes(promptSearch.trim().toLocaleLowerCase(lang==='tr'?'tr-TR':'en-US'))),[allQuestions,promptSearch,lang]);
  const tr = (value:string) => value;
  useEffect(()=>{
    document.documentElement.classList.toggle('chatbot-is-pinned',open&&pinned);
    return()=>document.documentElement.classList.remove('chatbot-is-pinned');
  },[open,pinned]);

  useEffect(()=>{
    if(!open || catalog.length)return;
    Promise.all([request<{items:Assistant[]}>('/assistants'),request<Task[]>('/assistant-tasks'),request<Experiment[]>('/experiments')])
      .then(([items,history,availableExperiments])=>{setCatalog(items.items||[]);setTasks(history.slice(0,8));setExperiments(availableExperiments);})
      .catch(e=>setError(e instanceof Error?e.message:String(e)));
  },[open,catalog.length]);

  useEffect(()=>{
    if(!open || !tasks.some(task=>activeStatuses.has(task.status)))return;
    const timer=setInterval(()=>request<Task[]>('/assistant-tasks').then(next=>setTasks(next.slice(0,8))).catch(()=>{}),2000);
    return()=>clearInterval(timer);
  },[open,tasks]);

  async function send(){
    const prompt=question.trim();
    if(!prompt||!assistant||busy)return;
    setBusy(true);setError('');
    try{
      const task=await request<Task>('/assistant-tasks','POST',{assistant_id:assistant.id,prompt,experiment_id:experimentId||null,run_backtest:false});
      setTasks(previous=>[task,...previous.filter(item=>item.id!==task.id)].slice(0,8));
      setQuestion('');
    }catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  }
  async function copy(text:string){try{await navigator.clipboard.writeText(text);}catch{setError('Kopyalama başarısız.');}}
  function exportChat(){
    const text=tasks.slice().reverse().map(task=>`[${task.assistant_name}]\nSoru: ${task.prompt}\n\nYanıt:\n${task.output||task.error||'Yanıt bekleniyor.'}`).join('\n\n---\n\n');
    const url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='regimelab-chat.txt';link.click();URL.revokeObjectURL(url);
  }
  function togglePinned(){const value=!pinned;setPinned(value);localStorage.setItem('regimelab-chat-pinned',String(value));}
  function addPrompt(){const value=newPrompt.trim();if(!value||allQuestions.includes(value))return;const next=[...customQuestions,value];setCustomQuestions(next);localStorage.setItem('regimelab-chat-prompts',JSON.stringify(next));setNewPrompt('');setPromptSearch('');}
  return <>
    {!open&&<button className="chatbot-launcher" aria-label={text('AI sohbetini aç','Open AI chat')} onClick={()=>setOpen(true)}><Sparkles size={17}/><span>AI Chat</span></button>}
    {open&&<>
      <button className="chatbot-backdrop" aria-label={text('Sohbeti kapat','Close chat')} onClick={()=>setOpen(false)}/>
      <aside className={`chatbot-panel ${fullscreen?'is-fullscreen':''} ${pinned?'is-pinned':''}`} aria-label={text('AI sohbet paneli','AI chat panel')}>
        <header className="chatbot-header"><div><span className="chatbot-kicker"><Bot size={14}/> REGIMELAB AI {pinned&&<em>{text('Sabitlendi','Pinned')}</em>}</span><h2>{text('Araştırma asistanı','Research assistant')}</h2><p>{text('Deneyleri, metrikleri ve backtest sonuçlarını incele.','Review experiments, metrics, and backtest results.')}</p></div><div className="chatbot-header-actions"><button title={pinned?text('Sabitlikten çıkar','Unpin chat'):text('Sohbeti sabitle','Pin chat')} onClick={togglePinned}>{pinned?<PinOff size={17}/>:<Pin size={17}/>}</button><button title={fullscreen?text('Pencere görünümü','Window view'):text('Tam ekran','Full screen')} onClick={()=>setFullscreen(value=>!value)}>{fullscreen?<Minimize2 size={17}/>:<Maximize2 size={17}/>}</button><button title={text('Sohbeti dışa aktar','Export chat')} onClick={exportChat} disabled={!tasks.length}><Download size={17}/></button><button title={text('Kapat','Close')} onClick={()=>setOpen(false)}><X size={18}/></button></div></header>
        <section className="chatbot-context"><label>{text('Asistan','Assistant')}<select value={assistant?.id||''} onChange={e=>setAssistantId(e.target.value)} disabled={!catalog.length}><option value="">{catalog.length?text('Asistan seçin','Choose an assistant'):text('Asistanlar yükleniyor…','Loading assistants…')}</option>{catalog.map(item=><option value={item.id} key={item.id}>{item.name}{item.template?` · ${text('şablon','template')}`:''}</option>)}</select></label><label>{text('Deney bağlamı','Experiment context')}<select value={experimentId} onChange={e=>setExperimentId(e.target.value)}><option value="">{text('Deney seçmeden sor','Ask without an experiment')}</option>{experiments.map(item=><option value={item.id} key={item.id}>{item.code} · {item.name}</option>)}</select></label>{assistant&&<small><Check size={12}/> {text('İzinler','Permissions')}: {assistant.permissions.join(', ')}</small>}</section>
        <main className="chatbot-messages" aria-live="polite">{!tasks.length&&<div className="chatbot-empty"><Bot size={34}/><strong>{text('Nasıl yardımcı olabilirim?','How can I help?')}</strong><p>{text('Hazır sorulardan birini seçebilir veya kendi sorunu yazabilirsin.','Choose a prepared question or write your own.')}</p></div>}{tasks.slice().reverse().map(task=><article className="chat-message" key={task.id}><div className="chat-question"><span>{text('SEN','YOU')}</span><p>{task.prompt}</p></div><div className="chat-answer"><span><Bot size={14}/> AI</span><p>{task.output||task.error||(activeStatuses.has(task.status)?text('Yanıt hazırlanıyor…','Preparing answer…'):text('Henüz yanıt yok.','No answer yet.'))}</p><div className="chat-message-actions"><button onClick={()=>void copy(task.output||task.error||'')} disabled={!task.output&&!task.error}><Clipboard size={13}/> {text('Kopyala','Copy')}</button><span>{task.status}</span></div></div></article>)}</main>
        <footer className="chatbot-composer"><div className="chatbot-prompt-toolbar"><label><Search size={14}/><input value={promptSearch} onChange={e=>setPromptSearch(e.target.value)} placeholder={text('Hazır sorularda ara…','Search prepared questions…')} aria-label={text('Hazır sorularda ara','Search prepared questions')}/></label><span>{visibleQuestions.length} {text('soru','questions')}</span></div><div className="chatbot-prompts">{visibleQuestions.map(item=><button key={item} onClick={()=>setQuestion(item)}>{item}</button>)}{!visibleQuestions.length&&<small>{text('Sonuç bulunamadı. Kendi sorunuzu yazabilirsiniz.','No results. You can write your own question.')}</small>}</div><div className="chatbot-add-prompt"><input value={newPrompt} onChange={e=>setNewPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();addPrompt();}}} placeholder={text('Yeni hazır soru ekle…','Add prepared question…')} aria-label={text('Yeni hazır soru ekle','Add prepared question')}/><button onClick={addPrompt} disabled={!newPrompt.trim()}><Plus size={13}/> {text('Ekle','Add')}</button></div><div className="chatbot-input"><textarea rows={3} value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void send();}}} placeholder={text('Araştırma sorunu yaz…','Write a research question…')} disabled={busy}/><button className="primary" onClick={()=>void send()} disabled={busy||!question.trim()||!assistant}><Send size={16}/>{busy?text('Gönderiliyor…','Sending…'):text('Gönder','Send')}</button></div><small>{text('Enter gönderir · Shift+Enter yeni satır','Enter sends · Shift+Enter adds a new line')}</small>{error&&<p className="chatbot-error" role="alert">{error}</p>}</footer>
      </aside>
    </>}
  </>;
}
