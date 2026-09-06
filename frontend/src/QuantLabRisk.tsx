import { useState } from 'react';
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { request, requestQuant } from './platform-api';
import type { Experiment, QuantCalibration, QuantFitness, QuantQuantile, QuantStress, QuantStressRow, Result } from './platform-api';
import { useLang } from './i18n';
import { demoCalibration, demoQuantile, demoStress } from './quant-demo';

export default function ModelsTab() {
  return <><FitnessCard /><CalibrationCard /><QuantileCard /></>;
}

function FitnessCard() {
  const { t, fmt } = useLang();
  const [sharpe, setSharpe] = useState(1.2), [quality, setQuality] = useState(0.6);
  const [dd, setDd] = useState(-0.12), [turnover, setTurnover] = useState(8);
  const [out, setOut] = useState<QuantFitness | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function run() {
    setBusy(true); setError('');
    try { setOut(await requestQuant<QuantFitness>('/optimization/fitness', 'POST', { sharpe, feature_quality: quality, max_drawdown: dd, turnover })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  const rows = out ? [
    ['Sharpe', out.breakdown.sharpe_contribution, '#55dfb0'],
    ['Feature quality', out.breakdown.feature_quality_contribution, '#8b91f3'],
    ['Drawdown', -out.breakdown.drawdown_penalty, '#ef8f93'],
    ['Turnover', -out.breakdown.turnover_penalty, '#efb66c'],
  ] as const : [];
  return <section className="panel"><div className="panel-heading"><div><h2>{t('q.fitness')}</h2><p>w1·sharpe + w2·quality − w3·dd − w4·turnover</p></div>
    <button className="primary" disabled={busy} onClick={run}>{busy ? '…' : t('q.run')}</button></div>
    {error && <div className="alert">{error}</div>}
    <div className="research-filters">
      <label>Sharpe<input type="number" step={0.1} value={sharpe} onChange={(e) => setSharpe(Number(e.target.value))} /></label>
      <label>Quality<input type="number" min={0} max={1} step={0.05} value={quality} onChange={(e) => setQuality(Number(e.target.value))} /></label>
      <label>Drawdown<input type="number" step={0.01} value={dd} onChange={(e) => setDd(Number(e.target.value))} /></label>
      <label>Turnover<input type="number" min={0} value={turnover} onChange={(e) => setTurnover(Number(e.target.value))} /></label>
    </div>
    {out && <><div className="inline-note">fitness = <b>{fmt(out.fitness, 4)}</b></div>
      <div className="survival-list">{rows.map(([l, v]) => <div className="weight-row" key={l}><div><span>{l}</span><b>{fmt(v, 4)}</b></div>
        <div className="weight-track"><span style={{ width: `${Math.min(100, Math.abs(v) * 100)}%`, background: v >= 0 ? '#55dfb0' : '#ef8f93' }} /></div></div>)}</div></>}
  </section>;
}

function CalibrationCard() {
  const { t, fmt } = useLang();
  const [method, setMethod] = useState('isotonic');
  const [out, setOut] = useState<QuantCalibration | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function run() {
    setBusy(true); setError('');
    try { const d = demoCalibration(); setOut(await requestQuant<QuantCalibration>('/calibration/run', 'POST', { ...d, method })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  const points = out ? out.curve_raw.prob_pred.map((p, i) => ({
    x: p, raw: out.curve_raw.prob_true[i],
    cal: out.curve_calibrated ? out.curve_calibrated.prob_true[Math.min(i, out.curve_calibrated.prob_true.length - 1)] : null,
  })) : [];
  return <section className="panel spacing-top"><div className="panel-heading"><div><h2>{t('q.calibration')}</h2>
    <p>{out ? `Brier ${fmt(out.brier_raw, 4)} → ${fmt(out.brier_calibrated, 4)} · LogLoss ${fmt(out.log_loss_raw, 4)} → ${fmt(out.log_loss_calibrated, 4)}` : 'Platt / isotonic'}</p></div>
    <div className="research-filters" style={{ padding: 0 }}><label>Method<select value={method} onChange={(e) => setMethod(e.target.value)}><option value="isotonic">Isotonic</option><option value="sigmoid">Platt (sigmoid)</option></select></label>
      <button className="primary" disabled={busy} onClick={run}>{busy ? '…' : `${t('q.run')} · ${t('q.demo')}`}</button></div></div>
    {error && <div className="alert">{error}</div>}
    {out && <div className="research-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={points}><CartesianGrid stroke="#27313f" /><XAxis dataKey="x" type="number" domain={[0, 1]} /><YAxis domain={[0, 1]} /><Tooltip contentStyle={{ background: '#172130' }} /><Line dataKey="raw" name="raw" stroke="#efb66c" dot={false} /><Line dataKey="cal" name="calibrated" stroke="#55dfb0" dot={false} /></ComposedChart></ResponsiveContainer></div>}
  </section>;
}

function QuantileCard() {
  const { t, fmt } = useLang();
  const [out, setOut] = useState<QuantQuantile | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function run() {
    setBusy(true); setError('');
    try { const d = demoQuantile(); setOut(await requestQuant<QuantQuantile>('/quantile/predict', 'POST', { ...d, quantiles: [0.1, 0.5, 0.9] })); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  const chart = (out?.predictions || []).slice(0, 120).map((p, i) => ({ i, ...p }));
  return <section className="panel spacing-top"><div className="panel-heading"><div><h2>{t('q.quantile')}</h2><p>{out ? `${out.predictions.length} bar` : 'LightGBM quantile / sklearn GBR'}</p></div>
    <button className="primary" disabled={busy} onClick={run}>{busy ? '…' : `${t('q.run')} · ${t('q.demo')}`}</button></div>
    {error && <div className="alert">{error}</div>}
    {out && <><div className="research-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chart}><CartesianGrid stroke="#27313f" /><XAxis dataKey="i" /><YAxis domain={['auto', 'auto']} /><Tooltip contentStyle={{ background: '#172130' }} /><Line dataKey="p10" stroke="#8b91f3" dot={false} /><Line dataKey="p50" stroke="#55dfb0" dot={false} strokeWidth={2} /><Line dataKey="p90" stroke="#8b91f3" dot={false} /></ComposedChart></ResponsiveContainer></div>
      <div className="table-wrap"><table><thead><tr><th>#</th><th>P10</th><th>P50</th><th>P90</th></tr></thead>
        <tbody>{out.predictions.slice(0, 15).map((p, i) => <tr key={i}><td>{i + 1}</td><td>{fmt(p.p10, 4)}</td><td>{fmt(p.p50, 4)}</td><td>{fmt(p.p90, 4)}</td></tr>)}</tbody></table></div></>}
  </section>;
}

export function StressTab({ experiments }: { experiments: Experiment[] }) {
  const { t, fmt } = useLang();
  const done = experiments.filter((e) => e.status === 'COMPLETED');
  const [expId, setExpId] = useState('');
  const [out, setOut] = useState<QuantStress | null>(null);
  const [latency, setLatency] = useState<QuantStressRow[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function run() {
    setBusy(true); setError('');
    try {
      let preds: number[], actuals: number[];
      if (expId) {
        const r = await request<Result>(`/experiments/${expId}/result`);
        preds = r.curve.map((p) => p.prediction_bps / 10000);
        actuals = r.curve.map((p) => p.return);
      } else { ({ predictions: preds, actuals } = demoStress()); }
      const body = { predictions: preds.slice(0, 2000), actuals: actuals.slice(0, 2000) };
      const [s, l] = await Promise.all([
        requestQuant<QuantStress>('/backtest/stress', 'POST', body),
        requestQuant<QuantStressRow[]>('/backtest/latency-stress', 'POST', body),
      ]);
      setOut(s); setLatency(l);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  }
  const pct = (v: number) => `${fmt(v * 100)}%`;
  const cards = out ? [
    [`${t('q.base')} Sharpe`, fmt(out.base.sharpe)], [`${t('q.worst')} Sharpe`, fmt(out.worst.sharpe)],
    [`${t('q.base')} return`, pct(out.base.total_return)], [`${t('q.worst')} return`, pct(out.worst.total_return)],
    [`${t('q.base')} DD`, pct(out.base.max_drawdown)], [`${t('q.worst')} DD`, pct(out.worst.max_drawdown)],
  ] : [];
  const mat = out ? Object.entries(out.sharpe_matrix) : [];
  const matCols = mat.length ? Object.keys(mat[0][1]) : [];
  const allSharpes = mat.flatMap(([, row]) => Object.values(row));
  const lo = Math.min(...allSharpes, 0), hi = Math.max(...allSharpes, 0.01);
  return <>
    <section className="panel"><div className="panel-heading"><div><h2>{t('q.stress')}</h2><p>{done.length ? t('q.experiment') : t('q.noCompleted')}</p></div>
      <div className="research-filters" style={{ padding: 0 }}>
        {done.length > 0 && <label>{t('q.experiment')}<select value={expId} onChange={(e) => setExpId(e.target.value)}><option value="">{t('q.demo')}</option>{done.map((e) => <option key={e.id} value={e.id}>{e.code} · {e.name}</option>)}</select></label>}
        <button className="primary" disabled={busy} onClick={run}>{busy ? '…' : t('q.run')}</button></div></div>
      {error && <div className="alert">{error}</div>}
      {out && <div className="metrics-grid">{cards.map(([l, v]) => <div className="metric-card" key={l}><div className="metric-label">{l}</div><div className="metric-value">{v}</div></div>)}</div>}
    </section>
    {out && <>
      <section className="panel spacing-top"><div className="panel-heading"><div><h2>Commission × Slippage</h2><p>Sharpe</p></div></div>
        <div className="table-wrap"><table><thead><tr><th>comm ↓ · slip →</th>{matCols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{mat.map(([comm, row]) => <tr key={comm}><td>{comm}</td>{matCols.map((c) => { const v = row[c]; const a = 0.15 + 0.7 * ((v - lo) / Math.max(1e-9, hi - lo)); return <td key={c} style={{ background: `rgba(85,223,176,${a.toFixed(2)})` }}>{fmt(v)}</td>; })}</tr>)}</tbody></table></div></section>
      <section className="panel spacing-top"><div className="panel-heading"><div><h2>Latency → Sharpe</h2></div></div>
        <div className="research-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={latency}><CartesianGrid stroke="#27313f" /><XAxis dataKey="latency_bars" /><YAxis domain={['auto', 'auto']} /><Tooltip contentStyle={{ background: '#172130' }} /><Line dataKey="sharpe" stroke="#efb66c" dot strokeWidth={2} /></ComposedChart></ResponsiveContainer></div>
        <div className="table-wrap"><table><thead><tr><th>Scenario</th><th>Sharpe</th><th>Return</th><th>DD</th></tr></thead>
          <tbody>{out.scenarios.map((s) => <tr key={s.scenario}><td>{s.scenario}</td><td>{fmt(s.sharpe)}</td><td>{pct(s.total_return)}</td><td>{pct(s.max_drawdown)}</td></tr>)}</tbody></table></div></section>
    </>}
  </>;
}
