"""
MCDA engine — 显式的加权求和模型 (WSM) 与 TOPSIS。

设计原则
--------
1. 收益型 / 成本型 / 目标区间型指标分别规范化，全部映射到 [0,1]，1 = 最受偏好。
2. 常量列不自动得满分：从有效计算中剔除并重新分配权重，同时给出告警；
   只有用户显式要求 keep_constants 时才保留（此时分数恒为 0.5，而不是 1）。
3. 缺失值不自动得满分：中位数/均值/最差(0) 三种插补，插补单元格显式标记。
4. 人工权重与数据推得权重（熵权法）严格分开记录，可核对、可组合。
5. 返回每一步的转换矩阵，前端逐格展示，便于委员会复核。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import stats

eps = 1e-12


@dataclass
class Criterion:
    id: int
    code: str
    name: str
    unit: str
    ctype: str  # benefit | cost | target
    weight: float
    source: str
    target_low: Optional[float] = None
    target_high: Optional[float] = None


@dataclass
class Candidate:
    id: int
    code: str
    name: str
    description: str = ""


@dataclass
class Options:
    missing_strategy: str = "median"       # median | mean | worst
    clip_outliers: bool = False
    clip_method: str = "mad"               # percentile | mad
    clip_mad_k: float = 3.0
    weight_basis: str = "manual"           # manual | entropy | combined
    combined_alpha: float = 0.5
    keep_constants: bool = False
    drop_criterion_ids: list[int] = field(default_factory=list)
    drop_candidate_ids: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 单指标规范化
# ---------------------------------------------------------------------------

def normalize_column(x: np.ndarray, crit: Criterion) -> tuple[np.ndarray, list[str]]:
    """把原始列规范化到 [0,1]。返回 (规范化列, 说明)。调用前 x 应已无缺失。"""
    notes: list[str] = []
    xmin, xmax = float(np.nanmin(x)), float(np.nanmax(x))

    if xmax - xmin <= eps:
        # 常量列：绝不自动给满分 1。中性 0.5（信息熵意义上"无偏好信息"）。
        notes.append(f"{crit.code}: 常量列（所有候选={xmin}），赋中性分 0.5 而非满分")
        return np.full_like(x, 0.5, dtype=float), notes

    if crit.ctype == "benefit":
        z = (x - xmin) / (xmax - xmin)
        notes.append(f"{crit.code}: 收益型 min-max，(x-min)/(max-min)")
    elif crit.ctype == "cost":
        z = (xmax - x) / (xmax - xmin)
        notes.append(f"{crit.code}: 成本型反向 min-max，(max-x)/(max-min)")
    else:
        lo, hi = crit.target_low, crit.target_high
        if lo is None or hi is None or hi < lo:
            lo = hi = float(np.median(x))
            notes.append(f"{crit.code}: 目标区间缺失/非法，退化为中位数目标")
        xc = np.clip(x, lo, hi)
        z = (xc - lo) / (hi - lo) if hi - lo > eps else np.full_like(x, 0.5, dtype=float)
        # 区间外按距离线性衰减，区间端点为 1，退化到观察极值为 0
        below = x < lo
        above = x > hi
        span_lo = lo - xmin if lo - xmin > eps else 1.0
        span_hi = xmax - hi if xmax - hi > eps else 1.0
        z = np.where(below, np.maximum(0.0, (x - xmin) / span_lo),
                     np.where(above, np.maximum(0.0, (xmax - x) / span_hi), 1.0))
        # 区间内部 = 1
        z = np.where((x >= lo) & (x <= hi), 1.0, z)
        notes.append(f"{crit.code}: 目标区间型 [{lo}, {hi}] 内=1，区间外向最近观察极值线性衰减到 0")
    return z, notes


# ---------------------------------------------------------------------------
# 缺失值 / 异常值
# ---------------------------------------------------------------------------

def find_missing(raw: np.ndarray, cands, crits) -> list[dict]:
    out = []
    for i, c in enumerate(cands):
        for j, cr in enumerate(crits):
            v = raw[i, j]
            if v is None or (isinstance(v, float) and math.isnan(v)):
                out.append({"candidate": c.code, "criterion": cr.code})
    return out


def impute(raw: np.ndarray, crits, strategy: str) -> tuple[np.ndarray, list[tuple[int, int, float]], list[str]]:
    """返回插补后矩阵、插补事件 (i,j,填充值)、说明。绝不填 1（满分）。"""
    data = np.array([[np.nan if v is None else float(v) for v in row] for row in raw], dtype=float)
    events: list[tuple[int, int, float]] = []
    notes: list[str] = []
    for j, cr in enumerate(crits):
        col = data[:, j]
        mask = np.isnan(col)
        if not mask.any():
            continue
        present = col[~mask]
        if present.size == 0:
            fill = 0.0
            notes.append(f"{cr.code}: 整列缺失，无法插补，填 0（最差）且指标不提供区分信息")
        elif strategy == "mean":
            fill = float(np.mean(present))
        elif strategy == "worst":
            fill = 0.0
        else:  # median（默认，对极端异常稳健）
            fill = float(np.median(present))
        idxs = np.where(mask)[0]
        data[idxs, j] = fill
        for i in idxs:
            events.append((i, j, fill))
        notes.append(f"{cr.code}: {len(idxs)} 个缺失值用{ {'median':'中位数','mean':'均值','worst':'最差值0'}[strategy] }插补 = {fill:.4g}")
    return data, events, notes


def detect_outliers(data: np.ndarray, cands, crits) -> list[dict]:
    """修正 z 分数 (MAD)，|0.6745*(x-med)/MAD| > 3.5 标记为异常。仅标记，不静默修改。"""
    out = []
    for j, cr in enumerate(crits):
        col = data[:, j]
        med = np.median(col)
        mad = np.median(np.abs(col - med))
        if mad <= eps:
            continue
        mz = 0.6745 * (col - med) / mad
        for i, z in enumerate(mz):
            if abs(z) > 3.5:
                out.append({
                    "candidate": cands[i].code,
                    "criterion": cr.code,
                    "value": float(col[i]),
                    "modified_z": round(float(z), 2),
                })
    return out


def clip_column(col: np.ndarray, method: str, k: float) -> tuple[np.ndarray, Optional[tuple[float, float]]]:
    lo, hi = float(np.min(col)), float(np.max(col))
    if method == "percentile":
        lo, hi = np.percentile(col, [5, 95])
    else:
        med = np.median(col)
        mad = np.median(np.abs(col - med))
        if mad > eps:
            lo, hi = med - k * 1.4826 * mad, med + k * 1.4826 * mad
        else:
            return col, None
    clipped = np.clip(col, lo, hi)
    if np.allclose(clipped, col):
        return col, None
    return clipped, (lo, hi)


# ---------------------------------------------------------------------------
# 数据推得权重：熵权法
# ---------------------------------------------------------------------------

def entropy_weights(norm: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """输入 min-max 规范化矩阵（列内已无常量）。返回 (权重, 熵值, 说明)。"""
    m, n = norm.shape
    # 平移避免 0：p 用列内占比
    notes: list[str] = []
    w = np.full(n, 1.0 / n)
    entropies = np.ones(n)
    if m <= 1:
        notes.append("候选数<=1，熵权法无法估计离散度，退化为等权")
        return w, entropies, notes
    shifted = norm + eps
    p = shifted / shifted.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        ent = (-1.0 / math.log(m)) * np.nansum(p * np.log(p), axis=0)
    entropies = ent
    d = 1.0 - ent
    if d.sum() <= eps:
        notes.append("各指标熵值均≈1（区分度为0），熵权退化为等权")
        return w, entropies, notes
    w = d / d.sum()
    return w, entropies, notes


# ---------------------------------------------------------------------------
# 重复 / 冗余指标检测
# ---------------------------------------------------------------------------

def duplicate_criteria(norm: np.ndarray, crits) -> list[dict]:
    """皮尔逊相关 + Spearman 秩相关都 >0.98，且非完全常量 → 疑似重复指标。"""
    out = []
    n = len(crits)
    for a in range(n):
        for b in range(a + 1, n):
            x, y = norm[:, a], norm[:, b]
            if np.std(x) <= eps or np.std(y) <= eps:
                continue
            pear = float(np.corrcoef(x, y)[0, 1])
            spear = float(stats.spearmanr(x, y).statistic)
            if abs(pear) > 0.98 and abs(spear) > 0.98:
                out.append({
                    "criterion_a": crits[a].code,
                    "criterion_b": crits[b].code,
                    "pearson": round(pear, 4),
                    "spearman": round(spear, 4),
                    "effect": "两者信息近似重复，同时计入相当于该维度被双重加权",
                })
    return out


# ---------------------------------------------------------------------------
# 主分析
# ---------------------------------------------------------------------------

def _rank(scores, codes, names, prev=None):
    order = np.argsort(-scores, kind="mergesort")
    rows = []
    for rank_pos, idx in enumerate(order, start=1):
        pr = None if prev is None else prev.get(int(idx))
        rows.append({
            "rank": rank_pos,
            "candidate_code": codes[int(idx)],
            "candidate_name": names[int(idx)],
            "score": round(float(scores[idx]), 6),
            "prev_rank": pr,
            "rank_shift": None if pr is None else pr - rank_pos,
        })
    return rows


def _prev_rank_map(rank_rows):
    return {r["candidate_code"]: r["rank"] for r in rank_rows}


def analyze(cands, crits, raw, options: Options, *, label: str = "") -> dict:
    warnings: list[str] = []
    all_notes: list[str] = []
    steps = []

    # --- 候选 / 指标筛选（用于增删候选、删除重复指标的情景） ---
    keep_c = [c for c in cands if c.id not in set(options.drop_candidate_ids)]
    crits_eff = [cr for cr in crits if cr.id not in set(options.drop_criterion_ids)]
    if not keep_c:
        raise ValueError("至少保留一个候选")
    if not crits_eff:
        raise ValueError("至少保留一个指标")

    ci = [cands.index(c) for c in keep_c]
    kj = [crits.index(cr) for cr in crits_eff]
    raw_sub = [[raw[i][j] for j in kj] for i in ci]

    codes = [c.code for c in keep_c]
    names = [c.name for c in keep_c]
    col_codes = [cr.code for cr in crits_eff]

    steps.append({
        "name": "1. 原始数据",
        "description": "数据库中的原始观测值（保留单位，未做任何变换）。None=缺失。",
        "matrix": [[None if v is None else float(v) for v in row] for row in raw_sub],
        "rows": codes, "columns": col_codes,
        "notes": [f"{cr.code} 单位={cr.unit or '无'}, 类型={ {'benefit':'收益','cost':'成本','target':'目标区间'}[cr.ctype]}" for cr in crits_eff],
    })

    missing_cells = find_missing(np.array(raw_sub, dtype=object), keep_c, crits_eff)
    data, imp_events, imp_notes = impute(raw_sub, crits_eff, options.missing_strategy)
    all_notes.extend(imp_notes)
    warnings.extend(f"缺失值：{e['candidate']}/{e['criterion']}" for e in missing_cells)

    # --- 异常值检测（在任何裁剪之前，对原始尺度） ---
    outliers = detect_outliers(data, keep_c, crits_eff)
    for o in outliers:
        warnings.append(
            f"极端异常值：{o['candidate']} 的 {o['criterion']}={o['value']:g}，修正z={o['modified_z']}（仅标记）")

    # --- 可选裁剪（用户显式开启，矩阵单独展示，绝不静默） ---
    clipped_data = data.copy()
    if options.clip_outliers:
        for j in range(data.shape[1]):
            clipped_data[:, j], bounds = clip_column(data[:, j], options.clip_method, options.clip_mad_k)
            if bounds:
                all_notes.append(f"{crits_eff[j].code}: 裁剪到 [{bounds[0]:.4g}, {bounds[1]:.4g}]（{options.clip_method}）")

    # --- 常量列识别 ---
    const_idx = [j for j in range(data.shape[1])
                 if float(np.nanmax(clipped_data[:, j])) - float(np.nanmin(clipped_data[:, j])) <= eps]
    excluded = set()
    weight_audit = []
    for j, cr in enumerate(crits_eff):
        reason = None
        if j in const_idx:
            reason = "常量列：不提供区分信息"
            if not options.keep_constants:
                excluded.add(j)
                warnings.append(f"指标 {cr.code} 为常量列，已从加权计算剔除并重分配权重（未自动给满分）")
            else:
                warnings.append(f"指标 {cr.code} 为常量列，按用户要求保留，规范化恒为 0.5")
        weight_audit.append({
            "criterion_code": cr.code, "manual_weight": cr.weight, "manual_source": cr.source,
            "entropy_weight": None, "effective_weight": cr.weight, "effective_share": 0.0,
            "basis": options.weight_basis, "excluded": j in excluded, "exclude_reason": reason,
        })
    active = [j for j in range(data.shape[1]) if j not in excluded]

    # --- 规范化（逐列，按类型） ---
    norm = np.zeros_like(clipped_data)
    for j, cr in enumerate(crits_eff):
        if j in excluded:
            continue
        norm[:, j], nnotes = normalize_column(clipped_data[:, j], cr)
        all_notes.extend(nnotes)

    norm_view = [[None if j in excluded else round(float(norm[i, j]), 6)
                  for j in range(len(crits_eff))] for i in range(len(keep_c))]
    steps.append({
        "name": "2. 缺失值插补 / 异常值裁剪",
        "description": "缺失按选定策略插补并在下方标注；异常值默认只标记，开启裁剪后才修改。",
        "matrix": [[round(float(clipped_data[i, j]), 6) for j in range(clipped_data.shape[1])]
                   for i in range(clipped_data.shape[0])],
        "rows": codes, "columns": col_codes,
        "notes": all_notes,
    })
    steps.append({
        "name": "3. 按指标类型规范化到 [0,1]",
        "description": "收益型/成本型 min-max（成本反向）；目标区间型区间内=1、向外衰减。None=常量列已剔除。",
        "matrix": norm_view, "rows": codes, "columns": col_codes,
        "notes": [f"共 {len(imp_events)} 个单元格由插补得到（见步骤2）" ] + [
            f"{codes[i]}/{col_codes[j]} 使用插补值 {v:.4g}"
            for (i, j, v) in sorted(imp_events) if j in active],
    })

    # --- 权重 ---
    raw_sum = float(sum(cr.weight for cr in crits))
    man_active = np.array([crits_eff[j].weight for j in active], dtype=float)
    man_share = man_active / man_active.sum() if man_active.sum() > eps else np.full(len(active), 1 / len(active))
    ent_w, entropies, ent_notes = entropy_weights(norm[:, active])
    all_notes.extend(ent_notes)
    if options.weight_basis == "entropy":
        eff = ent_w
        basis = "entropy"
    elif options.weight_basis == "combined":
        a = options.combined_alpha
        eff = a * man_share + (1 - a) * ent_w
        basis = f"{a:.2f}·人工 + {1-a:.2f}·熵权"
    else:
        eff = man_share
        basis = "manual"
    eff = eff / eff.sum()

    # 回填 audit
    for k, j in enumerate(active):
        cr = crits_eff[j]
        row = next(r for r in weight_audit if r["criterion_code"] == cr.code)
        row.update({"entropy_weight": round(float(ent_w[k]), 6),
                    "effective_weight": round(float(eff[k] * man_active.sum()), 6),
                    "effective_share": round(float(eff[k]), 6), "basis": basis})
    eff_sum = float(sum(cr.weight for j, cr in enumerate(crits_eff) if j in active))

    wmat = norm[:, active] * eff[np.newaxis, :]
    steps.append({
        "name": "4. 权重与加权矩阵",
        "description": f"权重口径：{basis}。人工权重原始合计={raw_sum:g}（在有效指标内重新归一）；熵权完全由数据离散度推得，单独列出。",
        "matrix": [[round(float(wmat[i, k]), 6) for k in range(len(active))]
                   for i in range(len(keep_c))],
        "rows": codes,
        "columns": [f"{col_codes[j]}(w={eff[k]:.3f})" for k, j in enumerate(active)],
        "notes": all_notes,
    })

    # --- WSM ---
    wsm = wmat.sum(axis=1)

    # --- TOPSIS（向量归一化的经典口径；成本型在规范化时已反向，这里统一按收益方向） ---
    v = norm[:, active]
    norms = np.sqrt((v ** 2).sum(axis=0))
    norms[norms <= eps] = 1.0
    r = v / norms[np.newaxis, :]
    weighted = r * eff[np.newaxis, :]
    ideal = weighted.max(axis=0)
    anti = weighted.min(axis=0)
    d_pos = np.sqrt(((weighted - ideal) ** 2).sum(axis=1))
    d_neg = np.sqrt(((weighted - anti) ** 2).sum(axis=1))
    denom = d_pos + d_neg
    closeness = np.where(denom > eps, d_neg / denom, 0.0)

    steps.append({
        "name": "5. TOPSIS 距离",
        "description": "向量归一→加权→正/负理想解→欧氏距离 D+/D-→贴近度 C=D-/(D++D-)。理想解随候选集合变化，这是增删候选可致排名逆转的机制。",
        "matrix": [[round(float(weighted[i, k]), 6) for k in range(len(active))]
                   for i in range(len(keep_c))],
        "rows": codes,
        "columns": [f"{col_codes[j]}*" for j in active],
        "notes": [
            "正理想解 A+ = " + ", ".join(f"{col_codes[j]}:{ideal[k]:.3f}" for k, j in enumerate(active)),
            "负理想解 A- = " + ", ".join(f"{col_codes[j]}:{anti[k]:.3f}" for k, j in enumerate(active)),
        ],
    })

    wsm_rank = _rank(wsm, codes, names)
    top_rank = _rank(closeness, codes, names)
    # 合并两模型到统一行结构
    by_code = {codes[i]: (d_pos[i], d_neg[i], closeness[i]) for i in range(len(codes))}
    wsm_out, top_out = [], []
    for r in wsm_rank:
        c = r["candidate_code"]
        wsm_out.append({"rank": r["rank"], "candidate_code": c, "candidate_name": r["candidate_name"],
                        "wsm_score": r["score"], "topsis_score": None,
                        "closeness_ideal": None, "distance_ideal": None, "distance_anti_ideal": None,
                        "prev_rank": r["prev_rank"], "rank_shift": r["rank_shift"]})
    for r in top_rank:
        c = r["candidate_code"]
        dp, dn, cl = by_code[c]
        top_out.append({"rank": r["rank"], "candidate_code": c, "candidate_name": r["candidate_name"],
                        "wsm_score": None, "topsis_score": r["score"],
                        "closeness_ideal": round(float(cl), 6),
                        "distance_ideal": round(float(dp), 6),
                        "distance_anti_ideal": round(float(dn), 6),
                        "prev_rank": r["prev_rank"], "rank_shift": r["rank_shift"]})

    return {
        "wsm_scores": {codes[i]: float(wsm[i]) for i in range(len(codes))},
        "closeness": {codes[i]: float(closeness[i]) for i in range(len(codes))},
        "wsm_rank": wsm_out,
        "topsis_rank": top_out,
        "steps": steps,
        "weight_audit": weight_audit,
        "weight_sum_raw": raw_sum,
        "weight_sum_effective": eff_sum,
        "duplicate_criteria": duplicate_criteria(norm[:, active], [crits_eff[j] for j in active]),
        "outlier_cells": outliers,
        "missing_cells": missing_cells,
        "warnings": warnings,
        "active_criteria": [col_codes[j] for j in active],
        "codes": codes,
        "names": names,
        "weighted_matrix": wmat,
        "norm_active": norm[:, active],
        "active_idx": active,
        "crits_eff": crits_eff,
    }


def compare_reversal(cands, crits, raw, options: Options) -> dict:
    """对比完整集合 vs 删除候选后的集合，定位排名逆转及其驱动指标。

    完整集合：仅应用指标删选与其他选项，忽略候选删选；
    缩减集合：在完整集合基础上删除 drop_candidate_ids（为空时默认删当前第一名）。
    """
    full_opts = Options(**{**options.__dict__, "drop_candidate_ids": []})
    full = analyze(cands, crits, raw, full_opts)
    reduced_opts = Options(**{**options.__dict__})
    # 若用户没指定删谁，默认剔除当前第一名（最容易暴露逆转）
    if not reduced_opts.drop_candidate_ids:
        top = full["wsm_rank"][0]["candidate_code"]
        cand = next(c for c in cands if c.code == top)
        reduced_opts.drop_candidate_ids = [cand.id]
    reduced = analyze(cands, crits, raw, reduced_opts)

    prev_map = _prev_rank_map(full["wsm_rank"])
    rows = []
    for r in reduced["wsm_rank"]:
        code = r["candidate_code"]
        pr = prev_map.get(code)
        shift = (pr - r["rank"]) if pr else 0
        rows.append({
            "candidate_code": code, "candidate_name": r["candidate_name"],
            "rank_full": pr, "rank_reduced": r["rank"], "shift": shift,
        })

    # 驱动指标：比较两次规范化+加权后每列的贡献变化幅度
    drivers = []
    full_idx = {c: i for i, c in enumerate(full["codes"])}
    red_idx = {c: i for i, c in enumerate(reduced["codes"])}
    common = [c for c in reduced["codes"]]
    for k, codecol in enumerate(reduced["active_criteria"]):
        deltas = []
        for c in common:
            fi, ri = full_idx[c], red_idx[c]
            kf = full["active_criteria"].index(codecol)
            deltas.append(float(reduced["weighted_matrix"][ri, k] - full["weighted_matrix"][fi, kf]))
        drivers.append((codecol, float(np.mean(np.abs(deltas))), deltas))
    drivers.sort(key=lambda t: -t[1])
    top_driver = drivers[0][0] if drivers else None

    explanations = []
    for row in rows:
        if row["shift"] != 0:
            explanations.append(
                f"{row['candidate_name']}（{row['candidate_code']}）：删除候选后第 {row['rank_full']} → 第 {row['rank_reduced']} 名。"
                f"min-max 的极值参照系与 TOPSIS 理想解随集合改变，{top_driver} 列贡献变化最大。"
                "这是方法机制，不是'客观事实'被推翻。")
        row["driver_criterion"] = top_driver
        row["explanation"] = (
            f"排序不变（第{row['rank_reduced']}名），但分数尺度已随参照系变化。"
            if row["shift"] == 0 else
            f"排名移动 {row['shift']:+d} 位；主要驱动列={top_driver}（min-max 端点/理想解随候选集合重算）。")

    return {
        "dropped_candidate_ids": reduced_opts.drop_candidate_ids,
        "dropped_label": next(c.name for c in cands if c.id in reduced_opts.drop_candidate_ids),
        "full_ranking": [{"candidate_code": r["candidate_code"], "rank": r["rank"], "score": r["wsm_score"]}
                         for r in full["wsm_rank"]],
        "reduced_ranking": [{"candidate_code": r["candidate_code"], "rank": r["rank"], "score": r["wsm_score"]}
                            for r in reduced["wsm_rank"]],
        "rows": rows,
        "drivers": [{"criterion": d[0], "mean_abs_contribution_change": round(d[1], 6)} for d in drivers],
        "explanations": explanations,
        "note": "排名逆转根源：min-max 规范化与 TOPSIS 理想解都依赖当前候选集合，增删候选会改变所有分数的参照系。",
    }
