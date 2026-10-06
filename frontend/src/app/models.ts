/** Shape of the backend payloads (only the fields the UI uses). */

export type CriterionKind = 'benefit' | 'cost' | 'target';
export type MissingPolicy = 'neutral' | 'row_mean' | 'exclude_weight';
export type WeightOrigin = 'manual' | 'entropy' | 'critic' | 'manual_adhoc';

export interface Criterion {
  key: string;
  label: string;
  unit: string;
  kind: CriterionKind;
  target_low?: number | null;
  target_high?: number | null;
  fixed_min?: number | null;
  fixed_max?: number | null;
}

export interface Alternative {
  key: string;
  label: string;
}

export interface WeightSet {
  id: number;
  name: string;
  method: 'manual' | 'entropy' | 'critic';
  source: string;
  weights: Record<string, number>;
}

export interface VersionMeta {
  id: number;
  label: string;
  method: 'wsm' | 'topsis';
  created_at: string;
  created_by: string;
}

export interface DecisionDetail {
  id: number;
  name: string;
  settings: Record<string, unknown>;
  criteria: Criterion[];
  alternatives: Alternative[];
  raw_values: (number | null)[][];
  value_notes: string[][];
  weight_sets: WeightSet[];
  versions: VersionMeta[];
}

export interface Scenario {
  id: number;
  key: string;
  name: string;
  description: string;
  decisions: { id: number; name: string }[];
}

export interface NormalizationMeta {
  key: string;
  label: string;
  kind: CriterionKind;
  unit: string;
  observed_min: number | null;
  observed_max: number | null;
  anchor_min: number;
  anchor_max: number;
  spread: number;
  constant: boolean;
  formula: string;
  missing_count: number;
  anchored: boolean;
  target_low?: number;
  target_high?: number;
}

export interface MissingCell {
  alternative: string;
  criterion: string;
  policy: string;
  imputed: number | null;
}

export interface ModelResult {
  scores: number[];
  ranks: number[];
  steps: Record<string, unknown>;
  warnings: string[];
}

export interface DuplicateFinding {
  a: string; a_label: string;
  b: string; b_label: string;
  spearman: number;
  same_direction: boolean;
  issue: string;
}

export interface OutlierFinding {
  alternative: string;
  criterion: string;
  criterion_label: string;
  value: number;
  median: number;
  robust_z: number;
  unit: string;
  issue: string;
}

export interface ReversalEvent {
  removed: string;
  model: 'wsm' | 'topsis';
  order_before: string[];
  order_after: string[];
  first_swaps: { a: string; b: string }[];
  anchored: boolean;
}

export interface Analysis {
  decision_id: number;
  criteria: Criterion[];
  alternatives: Alternative[];
  raw_values: (number | null)[][];
  value_notes: string[][];
  weight_vector: number[];
  weight_provenance: {
    origin: WeightOrigin;
    method: string;
    source?: string;
    notes?: string[];
    name?: string;
  };
  weight_sum: number;
  missing_policy: MissingPolicy;
  audits: {
    duplicates: DuplicateFinding[];
    outliers: OutlierFinding[];
  };
  derived_weights: {
    entropy: {
      weights: number[];
      diagnostics: Record<string, number[]>;
      notes: string[];
    };
    critic: {
      weights: number[];
      diagnostics: Record<string, number[]>;
      notes: string[];
    };
    disclaimer: string;
  };
  models: {
    normalization: {
      matrix: (number | null)[][];
      meta: NormalizationMeta[];
      missing_cells: MissingCell[];
      warnings: string[];
    };
    wsm: ModelResult;
    topsis: ModelResult;
  };
  rank_reversal: {
    dynamic_anchors: {
      anchored: boolean;
      reversals: ReversalEvent[];
      base_order: Record<string, string[]>;
    };
    fixed_anchors: {
      anchored: boolean;
      reversals: ReversalEvent[];
      base_order: Record<string, string[]>;
    };
    explanation: string;
  };
}

export interface VersionSnapshot {
  id: number;
  decision_id: number;
  label: string;
  method: 'wsm' | 'topsis';
  created_at: string;
  created_by: string;
  snapshot: {
    comment: string;
    criteria: Criterion[];
    alternatives: Alternative[];
    raw_values: (number | null)[][];
    weight_vector: number[];
    weight_provenance: Analysis['weight_provenance'];
    missing_policy: string;
    ranking: number[];
    scores: number[];
    normalization: Analysis['models']['normalization'];
    model_steps: Record<string, unknown>;
    audits: Analysis['audits'];
    rank_reversal_summary: { dynamic_reversal_count: number };
  };
}
