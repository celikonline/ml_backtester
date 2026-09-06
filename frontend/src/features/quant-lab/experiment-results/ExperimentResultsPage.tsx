import { Activity, BarChart3, BrainCircuit, ChartNoAxesCombined, Database, Layers3, LineChart as LineChartIcon, ShieldCheck, Table2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { Result } from '../../../platform-api';
import { useExperimentResults } from './hooks/useExperimentResults';
import type { EquityPoint, Trade } from './types/experiment-results.types';
import ExperimentHeader from './components/ExperimentHeader';
import MetricCard from './components/MetricCard';
import EquityChart from './components/EquityChart';
import DrawdownChart from './components/DrawdownChart';
import ModelPerformanceTable from './components/ModelPerformanceTable';
import FeatureImportanceChart from './components/FeatureImportanceChart';
import GeneticFitnessChart from './components/GeneticFitnessChart';
import TradesTable from './components/TradesTable';
import TradeDetailDrawer from './components/TradeDetailDrawer';
import AllocationPanel from './components/AllocationPanel';
import ExposurePanel from './components/ExposurePanel';
import './experiment-results.css';

function pct(v: unknown) { return typeof v === 'number' && Number.isFinite(v) ? `${(v * 100).toFixed(2)}%` : '—'; }
function num(v: unknown) { return typeof v === 'number' && Number.isFinite(v) ? v.toFixed(2) : '—'; }

function phaseFor(index: number, total: number, result: Result): EquityPoint['phase'] {
  const development = Math.max(0, Number(result.split?.development || 0));
  const test = Math.max(0, Number(result.split?.test || 0));
  if (development && index < development) return 'development';
  if (test && index >= total - test) return 'test';
  return 'validation';
}


export default function ExperimentResultsPage({ experimentId, onBack }: { experimentId: string; onBack: () => void }) {
  const { data, loading, error, reload } = useExperimentResults(experimentId);
  const [selectedTrade, setSelectedTrade] = useState<Trade | null>(null);
  const points = useMemo<EquityPoint[]>(() => data?.result?.curve?.map((p, i, all) => ({ ...p, phase: phaseFor(i, all.length, data.result!) })) || [], [data]);
  if (loading) return <div className="experiment-results-page"><div className="panel big-empty"><div className="loading-spinner"/><h2>Experiment dashboard yükleniyor…</h2></div></div>;
  if (error || !data) return <div className="experiment-results-page"><div className="alert">{error || 'Dashboard verisi bulunamadı.'}<button className="secondary" onClick={() => void reload()}>Tekrar dene</button></div></div>;
  const { experiment, result, optimization, features, models, trades, allocation, exposure } = data;
  if (experiment.status !== 'COMPLETED' || !result) return <div className="experiment-results-page"><ExperimentHeader experiment={experiment} onBack={onBack} onRefresh={() => void reload()}/><section className="panel big-empty"><ShieldCheck size={34}/><h2>Sonuç henüz hazır değil</h2><p>Experiment tamamlandığında bu ekran KPI, equity, optimizasyon ve trade verilerini gösterecek.</p></section></div>;
  const last = points[points.length - 1];
  const psr = result.metrics.psr;
  return <div className="experiment-results-page"><ExperimentHeader experiment={experiment} onBack={onBack} onRefresh={() => void reload()}/><div className="experiment-result-kpis"><MetricCard label="Total Return" value={pct(result.metrics.return)} detail="test sonucu" icon={ChartNoAxesCombined}/><MetricCard label="Sharpe" value={num(result.metrics.sharpe)} detail="test sonucu" icon={Activity}/><MetricCard label="Max Drawdown" value={pct(result.metrics.max_drawdown)} detail="test sonucu" icon={Layers3}/><MetricCard label="PSR" value={pct(psr)} detail={psr === undefined ? 'persist edilmemiş' : 'probabilistic Sharpe'} icon={ShieldCheck}/><MetricCard label="Portfolio Value" value={last ? num(last.equity) : '—'} detail="son equity noktası" icon={Database}/></div><section className="experiment-result-grid two"><section className="panel"><div className="panel-heading"><div><h2>Equity curve</h2><p>Strategy / benchmark · development / validation / test bölgeleri</p></div><LineChartIcon size={17} className="muted"/></div><div className="experiment-result-legend"><span><i className="legend-dot mint"/>Strategy</span><span><i className="legend-dot purple"/>Benchmark</span><span><i className="legend-dot test"/>Test</span></div><EquityChart points={points}/></section><section className="panel"><div className="panel-heading"><div><h2>Drawdown</h2><p>Persisted curve üzerinden hesaplanan drawdown</p></div><BarChart3 size={17} className="muted"/></div><DrawdownChart points={points}/></section></section><section className="experiment-result-grid two"><section className="panel"><div className="panel-heading"><div><h2>Portfolio allocation</h2><p>Pozisyon durumları</p></div></div><AllocationPanel data={allocation}/></section><section className="panel"><div className="panel-heading"><div><h2>Exposure</h2><p>Net / gross sinyal exposure özeti</p></div></div><ExposurePanel data={exposure}/></section></section><section className="panel"><div className="panel-heading"><div><h2>Model performance</h2><p>Seçilen model ve persisted candidate sonuçları</p></div><BrainCircuit size={17} className="muted"/></div><ModelPerformanceTable result={result} models={models}/></section><section className="experiment-result-grid two"><section className="panel"><div className="panel-heading"><div><h2>Feature importance</h2><p>{features?.evaluations?.length ? 'Feature intelligence' : 'Feature analysis'}</p></div></div><FeatureImportanceChart result={result} features={features}/></section><section className="panel"><div className="panel-heading"><div><h2>Genetic optimization</h2><p>Generation fitness progression</p></div></div><GeneticFitnessChart generations={optimization?.generations || result.optimization?.generations || []}/></section></section><section className="panel"><div className="panel-heading"><div><h2>Trades</h2><p>Position-change timeline</p></div><span className="badge"><Table2 size={13}/> {trades.length}</span></div><TradesTable trades={trades} onSelect={setSelectedTrade}/></section><TradeDetailDrawer trade={selectedTrade} onClose={() => setSelectedTrade(null)}/></div>;
}
