import { request } from '../../../../platform-api';
import type { Candidate, Experiment, FeatureIntelligence, Generation, Result } from '../../../../platform-api';
import type { DashboardAllocation, DashboardData, DashboardExposure, ModelCandidate, SignalConfidence, Trade } from '../types/experiment-results.types';

const optional = async <T>(path: string): Promise<T | null> => {
  try { return await request<T>(path); } catch { return null; }
};

export async function getExperiment(id: string) {
  return request<Experiment>(`/experiments/${id}`);
}

export async function getResult(id: string) {
  return request<Result>(`/experiments/${id}/result`);
}

export async function getOptimization(id: string) {
  const value = await optional<{ generations?: Generation[]; best?: Candidate; pareto?: Candidate[] }>(`/experiments/${id}/optimization`);
  return value ? { generations: value.generations || [], best: value.best, pareto: value.pareto || [] } : null;
}

export async function getFeatureIntelligence(id: string) {
  return optional<FeatureIntelligence>(`/experiments/${id}/feature-intelligence`);
}

export async function getCandidates(id: string) {
  return optional<ModelCandidate[]>(`/experiments/${id}/candidates`);
}

export async function getAllocation(id: string) {
  return optional<DashboardAllocation>(`/experiments/${id}/dashboard/allocation`);
}

export async function getExposure(id: string) {
  return optional<DashboardExposure>(`/experiments/${id}/dashboard/exposure`);
}

export async function getTradePage(id: string) {
  return optional<{ items: Trade[] }>(`/experiments/${id}/dashboard/trades?page=1&page_size=1000`);
}

export async function getSignalConfidence(id: string) {
  return optional<SignalConfidence>(`/experiments/${id}/dashboard/signal-confidence`);
}

/**
 * Trades are intentionally read from the persisted result only when the
 * engine has stored them. No synthetic trades are created in the UI.
 */
export function getTrades(result: Result | null): Trade[] {
  const raw = (result as (Result & { trades?: unknown[] }) | null)?.trades;
  return Array.isArray(raw) ? raw.filter((row): row is Trade => !!row && typeof row === 'object') : [];
}

export async function getDashboardData(id: string): Promise<DashboardData> {
  const experiment = await getExperiment(id);
  if (experiment.status !== 'COMPLETED') {
    return { experiment, result: null, optimization: await getOptimization(id), features: null, models: [], trades: [], allocation: null, exposure: null, confidence: null };
  }

  const [result, optimization, features, candidates, allocation, exposure, tradePage, confidence] = await Promise.all([
    getResult(id),
    getOptimization(id),
    getFeatureIntelligence(id),
    getCandidates(id),
    getAllocation(id),
    getExposure(id),
    getTradePage(id),
    getSignalConfidence(id),
  ]);
  const resultCandidates = result.optimization?.candidates || result.optimization?.pareto || [];
  return {
    experiment,
    result,
    optimization: optimization || {
      generations: result.optimization?.generations || [],
      best: result.optimization?.best,
      pareto: result.optimization?.pareto || [],
    },
    features,
    models: (candidates && candidates.length ? candidates : resultCandidates) as ModelCandidate[],
    trades: tradePage?.items || getTrades(result),
    allocation,
    exposure,
    confidence,
  };
}
