import { useMemo, useState } from 'react';
import { Check } from 'lucide-react';
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { requestQuant } from './platform-api';
import type { Experiment, QuantFold, QuantICDecayRow, QuantQuality } from './platform-api';
import { useLang } from './i18n';
import { demoFeatureMatrix, pearson } from './quant-demo';
import ModelsTab, { StressTab } from './QuantLabRisk';

export default function QuantLab({ experiments }: { experiments: Experiment[] }) {
  const { t } = useLang();
  const [tab, setTab] = useState('quality');
  return <>
    <div className="research-tabs detail-tabs">
      {[['quality', t('q.quality')], ['validation', t('q.validation')], ['models', t('q.models')], ['stress', t('q.stress')]].map(([id, l]) =>
        <button key={id} className={tab === id ? 'chosen' : ''} onClick={() => setTab(id)}>{l}</button>)}
    </div>
    {tab === 'quality' && <QualityTab />}
    {tab === 'validation' && <ValidationTab />}
    {tab === 'models' && <ModelsTab />}
    {tab === 'stress' && <StressTab experiments={experiments} />}
  </>;
}

function QualityTab() {
  const { t, fmt } = useLang();
  const [matrix, setMatrix] = useState<{ features: Record<string, number[]>; target: number[] } | null>(null);
  const [report, setReport] = useState<QuantQuality | null>(null);
  const [decay, setDecay] = useState<QuantICDecayRow[]>([]);
  const [decayFeat, setDecayFeat] = useState('');
  const [minIc, setMinIc] = useState(0), [minStab, setMinStab] = useState(0);
  const [selOnly, setSelOnly] = useState(false), [cluster, setCluster] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const names = useMemo(() => (matrix ? Object.keys(matrix.features) : []), [matrix]);
  const corr = useMemo(() => {
    if (!matrix) return [];
    const cols = names.slice(0, 8);
    return cols.map((a) => ({ feat: a, row: cols.map((b) => pearson(matrix.features[a], matrix.features[b])) }));
  }, [matrix, names]);

  async function run() {
    setBusy(true); setError('');
    try {
      const m = demoFeatureMatrix();
      setMatrix(m); setCluster(''); setDecay([]); setDecayFeat('');
      setReport(await requestQuant<QuantQuality>('/features/quality', 'POST', { features: m.features, target: m.target, threshold: 0.85 }));
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  async function showDecay(feat: string) {
    if (!matrix) return;
    setDecayFeat(feat);
    try { setDecay(await requestQuant<QuantICDecayRow[]>('/features/ic-decay', 'POST', { feature: matrix.features[feat], feature_name: feat, target: matrix.target })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  const rows = (report?.quality || []).filter((r) =>
    r.abs_ic >= minIc && r.sign_consistency >= minStab && (!selOnly || r.selected) && (!cluster || r.cluster === cluster));
  const clusters = Object.keys(report?.clusters || {});
  return <>
    <section className="panel">
      <div className="panel-heading"><div><h2>{t('q.quality')}</h2><p>IC · sign consistency · cluster · selected</p></div>
        <button className="primary" disabled={busy} onClick={run}>{busy ? '…' : `${t('q.run')} · ${t('q.demo')}`}</button></div>
      {error && <div className="alert">{error}</div>}
      {report && <div className="research-filters">
        <label>{t('q.minIc')}<input type="number" min={0} max={1} step={0.05} value={minIc} onChange={(e) => setMinIc(Number(e.target.value))} /></label>
        <label>{t('q.minStab')}<input type="number" min={0} max={1} step={0.05} value={minStab} onChange={(e) => setMinStab(Number(e.target.value))} /></label>
        <label><input type="checkbox" checked={selOnly} onChange={(e) => setSelOnly(e.target.checked)} />{t('q.selOnly')}</label>
        <label>{t('q.cluster')}<select value={cluster} onChange={(e) => setCluster(e.target.value)}><option value="">{t('q.all')}</option>{clusters.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
      </div>}
    </section>
    {report && <>
      <section className="panel"><div className="panel-heading"><div><h2>IC</h2><p>{rows.length} feature</p></div></div>
        <div className="survival-list">{[...rows].sort((a, b) => b.abs_ic - a.abs_ic).map((r) =>
          <div className="weight-row" key={r.feature}><div><span>{r.feature}</span><b>{fmt(r.ic, 3)}</b></div>
            <div className="weight-track"><span style={{ width: `${r.abs_ic * 100}%`, background: r.ic >= 0 ? '#55dfb0' : '#ef8f93' }} /></div></div>)}</div>
      </section>
      <section className="panel spacing-top"><div className="panel-heading"><div><h2>Feature</h2><p>quality · cluster · selected</p></div>
        <div className="research-filters" style={{ padding: 0 }}><label>Decay<select value={decayFeat} onChange={(e) => showDecay(e.target.value)}><option value="">—</option>{names.map((n) => <option key={n} value={n}>{n}</option>)}</select></label></div></div>
        <div className="table-wrap"><table><thead><tr><th>Feature</th><th>IC</th><th>|IC|</th><th>Sign</th><th>Quality</th><th>Cluster</th><th>✓</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.feature}><td>{r.feature}</td><td>{fmt(r.ic, 3)}</td><td>{fmt(r.abs_ic, 3)}</td><td>{fmt(r.sign_consistency, 2)}</td><td>{fmt(r.quality_score, 3)}</td><td>{r.cluster || '—'}</td><td>{r.selected ? <Check size={14} /> : '—'}</td></tr>)}</tbody></table></div>
      </section>
      {decay.length > 0 && <section className="panel spacing-top"><div className="panel-heading"><div><h2>{t('q.decay')}</h2><p>{decayFeat}</p></div></div>
        <div className="research-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={decay}><CartesianGrid stroke="#27313f" /><XAxis dataKey="horizon" /><YAxis domain={[-1, 1]} /><Tooltip contentStyle={{ background: '#172130' }} /><Line dataKey="ic" stroke="#8b91f3" dot strokeWidth={2} /></ComposedChart></ResponsiveContainer></div></section>}
      {corr.length > 0 && <section className="panel spacing-top"><div className="panel-heading"><div><h2>{t('q.corr')}</h2><p>Spearman ≈ Pearson (demo)</p></div></div>
        <div className="table-wrap"><table><thead><tr><th>—</th>{corr.map((c) => <th key={c.feat}>{c.feat.slice(0, 10)}</th>)}</tr></thead>
          <tbody>{corr.map((c, i) => <tr key={c.feat}><td>{c.feat.slice(0, 10)}</td>{c.row.map((v, j) => <td key={j} style={{ background: `rgba(139,145,243,${Math.abs(v) * 0.85})` }}>{fmt(v, 2)}</td>)}</tr>)}</tbody></table></div></section>}
    </>}
  </>;
}

function ValidationTab() {
  const { t, fmt } = useLang();
  const [mode, setMode] = useState('purged');
  const [n, setN] = useState(1000), [splits, setSplits] = useState(5), [purge, setPurge] = useState(5), [embargo, setEmbargo] = useState(1);
  const [trainWin, setTrainWin] = useState(500), [testWin, setTestWin] = useState(50), [step, setStep] = useState(50);
  const [folds, setFolds] = useState<QuantFold[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function run() {
    setBusy(true); setError('');
    try {
      if (mode === 'purged') {
        const r = await requestQuant<{ folds: QuantFold[] }>('/validation/purged-kfold', 'POST', { n_samples: n, n_splits: splits, purge_window: purge, embargo_pct: embargo / 100 });
        setFolds(r.folds);
      } else {
        const r = await requestQuant<{ folds: QuantFold[] }>('/validation/retraining', 'POST', { n_samples: n, mode, train_window: trainWin, test_window: testWin, step, initial_train_window: trainWin });
        setFolds(r.folds);
      }
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  const seg = (f: QuantFold, i: number) => {
    const t0 = f.train.length ? f.train[0] : 0, t1 = f.train.length ? f.train[f.train.length - 1] : 0;
    const v0 = f.validation[0] || 0, v1 = f.validation[f.validation.length - 1] || 0;
    const nextV = folds[i + 1]?.validation[0] ?? n;
    return { t0, t1, v0, v1, emb1: Math.min(n, Math.max(v1, nextV)) };
  };
  const bar = (a: number, b: number, color: string) => ({ left: `${(a / n) * 100}%`, width: `${Math.max(0.4, ((b - a) / n) * 100)}%`, background: color });
  return <>
    <section className="panel"><div className="panel-heading"><div><h2>{t('q.validation')}</h2><p>TRAIN · PURGE · VALIDATION · EMBARGO</p></div>
      <button className="primary" disabled={busy} onClick={run}>{busy ? '…' : t('q.run')}</button></div>
      {error && <div className="alert">{error}</div>}
      <div className="research-filters">
        <label>{t('q.mode')}<select value={mode} onChange={(e) => setMode(e.target.value)}><option value="purged">Purged K-Fold</option><option value="rolling">Rolling</option><option value="anchored">Anchored</option></select></label>
        <label>{t('q.nSamples')}<input type="number" min={10} max={200000} value={n} onChange={(e) => setN(Number(e.target.value))} /></label>
        {mode === 'purged' ? <>
          <label>{t('q.folds')}<input type="number" min={2} max={10} value={splits} onChange={(e) => setSplits(Number(e.target.value))} /></label>
          <label>{t('q.purge')}<input type="number" min={0} max={1000} value={purge} onChange={(e) => setPurge(Number(e.target.value))} /></label>
          <label>{t('q.embargo')}<input type="number" min={0} max={50} step={0.5} value={embargo} onChange={(e) => setEmbargo(Number(e.target.value))} /></label>
        </> : <>
          <label>{t('q.trainWin')}<input type="number" min={10} value={trainWin} onChange={(e) => setTrainWin(Number(e.target.value))} /></label>
          <label>{t('q.testWin')}<input type="number" min={1} value={testWin} onChange={(e) => setTestWin(Number(e.target.value))} /></label>
          <label>{t('q.step')}<input type="number" min={1} value={step} onChange={(e) => setStep(Number(e.target.value))} /></label>
        </>}
      </div></section>
    {folds.length > 0 && <>
      <section className="panel spacing-top"><div className="panel-heading"><div><h2>{t('q.timeline')}</h2><p>{folds.length} fold</p></div>
        <div className="overlay-legend"><span><i style={{ background: '#55dfb0' }} />TRAIN</span><span><i style={{ background: '#39475a' }} />PURGE</span><span><i style={{ background: '#8b91f3' }} />VALIDATION</span><span><i style={{ background: '#efb66c' }} />EMBARGO</span></div></div>
        <div style={{ padding: '0 20px 20px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {folds.map((f, i) => { const s = seg(f, i); return <div key={i} style={{ position: 'relative', height: 18, background: '#1c2530', borderRadius: 4 }}>
            <span style={{ position: 'absolute', top: 0, bottom: 0, ...bar(s.t0, s.t1 + 1, '#55dfb0') }} />
            <span style={{ position: 'absolute', top: 0, bottom: 0, ...bar(s.t1 + 1, s.v0, '#39475a') }} />
            <span style={{ position: 'absolute', top: 0, bottom: 0, ...bar(s.v0, s.v1 + 1, '#8b91f3') }} />
            <span style={{ position: 'absolute', top: 0, bottom: 0, ...bar(s.v1 + 1, s.emb1, '#efb66c') }} />
          </div>; })}
        </div></section>
      <section className="panel spacing-top"><div className="panel-heading"><div><h2>Fold</h2></div></div>
        <div className="table-wrap"><table><thead><tr><th>#</th><th>Train</th><th>Validation</th><th>Gap</th></tr></thead>
          <tbody>{folds.map((f, i) => { const s = seg(f, i); return <tr key={i}><td>{i + 1}</td><td>{fmt(f.train.length, 0)} bar</td><td>{s.v0}–{s.v1}</td><td>{s.v0 - s.t1 - 1}</td></tr>; })}</tbody></table></div></section>
    </>}
  </>;
}
