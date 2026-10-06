"""HTTP API: matrices, weights (manual vs derived), analysis, frozen versions."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.analysis import run_full_analysis
from ..core.normalization import normalize
from ..core.weights import validate_manual
from ..database import get_db
from ..db.models import (
    Alternative,
    Criterion,
    Decision,
    DecisionVersion,
    MetricValue,
    Scenario,
    WeightSet,
)
from ..repository import load_matrix, resolve_weights
from ..schemas import AnalyzeIn, DecisionIn, VersionIn, WeightSetIn
from ..seed import seed_all

router = APIRouter(prefix="/api")


def _json_clean(obj):
    """NaN/Inf are not valid JSON; raw missing values must become null."""
    import math
    if isinstance(obj, dict):
        return {k: _json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_clean(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


@router.post("/admin/seed")
def seed(db: Session = Depends(get_db)):
    n = seed_all(db)
    return {"seeded_scenarios": n}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/scenarios")
def list_scenarios(db: Session = Depends(get_db)):
    scenarios = db.scalars(select(Scenario).order_by(Scenario.id)).all()
    return [
        {
            "id": s.id,
            "key": s.key,
            "name": s.name,
            "description": s.description,
            "decisions": [
                {"id": d.id, "name": d.name} for d in s.decisions
            ],
        }
        for s in scenarios
    ]


def _decision_payload(db: Session, decision: Decision) -> dict:
    raw, crits, alts, notes = load_matrix(db, decision)
    weight_sets = [
        {
            "id": w.id,
            "name": w.name,
            "method": w.method,
            "source": w.source,
            "weights": w.weights,
        }
        for w in decision.weight_sets
    ]
    return {
        "id": decision.id,
        "name": decision.name,
        "settings": decision.settings,
        "criteria": crits,
        "alternatives": alts,
        # raw values as nulls — the frontend keeps the unit and the gap
        # visible, never a guessed 0.
        "raw_values": _json_clean(raw.tolist()),
        "value_notes": notes,
        "weight_sets": weight_sets,
        "versions": [
            {"id": v.id, "label": v.label, "method": v.method,
             "created_at": v.created_at.isoformat(), "created_by": v.created_by}
            for v in sorted(decision.versions, key=lambda v: v.id, reverse=True)
        ],
    }


@router.get("/decisions/{decision_id}")
def get_decision(decision_id: int, db: Session = Depends(get_db)):
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(404, "决策不存在")
    return _decision_payload(db, decision)


@router.post("/decisions")
def create_decision(body: DecisionIn, db: Session = Depends(get_db)):
    scenario = db.scalar(
        select(Scenario).where(Scenario.key == body.scenario_key)
    )
    if scenario is None:
        scenario = Scenario(key=body.scenario_key, name=body.scenario_key)
        db.add(scenario)
        db.flush()
    decision = Decision(scenario_id=scenario.id, name=body.name,
                        settings=body.settings)
    db.add(decision)
    db.flush()
    crit_rows = {
        c.key: Criterion(decision_id=decision.id, **c.model_dump())
        for c in body.criteria
    }
    db.add_all(crit_rows.values())
    alt_rows = {
        a.key: Alternative(decision_id=decision.id, **a.model_dump())
        for a in body.alternatives
    }
    db.add_all(alt_rows.values())
    db.flush()
    for v in body.values:
        if v.criterion not in crit_rows or v.alternative not in alt_rows:
            raise HTTPException(422, f"值引用了未知指标/候选: {v}")
        db.add(MetricValue(
            criterion_id=crit_rows[v.criterion].id,
            alternative_id=alt_rows[v.alternative].id,
            value=v.value, note=v.note,
        ))
    db.commit()
    return _decision_payload(db, decision)


@router.get("/decisions/{decision_id}/derived-weights")
def derived_weights_preview(
    decision_id: int,
    missing_policy: str = "neutral",
    db: Session = Depends(get_db),
):
    """Compute entropy & CRITIC weights without persisting them."""
    from ..core.analysis import derive_weights
    import numpy as np

    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(404, "决策不存在")
    raw, crits, alts, _ = load_matrix(db, decision)
    n = normalize(raw, crits, [a["key"] for a in alts], missing_policy)
    filled = np.nan_to_num(n.matrix, nan=0.5)
    out = {}
    for method in ("entropy", "critic"):
        dw = derive_weights(method, filled)
        out[method] = {
            "weights": {c["key"]: float(w) for c, w in zip(crits, dw.weights)},
            "diagnostics": dw.contributions,
            "notes": dw.notes,
        }
    return {"normalization_warnings": n.warnings, "methods": out}


@router.post("/decisions/{decision_id}/weight-sets")
def add_weight_set(
    decision_id: int, body: WeightSetIn, db: Session = Depends(get_db)
):
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(404, "决策不存在")
    crit_keys = [c.key for c in decision.criteria]
    if body.method == "manual":
        problems = validate_manual(body.weights, crit_keys)
        if problems:
            raise HTTPException(422, "人工权重校验失败：" + "；".join(problems))
        if not body.source.strip():
            raise HTTPException(
                422, "人工权重必须填写来源/依据，才能保存。"
            )
    ws = WeightSet(
        decision_id=decision.id,
        name=body.name,
        method=body.method,
        source=body.source or "由当前矩阵数据推得（熵权/CRITIC），不含价值判断。",
        weights=body.weights,
    )
    db.add(ws)
    db.commit()
    return {"id": ws.id, "name": ws.name, "method": ws.method,
            "weights": ws.weights, "source": ws.source}


@router.post("/decisions/{decision_id}/analyze")
def analyze(
    decision_id: int, body: AnalyzeIn, db: Session = Depends(get_db)
):
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(404, "决策不存在")
    raw, crits, alts, notes = load_matrix(db, decision)
    alt_keys = [a["key"] for a in alts]
    pre = normalize(raw, crits, alt_keys, body.missing_policy)
    import numpy as np
    try:
        vector, provenance = resolve_weights(
            body, db, decision, [c["key"] for c in crits], pre.matrix
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    if abs(float(np.sum(vector)) - 1.0) > 1e-6:
        raise HTTPException(422, "权重之和不为 1，拒绝计算。")

    result = run_full_analysis(
        raw, crits, alt_keys, vector, body.missing_policy
    )
    return _json_clean({
        "decision_id": decision.id,
        "criteria": crits,
        "alternatives": alts,
        "raw_values": _json_clean(raw.tolist()),
        "value_notes": notes,
        "weight_vector": vector.tolist(),
        "weight_provenance": provenance,
        "weight_sum": float(np.sum(vector)),
        "missing_policy": body.missing_policy,
        **result,
    })


@router.post("/decisions/{decision_id}/versions")
def freeze_version(
    decision_id: int, body: VersionIn, db: Session = Depends(get_db)
):
    """Freeze a ranked result as an immutable decision-of-record snapshot."""
    decision = db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(404, "决策不存在")
    raw, crits, alts, notes = load_matrix(db, decision)
    alt_keys = [a["key"] for a in alts]
    pre = normalize(raw, crits, alt_keys, body.missing_policy)
    analyze_body = AnalyzeIn(
        weight_set_id=body.weight_set_id,
        weights_override=body.weights_override,
        use_derived=body.use_derived,
        missing_policy=body.missing_policy,
    )
    try:
        vector, provenance = resolve_weights(
            analyze_body, db, decision, [c["key"] for c in crits], pre.matrix
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    result = run_full_analysis(
        raw, crits, alt_keys, vector, body.missing_policy
    )
    model_result = result["models"][body.method]
    version = DecisionVersion(
        decision_id=decision.id,
        label=body.label,
        weight_set_id=body.weight_set_id,
        method=body.method,
        created_by="committee",
        snapshot=_json_clean({
            "comment": body.comment,
            "criteria": crits,
            "alternatives": alts,
            "raw_values": raw.tolist(),
            "weight_vector": vector.tolist(),
            "weight_provenance": provenance,
            "missing_policy": body.missing_policy,
            "ranking": model_result["ranks"],
            "scores": model_result["scores"],
            "normalization": result["models"]["normalization"],
            "model_steps": model_result["steps"],
            "audits": result["audits"],
            "rank_reversal_summary": {
                "dynamic_reversal_count": len(
                    result["rank_reversal"]["dynamic_anchors"]["reversals"]
                ),
            },
        }),
    )
    db.add(version)
    db.commit()
    return {"id": version.id, "label": version.label}


@router.get("/versions/{version_id}")
def get_version(version_id: int, db: Session = Depends(get_db)):
    v = db.get(DecisionVersion, version_id)
    if v is None:
        raise HTTPException(404, "版本不存在")
    return {
        "id": v.id,
        "decision_id": v.decision_id,
        "label": v.label,
        "method": v.method,
        "created_at": v.created_at.isoformat(),
        "created_by": v.created_by,
        "snapshot": v.snapshot,
    }
