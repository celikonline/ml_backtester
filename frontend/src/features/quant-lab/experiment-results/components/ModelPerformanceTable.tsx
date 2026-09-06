import type { Result } from '../../../../platform-api';
import type { ModelCandidate } from '../types/experiment-results.types';

const n = (v: unknown, digits = 2) => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—';
const pct = (v: unknown) => typeof v === 'number' && Number.isFinite(v) ? `${(v * 100).toFixed(2)}%` : '—';

export default function ModelPerformanceTable({ result, models }: { result: Result | null; models: ModelCandidate[] }) {
  if (!result) return <div className="experiment-result-empty">Model sonucu henüz hazır değil.</div>;
  const modelName = (candidate: ModelCandidate) => candidate.model || String(candidate.genome?.model || candidate.genome?.model_id || candidate.candidate_key || 'candidate');
  const rows = [{ model: result.selected_model, metrics: result.metrics, selected: true }, ...models.filter(c => modelName(c) !== result.selected_model).slice(0, 8).map(c => ({ model: modelName(c), metrics: c.metrics, selected: false }))];
  return <div className="table-wrap"><table><thead><tr><th>Model</th><th>Seçim</th><th>Return</th><th>Sharpe</th><th>Max DD</th><th>Win rate</th><th>Turnover</th></tr></thead><tbody>{rows.map((r, i) => <tr key={`${r.model}-${i}`}><td><b>{r.model}</b></td><td>{r.selected ? <span className="cap-status var">selected</span> : '—'}</td><td>{pct(r.metrics.return)}</td><td>{n(r.metrics.sharpe)}</td><td>{pct(r.metrics.max_drawdown)}</td><td>{pct(r.metrics.win_rate)}</td><td>{n(r.metrics.turnover)}</td></tr>)}</tbody></table></div>;
}
