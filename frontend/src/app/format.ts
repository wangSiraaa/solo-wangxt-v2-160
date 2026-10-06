import { Criterion } from './models';

export function fmt(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  return Number(v.toFixed(digits)).toString();
}

export function pct(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(1)}%`;
}

export const KIND_LABEL: Record<Criterion['kind'], string> = {
  benefit: '收益型 ↑ 越大越好',
  cost: '成本型 ↓ 越小越好',
  target: '目标区间型 ◎ 落在区间内最好',
};

export const KIND_SHORT: Record<Criterion['kind'], string> = {
  benefit: '收益',
  cost: '成本',
  target: '区间',
};

/** Ordinal medal-ish badge for rank 1..n. */
export function rankBadge(rank: number): string {
  return ['①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧'][rank - 1] ?? `${rank}`;
}
