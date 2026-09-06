import { Area, CartesianGrid, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { EquityPoint } from '../types/experiment-results.types';

export default function DrawdownChart({ points }: { points: EquityPoint[] }) {
  if (!points.length) return <div className="experiment-result-empty">Drawdown verisi mevcut değil.</div>;
  return <div className="experiment-result-chart compact"><ResponsiveContainer width="100%" height="100%"><AreaChart data={points} margin={{ left: 4, right: 18, top: 12, bottom: 4 }}><CartesianGrid stroke="#27313f" strokeDasharray="3 5"/><XAxis dataKey="timestamp" minTickGap={80} tickFormatter={v => String(v).slice(0, 10)} tick={{ fill: '#8797aa', fontSize: 10 }}/><YAxis tickFormatter={v => `${(Number(v) * 100).toFixed(1)}%`} tick={{ fill: '#8797aa', fontSize: 10 }}/><Tooltip formatter={(v) => `${(Number(v || 0) * 100).toFixed(2)}%`} contentStyle={{ background: '#172130', border: '1px solid #39475a' }}/><Area type="monotone" dataKey="drawdown" name="Drawdown" stroke="#ef8f93" fill="#ef8f93" fillOpacity={0.2} dot={false} isAnimationActive={false}/></AreaChart></ResponsiveContainer></div>;
}
