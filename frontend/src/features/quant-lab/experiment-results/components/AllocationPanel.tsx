import type { DashboardAllocation } from '../types/experiment-results.types';

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
export default function AllocationPanel({ data }: { data: DashboardAllocation | null }) {
  if (!data) return <div className="experiment-result-empty">Allocation verisi mevcut değil.</div>;
  return <div className="allocation-panel"><div className="allocation-asset">{data.asset}<span>{data.derived ? 'signal-derived' : 'persisted'}</span></div>{data.items.map(item => <div className="allocation-row" key={item.name}><span>{item.name}</span><b>{pct(item.value)}</b><i><em style={{ width: `${Math.max(0, Math.min(100, item.value * 100))}%` }}/></i></div>)}<p className="chart-note">Kaynak: {data.source}. Gerçek portfolio ağırlıkları ayrı persist edilmemiştir.</p></div>;
}
