import { useEffect, useMemo, useState } from 'react';
import { Bot, Check, Clipboard, Download, Maximize2, Minimize2, Pin, PinOff, Plus, Search, Send, Sparkles, X } from 'lucide-react';
import { request } from './platform-api';
import type { Experiment } from './platform-api';
import './app/styles/chatbot.css';

type Assistant = { id:string; name:string; description:string; permissions:string[]; template:boolean; author:string };
type Task = { id:string; assistant_name:string; prompt:string; status:string; output:string; error?:string; created_at:string };

const preparedQuestions = [
  'Bu deneyde aşırı uyum riski var mı?',
  'Validation ve test sonuçlarını karşılaştır.',
  'Bu sonuçları maliyet ve drawdown açısından değerlendir.',
  'Bir sonraki araştırma adımlarını öner.',
  'En iyi adayın seçilme nedenini açıkla.',
  'Feature seçiminde kararsız veya zayıf özellikleri bul.',
  'Modelin farklı piyasa rejimlerindeki performansını incele.',
  'İşlem maliyetleri iki katına çıkarsa sonuç nasıl etkilenir?',
  'Test performansındaki düşüşü ve olası nedenlerini açıkla.',
  'Bu stratejinin risklerini yatırımcıya sade bir dille anlat.',
  'Pozisyon değişiklikleri ve turnover makul mü?',
  'Sonuçları benchmark ile karşılaştır ve farkı açıkla.',
  'En güvenilir üç metriği seç ve yorumla.',
  'Bu deney için daha sağlam bir validation planı öner.',
  'Aynı sonucu doğrulamak için hangi yeni deneyi kurmalıyım?',
  'Kullanılan veri ve snapshot bütünlüğü hakkında rapor hazırla.',
  'Final testin sealed test kurallarına uygunluğunu kontrol et.',
  'Bu modeli üretime almadan önce hangi kontroller yapılmalı?',
  'En kötü senaryoyu ve maksimum kayıp riskini özetle.',
  'Bu backtest sonucuna ne kadar güvenebiliriz? Gerekçelendir.',
  'İndikatörler arasında yüksek korelasyon veya tekrar eden bilgi var mı?',
  'Daha az özellik kullanarak benzer performans mümkün mü?',
  'Walk-forward fold sonuçlarının tutarlılığını incele.',
  'Bu deneyin sonuçlarını kısa bir yönetici özetine dönüştür.',
  'Dış kaynak gerekiyorsa hangi verileri aramalıyız ve neden?',
];
const activeStatuses = new Set(['QUEUED','RUNNING','WAITING_BACKTEST']);

export default function ChatBot({ experiments: initialExperiments = [] }: { experiments?: Experiment[] }) {
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
  const allQuestions=useMemo(()=>[...preparedQuestions,...customQuestions],[customQuestions]);
  const visibleQuestions=useMemo(()=>allQuestions.filter(item=>item.toLocaleLowerCase('tr-TR').includes(promptSearch.trim().toLocaleLowerCase('tr-TR'))),[allQuestions,promptSearch]);
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
    {!open&&<button className="chatbot-launcher" aria-label="AI sohbetini aç" onClick={()=>setOpen(true)}><Sparkles size={17}/><span>AI Chat</span></button>}
    {open&&<>
      <button className="chatbot-backdrop" aria-label="Sohbeti kapat" onClick={()=>setOpen(false)}/>
      <aside className={`chatbot-panel ${fullscreen?'is-fullscreen':''} ${pinned?'is-pinned':''}`} aria-label="AI sohbet paneli">
        <header className="chatbot-header"><div><span className="chatbot-kicker"><Bot size={14}/> REGIMELAB AI {pinned&&<em>Sabitlendi</em>}</span><h2>Araştırma asistanı</h2><p>Deneyleri, metrikleri ve backtest sonuçlarını incele.</p></div><div className="chatbot-header-actions"><button title={pinned?'Sabitlikten çıkar':'Sohbeti sabitle'} onClick={togglePinned}>{pinned?<PinOff size={17}/>:<Pin size={17}/>}</button><button title={fullscreen?'Pencere görünümü':'Tam ekran'} onClick={()=>setFullscreen(value=>!value)}>{fullscreen?<Minimize2 size={17}/>:<Maximize2 size={17}/>}</button><button title="Sohbeti dışa aktar" onClick={exportChat} disabled={!tasks.length}><Download size={17}/></button><button title="Kapat" onClick={()=>setOpen(false)}><X size={18}/></button></div></header>
        <section className="chatbot-context"><label>Asistan<select value={assistant?.id||''} onChange={e=>setAssistantId(e.target.value)} disabled={!catalog.length}><option value="">{catalog.length?'Asistan seçin':'Asistanlar yükleniyor…'}</option>{catalog.map(item=><option value={item.id} key={item.id}>{item.name}{item.template?' · şablon':''}</option>)}</select></label><label>Deney bağlamı<select value={experimentId} onChange={e=>setExperimentId(e.target.value)}><option value="">Deney seçmeden sor</option>{experiments.map(item=><option value={item.id} key={item.id}>{item.code} · {item.name}</option>)}</select></label>{assistant&&<small><Check size={12}/> İzinler: {assistant.permissions.join(', ')}</small>}</section>
        <main className="chatbot-messages" aria-live="polite">{!tasks.length&&<div className="chatbot-empty"><Bot size={34}/><strong>Nasıl yardımcı olabilirim?</strong><p>Hazır sorulardan birini seçebilir veya kendi sorunu yazabilirsin.</p></div>}{tasks.slice().reverse().map(task=><article className="chat-message" key={task.id}><div className="chat-question"><span>SEN</span><p>{task.prompt}</p></div><div className="chat-answer"><span><Bot size={14}/> AI</span><p>{task.output||task.error||(activeStatuses.has(task.status)?'Yanıt hazırlanıyor…':'Henüz yanıt yok.')}</p><div className="chat-message-actions"><button onClick={()=>void copy(task.output||task.error||'')} disabled={!task.output&&!task.error}><Clipboard size={13}/> Kopyala</button><span>{task.status}</span></div></div></article>)}</main>
        <footer className="chatbot-composer"><div className="chatbot-prompt-toolbar"><label><Search size={14}/><input value={promptSearch} onChange={e=>setPromptSearch(e.target.value)} placeholder="Hazır sorularda ara…" aria-label="Hazır sorularda ara"/></label><span>{visibleQuestions.length} soru</span></div><div className="chatbot-prompts">{visibleQuestions.map(item=><button key={item} onClick={()=>setQuestion(item)}>{item}</button>)}{!visibleQuestions.length&&<small>Sonuç bulunamadı. Kendi sorunuzu yazabilirsiniz.</small>}</div><div className="chatbot-add-prompt"><input value={newPrompt} onChange={e=>setNewPrompt(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();addPrompt();}}} placeholder="Yeni hazır soru ekle…" aria-label="Yeni hazır soru ekle"/><button onClick={addPrompt} disabled={!newPrompt.trim()}><Plus size={13}/> Ekle</button></div><div className="chatbot-input"><textarea rows={3} value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void send();}}} placeholder="Araştırma sorunu yaz…" disabled={busy}/><button className="primary" onClick={()=>void send()} disabled={busy||!question.trim()||!assistant}><Send size={16}/>{busy?'Gönderiliyor…':'Gönder'}</button></div><small>Enter gönderir · Shift+Enter yeni satır</small>{error&&<p className="chatbot-error" role="alert">{error}</p>}</footer>
      </aside>
    </>}
  </>;
}
