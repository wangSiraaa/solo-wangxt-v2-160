"""把仓储数据装配为引擎输入，运行分析。"""
from __future__ import annotations

from . import engine
from .engine import Options


def _assemble(repo):
    crits = [engine.Criterion(
        id=c["id"], code=c["code"], name=c["name"], unit=c["unit"], ctype=c["ctype"],
        weight=float(c["weight"]), source=c["source"],
        target_low=c["target_low"], target_high=c["target_high"]) for c in repo.list_criteria()]
    cands = [engine.Candidate(id=c["id"], code=c["code"], name=c["name"], description=c.get("description", ""))
             for c in repo.list_candidates()]
    vals = repo.matrix()
    raw = [[vals.get((cand.id, cr.id)) for cr in crits] for cand in cands]
    return cands, crits, raw


def opts_from_version(v: dict) -> Options:
    keys = set(Options.__dataclass_fields__)
    return Options(**{k: v[k] for k in keys if k in v})


def run(repo, overrides: dict | None = None):
    cands, crits, raw = _assemble(repo)
    base = {
        "missing_strategy": "median", "clip_outliers": False, "clip_method": "mad",
        "clip_mad_k": 3.0, "weight_basis": "manual", "combined_alpha": 0.5,
        "keep_constants": False, "drop_criterion_ids": [], "drop_candidate_ids": [],
    }
    if overrides:
        base.update({k: v for k, v in overrides.items() if v is not None})
    options = Options(**base)
    return engine.analyze(cands, crits, raw, options), cands, crits, raw, options


def run_version(repo, version_id: int):
    v = next(x for x in repo.list_versions() if x["id"] == version_id)
    cands, crits, raw = _assemble(repo)
    return engine.analyze(cands, crits, raw, opts_from_version(v)), v


def run_reversal(repo, overrides: dict):
    cands, crits, raw = _assemble(repo)
    base = {
        "missing_strategy": "median", "clip_outliers": False, "clip_method": "mad",
        "clip_mad_k": 3.0, "weight_basis": "manual", "combined_alpha": 0.5,
        "keep_constants": False, "drop_criterion_ids": [], "drop_candidate_ids": [],
    }
    base.update({k: v for k, v in (overrides or {}).items() if v is not None})
    return engine.compare_reversal(cands, crits, raw, Options(**base))
