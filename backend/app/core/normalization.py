"""Normalisation with explicit criterion directions.

Three directions are supported:

* ``benefit`` — larger raw value is better:        (x - min) / (max - min)
* ``cost``    — smaller raw value is better:       (max - x) / (max - min)
* ``target``  — values inside [low, high] score 1, outside decay linearly
                with distance to the interval.

Safety rules enforced here (so they can never be hidden inside a score):

* Constant columns (max == min) do NOT score 1 for everyone and do NOT
  divide by zero.  They receive the neutral score 0.5 plus a warning.
* Missing cells are never silently treated as best (or worst).  They are
  flagged and replaced by an explicit policy default (neutral 0.5, or the
  row-wise mean of the other normalised scores), and the imputation is
  listed cell-by-cell in the step log.
* Fixed anchors (``fixed_min`` / ``fixed_max``) normalise against external
  reference bounds instead of the observed extremes, so adding or removing
  an alternative cannot rescale everyone else — this is the cure for the
  rank-reversal examples shown in the UI.
"""
from dataclasses import dataclass, field

import numpy as np

NEUTRAL = 0.5


@dataclass
class NormalizationResult:
    matrix: np.ndarray                 # shape (n_alt, n_crit), values 0..1
    meta: list[dict]                   # one dict per criterion
    missing_cells: list[dict]          # every imputed cell, with policy used
    warnings: list[str] = field(default_factory=list)


def _resolve_bounds(raw: np.ndarray, kind: str, crit: dict) -> tuple[float, float]:
    """Observed or fixed-anchor bounds used for the denominator."""
    lo = crit.get("fixed_min")
    hi = crit.get("fixed_max")
    if lo is None or hi is None:
        observed = raw[~np.isnan(raw)]
        o_lo = float(np.min(observed)) if observed.size else 0.0
        o_hi = float(np.max(observed)) if observed.size else 0.0
        lo = o_lo if lo is None else lo
        hi = o_hi if hi is None else hi
    return float(lo), float(hi)


