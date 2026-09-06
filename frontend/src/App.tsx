import { useEffect, useRef, useState } from 'react';
import { Activity, ArrowDownToLine, ArrowRight, ArrowUpRight, BookOpen, Calendar, Check, ChevronDown, Circle, CircleHelp, Clock3, Database, FlaskConical, Layers3, LayoutDashboard, LayoutGrid, List, Loader2, LogOut, Moon, Play, Plus, Radio, Search, Settings2, Square, Sun, Tag, Terminal, Upload, User, X, Zap } from 'lucide-react';
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Config, Dataset, Job, Result } from './types';
import ResearchPlatform from './ResearchPlatform';
import NotebookLab from './NotebookLab';
import AccountPage from './AccountPage';
import AuthPage from './AuthPage';
import { ExperimentResultsPage } from './features/quant-lab/experiment-results';
import { getToken, useAuth } from './auth';
import { useLang } from './i18n';
import type { Lang } from './i18n';
import { useWorkspace } from './workspace';
import { getStoredWorkspaceId } from './ws-store';
import './app/styles/workspace.css';

const colors = ['#55dfb0','#8b91f3','#efb66c','#62b5ef','#e78fbe'];

type CapabilityRow = { name: string; explanation: string; status: 'Var'|'Kısmen var'|'Yok'; plan: string };
const capabilityTables: { title: string; rows: CapabilityRow[] }[] = [
  { title: 'Veri yönetimi', rows: [
    {name:'CSV veri yükleme', explanation:'OHLC, makro, FX, faiz ve cross-asset verilerini içeri alma.', status:'Var', plan:'Canlı veri bağlantıları'},
    {name:'Point-in-time veri', explanation:'available_at alanıyla verinin kullanılabilirlik zamanını kontrol etme.', status:'Kısmen var', plan:'Vintage veri ve release takvimi'},
    {name:'Snapshot ve SHA-256 hash', explanation:'Veri setinin değişmez kopyasını ve bütünlüğünü saklama.', status:'Var', plan:'Daha ayrıntılı veri lineage sistemi'},
    {name:'Revision kontrolü', explanation:'Makro verilerin sonradan değiştirilip değiştirilmediğini izleme.', status:'Yok', plan:'ALFRED vintage entegrasyonu'},
    {name:'Timezone / DST kontrolü', explanation:'Zaman damgalarını UTC’ye normalize etme.', status:'Kısmen var', plan:'Ayrıntılı timezone ve DST audit raporu'},
  ]},
  { title: 'Makro finans', rows: [
    {name:'Makro indikatörler', explanation:'CPI, faiz, TGA ve benzeri harici serileri kullanma.', status:'Kısmen var', plan:'Daha geniş makro veri sağlayıcıları'},
    {name:'FX ve rates kolonları', explanation:'fx__, rates__, macro__ ve cross_asset__ veri aileleri.', status:'Var', plan:'Otomatik veri keşfi'},
    {name:'FX option IV surface', explanation:'Vade ve strike bazlı implied volatility yüzeyi.', status:'Yok', plan:'Opsiyon veri kaynağı ve surface modeli'},
    {name:'Forward points / FX swaps', explanation:'Carry ve forward primi hesaplama.', status:'Yok', plan:'Forward ve swap eğrisi'},
    {name:'OIS / cross-currency basis', explanation:'Faiz eğrisi ve para birimleri arası fonlama farkı.', status:'Yok', plan:'Eğri bootstrap sistemi'},
    {name:'CFTC / dealer positioning', explanation:'Piyasa pozisyonlanmasını analiz etme.', status:'Yok', plan:'Positioning veri pipeline’ı'},
    {name:'Order flow / microstructure', explanation:'Spread, imbalance ve işlem akışı özellikleri.', status:'Yok', plan:'Tick ve order-book veri katmanı'},
  ]},
  { title: 'Feature engineering', rows: [
    {name:'Lag, delta ve return', explanation:'Harici serilerden gecikme, değişim ve getiri feature’ları üretme.', status:'Var', plan:'Daha geniş feature registry'},
    {name:'Rolling istatistikler', explanation:'Rolling volatility, correlation, beta ve benzeri ölçümler.', status:'Kısmen var', plan:'Quantile, MAD, IQR, entropy ve skew'},
    {name:'Nonlinear transformations', explanation:'Sigmoid, tanh, threshold ve spline dönüşümleri.', status:'Kısmen var', plan:'Quant Lab'},
    {name:'PCA / PLS / factor extraction', explanation:'Boyut indirgeme ve ortak faktör çıkarımı.', status:'Kısmen var', plan:'Quant Lab grafikleri'},
    {name:'Fractional differentiation', explanation:'Serinin hafızasını koruyarak durağanlaştırma.', status:'Yok', plan:'Zaman serisi dönüşüm modülü'},
  ]},
  { title: 'Feature stability', rows: [
    {name:'Information Coefficient', explanation:'Feature ile hedef arasındaki bilgi gücünü ölçme.', status:'Var', plan:'Quant Lab'},
    {name:'IC decay / sign consistency', explanation:'Feature performansının zaman içindeki kararlılığını ölçme.', status:'Var', plan:'Quant Lab'},
    {name:'Orthogonalization / residualization', explanation:'Tekrarlayan bilgiyi azaltma.', status:'Yok', plan:'Leakage kontrollü dönüşümler'},
    {name:'Feature clustering / pruning', explanation:'Benzer ve gereksiz feature’ları eleme.', status:'Var', plan:'Quant Lab'},
    {name:'SHAP stability / ablation', explanation:'Feature katkısının rejimlere göre dayanıklılığını test etme.', status:'Kısmen var', plan:'Quant Lab grafikleri'},
  ]},
  { title: 'Rejim analizi', rows: [
    {name:'Gaussian HMM', explanation:'Piyasa rejimlerini istatistiksel olarak sınıflandırma.', status:'Var', plan:'Daha gelişmiş rejim modelleri'},
  ]},
  { title: 'Modelleme', rows: [
    {name:'Ridge', explanation:'Trend uzmanı modeli.', status:'Var', plan:'Model kalibrasyonu'},
    {name:'Random Forest', explanation:'Momentum uzmanı modeli.', status:'Var', plan:'Daha geniş hiperparametre araması'},
    {name:'Histogram Gradient Boosting', explanation:'Volatilite uzmanı modeli.', status:'Var', plan:'Model çeşitliliğini artırma'},
    {name:'XGBoost / LightGBM', explanation:'Gradient boosting tabanlı model seçenekleri.', status:'Var', plan:'Daha kapsamlı ensemble sistemi'},
    {name:'Stacking / blending', explanation:'Birden fazla modeli üst modelle birleştirme.', status:'Kısmen var', plan:'Leakage kontrollü stacking'},
  ]},
  { title: 'Tahmin', rows: [
    {name:'Quantile regression', explanation:'Tahmin aralıklarını üretme.', status:'Kısmen var', plan:'Quant Lab'},
    {name:'Probability calibration', explanation:'Tahmin olasılıklarının güvenilirliğini ölçme.', status:'Kısmen var', plan:'Quant Lab'},
    {name:'Conformal prediction', explanation:'Tahmin belirsizliğini istatistiksel olarak hesaplama.', status:'Yok', plan:'Conformal prediction modülü'},
    {name:'Distributional forecasting', explanation:'Tek değer yerine tahmin dağılımı üretme.', status:'Yok', plan:'Rejim bazlı dağılımsal tahmin'},
    {name:'Online / incremental learning', explanation:'Modeli yeni veriler geldikçe güncelleme.', status:'Yok', plan:'Concept-drift destekli online öğrenme'},
  ]},
  { title: 'Validasyon', rows: [
    {name:'Walk-forward analysis', explanation:'Zaman sırasını koruyan ileriye dönük test.', status:'Var', plan:'Daha ayrıntılı fold raporları'},
    {name:'Nested time-series CV', explanation:'Model seçimini iç ve dış zaman bölümlerinde yapma.', status:'Var', plan:'Quant Lab'},
    {name:'Purged K-Fold / embargo', explanation:'Bilgi sızıntısını engelleyen gelişmiş CV.', status:'Var', plan:'Quant Lab'},
    {name:'CPCV', explanation:'Combinatorial Purged Cross-Validation.', status:'Yok', plan:'CPCV modülü'},
    {name:'Rolling / anchored retraining', explanation:'Modeli hareketli veya sabit başlangıçlı pencerelerde yenileme.', status:'Var', plan:'Quant Lab'},
  ]},
  { title: 'Backtest', rows: [
    {name:'Maliyet duyarlılığı', explanation:'Spread, komisyon ve işlem maliyetlerini hesaba katma.', status:'Var', plan:'Daha gerçekçi maliyet modelleri'},
    {name:'Slippage / latency sensitivity', explanation:'Kayma ve gecikmenin sonuçlara etkisini test etme.', status:'Var', plan:'Quant Lab'},
    {name:'Final holdout', explanation:'Model seçimi sonrası dokunulmamış final test.', status:'Var', plan:'Test governance geliştirmeleri'},
  ]},
  { title: 'Optimizasyon', rows: [
    {name:'Genetic algorithm', explanation:'Feature, model ve sınırlı parametre seçimi.', status:'Var', plan:'Daha geniş arama alanı'},
    {name:'Hyperparameter optimization', explanation:'Model parametrelerini optimize etme.', status:'Var', plan:'Quant Lab fitness'},
  ]},
  { title: 'Risk ve sağlamlık', rows: [
    {name:'Stress testing', explanation:'Farklı maliyet ve piyasa koşullarında dayanıklılık testi.', status:'Var', plan:'Quant Lab'},
  ]},
  { title: 'Açıklanabilirlik', rows: [
    {name:'SHAP / permutation importance', explanation:'Feature katkılarını açıklama.', status:'Kısmen var', plan:'Açıklama kararlılığı analizi'},
  ]},
  { title: 'Deney yönetimi', rows: [
    {name:'Experiment registry', explanation:'Deney konfigürasyonu, sonuçları ve loglarını saklama.', status:'Var', plan:'Daha kapsamlı artifact yönetimi'},
    {name:'Workspace izolasyonu', explanation:'Kullanıcı ve deney alanlarını birbirinden ayırma.', status:'Var', plan:'Gelişmiş rol ve erişim yönetimi'},
  ]},
  { title: 'Notebook', rows: [
    {name:'optimusprime.ipynb desteği', explanation:'Teknik indikatör, DL ve backtest çalışmalarını referans alma.', status:'Kısmen var', plan:'Notebook çalıştırma ve migration'},
    {name:'tezmodelfinal (1).ipynb desteği', explanation:'Makro indikatörler, FX verileri, HMM ve ensemble yaklaşımı.', status:'Kısmen var', plan:'Parametreli notebook pipeline’ı'},
  ]},
];

