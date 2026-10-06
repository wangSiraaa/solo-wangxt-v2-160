"""核心性质测试：边界情况与排名机制，而不是某个固定分数。"""
import numpy as np
import pytest

from app import engine
from app.engine import Criterion as C, Candidate as K, Options, analyze, compare_reversal


def crit(i, code, t="benefit", w=1.0, lo=None, hi=None):
    return C(i, code, code, "u", t, w, "test", lo, hi)


def cand(i, code):
    return K(i, code, code)


def test_constant_column_not_full_marks():
    crits = [crit(1, "x"), crit(2, "const")]
    cands = [cand(1, "A"), cand(2, "B"), cand(3, "C")]
    raw = [[1.0, 5], [2.0, 5], [3.0, 5]]
    r = analyze(cands, crits, raw, Options())
    # 常量列默认剔除
    assert r["active_criteria"] == ["x"]
    assert any("常量" in w for w in r["warnings"])
    # 保留时恒为 0.5，不是 1
    r2 = analyze(cands, crits, raw, Options(keep_constants=True))
    col = r2["steps"][2]["matrix"][0]
    assert all(row[1] == 0.5 for row in r2["steps"][2]["matrix"])


def test_cost_and_benefit_orientation():
    crits = [crit(1, "gain", "benefit"), crit(2, "loss", "cost")]
    cands = [cand(1, "A"), cand(2, "B")]
    raw = [[10.0, 100.0], [20.0, 50.0]]
    r = analyze(cands, crits, raw, Options())
    n = r["steps"][2]["matrix"]
    # 收益：B=1；成本：B（更小）=1
    assert n[1][0] == 1.0 and n[0][1] == 0.0
    assert n[0][0] == 0.0 and n[1][1] == 1.0


def test_target_interval():
    crits = [crit(1, "rto", "target", lo=2.0, hi=4.0)]
    cands = [cand(1, "A"), cand(2, "B"), cand(3, "C")]
    raw = [[1.0], [3.0], [9.0]]
    r = analyze(cands, crits, raw, Options())
    n = [row[0] for row in r["steps"][2]["matrix"]]
    assert n[1] == 1.0          # 区间内满分
    assert 0.0 <= n[0] < 1.0    # 区间外衰减
    assert n[2] == 0.0          # 另一观察极值为 0


def test_missing_value_never_full_mark():
    crits = [crit(1, "x")]
    cands = [cand(1, "A"), cand(2, "B"), cand(3, "C")]
    raw = [[1.0], [None], [3.0]]
    for strat, fill in [("median", 2.0), ("mean", 2.0), ("worst", 0.0)]:
        r = analyze(cands, crits, raw, Options(missing_strategy=strat))
        assert r["steps"][1]["matrix"][1][0] == fill
    # 插补后缺失者得分严格小于最大值持有者
    r = analyze(cands, crits, raw, Options())
    assert r["wsm_rank"][0]["candidate_code"] == "C"


def test_weights_normalized_and_separable():
    crits = [crit(1, "x", w=30), crit(2, "y", w=70)]
    cands = [cand(1, "A"), cand(2, "B")]
    raw = [[1.0, 1.0], [0.0, 0.0]]
    r = analyze(cands, crits, raw, Options())
    shares = [a["effective_share"] for a in r["weight_audit"]]
    assert abs(sum(shares) - 1.0) < 1e-9
    assert shares == [0.3, 0.7]          # 原始合计 100，直接归一
    # 合计 != 100 也归一
    crits2 = [crit(1, "x", w=3), crit(2, "y", w=9)]
    r2 = analyze(cands, crits2, raw, Options())
    shares2 = [a["effective_share"] for a in r2["weight_audit"]]
    assert abs(shares2[0] - 0.25) < 1e-9


def test_entropy_equal_weights_on_manual_disagreement():
    # 数据离散度相同 => 熵权等权，与人工权重无关
    crits = [crit(1, "x", w=99), crit(2, "y", w=1)]
    cands = [cand(1, "A"), cand(2, "B")]
    raw = [[0.0, 0.0], [1.0, 1.0]]
    r = analyze(cands, crits, raw, Options(weight_basis="entropy"))
    shares = [a["effective_share"] for a in r["weight_audit"]]
    assert abs(shares[0] - 0.5) < 1e-9
    # 人工口径下保持 0.99/0.01
    rm = analyze(cands, crits, raw, Options(weight_basis="manual"))
    assert abs(rm["weight_audit"][0]["effective_share"] - 0.99) < 1e-9


def test_duplicate_detection():
    crits = [crit(1, "x"), crit(2, "x_copy")]
    cands = [cand(i, f"C{i}") for i in range(1, 5)]
    col = [1.0, 2.0, 3.0, 4.0]
    raw = [[v, v * 2 + 1] for v in col]
    r = analyze(cands, crits, raw, Options())
    assert any(d["criterion_a"] == "x" for d in r["duplicate_criteria"])


def test_outlier_flagged_not_silently_changed():
    crits = [crit(1, "x")]
    cands = [cand(i, f"C{i}") for i in range(1, 8)]
    raw = [[1.0], [1.1], [0.9], [1.0], [1.05], [0.95], [100.0]]
    r = analyze(cands, crits, raw, Options())
    assert any(o["candidate"] == "C7" for o in r["outlier_cells"])
    # 默认不裁剪：原始矩阵保留 100
    assert r["steps"][1]["matrix"][6][0] == 100.0
    rc = analyze(cands, crits, raw, Options(clip_outliers=True, clip_mad_k=3.0))
    assert rc["steps"][1]["matrix"][6][0] < 100.0


def test_rank_reversal_is_method_specific():
    """增删候选时 TOPSIS 可发生排名逆转（理想解依赖候选集），
    而 min-max WSM 在固定指标/正权重下保持相对排序——逆转是方法机制，不是客观结论。"""
    crits = [crit(1, "x", "benefit", 3.0), crit(2, "y", "benefit", 7.0)]
    cands = [cand(1, "A"), cand(2, "B"), cand(3, "D")]
    raw = [[1.0, 5.0],    # A：y 上占优
           [10.0, 4.0],   # B：x 上占优
           [20.0, 1.0]]   # D：极端 x，改变 TOPSIS 理想解
    full = analyze(cands, crits, raw, Options())
    reduced = analyze(cands, crits, raw, Options(drop_candidate_ids=[3]))

    ft = [r["candidate_code"] for r in full["topsis_rank"]]
    rt = [r["candidate_code"] for r in reduced["topsis_rank"]]
    assert ft.index("B") < ft.index("A")      # 有 D：B 优于 A
    assert rt.index("A") < rt.index("B")      # 删 D：A 反超

    fw = [r["candidate_code"] for r in full["wsm_rank"]]
    rw = [r["candidate_code"] for r in reduced["wsm_rank"]]
    assert [c for c in fw if c != "D"] == [c for c in rw if c != "D"]  # WSM 相对序不变

    rev = compare_reversal(cands, crits, raw, Options(drop_candidate_ids=[3]))
    assert "参照系" in rev["note"]


def test_topsis_scores_in_unit_interval():
    crits = [crit(1, "x", "benefit"), crit(2, "y", "cost")]
    cands = [cand(i, f"C{i}") for i in range(1, 5)]
    rng = np.random.default_rng(0)
    raw = [[float(rng.integers(1, 10)), float(rng.integers(1, 10))] for _ in cands]
    r = analyze(cands, crits, raw, Options())
    for row in r["topsis_rank"]:
        assert 0.0 <= row["closeness_ideal"] <= 1.0
