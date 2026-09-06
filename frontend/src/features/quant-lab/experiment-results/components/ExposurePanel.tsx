import type { DashboardExposure } from '../types/experiment-results.types';

const n = (v: number) => v.toFixed(3);
export default function ExposurePanel({ data }: { data: DashboardExposure | null }) {
  if (!data) return <div className="experiment-result-empty">Exposure verisi mevcut değil.</div>;
  return <div className="exposure-panel"><div className="exposure-values"><div><span>Net exposure</span><b>{n(data.net)}</b></div><div><span>Gross exposure</span><b>{n(data.gross)}</b></div></div><div className="exposure-split"><span>Long {`${(data.long_share * 100).toFixed(1)}%`}</span><span>Short {`${(data.short_share * 100).toFixed(1)}%`}</span><span>Flat {`${(data.flat_share * 100).toFixed(1)}%`}</span></div><p className="chart-note">Kaynak: {data.source}. Trade-level execution exposure ayrıca persist edilmemiştir.</p></div>;
}