function statusLabelFor(status: string, lang: Lang): string {
  const map: Record<string, Record<Lang, string>> = {
    queued: { tr: 'Sırada', en: 'Queued' },
    running: { tr: 'Çalışıyor', en: 'Running' },
    completed: { tr: 'Tamamlandı', en: 'Completed' },
    failed: { tr: 'Başarısız', en: 'Failed' },
    cancelled: { tr: 'İptal edildi', en: 'Cancelled' },
  };
  return map[status]?.[lang] ?? status;
}

export async function api<T>(url:string, options?:RequestInit, lang: Lang = 'tr'):Promise<T>{
  const wsId = getStoredWorkspaceId();
  const authToken = getToken();
  const langHeader = { 'Accept-Language': lang, ...(wsId?{'X-Workspace-Id':wsId}:{}), ...(authToken?{Authorization:`Bearer ${authToken}`}:{}) };
  const merged: RequestInit = { ...options, headers: { ...(options?.headers as Record<string,string> | undefined), ...langHeader } };
  const response = await fetch(`/api${url}`,merged);
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:(lang==='en'?'Request failed. Check the parameters.':'İstek tamamlanamadı. Parametreleri kontrol edin.'));}
  return response.json();
}

function Performance({result,mode,theme}:{result:Result;mode:string;theme:'dark'|'light'}){
  const { t, fmt, fmtDate, locale } = useLang();
  const pct = (v:number) => `${v>0?'+':''}${fmt(v*100)}%`;
  const step=Math.max(1,Math.ceil(result.curve.length/600));
  const points=result.curve.filter((_,i)=>i%step===0||i===result.curve.length-1);
  const data=points;
  return <div className="chart" role="img" aria-label={mode==='equity'?t('perf.ariaEquity'):t('perf.ariaDd')}>
    <ResponsiveContainer width="100%" height="100%"><ComposedChart data={data} margin={{top:18,right:8,left:0,bottom:4}}>
      <defs><linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#50dfad" stopOpacity={0.19}/><stop offset="100%" stopColor="#50dfad" stopOpacity={0}/></linearGradient></defs>
      <CartesianGrid stroke={theme==='light'?'#dce3ea':'#242b35'} strokeDasharray="3 5" vertical={false}/>
      <XAxis dataKey="timestamp" tickFormatter={s=>new Date(s).toLocaleDateString(locale,{month:'short',day:'2-digit',timeZone:'UTC'})} minTickGap={65} tick={{fill:theme==='light'?'#64748b':'#748092',fontSize:11}} axisLine={false} tickLine={false}/>
      <YAxis domain={mode==='equity'?['auto','auto']:['auto',0]} width={66} tickFormatter={v=>mode==='equity'?`$${fmt(v,0)}`:`${fmt(v,1)}%`} tick={{fill:theme==='light'?'#64748b':'#748092',fontSize:11}} axisLine={false} tickLine={false}/>
      <Tooltip contentStyle={{background:theme==='light'?'#ffffff':'#161d27',border:`1px solid ${theme==='light'?'#d5dde5':'#354153'}`,borderRadius:10,fontSize:12,color:theme==='light'?'#172033':'#e8edf4'}} labelFormatter={s=>fmtDate(String(s))} formatter={(v,name)=>[mode==='equity'?`$${fmt(Number(v))}`:`${fmt(Number(v))}%`,name]}/>
      {mode==='equity'?<><Line dataKey="benchmark" name={t('perf.benchmark')} stroke="#858fa5" dot={false} strokeDasharray="5 5" strokeWidth={1.5}/><Area dataKey="equity" name={t('perf.hmm')} type="monotone" stroke="#55dfb0" fill="url(#equityFill)" strokeWidth={2.3} isAnimationActive={false}/></>:<Area dataKey="drawdown" name={t('perf.drawdown')} stroke="#ef8f93" fill="#ef8f9320" isAnimationActive={false}/>}
    </ComposedChart></ResponsiveContainer>
  </div>;
}

function LangSwitch(){
  const { lang, setLang, t } = useLang();
  return <div className="segmented" role="group" aria-label={t('lang.label')} title={t('lang.label')}>
    <button className={lang==='tr'?'chosen':''} onClick={()=>setLang('tr')} aria-pressed={lang==='tr'}>TR</button>
    <button className={lang==='en'?'chosen':''} onClick={()=>setLang('en')} aria-pressed={lang==='en'}>EN</button>
  </div>;
}

