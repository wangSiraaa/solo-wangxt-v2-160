"""Pydantic schemas — the API contract shared between FastAPI and Angular."""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CriterionType(str, Enum):
    benefit = "benefit"          # 越大越好
    cost = "cost"               # 越小越好
    target_interval = "target"  # 落在区间内最好


class CriterionIn(BaseModel):
    code: str = Field(..., examples=["perf_qps"])
    name: str
    unit: str = ""
    ctype: CriterionType
    weight: float = Field(..., description="人工设定权重（可在引擎中与数据推得权重组合）")
    source: str = Field("manual", description="权重来源说明，便于核对")
    target_low: Optional[float] = None
    target_high: Optional[float] = None


class CriterionOut(CriterionIn):
    id: int


class CandidateIn(BaseModel):
    code: str
    name: str
    description: str = ""


class CandidateOut(CandidateIn):
    id: int


class ValueIn(BaseModel):
    candidate_id: int
    criterion_id: int
    value: Optional[float] = None


class ValueOut(ValueIn):
    id: int


class VersionIn(BaseModel):
    label: str
    note: str = ""
    # 计算选项
    missing_strategy: Literal["median", "mean", "worst"] = "median"
    clip_outliers: bool = False
    clip_method: Literal["percentile", "mad"] = "mad"
    clip_mad_k: float = 3.0
    weight_basis: Literal["manual", "entropy", "combined"] = "manual"
    combined_alpha: float = Field(
        0.5, ge=0.0, le=1.0,
        description="combined 模式: alpha*manual+(1-alpha)*entropy",
    )
    keep_constants: bool = False
    drop_criterion_ids: list[int] = Field(default_factory=list)
    drop_candidate_ids: list[int] = Field(default_factory=list)


class VersionOut(VersionIn):
    id: int
    created_at: str


class WeightAudit(BaseModel):
    criterion_code: str
    manual_weight: float
    manual_source: str
    entropy_weight: Optional[float]
    effective_weight: float
    effective_share: float
    basis: str
    excluded: bool
    exclude_reason: Optional[str] = None


class StepTrace(BaseModel):
    name: str
    description: str
    matrix: list[list[Optional[float]]]
    rows: list[str]
    columns: list[str]
    notes: list[str] = Field(default_factory=list)


class RankRow(BaseModel):
    rank: int
    candidate_code: str
    candidate_name: str
    wsm_score: Optional[float] = None
    topsis_score: Optional[float] = None
    closeness_ideal: Optional[float] = None
    distance_ideal: Optional[float] = None
    distance_anti_ideal: Optional[float] = None
    prev_rank: Optional[int] = None
    rank_shift: Optional[int] = None


class ReversalRow(BaseModel):
    candidate_code: str
    candidate_name: str
    rank_full: int
    rank_reduced: int
    shift: int
    driver_criterion: Optional[str] = None
    explanation: str


class AnalysisReport(BaseModel):
    version: VersionOut
    candidates: list[CandidateOut]
    criteria: list[CriterionOut]
    raw_matrix: list[list[Optional[float]]]
    steps: list[StepTrace]
    weight_audit: list[WeightAudit]
    weight_sum_raw: float
    weight_sum_effective: float
    wsm_rank: list[RankRow]
    topsis_rank: list[RankRow]
    reversal: Optional[dict] = None
    duplicate_criteria: list[dict]
    outlier_cells: list[dict]
    warnings: list[str]
