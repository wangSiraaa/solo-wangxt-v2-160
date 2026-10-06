from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import service
from .models import (AnalysisReport, CandidateIn, CandidateOut, CriterionIn,
                     CriterionOut, ValueIn, VersionIn, VersionOut)
from .repository import get_repo
from .seed import seed

app = FastAPI(title="技术选型 MCDA 服务",
              description="显式 WSM + TOPSIS；三种规范化；人工/熵权分离；逐步转换可核对")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

repo = get_repo()
_seed_info = seed(repo)


@app.get("/health")
def health():
    return {"status": "ok", "backend": repo.backend,
            "note": "memory 表示数据未持久化；配置 DATABASE_URL 后使用 PostgreSQL"}


@app.get("/criteria", response_model=list[CriterionOut])
def list_criteria():
    return repo.list_criteria()


@app.post("/criteria", response_model=CriterionOut)
def add_criterion(c: CriterionIn):
    return {"id": repo.add_criterion(c), **c.model_dump()}


@app.delete("/criteria/{cid}", status_code=204)
def delete_criterion(cid: int):
    repo.delete_criterion(cid)


@app.get("/candidates", response_model=list[CandidateOut])
def list_candidates():
    return repo.list_candidates()


@app.post("/candidates", response_model=CandidateOut)
def add_candidate(c: CandidateIn):
    return {"id": repo.add_candidate(c), **c.model_dump()}


@app.delete("/candidates/{cid}", status_code=204)
def delete_candidate(cid: int):
    repo.delete_candidate(cid)


@app.get("/values")
def get_values():
    return [{"candidate_id": a, "criterion_id": b, "value": v} for (a, b), v in sorted(repo.matrix().items())]


@app.post("/values", status_code=201)
def set_value(body: ValueIn):
    repo.set_value(body.candidate_id, body.criterion_id, body.value)
    return body


@app.get("/versions", response_model=list[VersionOut])
def list_versions():
    return repo.list_versions()


@app.post("/versions", response_model=VersionOut)
def create_version(v: VersionIn):
    vid = repo.create_version(v)
    return {"id": vid, "created_at": "", **v.model_dump()}

def _build_report(result, version=None) -> dict:
    """把引擎输出整理为 AnalysisReport 形状。"""
    crits_out = repo.list_criteria()
    cands_out = repo.list_candidates()
    adhoc = {
        "id": 0, "label": "ad-hoc 情景", "note": "未保存的临时计算", "created_at": "",
        "missing_strategy": "median", "clip_outliers": False, "clip_method": "mad",
        "clip_mad_k": 3.0, "weight_basis": "manual", "combined_alpha": 0.5,
        "keep_constants": False, "drop_criterion_ids": [], "drop_candidate_ids": [],
    }
    return {
        "version": version or adhoc,
        "candidates": cands_out,
        "criteria": crits_out,
        "raw_matrix": result["steps"][0]["matrix"],
        "steps": result["steps"],
        "weight_audit": result["weight_audit"],
        "weight_sum_raw": result["weight_sum_raw"],
        "weight_sum_effective": result["weight_sum_effective"],
        "wsm_rank": result["wsm_rank"],
        "topsis_rank": result["topsis_rank"],
        "reversal": None,
        "duplicate_criteria": result["duplicate_criteria"],
        "outlier_cells": result["outlier_cells"],
        "warnings": result["warnings"],
    }


@app.post("/analyze", response_model=AnalysisReport)
def analyze(body: dict | None = None):
    """即席分析：前端把选项（含增删候选/指标、裁剪、权重口径）直接发来。"""
    result, *_ = service.run(repo, body or {})
    return _build_report(result)


@app.get("/versions/{vid}/report", response_model=AnalysisReport)
def version_report(vid: int):
    try:
        result, v = service.run_version(repo, vid)
    except StopIteration:
        raise HTTPException(404, "版本不存在")
    return _build_report(result, v)


@app.post("/reversal")
def reversal(body: dict | None = None):
    """完整候选集 vs 删除候选后的集合：展示排名逆转及驱动指标。"""
    return service.run_reversal(repo, body or {})
