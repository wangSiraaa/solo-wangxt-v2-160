"""Helpers to turn persisted rows into the numeric matrix and back."""
import numpy as np

from .db.models import Alternative, Criterion, Decision, MetricValue, WeightSet


def load_matrix(db, decision: Decision) -> tuple[np.ndarray, list[dict], list[dict]]:
    criteria = (
        db.query(Criterion)
        .filter(Criterion.decision_id == decision.id)
        .order_by(Criterion.id)
        .all()
    )
    alternatives = (
        db.query(Alternative)
        .filter(Alternative.decision_id == decision.id)
        .order_by(Alternative.id)
        .all()
    )
    values = (
        db.query(MetricValue)
        .join(Alternative)
        .filter(Alternative.decision_id == decision.id)
        .all()
    )
    lookup = {
        (v.alternative_id, v.criterion_id): (v.value, v.note) for v in values
    }
    raw = np.full((len(alternatives), len(criteria)), np.nan)
    raw_notes = [["" for _ in criteria] for _ in alternatives]
    for i, alt in enumerate(alternatives):
        for j, crit in enumerate(criteria):
            pair = lookup.get((alt.id, crit.id))
            if pair is not None:
                raw[i, j] = np.nan if pair[0] is None else pair[0]
                raw_notes[i][j] = pair[1] or ""

    crit_dicts = [
        {
            "key": c.key,
            "label": c.label,
            "unit": c.unit,
            "kind": c.kind,
            "target_low": c.target_low,
            "target_high": c.target_high,
            "fixed_min": c.fixed_min,
            "fixed_max": c.fixed_max,
        }
        for c in criteria
    ]
    alt_dicts = [{"key": a.key, "label": a.label} for a in alternatives]
    return raw, crit_dicts, alt_dicts, raw_notes


def resolve_weights(body, db, decision: Decision, crit_keys: list[str],
                    norm_matrix: np.ndarray):
    """Return (vector, provenance dict) according to the request."""
    from .core.weights import validate_manual
    from .core.analysis import derive_weights

    if body.use_derived in ("entropy", "critic"):
        dw = derive_weights(body.use_derived, np.nan_to_num(norm_matrix, nan=0.5))
        return dw.weights, {
            "origin": "derived",
            "method": body.use_derived,
            "notes": dw.notes,
            "diagnostics": dw.contributions,
        }

    if body.weights_override is not None:
        problems = validate_manual(body.weights_override, crit_keys)
        if problems:
            raise ValueError("；".join(problems))
        return (
            np.array([body.weights_override[k] for k in crit_keys]),
            {"origin": "manual_adhoc", "method": "manual",
             "source": "页面临时设定，未保存"},
        )

    if body.weight_set_id is not None:
        ws = db.get(WeightSet, body.weight_set_id)
        if ws is None or ws.decision_id != decision.id:
            raise ValueError("权重集不存在或不属于该决策。")
        return (
            np.array([ws.weights[k] for k in crit_keys]),
            {"origin": ws.method, "method": ws.method, "source": ws.source,
             "weight_set_id": ws.id, "name": ws.name},
        )

    raise ValueError(
        "请选择人工权重集、给出临时权重，或明确选择熵权/CRITIC 推求权重。"
    )
