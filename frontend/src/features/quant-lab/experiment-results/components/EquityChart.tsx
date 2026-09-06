import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { EquityPoint } from '../types/experiment-results.types';

export default function EquityChart({ points }: { points: EquityPoint[] }) {
  if (!points.length) return <div className="experiment-result-empty">Equity verisi mevcut değil.</div>;
  const phase = (name: EquityPoint['phase']) => points.filter(p => p.phase === name);
  const area = (name: EquityPoint['phase']) => { const p = phase(name); return p.length ? <ReferenceArea key={name} x1={p[0].timestamp} x2={p[p.length - 1].timestamp} fill={name === 'test' ? '#55dfb0' : '#8b91f3'} fillOpacity={0.045} label={{ value: name?.toUpperCase(), fill: '#71839a', fontSize: 10, position: 'insideTopLeft' }} /> : null; };
  return <div className="experiment-result-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={points} margin={{ left: 4, right: 18, top: 22, bottom: 4 }}><CartesianGrid stroke="#27313f" strokeDasharray="3 5"/><XAxis dataKey="timestamp" minTickGap={80} tickFormatter={v => String(v).slice(0, 10)} tick={{ fill: '#8797aa', fontSize: 10 }}/><YAxis tick={{ fill: '#8797aa', fontSize: 10 }}/><Tooltip contentStyle={{ background: '#172130', border: '1px solid #39475a' }}/>{area('development')}{area('validation')}{area('test')}<Area type="monotone" dataKey="equity" name="Strategy" stroke="#55dfb0" fill="#55dfb0" fillOpacity={0.08} dot={false} isAnimationActive={false}/><Line type="monotone" dataKey="benchmark" name="Benchmark" stroke="#8b91f3" dot={false} strokeWidth={1.5} isAnimationActive={false}/></ComposedChart></ResponsiveContainer></div>;
}
