import { useCallback, useEffect, useState } from 'react';
import { getDashboardData } from '../api/experiment-results.api';
import type { DashboardData } from '../types/experiment-results.types';

export function useExperimentResults(id: string) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const reload = useCallback(async () => {
    setLoading(true); setError('');
    try { setData(await getDashboardData(id)); }
    catch (e) { setError((e as Error).message || 'Deney sonuçları yüklenemedi.'); }
    finally { setLoading(false); }
  }, [id]);

  useEffect(() => { void reload(); }, [reload]);
  return { data, loading, error, reload };
}