def normalize(
    raw: np.ndarray,
    criteria: list[dict],
    alt_keys: list[str],
    missing_policy: str = "neutral",
) -> NormalizationResult:
    """Normalise one raw decision matrix.

    ``criteria`` items need: key, label, kind ("benefit"/"cost"/"target"),
    optional target_low/target_high, optional fixed_min/fixed_max.
    ``missing_policy`` is "neutral" (0.5) or "row_mean".
    """
    raw = np.asarray(raw, dtype=float)
    n_alt, n_crit = raw.shape
    norm = np.full((n_alt, n_crit), np.nan)
    meta: list[dict] = []
    warnings: list[str] = []
    missing_cells: list[dict] = []

    for j, crit in enumerate(criteria):
        kind = crit["kind"]
        col = raw[:, j].copy()
        observed_mask = ~np.isnan(col)
        n_missing = int((~observed_mask).sum())
        lo, hi = _resolve_bounds(col, kind, crit)
        spread = hi - lo

        entry: dict = {
            "key": crit["key"],
            "label": crit.get("label", crit["key"]),
            "kind": kind,
            "unit": crit.get("unit", ""),
            "observed_min": None,
            "observed_max": None,
            "anchor_min": lo,
            "anchor_max": hi,
            "spread": spread,
            "constant": False,
            "formula": "",
            "missing_count": n_missing,
        }
        if observed_mask.any():
            entry["observed_min"] = float(np.min(col[observed_mask]))
            entry["observed_max"] = float(np.max(col[observed_mask]))

        if kind == "target":
            tlo = crit.get("target_low")
            thi = crit.get("target_high")
            entry["target_low"] = tlo
            entry["target_high"] = thi
            if tlo is None or thi is None or tlo > thi:
                raise ValueError(
                    f"目标区间型指标 {crit['key']} 缺少合法的 target_low/target_high"
                )
            # distance outside the interval; inside => 0 distance => score 1
            dist = np.where(
                col < tlo, tlo - col,
                np.where(col > thi, col - thi, 0.0),
            )
            max_dist = max(tlo - lo, hi - thi, 0.0)
            if max_dist <= 0.0:
                # Every observed value lies inside the target interval:
                # full marks for observed data are mathematically correct,
                # but the criterion has no discriminating power — say so.
                entry["constant"] = True
                entry["formula"] = (
                    "所有观测值均在目标区间内 → 区间内=1；该列无区分度，缺失值仍记中性 0.5"
                )
                warnings.append(
                    f"指标「{entry['label']}」的所有观测值都在目标区间内，"
                    "无法区分方案（但这并非除零或自动满分问题：区间内满分是定义使然）。"
                )
                norm[observed_mask, j] = 1.0
            else:
                score = 1.0 - dist / max_dist
                score = np.clip(score, 0.0, 1.0)
                norm[:, j] = score
                entry["formula"] = (
                    f"1 - 到区间[{tlo}, {thi}]的距离 / 最大可能距离({max_dist:g})，"
                    f"锚点[{lo:g}, {hi:g}]"
                )
        else:
            if spread <= 0.0:
                # Constant column (or identical fixed bounds). Neutral 0.5
                # for observed rows — nobody wins a 1.0 by accident.
                entry["constant"] = True
                entry["formula"] = "常量列 (max=min)：不做除法，观测值记中性分 0.5"
                warnings.append(
                    f"指标「{entry['label']}」是常量列（所有方案取值相同），"
                    "除以极差会除零；已按规则给中性分 0.5，且数据推得权重中其权重为 0。"
                )
                norm[observed_mask, j] = NEUTRAL
            else:
                if kind == "benefit":
                    norm[:, j] = (col - lo) / spread
                    entry["formula"] = (
                        f"(x - {lo:g}) / ({hi:g} - {lo:g})，越大越好"
                    )
                else:  # cost
                    norm[:, j] = (hi - col) / spread
                    entry["formula"] = (
                        f"({hi:g} - x) / ({hi:g} - {lo:g})，越小越好"
                    )
                norm[:, j] = np.clip(norm[:, j], 0.0, 1.0)

        if crit.get("fixed_min") is not None or crit.get("fixed_max") is not None:
            entry["anchored"] = True
            entry["formula"] += "（使用固定锚点，增删候选不会重标定其他人）"
        else:
            entry["anchored"] = False

        for i in np.where(~observed_mask)[0]:
            missing_cells.append(
                {
                    "alternative": alt_keys[i],
                    "criterion": crit["key"],
                    "policy": missing_policy,
                }
            )
        meta.append(entry)

    # Impute missing normalised scores — never 1.0 by default.
    if missing_cells:
        warnings.append(
            f"存在 {len(missing_cells)} 个缺失单元格，按策略「{missing_policy}」"
            "处理；缺失绝不自动按满分计算。"
        )
        for cell in missing_cells:
            i = alt_keys.index(cell["alternative"])
            crit_keys = [c["key"] for c in criteria]
            j = crit_keys.index(cell["criterion"])
            if missing_policy == "neutral":
                norm[i, j] = NEUTRAL
                cell["imputed"] = NEUTRAL
            elif missing_policy == "row_mean":
                row_vals = norm[i, :]
                known = row_vals[~np.isnan(row_vals)]
                fill = float(np.mean(known)) if known.size else NEUTRAL
                norm[i, j] = fill
                cell["imputed"] = fill
            elif missing_policy == "exclude_weight":
                # Handled downstream by renormalising weights per row.
                cell["imputed"] = None
            else:
                raise ValueError(f"未知缺失值策略: {missing_policy}")

    if missing_policy == "exclude_weight":
        # NaNs remain; scoring code renormalises weights per row.
        pass
    else:
        if np.isnan(norm).any():
            warnings.append("规范化矩阵仍有 NaN（应仅发生在 exclude_weight 策略下）。")

    return NormalizationResult(norm, meta, missing_cells, warnings)
