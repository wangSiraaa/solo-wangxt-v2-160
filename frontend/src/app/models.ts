export interface Criterion {
  id: number;
  code: string;
  name: string;
  unit: string;
  ctype: 'benefit' | 'cost' | 'target';
  weight: number;
  source: string;
  target_low?: number | null;
  target_high?: number | null;
}

export interface Candidate {
  id: number;
  code: string;
  name: string;
  description?: string;
}

export interface AnalyzeOptions {
  missing_strategy: 'median' | 'mean' | 'worst';
  clip_outliers: boolean;
  clip_method: 'percentile' | 'mad';
  clip_mad_k: number;
  weight_basis: 'manual' | 'entropy' | 'combined';
  combined_alpha: number;
  keep_constants: boolean;
  drop_criterion_ids: number[];
  drop_candidate_ids: number[];
}

export interface Version extends AnalyzeOptions {
  id: number;
  label: string;
  note: string;
  created_at: string;
}

export interface StepTrace {
  name: string;
  description: string;
  matrix: (number | null)[][];
  rows: string[];
  columns: string[];
  notes: string[];
}

export interface WeightAudit {
  criterion_code: string;
  manual_weight: number;
  manual_source: string;
  entropy_weight: number | null;
  effective_weight: number;
  effective_share: number;
  basis: string;
  excluded: boolean;
  exclude_reason: string | null;
}

export interface RankRow {
  rank: number;
  candidate_code: string;
  candidate_name: string;
  wsm_score: number | null;
  topsis_score: number | null;
  closeness_ideal: number | null;
  distance_ideal: number | null;
  distance_anti_ideal: number | null;
}

export interface DuplicateInfo {
  criterion_a: string;
  criterion_b: string;
  pearson: number;
  spearman: number;
  effect: string;
}

export interface OutlierCell {
  candidate: string;
  criterion: string;
  value: number;
  modified_z: number;
}

export interface Report {
  version: Partial<Version>;
  candidates: Candidate[];
  criteria: Criterion[];
  raw_matrix: (number | null)[][];
  steps: StepTrace[];
  weight_audit: WeightAudit[];
  weight_sum_raw: number;
  weight_sum_effective: number;
  wsm_rank: RankRow[];
  topsis_rank: RankRow[];
  duplicate_criteria: DuplicateInfo[];
  outlier_cells: OutlierCell[];
  warnings: string[];
}

export interface ReversalRow {
  candidate_code: string;
  candidate_name: string;
  rank_full: number;
  rank_reduced: number;
  shift: number;
  driver_criterion: string | null;
  explanation: string;
}

export interface ReversalReport {
  dropped_label: string;
  full_ranking: { candidate_code: string; rank: number; score: number }[];
  reduced_ranking: { candidate_code: string; rank: number; score: number }[];
  rows: ReversalRow[];
  drivers: { criterion: string; mean_abs_contribution_change: number }[];
  explanations: string[];
  note: string;
}
