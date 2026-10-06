"""End-to-end analysis orchestration and the three "show, don't tell" audits.

1. Duplicate criteria — two columns with perfect rank correlation add no
   information but double their weight.  Reported, never auto-merged.
2. Extreme outliers — median + MAD (robust z) and IQR fences; the UI shows
   which alternative's raw value dominates a min/max-normalised column.
3. Rank reversal — re-run the whole pipeline after dropping each
   alternative (and for a flagged "add candidate" scenario) to expose that
   min/max normalisation + TOPSIS can re-order the survivors.  With fixed
   anchors and WSM it cannot; both versions are returned.
"""
from dataclasses import asdict
from itertools import combinations

import numpy as np
from scipy import stats

from .normalization import normalize
from .scoring import topsis, wsm
from .weights import DerivedWeights, critic_weights, entropy_weights


def _to_native(obj):
    """Recursively turn numpy scalars/arrays into JSON-native types."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _to_native(obj.tolist())
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def find_duplicate_criteria(
    raw: np.ndarray, criteria: list[dict]
) -> list[dict]:
    """Pairs whose raw values move in perfect lockstep (Spearman |rho|=1)."""
    findings = []
    m = raw.shape[1]
    for a, b in combinations(range(m), 2):
        x, y = raw[:, a], raw[:, b]
        # A constant column has no ranking to correlate with anything;
        # its (non-)information is handled by normalization/weights instead.
        x_obs, y_obs = x[~np.isnan(x)], y[~np.isnan(y)]
        if (x_obs.size < 3 or y_obs.size < 3
                or np.isclose(x_obs, x_obs[0]).all()
                or np.isclose(y_obs, y_obs[0]).all()):
            continue
        mask = ~(np.isnan(x) | np.isnan(y))
        # With only 3 pairs a perfect rank match is still flagged, but the
        # UI message notes the small-sample caveat rather than asserting
        # duplication with certainty.
        if mask.sum() < 3:
            continue
        rho, _ = stats.spearmanr(x[mask], y[mask])
        if np.isfinite(rho) and abs(rho) >= 0.999:
            caveat = (
                "（仅 3-4 个候选时，排名巧合一致的概率不低，请结合业务含义判断）"
                if mask.sum() < 5 else ""
            )
            findings.append(
                {
                    "a": criteria[a]["key"],
                    "a_label": criteria[a].get("label", criteria[a]["key"]),
                    "b": criteria[b]["key"],
                    "b_label": criteria[b].get("label", criteria[b]["key"]),
                    "spearman": round(float(rho), 4),
                    "same_direction": rho > 0,
                    "issue": (
                        "两个指标排名完全一致：同时计入等于把这一维的权重翻倍。"
                        "请删除其一或合并，而不是让总分悄悄偏向该维度。" + caveat
                    ),
                }
            )
    return findings


def find_outliers(
    raw: np.ndarray, criteria: list[dict], alt_keys: list[str]
) -> list[dict]:
    findings = []
    for j, crit in enumerate(criteria):
        col = raw[:, j]
        col = col[~np.isnan(col)]
        if col.size < 3 or np.isclose(col, col[0]).all():
            continue
        med = float(np.median(col))
        mad = float(stats.median_abs_deviation(col, scale="normal"))
        q1, q3 = np.percentile(col, [25, 75])
        iqr = q3 - q1
        for i, key in enumerate(alt_keys):
            v = raw[i, j]
            if np.isnan(v):
                continue
            robust_z = abs(v - med) / mad if mad > 0 else 0.0
            beyond_iqr = iqr > 0 and (v < q1 - 3 * iqr or v > q3 + 3 * iqr)
            if robust_z >= 3.5 or beyond_iqr:
                findings.append(
                    {
                        "alternative": key,
                        "criterion": crit["key"],
                        "criterion_label": crit.get("label", crit["key"]),
                        "value": float(v),
                        "median": med,
                        "robust_z": round(float(robust_z), 2),
                        "unit": crit.get("unit", ""),
                        "issue": (
                            "极端异常值：在 min/max 规范化下它会单独占掉一个 0/1 端点，"
                            "把其余方案压缩到很窄的分数区间。请核对数据或改用固定锚点。"
                        ),
                    }
                )
    return findings


def derive_weights(
    method: str, norm: np.ndarray
) -> DerivedWeights:
    if method == "entropy":
        return entropy_weights(norm)
    if method == "critic":
        return critic_weights(norm)
    raise ValueError(f"未知权重推求方法: {method}")


def _rankings_for(
    raw: np.ndarray,
    criteria: list[dict],
    alt_keys: list[str],
    weights: np.ndarray,
    missing_policy: str,
) -> dict:
    n = normalize(raw, criteria, alt_keys, missing_policy)
    w = wsm(n.matrix, weights, alt_keys)
    t = topsis(n.matrix, weights, alt_keys)
    return {
        "normalization": {
            "matrix": n.matrix.tolist(),
            "meta": n.meta,
            "missing_cells": n.missing_cells,
            "warnings": n.warnings,
        },
        "wsm": {"scores": w.scores, "ranks": w.ranks, "steps": w.steps,
                "warnings": w.warnings},
        "topsis": {"scores": t.scores, "ranks": t.ranks, "steps": t.steps,
                   "warnings": t.warnings},
    }


def rank_reversal_audit(
    raw: np.ndarray,
    criteria: list[dict],
    alt_keys: list[str],
    weights: np.ndarray,
    missing_policy: str = "neutral",
) -> dict:
    """Drop each alternative in turn and compare the survivors' order.

    Runs the pipeline twice:
      * dynamic anchors (default min/max) — reversal is possible
      * fixed anchors (observed global extremes injected) — WSM is immune
    """
    def run(with_anchors: bool) -> dict:
        crit = [dict(c) for c in criteria]
        if with_anchors:
            for j, c in enumerate(crit):
                col = raw[:, j]
                col = col[~np.isnan(col)]
                c["fixed_min"] = float(col.min()) if col.size else 0.0
                c["fixed_max"] = float(col.max()) if col.size else 1.0
        base = _rankings_for(raw, crit, alt_keys, weights, missing_policy)
        base_order = {
            m: [k for _, k in sorted(zip(base[m]["ranks"], alt_keys))]
            for m in ("wsm", "topsis")
        }
        drops = []
        for drop_idx, drop_key in enumerate(alt_keys):
            keep = [i for i in range(len(alt_keys)) if i != drop_idx]
            sub_raw = raw[keep, :]
            sub_keys = [alt_keys[i] for i in keep]
            sub = _rankings_for(sub_raw, crit, sub_keys, weights, missing_policy)
            for model in ("wsm", "topsis"):
                sub_order = [
                    k for _, k in sorted(zip(sub[model]["ranks"], sub_keys))
                ]
                base_survivors = [k for k in base_order[model] if k != drop_key]
                if sub_order != base_survivors:
                    # Identify the first adjacent swap for the explanation
                    swaps = []
                    rank_base = {k: i for i, k in enumerate(base_survivors)}
                    for a, b in zip(sub_order, sub_order[1:]):
                        if rank_base[a] > rank_base[b]:
                            swaps.append({"a": a, "b": b})
                    drops.append(
                        {
                            "removed": drop_key,
                            "model": model,
                            "order_before": base_survivors,
                            "order_after": sub_order,
                            "first_swaps": swaps[:3],
                            "anchored": with_anchors,
                        }
                    )
        return {
            "anchored": with_anchors,
            "reversals": drops,
            "base_order": base_order,
        }

    dynamic = run(False)
    anchored = run(True)
    return {
        "dynamic_anchors": dynamic,
        "fixed_anchors": anchored,
        "explanation": (
            "删除候选后，min/max 规范化会用剩余候选重新确定端点、"
            "TOPSIS 会重新确定理想解，幸存者之间的相对顺序可能改变（排名逆转）。"
            "固定锚点下 WSM 不会逆转；若仍逆转，说明权重或缺失值处理在起作用。"
        ),
    }


def run_full_analysis(
    raw: np.ndarray,
    criteria: list[dict],
    alt_keys: list[str],
    weight_vector: np.ndarray,
    missing_policy: str = "neutral",
) -> dict:
    duplicates = find_duplicate_criteria(raw, criteria)
    outliers = find_outliers(raw, criteria, alt_keys)
    base_norm = normalize(raw, criteria, alt_keys, missing_policy)
    ent = derive_weights("entropy", np.nan_to_num(base_norm.matrix, nan=0.5))
    cri = derive_weights("critic", np.nan_to_num(base_norm.matrix, nan=0.5))
    models = _rankings_for(raw, criteria, alt_keys, weight_vector, missing_policy)
    reversal = rank_reversal_audit(
        raw, criteria, alt_keys, weight_vector, missing_policy
    )
    return _to_native({
        "audits": {"duplicates": duplicates, "outliers": outliers},
        "derived_weights": {
            "entropy": {
                "weights": ent.weights.tolist(),
                "diagnostics": ent.contributions,
                "notes": ent.notes,
            },
            "critic": {
                "weights": cri.weights.tolist(),
                "diagnostics": cri.contributions,
                "notes": cri.notes,
            },
            "disclaimer": (
                "数据推得的权重只反映「数据在哪里有区分度」，"
                "不反映委员会的价值判断；与人工权重分开保存、分开选择。"
            ),
        },
        "models": models,
        "rank_reversal": reversal,
    })
