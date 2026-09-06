import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { Generation } from '../../../../platform-api';

export default function GeneticFitnessChart({ generations }: { generations: Generation[] }) {
  if (!generations.length) return <div className="experiment-result-empty">Genetik optimizasyon geçmişi mevcut değil.</div>;
  return <div className="experiment-result-chart compact"><ResponsiveContainer width="100%" height="100%"><LineChart data={generations} margin={{ left: 4, right: 18, top: 12, bottom: 4 }}><CartesianGrid stroke="#27313f" strokeDasharray="3 5"/><XAxis dataKey="generation" tick={{ fill: '#8797aa', fontSize: 10 }}/><YAxis tick={{ fill: '#8797aa', fontSize: 10 }}/><Tooltip contentStyle={{ background: '#172130', border: '1px solid #39475a' }}/><Line dataKey="best_fitness" name="Best fitness" stroke="#55dfb0" dot={false} strokeWidth={2} isAnimationActive={false}/><Line dataKey="mean_fitness" name="Mean fitness" stroke="#8b91f3" dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer></div>;
}
