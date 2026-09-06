import type { Candidate, Experiment, FeatureIntelligence, Generation, Result } from '../../../../platform-api';
export type ModelCandidate = Candidate & { candidate_key?: string; genome?: Record<string, unknown> };

export type DashboardData = {
  experiment: Experiment;
  result: Result | null;
  optimization: { generations: Generation[]; best?: Candidate | null; pareto: Candidate[] } | null;
  features: FeatureIntelligence | null;
  models: ModelCandidate[];
  trades: Trade[];
  allocation: DashboardAllocation | null;
  exposure: DashboardExposure | null;
  confidence: SignalConfidence | null;
};

export type Trade = {
  timestamp: string;
  side: 'long' | 'short' | 'flat' | string;
  price?: number;
  return?: number;
  pnl?: number;
  signal?: number;
  [key: string]: unknown;
};

export type EquityPoint = {
  timestamp: string;
  equity: number;
  benchmark: number;
  drawdown: number;
  signal: number;
  phase?: 'development' | 'validation' | 'test';
};

export type AllocationRow = { name: string; value: number; available: boolean };
export type ExposureRow = { name: string; value: number; available: boolean };
export type DashboardAllocation = { source: string; asset: string; derived: boolean; items: { name: string; value: number }[] };
export type DashboardExposure = { source: string; asset: string; derived: boolean; net: number; gross: number; long_share: number; short_share: number; flat_share: number };
export type SignalConfidence = { source: string; calibrated: boolean; items: { timestamp: string; confidence: number; prediction_bps?: number; signal?: number }[] };
