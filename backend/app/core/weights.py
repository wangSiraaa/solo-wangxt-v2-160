"""Weights: human-set vs data-derived, always kept separate.

* Manual weights come with a free-text ``source`` justification and are
  validated to sum to 1.  The API never edits them silently.
* Entropy weights measure how much *information* each criterion column
  carries: a constant column has entropy 1 -> weight 0 (it cannot
  discriminate alternatives).
* CRITIC weights combine contrast (standard deviation) with conflict
  (correlation structure), implemented with SciPy.

Data-derived weights are descriptive ("the data varies mostly here"), not
prescriptive ("this matters most").  The UI labels them as such.
"""
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class DerivedWeights:
    weights: np.ndarray
    contributions: dict     # per-criterion diagnostic numbers
    notes: list[str]


def _valid_distribution(norm: np.ndarray) -> np.ndarray:
    """Turn a 0..1 column into a probability column without 0/0 rows."""
    col_sum = norm.sum(axis=0)
    # Columns with zero mass get a uniform fallback; their weight ends up 0
    # via the constant-column guard below.
    safe = np.where(col_sum > 0, col_sum, 1.0)
    return norm / safe


def entropy_weights(norm: np.ndarray) -> DerivedWeights:
    """Objective entropy weights on the normalised 0..1 matrix."""
    n, m = norm.shape
    p = _valid_distribution(norm)
    k = 1.0 / np.log(n) if n > 1 else 1.0

    entropies = np.zeros(m)
    for j in range(m):
        if np.allclose(norm[:, j], norm[0, j]):
            entropies[j] = 1.0          # constant -> maximum entropy
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            terms = np.where(p[:, j] > 0, p[:, j] * np.log(p[:, j]), 0.0)
        entropies[j] = -k * terms.sum()

    divergence = 1.0 - entropies         # information content
    total = divergence.sum()
    if total <= 0:
        weights = np.full(m, 1.0 / m)
        notes = ["所有指标均为常量列，熵权退化为等权（仅作占位，不代表偏好）。"]
    else:
        weights = divergence / total
        notes = []
    const_idx = np.where(np.isclose(entropies, 1.0))[0]
    if len(const_idx):
        notes.append(
            f"第 {list(map(int, const_idx))} 列为常量列，熵为 1、信息量为 0，"
            "数据推得权重为 0；请人工判断该指标是否仍应保留。"
        )
    return DerivedWeights(
        weights,
        {
            "entropy": entropies.tolist(),
            "divergence_1_minus_e": divergence.tolist(),
        },
        notes,
    )


def critic_weights(norm: np.ndarray) -> DerivedWeights:
    """CRITIC weights: contrast (std) x conflict (1 - correlation)."""
    n, m = norm.shape
    if n < 3:
        return DerivedWeights(
            np.full(m, 1.0 / m),
            {},
            ["候选少于 3 个时相关系数不稳定，CRITIC 退化为等权。"],
        )
    sd = np.std(norm, axis=0, ddof=1)
    # Spearman correlation (rank-based) via SciPy — robust to the nonlinear
    # normalisation. spearmanr treats rows as observations and columns as
    # variables, so the (n_alt x n_crit) matrix can be passed directly.
    constant_cols = np.isclose(sd, 0.0)
    if constant_cols.all():
        return DerivedWeights(
            np.full(m, 1.0 / m),
            {"std": sd.tolist()},
            ["所有指标均无波动，CRITIC 退化为等权。"],
        )
    valid = ~constant_cols
    conflict_full = np.zeros(m)
    if valid.sum() >= 2:
        # Constant columns have undefined correlation (NaN); mask them.
        # spearmanr: rows are observations, columns are variables.
        sub = norm[:, valid]
        sub_idx = np.where(valid)[0]
        k = int(valid.sum())
        rho_flat = stats.spearmanr(sub).statistic
        if k == 2:
            rho_sub = np.array([[1.0, float(rho_flat)],
                                [float(rho_flat), 1.0]])
        else:
            rho_sub = np.atleast_2d(np.asarray(rho_flat, dtype=float))
        corr_sub = np.nan_to_num(1.0 - rho_sub, nan=0.0)
        np.fill_diagonal(corr_sub, 0.0)
        sums = corr_sub.sum(axis=1)
        conflict_full[sub_idx] = sums

    information = sd * (1.0 + conflict_full)
    total = information.sum()
    weights = information / total if total > 0 else np.full(m, 1.0 / m)
    notes = []
    if constant_cols.any():
        notes.append(
            f"第 {list(map(int, np.where(constant_cols)[0]))} 列为常量列，"
            "标准差为 0，CRITIC 权重为 0。"
        )
    return DerivedWeights(
        weights, {"std": sd.tolist(), "conflict": conflict_full.tolist()}, notes
    )


def validate_manual(weights: dict, criterion_keys: list[str]) -> list[str]:
    """Check a human weight set; return human-readable problems."""
    problems: list[str] = []
    missing = set(criterion_keys) - set(weights)
    extra = set(weights) - set(criterion_keys)
    if missing:
        problems.append(f"缺少指标的权重: {sorted(missing)}")
    if extra:
        problems.append(f"权重里有未知指标: {sorted(extra)}")
    vals = [v for k, v in weights.items() if k in criterion_keys]
    if any(v < 0 for v in vals):
        problems.append("权重不能为负数。")
    if vals and abs(sum(vals) - 1.0) > 1e-6:
        problems.append(f"权重之和为 {sum(vals):.6f}，必须等于 1.0。")
    return problems