function App(){
  const { t, lang, fmt, fmtDate, locale } = useLang();
  const pct = (v:number) => `${v>0?'+':''}${fmt(v*100)}%`;
  const time = (s:string) => { try { return new Date(s).toLocaleTimeString(locale); } catch { return s; } };
  const [datasets,setDatasets]=useState<Dataset[]>([]),[history,setHistory]=useState<Job[]>([]),[job,setJob]=useState<Job|null>(null);
  const [previewRows,setPreviewRows]=useState<Record<string,string|number>[]>([]),[previewPage,setPreviewPage]=useState(1),[previewTotal,setPreviewTotal]=useState(0);
  const previewPageSize=25;
  const [page,setPage]=useState('platform'),[modal,setModal]=useState(false),[workspaceModal,setWorkspaceModal]=useState(false),[newWsName,setNewWsName]=useState(''),[newWsMarket,setNewWsMarket]=useState('FX'),[error,setError]=useState(''),[busy,setBusy]=useState(false),[uploading,setUploading]=useState(false),[online,setOnline]=useState(false),[chartMode,setChartMode]=useState('equity');
  const { current: workspace, workspaces, switchWorkspace, createWorkspace, archiveWorkspace, error: wsError } = useWorkspace();
  const wsId = workspace?.id ?? null;
  const [platformNew,setPlatformNew]=useState(0),[resultsExperimentId,setResultsExperimentId]=useState<string|null>(null);
  const [histQuery,setHistQuery]=useState(''),[histStatus,setHistStatus]=useState(''),[histDataset,setHistDataset]=useState(''),[histView,setHistView]=useState<'grid'|'list'>('grid');
  const [datasetQuery,setDatasetQuery]=useState(''),[datasetSource,setDatasetSource]=useState(''),[datasetView,setDatasetView]=useState<'grid'|'list'>('grid');
  const [theme,setTheme]=useState<'dark'|'light'>(()=>localStorage.getItem('regimelab.theme')==='light'?'light':'dark');
  const { user: authUser, ready: authReady, logout } = useAuth();
  const [showProfile, setShowProfile] = useState(false);
  const [project,setProject]=useState<{notebooks:{name:string;cells:number}[];scope:string}|null>(null);
  const [config,setConfig]=useState<Config>({dataset_id:'demo',interval:'native',train_ratio:0.65,states:3,cost_bps:0.5,capital:10000});
  const uploadRef=useRef<HTMLInputElement>(null),dialogRef=useRef<HTMLDialogElement>(null),workspaceDialogRef=useRef<HTMLDialogElement>(null),profileMenuRef=useRef<HTMLDivElement>(null);
  const result=job?.result,active=!!job&&['running','queued'].includes(job.status);
  const selected=datasets.find(d=>d.id===config.dataset_id)||datasets[0];
  const filteredDatasets=datasets.filter(d=>{
    const q=datasetQuery.trim().toLowerCase();
    return (!q||d.name.toLowerCase().includes(q)||d.id.toLowerCase().includes(q)||d.columns.some(c=>c.toLowerCase().includes(q))) && (!datasetSource||(datasetSource==='synthetic'&&d.demo)||(datasetSource==='csv'&&!d.demo));
  });
  useEffect(()=>{
    if(!selected)return;
    let alive=true;
    api<{rows:Record<string,string|number>[];total:number}>(`/datasets/${encodeURIComponent(selected.id)}/preview?page=${previewPage}&page_size=${previewPageSize}`,undefined,lang)
      .then(v=>{if(alive){setPreviewRows(v.rows);setPreviewTotal(v.total);}})
      .catch(e=>{if(alive)setError(e.message);});
    return()=>{alive=false;};
  },[selected?.id,previewPage,lang,wsId]);
  const histDatasets=Array.from(new Set(history.map(h=>h.dataset_name).filter(Boolean)));
  const histFiltered=history.filter(h=>{
    const q=histQuery.trim().toLowerCase();
    const okQ=!q||h.id.toLowerCase().includes(q)||h.dataset_name.toLowerCase().includes(q)||statusLabelFor(h.status,lang).toLowerCase().includes(q);
    const okS=!histStatus||h.status===histStatus;
    const okD=!histDataset||h.dataset_name===histDataset;
    return okQ&&okS&&okD;
  });
  async function refresh(){const [ds,hs,pr]=await Promise.all([api<Dataset[]>('/datasets',undefined,lang),api<Job[]>('/runs',undefined,lang),api<{notebooks:{name:string;cells:number}[];scope:string}>('/project',undefined,lang)]);setDatasets(ds);setHistory(hs);setProject(pr);setOnline(true);return hs;}
  useEffect(()=>{let alive=true;refresh().then(async hs=>{if(hs.length){const j=await api<Job>(`/runs/${hs[0].id}`,undefined,lang);if(alive)setJob(j);}}).catch(e=>{setError(e.message);setOnline(false);});return()=>{alive=false;};},[wsId]);
  useEffect(()=>{if(!active||!job)return;let alive=true;const id=job.id;const timer=setInterval(()=>{api<Job>(`/runs/${id}`,undefined,lang).then(j=>{if(!alive)return;setJob(j);setOnline(true);if(!['running','queued'].includes(j.status))refresh().catch(()=>{});}).catch(e=>{if(alive){setError(e.message);setOnline(false);}});},1000);return()=>{alive=false;clearInterval(timer);};},[job?.id,active]);
  useEffect(()=>{const d=dialogRef.current;if(modal&&!d?.open)d?.showModal();if(!modal&&d?.open)d.close();},[modal]);
  useEffect(()=>{const d=workspaceDialogRef.current;if(workspaceModal&&!d?.open)d?.showModal();if(!workspaceModal&&d?.open)d.close();},[workspaceModal]);
  useEffect(()=>{
    if(!showProfile)return;
    function handleClickOutside(event:MouseEvent){
      if(profileMenuRef.current&&!profileMenuRef.current.contains(event.target as Node)){
        setShowProfile(false);
      }
    }
    function handleKeyDown(event:KeyboardEvent){
      if(event.key==='Escape'){
        setShowProfile(false);
      }
    }
    document.addEventListener('mousedown',handleClickOutside);
    document.addEventListener('keydown',handleKeyDown);
    return()=>{
      document.removeEventListener('mousedown',handleClickOutside);
      document.removeEventListener('keydown',handleKeyDown);
    };
  },[showProfile]);
  useEffect(()=>{
    document.documentElement.dataset.theme=theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='light'?'#f7f9fc':'#0c1017');
    localStorage.setItem('regimelab.theme',theme);
  },[theme]);
  async function run(){setBusy(true);setError('');try{const wsHeaders: Record<string,string> = wsId?{'X-Workspace-Id':wsId}:{};const j=await api<Job>('/runs',{method:'POST',headers:{'Content-Type':'application/json','Accept-Language':lang,...wsHeaders},body:JSON.stringify(config)},lang);setJob(j);setModal(false);setPage('overview');setOnline(true);}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function upload(file?:File){if(!file)return;setUploading(true);setError('');try{const form=new FormData();form.append('file',file);const authToken=getToken();const wsHeaders: Record<string,string> = {...(wsId?{'X-Workspace-Id':wsId}:{}),...(authToken?{Authorization:`Bearer ${authToken}`}:{})};const res=await fetch('/api/datasets',{method:'POST',headers:{'Accept-Language':lang,...wsHeaders},body:form});if(!res.ok){const body=await res.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:body.error?.message||t('api.genericError'));}const ds=await res.json() as Dataset;setDatasets(prev=>[...prev,ds]);setConfig(prev=>({...prev,dataset_id:ds.id}));setPage('data');}catch(e){setError((e as Error).message);}finally{setUploading(false);if(uploadRef.current)uploadRef.current.value='';}}
  async function openRun(id:string){try{setJob(await api<Job>(`/runs/${id}`,undefined,lang));setPage('overview');}catch(e){setError((e as Error).message);}}
  async function switchAndReload(id:string){switchWorkspace(id);setWorkspaceModal(false);setJob(null);}
  async function createAndSwitch(){const name=newWsName.trim();if(!name)return;setError('');try{await createWorkspace(name.slice(0,120),newWsMarket.trim().slice(0,16));setNewWsName('');setWorkspaceModal(false);}catch(e){setError((e as Error).message);}}
  async function archiveAndRefresh(id:string){if(!window.confirm(t('ws.confirmArchive')))return;setError('');try{await archiveWorkspace(id);}catch(e){setError((e as Error).message);}}
  const nav=[['platform',t('nav.platform'),FlaskConical],['overview',t('nav.overview'),LayoutDashboard],['data',t('nav.data'),Database],['models',t('nav.models'),Layers3],['regimes',t('nav.regimes'),Activity],['notebook','Notebook Lab',BookOpen],['history',t('nav.history'),Clock3]] as const;
  const heading:Record<string,string>={platform:t('heading.platform'),overview:t('heading.overview'),data:t('heading.data'),models:t('heading.models'),regimes:t('heading.regimes'),history:t('heading.history'),method:t('heading.method'),notebook:'Notebook Lab',account:t('nav.account'),'experiment-results':'Experiment Results'};
  if(!authReady)return <div className="auth-loading"><Loader2 size={26} className="spin"/></div>;
  if(!authUser)return <AuthPage/>;
  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#" onClick={e=>{e.preventDefault();setPage('overview');}}><span className="brand-mark"><Activity size={23}/></span><span>regime<span className="brand-light">lab</span><small>{t('brand.sub')}</small></span></a>
      <button type="button" className="workspace" onClick={()=>setWorkspaceModal(true)} title={t('ws.switchTitle')}><span className="workspace-icon">FX</span><div>{workspace?.name||t('strip.loading')}<small>{workspace?`${workspace.code} · ${workspace.experiment_count} ${t('ws.experiments')}`:t('ws.switchTitle')}</small></div><ChevronDown size={14}/></button>
      <span className="nav-label">{t('workspace.label')}</span>
      <nav>{nav.map(([id,label,Icon])=><button key={id} className={page===id?'nav-item selected':'nav-item'} onClick={()=>setPage(id)}><Icon size={18}/>{label}{id==='overview'&&<span className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-note"><div className="tiny-icon"><FlaskConical size={17}/></div><strong>{t('sidebar.tagline')}</strong><p>{t('sidebar.taglineSub')}</p><button onClick={()=>setPage('method')}>{t('sidebar.structure')} <ArrowUpRight size={14}/></button></div>
      <div className="sidebar-bottom">
        <button className={`nav-item ${page==='method'?'selected':''}`} onClick={()=>setPage('method')}><BookOpen size={18}/>{t('nav.method')}</button>
      </div>
    </aside>
    <div className="main-shell">
      <header className="topbar">
        <div className="breadcrumb">{t('topbar.workspace')} <span>/</span><b>{heading[page]}</b></div>
        <div className="topbar-right">
          <span className={online?'connection':'connection offline'}><i/>{online?t('topbar.online'):t('topbar.offline')}</span>
          <span className="local-label">LOCAL</span>
          <LangSwitch/>
          <button className="icon-button theme-toggle" title={theme==='dark'?t('topbar.light'):t('topbar.dark')} aria-label={theme==='dark'?t('topbar.light'):t('topbar.dark')} onClick={()=>setTheme(current=>current==='dark'?'light':'dark')}>{theme==='dark'?<Sun size={17}/>:<Moon size={17}/>}</button>
          <button className="icon-button" title={t('topbar.methodology')} aria-label={t('topbar.openMethodology')} onClick={()=>setPage('method')}><CircleHelp size={18}/></button>

          <div className="topbar-separator"/>

          <div className="profile-menu-container" ref={profileMenuRef}>
            <button
              type="button"
              className={`profile-trigger ${showProfile?'active':''}`}
              onClick={()=>setShowProfile(prev=>!prev)}
              aria-expanded={showProfile}
              aria-haspopup="true"
              title={authUser.name||authUser.email}
            >
              <span className="profile-avatar">
                {(authUser.name||authUser.email||'Q').trim().charAt(0).toUpperCase()}
              </span>
              <div className="profile-trigger-info hide-small">
                <span className="profile-trigger-name">{authUser.name||authUser.email?.split('@')[0]}</span>
                <span className="profile-trigger-role">{authUser.role||'Quant'}</span>
              </div>
              <ChevronDown size={14} className={`profile-chevron ${showProfile?'rotated':''}`}/>
            </button>

            {showProfile && (
              <div className="profile-dropdown-menu" role="menu">
                <div className="profile-dropdown-header">
                  <div className="profile-dropdown-avatar">
                    {(authUser.name||authUser.email||'Q').trim().charAt(0).toUpperCase()}
                  </div>
                  <div className="profile-dropdown-user-info">
                    <b className="profile-dropdown-name" title={authUser.name||authUser.email}>
                      {authUser.name || 'User'}
                    </b>
                    <small className="profile-dropdown-email" title={authUser.email}>
                      {authUser.email}
                    </small>
                    <div className="profile-dropdown-badges">
                      <span className="profile-badge-role">{authUser.role || 'Quant Trader'}</span>
                      {workspace && <span className="profile-badge-ws">{workspace.code}</span>}
                    </div>
                  </div>
                </div>

                <div className="profile-dropdown-divider"/>

                <div className="profile-dropdown-list">
                  <button
                    type="button"
                    className="profile-dropdown-item"
                    role="menuitem"
                    onClick={()=>{setPage('account');setShowProfile(false);}}
                  >
                    <User size={15}/>
                    <span>{t('profile.viewAccount')}</span>
                  </button>
                  <button
                    type="button"
                    className="profile-dropdown-item"
                    role="menuitem"
                    onClick={()=>{setWorkspaceModal(true);setShowProfile(false);}}
                  >
                    <Layers3 size={15}/>
                    <span>{t('profile.switchWs')}</span>
                  </button>
                  <button
                    type="button"
                    className="profile-dropdown-item"
                    role="menuitem"
                    onClick={()=>{setPage('notebook');setShowProfile(false);}}
                  >
                    <BookOpen size={15}/>
                    <span>{t('profile.notebookLab')}</span>
                  </button>
                </div>

                <div className="profile-dropdown-divider"/>

                <div className="profile-dropdown-list">
                  <button
                    type="button"
                    className="profile-dropdown-item danger"
                    role="menuitem"
                    onClick={()=>{logout();setShowProfile(false);}}
                  >
                    <LogOut size={15}/>
                    <span>{t('profile.logout')}</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>
    <main>
      <div className="page-heading"><div><div className="eyebrow">EUR/USD <span>·</span> {lang==='en'?'REGIME-AWARE MODELING':'REJİM ODAKLI MODELLEME'}</div><h1>{page==='overview'?t('hero.title'):heading[page]}</h1><p>{page==='overview'?t('hero.subOverview'):t('hero.subOther')}</p></div><button className="primary" onClick={()=>{setError('');if(page==='platform')setPlatformNew(n=>n+1);else setModal(true);}} disabled={page!=='platform'&&active}><Plus size={17}/>{t('action.newExperiment')}</button></div>
      {error&&<div className="alert" role="alert"><span>{error}</span><button aria-label={t('alert.closeError')} onClick={()=>setError('')}><X size={16}/></button></div>}
      <input ref={uploadRef} type="file" accept=".csv,text/csv" hidden onChange={e=>upload(e.target.files?.[0])}/>
      {page==='platform'&&<ResearchPlatform newRequest={platformNew} onOpenResults={id=>{setResultsExperimentId(id);setPage('experiment-results');}}/>}
      {page==='experiment-results'&&resultsExperimentId&&<ExperimentResultsPage experimentId={resultsExperimentId} onBack={()=>setPage('platform')}/>}
      {page==='notebook'&&<NotebookLab/>}
      {page==='account'&&<AccountPage/>}
      {page==='overview'&&<>
        <div className="dataset-strip"><div className="pair-icon">€<span>$</span></div><div className="pair-title"><strong>EUR / USD</strong><span>{t('pair.quote')}</span></div><span className="divider"/><div className="strip-detail"><small>{t('strip.source')}</small><b>{job?job.dataset_name:selected?.name||t('strip.loading')}</b></div><div className="strip-detail hide-small"><small>{t('strip.experiment')}</small><b>{job?`#${job.id.slice(0,8)}`:t('strip.notStarted')}</b></div><span className={`badge ${job?.demo??selected?.demo?'amber':''}`}>{(job?.demo??selected?.demo)?t('strip.synthetic'):t('strip.uploaded')}</span></div>
        <div className="metrics-grid">{[
          {label:t('metric.totalReturn'),value:result?pct(result.metrics.return):'—',sub:t('metric.totalReturnSub'),kind:result&&result.metrics.return>=0?'positive':'',icon:ArrowUpRight},
          {label:t('metric.sharpe'),value:result?fmt(result.metrics.sharpe):'—',sub:t('metric.sharpeSub'),kind:'',icon:Activity},
          {label:t('metric.maxDd'),value:result?pct(result.metrics.max_drawdown):'—',sub:t('metric.maxDdSub'),kind:'negative',icon:Layers3},
          {label:t('metric.posChanges'),value:result?fmt(result.metrics.position_changes,0):'—',sub:result?`${fmt(result.metrics.active_bars,0)} ${t('metric.activeBars')}`:t('metric.posChangesSub'),kind:'',icon:Zap}
        ].map(m=><div className="metric-card" key={m.label}><div className="metric-label">{m.label}<m.icon size={15}/></div><div className={`metric-value ${m.kind}`}>{m.value}</div><span className="metric-sub">{m.sub}</span></div>)}</div>
        <div className="dashboard-grid"><section className="panel performance"><div className="panel-heading"><div><h2>{t('perf.title')} <span className="mini-badge">{t('perf.testBadge')}</span></h2><p>{result?`${fmtDate(result.split.test_start)} — ${fmtDate(result.split.test_end)}`:t('perf.noResult')}</p></div><div className="segmented"><button className={chartMode==='equity'?'chosen':''} onClick={()=>setChartMode('equity')}>{t('perf.equity')}</button><button className={chartMode==='drawdown'?'chosen':''} onClick={()=>setChartMode('drawdown')}>{t('perf.drawdown')}</button></div></div>
        {result?<><div className="chart-legend"><span><i style={{background:colors[0]}}/>{t('perf.hmm')}</span><span><i style={{background:'#858fa5'}}/>{t('perf.benchmark')}</span><b>USD</b></div><Performance result={result} mode={chartMode} theme={theme}/></>:<div className="chart-empty"><div className="empty-graph"><Activity size={60} strokeWidth={1}/></div><strong>{active?t('perf.emptyTitleActive'):t('perf.emptyTitleIdle')}</strong><p>{active?t('perf.emptySubActive'):t('perf.emptySubIdle')}</p><button className="secondary" onClick={()=>setModal(true)} disabled={active}><Play size={14}/>{t('perf.configure')}</button></div>}
        <div className="panel-footer"><span className="dot green"/>{job?.demo??true?t('perf.syntheticNote'):t('perf.realNote')}<span className="right">{result?`${fmt(result.split.test,0)} ${t('perf.testBars')}`:t('perf.awaiting')}</span></div></section>
        <section className="panel pipeline"><div className="panel-heading"><div><h2>{t('pipe.title')}</h2><p>{t('pipe.sub')}</p></div><Settings2 size={17} className="muted"/></div><div className="pipeline-steps">{[[t('pipe.s1t'),t('pipe.s1s'),15],[t('pipe.s2t'),t('pipe.s2s'),65],[t('pipe.s3t'),t('pipe.s3s'),80],[t('pipe.s4t'),t('pipe.s4s'),100]].map(([title,sub,threshold],i)=>{const done=job&&job.progress>=Number(threshold),current=active&&!done&&(i===0||job.progress>=Number([0,15,65,80][i]));return <div className={`pipeline-step ${done?'done':''} ${current?'current':''}`} key={title}><span className="step-circle">{done?<Check size={14}/>:current?<Loader2 className="spin" size={14}/>:String(i+1).padStart(2,'0')}</span><div><b>{title}</b><small>{sub}</small></div></div>;})}</div><button className="run-button" disabled={active||busy||!online} onClick={()=>setModal(true)}>{active?<Loader2 size={16} className="spin"/>:<Play size={16}/>} {active?t('pipe.running'):t('pipe.run')}<ArrowRight size={16}/></button><p className="pipeline-note">{t('pipe.note')}</p></section></div>
        <div className="lower-grid"><section className="panel"><div className="panel-heading"><div><h2>{t('cmp.title')}</h2><p>{t('cmp.sub')}</p></div><button className="text-button" disabled={!result} onClick={()=>job&&window.open(`/api/runs/${job.id}/export${wsId?`?workspace_id=${encodeURIComponent(wsId)}`:''}`,'_blank')}><ArrowDownToLine size={15}/>CSV</button></div>{result?<Comparison result={result}/>:<div className="small-empty"><Layers3 size={25}/><span>{t('cmp.empty')}</span></div>}</section><section className="panel"><div className="panel-heading"><div><h2>{t('reg.title')}</h2><p>{t('reg.sub')}</p></div><Radio size={17} className="muted"/></div>{result?<div className="regime-summary"><div className="distribution">{result.regimes.map(r=><span key={r.id} style={{width:`${r.share*100}%`,background:colors[r.id]}} title={`S${r.id}: ${fmt(r.share*100,1)}%`}/>)}</div>{result.regimes.map(r=><div className="regime-line" key={r.id}><span><i className="dot" style={{background:colors[r.id]}}/>{t('reg.state')} {r.id}</span><small>{fmt(r.bars,0)} {t('reg.bar')}</small><b>{fmt(r.share*100,1)}%</b></div>)}<button className="text-button regime-link" onClick={()=>setPage('regimes')}>{t('reg.details')} <ArrowRight size={14}/></button></div>:<div className="small-empty"><Activity size={25}/><span>{t('reg.empty')}</span></div>}</section></div>
        {job&&<section className="panel log-panel"><div className="panel-heading"><div className="log-title"><Terminal size={17}/><h2>{t('log.title')}</h2><span className={`badge ${job.status==='failed'?'amber':''}`}>{statusLabelFor(job.status,lang)}</span></div><div className="log-actions"><span>{job.progress}%</span>{active&&<button className="text-button" disabled={job.cancel_requested} onClick={async()=>{try{await api(`/runs/${job.id}/cancel`,{method:'POST'},lang);setJob({...job,cancel_requested:true});}catch(e){setError((e as Error).message);}}}><Square size={12}/>{job.cancel_requested?t('log.cancelWait'):t('log.cancel')}</button>}</div></div><div className="progress-track"><span style={{width:`${job.progress}%`}}/></div><div className="logs" aria-live="polite">{job.logs.slice(-5).map((log,i)=><div key={i}><time>{time(log.time)}</time><span>{log.message}</span></div>)}{['failed','cancelled'].includes(job.status)&&<div className="negative">{job.message}</div>}</div></section>}
      </>}
      {page==='data'&&<><div className="upload-zone" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!uploading)upload(e.dataTransfer.files[0]);}}><Upload size={30}/><h2>{t('data.dropTitle')}</h2><p>{t('data.dropSub')}</p><div><button className="primary" disabled={uploading} onClick={()=>uploadRef.current?.click()}>{uploading?<Loader2 size={16} className="spin"/>:<Upload size={16}/>}{t('data.upload')}</button><a className="secondary" href="/api/sample.csv" download>{t('data.sample')}</a><a className="secondary" href="/api/sample-external.csv" download>{t('data.lagSample')}</a></div><code>Timestamp, Open, High, Low, Close[, macro__name, macro__name__available_at]</code><p className="footnote">{t('data.footnote')} <code>macro__</code>, <code>cross_asset__</code>, <code>fx__</code> {lang==='en'?'or':'veya'} <code>rates__</code> {t('data.footnote2')} <code>__available_at</code> {t('data.footnote3')}</p></div><DatasetCatalog datasets={filteredDatasets} selectedId={config.dataset_id} query={datasetQuery} setQuery={setDatasetQuery} source={datasetSource} setSource={setDatasetSource} view={datasetView} setView={setDatasetView} onSelect={id=>{setConfig({...config,dataset_id:id});setPreviewPage(1);}} />{selected&&<section className="panel spacing-top"><div className="panel-heading"><div><h2>{t('data.preview')}</h2><p>{selected.name} · {previewTotal.toLocaleString(locale)} {t('data.colRows')}</p></div><button className="secondary" onClick={()=>setModal(true)} disabled={active}>{t('data.withData')} <ArrowRight size={14}/></button></div><div className="table-wrap"><table><thead><tr><th>{t('data.colTime')}</th>{selected.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{previewRows.map((r,i)=><tr key={`${previewPage}-${i}`}><td>{String(r.timestamp).replace('T',' ').slice(0,16)}</td>{selected.columns.map(c=><td key={c}>{typeof r[c]==='number'?fmt(Number(r[c]),5):String(r[c]??'—')}</td>)}</tr>)}</tbody></table></div><div className="data-pager"><button className="secondary" disabled={previewPage<=1} onClick={()=>setPreviewPage(p=>p-1)}>← {t('data.previous')}</button><span>{previewPage} / {Math.max(1,Math.ceil(previewTotal/previewPageSize))}</span><button className="secondary" disabled={previewPage>=Math.ceil(previewTotal/previewPageSize)} onClick={()=>setPreviewPage(p=>p+1)}>{t('data.next')} →</button></div></section>}</>}
      {page==='models'&&(result?<><div className="expert-grid">{result.experts.map((expert,i)=><section className="panel expert-card" key={expert.name}><span className="expert-icon" style={{color:colors[i],background:`${colors[i]}15`}}><Layers3 size={24}/></span><span className="eyebrow">{t('models.expert')} 0{i+1}</span><h2>{expert.name}</h2><p>{expert.family}</p><div className="expert-stat"><b>{expert.features.length}</b><span>{t('models.techFeat')}</span></div><div className="feature-tags">{expert.features.map(f=><span key={f}>{f}</span>)}</div></section>)}</div><section className="panel spacing-top"><div className="panel-heading"><div><h2>{t('models.results')}</h2><p>{t('models.resultsSub')}</p></div></div><Comparison result={result}/></section></>:<Empty onStart={()=>setModal(true)} title={t('models.emptyTitle')} text={t('models.emptyText')}/>)}
      {page==='regimes'&&(result?<><div className="regime-cards">{result.regimes.map(r=><section className="panel regime-card" key={r.id}><span className="badge" style={{color:colors[r.id]}}>{t('regimes.stateBadge')} {r.id}</span><h2>{fmt(r.share*100,1)}<small>%</small></h2><p>{fmt(r.bars,0)} {t('regimes.testBars')}</p><div className="regime-stat"><span>{t('regimes.persistence')}</span><b>{fmt(r.persistence*100,1)}%</b></div><div className="regime-stat"><span>{t('regimes.meanRet')}</span><b>{fmt(r.mean_return_bps)} bp</b></div><h3>{t('regimes.weights')}</h3>{r.weights.map((w,i)=><div className="weight-row" key={i}><div><span>{result.experts[i].name}</span><b>{fmt(w*100,1)}%</b></div><div className="weight-track"><span style={{width:`${w*100}%`,background:colors[i]}}/></div></div>)}</section>)}</div><section className="panel spacing-top"><div className="panel-heading"><div><h2>{t('regimes.matrix')}</h2><p>{t('regimes.matrixSub')}</p></div></div><div className="table-wrap"><table className="transition-table"><thead><tr><th>{t('regimes.transition')}</th>{result.regimes.map(r=><th key={r.id}>S{r.id}</th>)}</tr></thead><tbody>{result.transition.map((row,i)=><tr key={i}><th>S{i}</th>{row.map((v,j)=><td key={j} style={{background:`rgba(85,223,176,${v*.23})`}}>{fmt(v*100,1)}%</td>)}</tr>)}</tbody></table></div></section><p className="footnote">{t('regimes.note')}</p></>:<Empty onStart={()=>setModal(true)} title={t('regimes.emptyTitle')} text={t('regimes.emptyText')}/>)}
      {page==='history'&&<HistoryCatalog history={history} filtered={histFiltered} datasets={histDatasets} query={histQuery} setQuery={setHistQuery} status={histStatus} setStatus={setHistStatus} dataset={histDataset} setDataset={setHistDataset} view={histView} setView={setHistView} active={active} jobId={job?.id} onOpen={openRun} onNew={()=>setModal(true)} />}
      {page==='method'&&<div className="method-layout"><section className="panel prose"><span className="eyebrow">{t('method.kicker')}</span><h2>{t('method.title')}</h2><p>{t('method.intro')}</p><h3>{t('method.notebooks')}</h3>{project?.notebooks.map(n=><div className="notebook" key={n.name}><BookOpen size={20}/><div><b>{n.name}</b><p>{n.name.startsWith('optimus')?t('method.nbOptimus'):t('method.nbTez')}</p></div><span>{n.cells} {t('method.cells')}</span></div>)}<h3>{t('method.flow')}</h3><p>{project?.scope}</p><ol>{(result?.notes||[t('method.note1'),t('method.note2'),t('method.note3'),t('method.note4'),t('method.note5')]).map(n=><li key={n}>{n}</li>)}</ol><h3>{t('method.findings')}</h3><p>{t('method.findingsText')}</p><p>{t('method.sharpe')}</p><div className="inline-note">{t('method.synthetic')}</div></section><section className="panel method-side"><h2>{t('method.protocol')}</h2><div><small>{t('method.goal')}</small><b>{t('method.goalV')}</b></div><div><small>{t('method.val')}</small><b>{t('method.valV')}</b></div><div><small>{t('method.gap')}</small><b>{t('method.gapV')}</b></div><div><small>{t('method.regime')}</small><b>{t('method.regimeV')}</b></div><div><small>{t('method.seed')}</small><b>42</b></div><div><small>{t('method.cost')}</small><b>{t('method.costV')}</b></div></section><section className="panel capability-panel"><h2>Özellik kapsamı ve gelecek planı</h2><p className="table-note">Durumlar mevcut kod ve veri sözleşmesine göre işaretlenmiştir. “Kısmen var”, temel mekanizmanın bulunduğunu ancak üretim seviyesinde tam kapsama ulaşmadığını belirtir.</p>{capabilityTables.map(table=><div className="capability-group" key={table.title}><h3>{table.title}</h3><div className="capability-table-wrap"><table className="capability-table"><thead><tr><th>Özellik</th><th>Açıklama</th><th>Durum</th><th>Gelecek planı</th></tr></thead><tbody>{table.rows.map(row=><tr key={row.name}><td><b>{row.name}</b></td><td>{row.explanation}</td><td><span className={`cap-status ${row.status.replace(' ','-').toLowerCase()}`}>{row.status}</span></td><td>{row.plan}</td></tr>)}</tbody></table></div></div>)}<p className="table-note">{t('cap.summary')}</p></section></div>}
      <footer className="footer"><span><Activity size={13}/>REGIME LAB <i/> {t('footer.built')}</span><span>{t('footer.local')}</span></footer>
    </main></div>
    <dialog ref={workspaceDialogRef} onCancel={()=>setWorkspaceModal(false)} onClick={e=>{if(e.target===workspaceDialogRef.current)setWorkspaceModal(false);}}><div><div className="dialog-heading"><span className="workspace-icon">FX</span><button type="button" className="icon-button" aria-label={t('ws.close')} onClick={()=>setWorkspaceModal(false)}><X size={20}/></button></div><h2>{t('ws.switchTitle')}</h2><p className="dialog-description">{t('ws.switchDesc')}</p>{wsError&&<div className="alert" role="alert">{wsError}</div>}<div className="workspace-list">{workspaces.map(w=><div key={w.id} className={w.id===workspace?.id?'workspace-row current':'workspace-row'}><button type="button" onClick={()=>switchAndReload(w.id)} disabled={w.id===workspace?.id}><b>{w.name}</b><small>{w.code} · {w.experiment_count} {t('ws.experiments')} · {w.dataset_count} {t('ws.datasets')}{w.id===workspace?.id?` · ${t('ws.current')}`:''}</small></button>{w.code!=='WS-DEFAULT'&&<button type="button" className="text-button" onClick={()=>archiveAndRefresh(w.id)}>{t('ws.archive')}</button>}</div>)}</div><form onSubmit={e=>{e.preventDefault();createAndSwitch();}}><div className="form-grid"><label>{t('ws.newName')}<input required maxLength={120} value={newWsName} onChange={e=>setNewWsName(e.target.value)}/></label><label>{t('ws.market')}<input maxLength={16} value={newWsMarket} onChange={e=>setNewWsMarket(e.target.value)}/></label></div><button className="primary full-width" type="submit"><Plus size={16}/>{t('ws.create')}</button></form></div></dialog>
    <dialog ref={dialogRef} onCancel={()=>setModal(false)} onClick={e=>{if(e.target===dialogRef.current)setModal(false);}}><form onSubmit={e=>{e.preventDefault();run();}}><div className="dialog-heading"><span className="expert-icon"><FlaskConical size={22}/></span><button type="button" className="icon-button" aria-label={t('ws.close')} onClick={()=>setModal(false)}><X size={20}/></button></div><h2>{t('dlg.newTitle')}</h2><p className="dialog-description">{t('dlg.newDesc')}</p>{error&&<div className="alert" role="alert">{error}</div>}
    <label>{t('dlg.dataset')}<select value={config.dataset_id} onChange={e=>setConfig({...config,dataset_id:e.target.value})}>{datasets.map(d=><option key={d.id} value={d.id}>{d.name}{d.demo?` ${t('dlg.syntheticOpt')}`:''}</option>)}</select></label>
    <div className="form-grid"><label>{t('dlg.interval')}<select value={config.interval} onChange={e=>setConfig({...config,interval:e.target.value})}><option value="native">{t('dlg.native')}</option><option value="10min">10 {lang==='en'?'minutes':'dakika'}</option><option value="1h">1 {lang==='en'?'hour':'saat'}</option><option value="4h">4 {lang==='en'?'hours':'saat'}</option><option value="1D">1 {lang==='en'?'day':'gün'}</option></select></label><label>{t('dlg.states')}<select value={config.states} onChange={e=>setConfig({...config,states:Number(e.target.value)})}>{[2,3,4,5].map(n=><option key={n} value={n}>{n} {t('dlg.statesOpt')}</option>)}</select></label><label>{t('dlg.capital')}<input required type="number" min="100" max="100000000" value={config.capital} onChange={e=>setConfig({...config,capital:Number(e.target.value)})}/></label><label>{t('dlg.cost')}<input required type="number" min="0" max="20" step="0.1" value={config.cost_bps} onChange={e=>setConfig({...config,cost_bps:Number(e.target.value)})}/></label></div>
    <label className="slider-label">{t('dlg.trainRatio')} <b>{fmt(config.train_ratio*100,0)}%</b><input type="range" min="50" max="75" step="5" value={Math.round(config.train_ratio*100)} onChange={e=>setConfig({...config,train_ratio:Number(e.target.value)/100})}/></label><div className="split-bar"><span style={{width:`${config.train_ratio*100}%`}}/><span style={{width:'15%'}}/><span style={{flex:1}}/></div><div className="split-labels"><span>{t('dlg.train')} %{fmt(config.train_ratio*100,0)}</span><span>{t('dlg.validation')} %15</span><span>{t('dlg.test')} %{fmt((.85-config.train_ratio)*100,0)}</span></div>
    <div className="inline-note"><Clock3 size={16}/><span>{t('dlg.note')}</span></div><button className="primary full-width" disabled={busy||active||!datasets.length} type="submit">{busy?<Loader2 size={16} className="spin"/>:<Play size={16}/>}{t('dlg.start')}</button></form></dialog>
  </div>;
}

function DatasetCatalog({datasets,selectedId,query,setQuery,source,setSource,view,setView,onSelect}:{datasets:Dataset[];selectedId:string;query:string;setQuery:(v:string)=>void;source:string;setSource:(v:string)=>void;view:'grid'|'list';setView:(v:'grid'|'list')=>void;onSelect:(id:string)=>void}){
  const { t, fmt, fmtDate } = useLang();
  return <section className="panel hist-catalog dataset-catalog">
    <div className="panel-heading hist-heading"><div><h2>{t('data.sets')}</h2><p>{t('data.setsSub')}</p></div><span className="badge">{datasets.length} {t('data.setCount')}</span></div>
    <div className="hist-toolbar dataset-toolbar"><div className="hist-filters">
      <label className="hist-select"><select aria-label={t('data.sourceFilter')} value={source} onChange={e=>setSource(e.target.value)}><option value="">{t('data.sourceAll')}</option><option value="synthetic">{t('data.synthetic')}</option><option value="csv">CSV</option></select><ChevronDown size={15}/></label>
      <label className="hist-search"><input placeholder={t('data.search')} aria-label={t('data.search')} value={query} onChange={e=>setQuery(e.target.value)}/><Search size={16}/></label>
      <span className="dataset-filter-count">{datasets.length} {t('data.setCount')}</span>
    </div><div className="hist-view-toggle" role="group"><button className={view==='grid'?'chosen':''} onClick={()=>setView('grid')}><LayoutGrid size={16}/></button><button className={view==='list'?'chosen':''} onClick={()=>setView('list')}><List size={16}/></button></div></div>
    {!datasets.length ? <div className="small-empty"><Database size={26}/><span>{t('data.noResults')}</span></div> : view==='grid' ? <div className="hist-grid dataset-grid">{datasets.map(d=><article className={`hist-card dataset-card ${selectedId===d.id?'dataset-selected':''}`} key={d.id}>
      <div className="hist-vendor"><span className="hist-wordmark"><Database size={22}/></span><span className={`badge ${d.demo?'amber':''}`}>{d.demo?t('data.synthetic'):'CSV'}</span></div>
      <h3>{d.name}</h3><p>{d.columns.slice(0,5).join(' · ')}{d.columns.length>5?' …':''}</p>
      <ul className="hist-meta"><li><Database size={14}/><span>{fmt(d.rows,0)} {t('data.colRows')}</span></li><li><Calendar size={14}/><span>{fmtDate(d.start)} – {fmtDate(d.end)}</span></li><li><Tag size={14}/><span>{d.columns.length} columns</span></li></ul>
      <button className="hist-learn" onClick={()=>onSelect(d.id)}>{selectedId===d.id?t('data.selected'):t('data.select')} <ArrowUpRight size={14}/></button>
    </article>)}</div> : <div className="table-wrap hist-list dataset-list"><table><thead><tr><th>{t('data.colDataset')}</th><th>{t('data.colRows')}</th><th>{t('data.colStart')}</th><th>{t('data.colSource')}</th><th /></tr></thead><tbody>{datasets.map(d=><tr key={d.id}><td><Database size={14}/> {d.name}</td><td>{fmt(d.rows,0)}</td><td>{fmtDate(d.start)}</td><td><span className={`badge ${d.demo?'amber':''}`}>{d.demo?t('data.synthetic'):'CSV'}</span></td><td><button className="hist-learn" onClick={()=>onSelect(d.id)}>{selectedId===d.id?t('data.selected'):t('data.select')} <ArrowUpRight size={14}/></button></td></tr>)}</tbody></table></div>}
  </section>;
}

function HistoryCatalog({history,filtered,datasets,query,setQuery,status,setStatus,dataset,setDataset,view,setView,active,jobId,onOpen,onNew}:{history:Job[];filtered:Job[];datasets:string[];query:string;setQuery:(v:string)=>void;status:string;setStatus:(v:string)=>void;dataset:string;setDataset:(v:string)=>void;view:'grid'|'list';setView:(v:'grid'|'list')=>void;active:boolean;jobId?:string;onOpen:(id:string)=>void;onNew:()=>void}){
  const { t, lang, fmt, fmtDate } = useLang();
  const statuses=['queued','running','completed','failed','cancelled'];
  return <section className="panel hist-catalog">
    <div className="panel-heading hist-heading"><div><h2>{t('hist.title')}</h2><p>{t('hist.sub')}</p></div><span className="badge">{history.length} {t('hist.count')}</span></div>
    <div className="hist-toolbar">
      <div className="hist-filters">
        <label className="hist-select"><select aria-label={t('hist.colStatus')} value={status} onChange={e=>setStatus(e.target.value)}><option value="">{t('hist.statusAll')}</option>{statuses.map(s=><option key={s} value={s}>{statusLabelFor(s,lang)}</option>)}</select><ChevronDown size={15}/></label>
        <label className="hist-select"><select aria-label={t('hist.colDataset')} value={dataset} onChange={e=>setDataset(e.target.value)}><option value="">{t('hist.datasetAll')}</option>{datasets.map(d=><option key={d} value={d}>{d}</option>)}</select><ChevronDown size={15}/></label>
        <label className="hist-search"><input placeholder={t('hist.searchPh')} aria-label={t('hist.searchAria')} value={query} onChange={e=>setQuery(e.target.value)}/><Search size={16}/></label>
        <button className="hist-list-btn" onClick={onNew}><Plus size={15}/>{t('action.newExperiment')}</button>
      </div>
      <div className="hist-view-toggle" role="group" aria-label="view">
        <button className={view==='grid'?'chosen':''} title={t('hist.gridView')} aria-label={t('hist.gridView')} aria-pressed={view==='grid'} onClick={()=>setView('grid')}><LayoutGrid size={16}/></button>
        <button className={view==='list'?'chosen':''} title={t('hist.listView')} aria-label={t('hist.listView')} aria-pressed={view==='list'} onClick={()=>setView('list')}><List size={16}/></button>
      </div>
    </div>
    {!filtered.length?<div className="small-empty"><Clock3 size={26}/><span>{history.length?t('hist.noResult'):t('hist.empty')}</span></div>:
    view==='grid'?<div className="hist-grid">{filtered.map(h=>{
      const m=h.result?.metrics;
      const desc=m
        ? `${lang==='en'?'Net return':'Net getiri'} ${m.return>=0?'+':''}${fmt(m.return*100)}% · Sharpe ${fmt(m.sharpe)} · ${lang==='en'?'Max DD':'Maks. düşüş'} ${fmt(m.max_drawdown*100)}%`
        : (h.message||`${h.config.states} ${t('hist.statesShort')} · ${h.config.interval} · ${fmt(h.config.cost_bps,1)} bp · $${fmt(h.config.capital,0)}`);
      return <article className="hist-card" key={h.id}>
        <div className="hist-vendor"><span className="hist-wordmark">#{h.id.slice(0,8)}</span><span className={`badge hist-status-${h.status}`}>{statusLabelFor(h.status,lang)}</span></div>
        <h3>{h.dataset_name}</h3>
        <p title={desc}>{desc}</p>
        <ul className="hist-meta">
          <li><Circle size={13}/><span>{h.config.states} {t('hist.states')} · {h.config.interval}</span></li>
          <li><Calendar size={13}/><span>{fmtDate(h.created_at)}</span></li>
          <li><Tag size={13}/><span>{h.demo?(lang==='en'?'Synthetic':'Sentetik'):'CSV'} · {h.progress}% · {h.config.train_ratio?`${fmt(h.config.train_ratio*100,0)}% train`:''}</span></li>
        </ul>
        <button className="hist-learn" disabled={active&&h.id!==jobId} onClick={()=>onOpen(h.id)}>{t('hist.learnMore')} <ArrowUpRight size={14}/></button>
      </article>;
    })}</div>:
    <div className="table-wrap hist-list"><table><thead><tr><th>{t('hist.colExp')}</th><th>{t('hist.colDataset')}</th><th>{t('hist.colDate')}</th><th>{t('hist.colStatus')}</th><th>{t('hist.colRegime')}</th><th/></tr></thead><tbody>{filtered.map(h=><tr key={h.id}><td><span className="hist-wordmark small">#{h.id.slice(0,8)}</span><small className="table-subline">{h.dataset_name}</small></td><td>{h.dataset_name}</td><td>{fmtDate(h.created_at)}</td><td><span className="badge">{statusLabelFor(h.status,lang)}</span></td><td>{h.config.states} {t('hist.states')}</td><td><button className="hist-learn" disabled={active&&h.id!==jobId} onClick={()=>onOpen(h.id)}>{t('hist.inspect')} <ArrowUpRight size={14}/></button></td></tr>)}</tbody></table></div>}
  </section>;
}

function Comparison({result}:{result:Result}){
  const { t, fmt } = useLang();
  const pct = (v:number) => `${v>0?'+':''}${fmt(v*100)}%`;
  return <div className="table-wrap"><table><thead><tr><th>{t('cmp.strategy')}</th><th>{t('cmp.return')}</th><th>{t('cmp.sharpe')}</th><th>{t('cmp.maxdd')}</th></tr></thead><tbody>{result.comparison.map((m,i)=><tr key={m.name} className={i===0?'highlight-row':''}><td><span className="model-dot" style={{background:colors[i%colors.length]}}/>{m.name}{i===0&&<span className="table-tag">{t('cmp.ensemble')}</span>}</td><td className={m.return>=0?'positive':'negative'}>{pct(m.return)}</td><td>{fmt(m.sharpe)}</td><td className="muted">{pct(m.max_drawdown)}</td></tr>)}</tbody></table></div>;
}
function Empty({onStart,title,text}:{onStart:()=>void;title:string;text:string}){
  const { t } = useLang();
  return <section className="panel big-empty"><FlaskConical size={40}/><h2>{title}</h2><p>{text}</p><button className="primary" onClick={onStart}><Play size={16}/>{t('models.create')}</button></section>;
}
export default App;
