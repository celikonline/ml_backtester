import { X } from 'lucide-react';
import type { Trade } from '../types/experiment-results.types';

export default function TradeDetailDrawer({ trade, onClose }: { trade: Trade | null; onClose: () => void }) {
  if (!trade) return null;
  return <div className="trade-detail-drawer" role="dialog" aria-label="Trade detayı"><div className="panel-heading"><h3>Trade detayı</h3><button className="icon-button" onClick={onClose} aria-label="Kapat"><X size={16}/></button></div><dl>{Object.entries(trade).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value ?? '—')}</dd></div>)}</dl></div>;
}
