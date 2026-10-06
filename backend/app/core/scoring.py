"""Scoring models with fully exposed intermediate steps.

Two deliberately different models are provided so the UI can show that
ranking is model-dependent, not a single objective truth:

* WSM  (weighted sum model):  score_i = sum_j w_j * n_ij
* TOPSIS: distance to ideal / (distance to ideal + distance to anti-ideal)

Both return every intermediate matrix and vector needed to audit the result.
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ScoreResult:
    method: str
    scores: list[float]
    ranks: list[int]                    # 1-based rank per alternative
    steps: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _effective_weights(
    norm: np.ndarray, weights: np.ndarray
) -> np.ndarray:
    """For rows with NaNs (exclude_weight policy), renormalise per row so
    no missing cell is silently worth either 0 or the best value."""
    if not np.isnan(norm).any():
        return np.broadcast_to(weights, norm.shape)
    eff = np.zeros_like(norm)
    for i in range(norm.shape[0]):
        known = ~np.isnan(norm[i])
        w = weights[known]
        eff[i, known] = w / w.sum() if w.sum() > 0 else w
    return eff


def wsm(
    norm: np.ndarray, weights: np.ndarray, alt_keys: list[str]
) -> ScoreResult:
    eff = _effective_weights(norm, weights)
    safe_norm = np.nan_to_num(norm, nan=0.0)
    contributions = eff * safe_norm                 # what every cell adds
    scores = contributions.sum(axis=1)
    steps = {
        "weighted_matrix": contributions.tolist(),
        "column_weights_effective": eff.tolist(),
        "score_formula": "总分 = Σ(权重 × 规范化值)，逐项贡献见 weighted_matrix",
    }
    warnings = []
    if np.isnan(norm).any():
        warnings.append("存在缺失值：已按每行实际可用指标对权重重新归一。")
    ranks = _ranks(scores)
    return ScoreResult("wsm", scores.tolist(), ranks, steps, warnings)


def topsis(
    norm: np.ndarray, weights: np.ndarray, alt_keys: list[str]
) -> ScoreResult:
    # Vector-normalisation on top of the 0..1 directional normalisation,
    # exactly as textbook TOPSIS specifies — shown as its own step.
    with np.errstate(invalid="ignore"):
        norms = np.sqrt(np.nansum(norm ** 2, axis=0))
    unit = np.divide(
        norm, norms, out=np.zeros_like(norm), where=norms > 0
    )
    warnings: list[str] = []
    if (norms == 0).any():
        j = int(np.where(norms == 0)[0][0])
        warnings.append(
            f"第 {j} 列向量范数为 0（常量列），TOPSIS 该列跳过且不产生除零；"
            "请配合其权重（数据推得时应为 0）一起核对。"
        )

    eff = _effective_weights(unit, weights)
    weighted = eff * np.nan_to_num(unit, nan=0.0)

    ideal_best = np.nanmax(weighted, axis=0)
    ideal_worst = np.nanmin(weighted, axis=0)
    # NaN cells must not pull the ideal: mask them.
    mask = np.isnan(unit)
    diff_best = np.where(mask, 0.0, weighted - ideal_best)
    diff_worst = np.where(mask, 0.0, weighted - ideal_worst)
    d_best = np.sqrt((diff_best ** 2).sum(axis=1))
    d_worst = np.sqrt((diff_worst ** 2).sum(axis=1))

    closeness = np.divide(
        d_worst,
        d_best + d_worst,
        out=np.full_like(d_best, 0.5),
        where=(d_best + d_worst) > 0,
    )
    if ((d_best + d_worst) == 0).any():
        warnings.append(
            "有方案与理想解、反理想解等距（含全常量退化情形），接近度记 0.5 而非除零。"
        )
    if np.isnan(norm).any():
        warnings.append("存在缺失值：该单元格不参与距离计算，行内权重已重归一。")

    ranks = _ranks(closeness)
    steps = {
        "vector_normalized": unit.tolist(),
        "weighted_matrix": weighted.tolist(),
        "ideal_best": ideal_best.tolist(),
        "ideal_worst": ideal_worst.tolist(),
        "distance_to_best": d_best.tolist(),
        "distance_to_worst": d_worst.tolist(),
        "closeness_formula": "C = D⁻ / (D⁺ + D⁻)，D⁺=到理想解距离，D⁻=到反理想解距离",
    }
    return ScoreResult("topsis", closeness.tolist(), ranks, steps, warnings)


def _ranks(scores: np.ndarray) -> list[int]:
    """Competition ranking (1,2,2,4...); higher score = rank 1."""
    order = np.argsort(-scores, kind="stable")
    ranks = [0] * len(scores)
    prev = None
    prev_rank = 0
    for pos, idx in enumerate(order, start=1):
        if prev is not None and np.isclose(scores[idx], prev):
            ranks[idx] = prev_rank
        else:
            ranks[idx] = pos
            prev_rank = pos
        prev = scores[idx]
    return ranks
