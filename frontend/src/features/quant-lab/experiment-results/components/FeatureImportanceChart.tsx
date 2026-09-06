import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Result } from '../../../../platform-api';
import type { FeatureIntelligence } from '../../../../platform-api';

export default function FeatureImportanceChart({ result, features }: { result: Result | null; features: FeatureIntelligence | null }) {
  const source = features?.evaluations?.length ? features.evaluations.map(f => ({ name: f.feature, importance: Math.abs(f.ic), method: 'abs(IC)' })) : result?.feature_analysis?.features?.map(f => ({ name: f.feature, importance: Math.abs(f.ic), method: 'abs(IC)' })) || [];
  const data = source.sort((a, b) => b.importance - a.importance).slice(0, 12);
  if (!data.length) return <div className="experiment-result-empty">Feature importance verisi mevcut değil.</div>;
  return <><div className="chart-note">Model-native importance kaydedilmediği için gösterim, persisted feature IC değerinin mutlak değeridir.</div><div className="experiment-result-chart feature-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} layout="vertical" margin={{ left: 20, right: 18, top: 8, bottom: 4 }}><CartesianGrid stroke="#27313f" strokeDasharray="3 5"/><XAxis type="number" tick={{ fill: '#8797aa', fontSize: 10 }}/><YAxis type="category" dataKey="name" width={125} tick={{ fill: '#8797aa', fontSize: 10 }}/><Tooltip contentStyle={{ background: '#172130', border: '1px solid #39475a' }}/><Bar dataKey="importance" name="abs(IC)" fill="#55dfb0" radius={[0, 4, 4, 0]}/></BarChart></ResponsiveContainer></div></>;
}
