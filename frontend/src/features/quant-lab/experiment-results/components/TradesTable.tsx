import type { Trade } from '../types/experiment-results.types';

const value = (v: unknown) => typeof v === 'number' ? v.toFixed(5) : String(v ?? '—');
export default function TradesTable({ trades, onSelect }: { trades: Trade[]; onSelect: (trade: Trade) => void }) {
  if (!trades.length) return <div className="experiment-result-empty"><b>Trade kayıtları mevcut değil.</b><span>Mevcut engine sonucu trade-level kayıt persist etmiyor.</span></div>;
  return <div className="table-wrap"><table><thead><tr><th>Zaman</th><th>Yön</th><th>Fiyat</th><th>Return</th><th>PnL</th><th/></tr></thead><tbody>{trades.map((trade, i) => <tr key={`${trade.timestamp}-${i}`}><td>{trade.timestamp}</td><td>{trade.side}</td><td>{value(trade.price)}</td><td>{value(trade.return)}</td><td>{value(trade.pnl)}</td><td><button className="text-button" onClick={() => onSelect(trade)}>Detay</button></td></tr>)}</tbody></table></div>;
}
