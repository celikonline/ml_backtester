import type { LucideIcon } from 'lucide-react';

export default function MetricCard({ label, value, detail, icon: Icon }: { label: string; value: string; detail?: string; icon?: LucideIcon }) {
  return <div className="experiment-result-metric"><div className="experiment-result-metric-label">{label}{Icon && <Icon size={15}/>}</div><strong>{value}</strong>{detail && <span>{detail}</span>}</div>;
}
