import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { SignalConfidence } from '../types/experiment-results.types';

export default function SignalConfidencePanel({ data }: { data: SignalConfidence | null }) {
  if (!data?.items.length) return <div className="experiment-result-empty">Signal confidence verisi mevcut değil.</div>;
  return <><div className="chart-note">Kaynak: {data.source} · {data.calibrated ? 'kalibre edilmiş' : 'kalibrasyonsuz türetilmiş'} değer</div><div className="experiment-result-chart compact"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.items} margin={{ left: 4, right: 18, top: 12, bottom: 4 }}><CartesianGrid stroke="#27313f" strokeDasharray="3 5"/><XAxis dataKey="timestamp" minTickGap={80} tickFormatter={v => String(v).slice(0, 10)} tick={{ fill: '#8797aa', fontSize: 10 }}/><YAxis domain={[0, 1]} tickFormatter={v => `${Number(v) * 100}%`} tick={{ fill: '#8797aa', fontSize: 10 }}/><Tooltip formatter={v => `${(Number(v || 0) * 100).toFixed(1)}%`} contentStyle={{ background: '#172130', border: '1px solid #39475a' }}/><Area type="monotone" dataKey="confidence" name="Confidence" stroke="#62b5ef" fill="#62b5ef" fillOpacity={0.17} dot={false} isAnimationActive={false}/></AreaChart></ResponsiveContainer></div></>;
}
