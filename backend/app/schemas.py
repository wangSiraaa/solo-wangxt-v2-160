"""Request/response schemas."""
from typing import Literal

from pydantic import BaseModel, Field


class CriterionIn(BaseModel):
    key: str
    label: str
    unit: str = ""
    kind: Literal["benefit", "cost", "target"]
    target_low: float | None = None
    target_high: float | None = None
    fixed_min: float | None = None
    fixed_max: float | None = None


class AlternativeIn(BaseModel):
    key: str
    label: str


class ValueIn(BaseModel):
    criterion: str
    alternative: str
    value: float | None = None
    note: str = ""


class DecisionIn(BaseModel):
    scenario_key: str
    name: str
    settings: dict = Field(default_factory=dict)
    criteria: list[CriterionIn]
    alternatives: list[AlternativeIn]
    values: list[ValueIn]


class WeightSetIn(BaseModel):
    name: str
    method: Literal["manual", "entropy", "critic"]
    source: str = ""
    weights: dict[str, float]
    save_derived: bool = False


class AnalyzeIn(BaseModel):
    weight_set_id: int | None = None
    # Ad-hoc manual weights for "what if" analysis without persisting.
    weights_override: dict[str, float] | None = None
    use_derived: Literal["manual", "entropy", "critic"] = "manual"
    missing_policy: Literal["neutral", "row_mean", "exclude_weight"] = "neutral"


class VersionIn(BaseModel):
    label: str
    method: Literal["wsm", "topsis"]
    weight_set_id: int | None = None
    weights_override: dict[str, float] | None = None
    use_derived: Literal["manual", "entropy", "critic"] = "manual"
    missing_policy: Literal["neutral", "row_mean", "exclude_weight"] = "neutral"
    comment: str = ""
