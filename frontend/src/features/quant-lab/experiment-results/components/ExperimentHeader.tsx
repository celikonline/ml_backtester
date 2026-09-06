import { ArrowLeft, Download, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { download } from '../../../../platform-api';
import type { Experiment } from '../../../../platform-api';
import { getSignalConfidence } from '../api/experiment-results.api';
import type { SignalConfidence } from '../types/experiment-results.types';
import SignalConfidencePanel from './SignalConfidencePanel';

export default function ExperimentHeader({ experiment, onBack, onRefresh }: { experiment: Experiment; onBack: () => void; onRefresh: () => void }) {
  const [confidence, setConfidence] = useState<SignalConfidence | null>(null);
  useEffect(() => { if (experiment.status === 'COMPLETED') void getSignalConfidence(experiment.id).then(setConfidence); else setConfidence(null); }, [experiment.id, experiment.status]);
  return <><section className="experiment-result-header"><div className="experiment-result-header-main"><button className="text-button" onClick={onBack}><ArrowLeft size={15}/> Deneylere dön</button><span className="eyebrow">{experiment.code} · EXPERIMENT RESULTS</span><h1>{experiment.name}</h1><p>{experiment.snapshot.details.name} · {experiment.specification.symbol} · {experiment.specification.timeframe}</p><div className="experiment-result-meta"><span>{experiment.specification.validation.method}</span><span>{experiment.specification.models.join(' + ')}</span><span>{experiment.snapshot.details.rows.toLocaleString('tr-TR')} bar</span><code>SHA256 {experiment.snapshot.sha256.slice(0, 16)}…</code></div></div><div className="experiment-result-header-actions"><span className="badge">{experiment.status}</span><button className="secondary" onClick={onRefresh}><RefreshCw size={14}/> Yenile</button><button className="secondary" disabled={experiment.status !== 'COMPLETED'} onClick={() => void download(`/experiments/${experiment.id}/export`, `${experiment.code}.csv`)}><Download size={14}/> CSV</button></div></section>{confidence && <section className="panel signal-confidence-panel"><div className="panel-heading"><div><h2>Signal confidence</h2><p>Model sinyali büyüklüğünden türetilen confidence serisi</p></div></div><SignalConfidencePanel data={confidence}/></section>}</>;
}
