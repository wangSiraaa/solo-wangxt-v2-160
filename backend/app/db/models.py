"""SQLAlchemy models: raw metrics, units, weight provenance and decision snapshots."""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


# JSONB on PostgreSQL, plain JSON on SQLite (local fallback).
JSONType = JSONB().with_variant(JSON(), "sqlite")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )


class Decision(Base):
    """A working decision matrix: alternatives, criteria, raw values."""
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id"))
    name: Mapped[str] = mapped_column(String(200))
    # JSON of {"anchors": {criterion_key: {"min": x, "max": y}}} — fixed
    # reference bounds that suppress rank reversal when the set changes.
    settings: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    scenario: Mapped[Scenario] = relationship(back_populates="decisions")
    criteria: Mapped[list["Criterion"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )
    alternatives: Mapped[list["Alternative"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )
    weight_sets: Mapped[list["WeightSet"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )
    versions: Mapped[list["DecisionVersion"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )


class Criterion(Base):
    """A metric definition: kind (benefit/cost/target), unit, target interval."""
    __tablename__ = "criteria"
    __table_args__ = (UniqueConstraint("decision_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(64), default="")
    # "benefit" (higher better), "cost" (lower better), "target" (interval)
    kind: Mapped[str] = mapped_column(String(16))
    target_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Optional fixed anchor for reversal-free normalization.
    fixed_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    fixed_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    decision: Mapped[Decision] = relationship(back_populates="criteria")
    values: Mapped[list["MetricValue"]] = relationship(
        back_populates="criterion", cascade="all, delete-orphan"
    )


class Alternative(Base):
    __tablename__ = "alternatives"
    __table_args__ = (UniqueConstraint("decision_id", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(200))

    decision: Mapped[Decision] = relationship(back_populates="alternatives")
    values: Mapped[list["MetricValue"]] = relationship(
        back_populates="alternative", cascade="all, delete-orphan"
    )


class MetricValue(Base):
    """Raw, un-normalised measurement.  NULL means missing."""
    __tablename__ = "metric_values"
    __table_args__ = (UniqueConstraint("alternative_id", "criterion_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    alternative_id: Mapped[int] = mapped_column(ForeignKey("alternatives.id"))
    criterion_id: Mapped[int] = mapped_column(ForeignKey("criteria.id"))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(String(300), default="")

    alternative: Mapped[Alternative] = relationship(back_populates="values")
    criterion: Mapped[Criterion] = relationship(back_populates="values")


class WeightSet(Base):
    """Weights are either human-set (provenance required) or data-derived."""
    __tablename__ = "weight_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    name: Mapped[str] = mapped_column(String(200))
    # "manual" | "entropy" | "critic"
    method: Mapped[str] = mapped_column(String(32))
    # Free-text justification / data source for manual weights; for derived
    # sets this records the algorithm settings used.
    source: Mapped[str] = mapped_column(Text, default="")
    weights: Mapped[dict] = mapped_column(JSONType)  # {criterion_key: w}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    decision: Mapped[Decision] = relationship(back_populates="weight_sets")


class DecisionVersion(Base):
    """Immutable frozen record of a ranked result — the 'decision of record'."""
    __tablename__ = "decision_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    label: Mapped[str] = mapped_column(String(200))
    weight_set_id: Mapped[int | None] = mapped_column(
        ForeignKey("weight_sets.id"), nullable=True
    )
    method: Mapped[str] = mapped_column(String(32))  # wsm | topsis
    # Full snapshot: raw matrix, normalised matrices, rankings, warnings.
    snapshot: Mapped[dict] = mapped_column(JSONType)
    created_by: Mapped[str] = mapped_column(String(120), default="committee")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    decision: Mapped[Decision] = relationship(back_populates="versions")
