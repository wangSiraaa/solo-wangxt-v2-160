"""Behavioural tests for the non-negotiable safety properties."""
import numpy as np

from app.core.analysis import (
    find_duplicate_criteria,
    find_outliers,
    rank_reversal_audit,
)
from app.core.normalization import normalize
from app.core.scoring import topsis, wsm
from app.core.weights import critic_weights, entropy_weights, validate_manual

B = {"key": "b", "label": "收益", "kind": "benefit"}
C = {"key": "c", "label": "成本", "kind": "cost"}
T = {"key": "t", "label": "区间", "kind": "target",
     "target_low": 2.0, "target_high": 4.0}


def test_benefit_and_cost_directions_are_opposite():
    raw = np.array([[1.0], [2.0], [4.0]])
    nb = normalize(raw, [B], ["x", "y", "z"])
    nc = normalize(raw, [C], ["x", "y", "z"])
    assert np.allclose(nb.matrix[:, 0], [0.0, 1 / 3, 1.0])
    # Cost direction must be exactly the mirror image, never accidentally
    # scored in the same direction as a benefit column.
    assert np.allclose(nc.matrix[:, 0], 1.0 - nb.matrix[:, 0])


def test_target_interval_full_marks_inside_decaying_outside():
    raw = np.array([[1.0], [3.0], [4.5], [5.0]])
    n = normalize(raw, [T], ["x", "y", "z", "w"])
    m = n.matrix[:, 0]
    assert m[1] == 1.0           # inside [2,4]
    assert np.isclose(m[2], 0.5)  # 4.5: half way between high(4) and anchor(5)
    assert m[0] == 0.0 and m[3] == 0.0  # on the anchors -> 0, no division issue


def test_meta_is_emitted_for_every_criterion_with_formula():
    raw = np.array([[1.0, 5.0], [1.0, 5.0], [1.0, 7.0]])
    crits = [dict(B), dict(B, key="x")]
    n = normalize(raw, crits, ["a", "b", "c"])
    assert len(n.meta) == 2
    assert all(m["formula"] for m in n.meta)
    assert n.meta[0]["constant"] and not n.meta[1]["constant"]


def test_constant_column_no_division_by_zero_and_neutral_not_full():
    raw = np.array([[7.0], [7.0], [7.0]])
    for kind, crit in (("benefit", B), ("cost", C)):
        n = normalize(raw, [crit], ["x", "y", "z"])
        assert np.allclose(n.matrix[:, 0], 0.5)   # neutral, NOT 1.0
        assert any("常量列" in w for w in n.warnings)


def test_missing_value_is_never_auto_full_marks():
    raw = np.array([[1.0], [np.nan], [4.0]])
    n = normalize(raw, [B], ["x", "y", "z"], "neutral")
    assert n.matrix[1, 0] == 0.5
    assert n.missing_cells[0]["alternative"] == "y"
    # row_mean policy: mean of the row's *other* known scores
    raw2 = np.array([[1.0, 10.0], [np.nan, 2.0], [4.0, 8.0]])
    crits = [dict(B), dict(B, key="b2")]
    n2 = normalize(raw2, crits, ["x", "y", "z"], "row_mean")
    # y row: only b2 known, normalised (2,8->0,10->1): 2->0 -> mean 0
    assert n2.matrix[1, 0] == 0.0


def test_entropy_gives_constant_column_zero_weight():
    raw = np.array([[1.0, 9.0], [1.0, 3.0], [1.0, 6.0]])
    n = normalize(raw, [dict(B), dict(B, key="x")], ["a", "b", "c"])
    dw = entropy_weights(n.matrix)
    assert np.isclose(dw.weights[0], 0.0)
    assert np.isclose(dw.weights.sum(), 1.0)
    # CRITIC agrees: no contrast => zero weight
    cw = critic_weights(n.matrix)
    assert np.isclose(cw.weights[0], 0.0)


def test_manual_weight_validation():
    keys = ["b", "c"]
    assert validate_manual({"b": 0.6, "c": 0.4}, keys) == []
    problems = " ".join(validate_manual({"b": 0.6, "c": 0.3}, keys))
    assert "必须等于 1" in problems
    assert validate_manual({"b": -0.2, "c": 1.2}, keys)
    assert validate_manual({"b": 0.5}, keys)        # missing key reported


def test_duplicate_pair_detected():
    raw = np.array([[10.0, 100.0], [20.0, 200.0], [30.0, 300.0]])
    crits = [dict(B), dict(C, key="c")]
    dups = find_duplicate_criteria(raw, crits)
    assert len(dups) == 1 and dups[0]["a"] == "b" and dups[0]["b"] == "c"


def test_outlier_detected_by_robust_z():
    raw = np.array([[10.0], [11.0], [9.0], [10.5], [240.0]])
    out = find_outliers(raw, [dict(B, unit="万")], ["a", "b", "c", "d", "e"])
    assert len(out) == 1 and out[0]["alternative"] == "e"


def test_topsis_rank_reversal_on_removal_and_anchor_immunity():
    raw = np.array([[10.0, 9.0], [7.0, 4.5], [6.0, 4.0], [1.0, 0.5]])
    crits = [dict(B), dict(C)]
    audit = rank_reversal_audit(raw, crits, ["A", "B", "C", "D"],
                                np.array([0.5, 0.5]))
    dyn = audit["dynamic_anchors"]["reversals"]
    # Removing B swaps A and D under TOPSIS in the dynamic-anchor run.
    assert any(r["removed"] == "B" and r["model"] == "topsis" for r in dyn)
    # With fixed global anchors, WSM scores of survivors must be unchanged,
    # so no WSM reversal is reported.
    anchored_wsm = [
        r for r in audit["fixed_anchors"]["reversals"]
        if r["model"] == "wsm"
    ]
    assert anchored_wsm == []


def test_wsm_cell_contributions_sum_to_score():
    n = normalize(np.array([[3.0, 9.0], [1.0, 2.0]]), [dict(B), dict(C)],
                  ["x", "y"])
    res = wsm(n.matrix, np.array([0.3, 0.7]), ["x", "y"])
    contribs = np.array(res.steps["weighted_matrix"]).sum(axis=1)
    assert np.allclose(contribs, res.scores)


def test_topsis_handles_all_constant_matrix_without_nan():
    raw = np.array([[5.0], [5.0], [5.0]])
    n = normalize(raw, [dict(B)], ["x", "y", "z"])
    res = topsis(n.matrix, np.array([1.0]), ["x", "y", "z"])
    assert np.isfinite(res.scores).all()
