"""Seed scenarios.

Scenario "vendor": one decision matrix containing every trap on purpose —
a constant column, a missing cell, a duplicate (perfectly co-ranked)
criterion pair, and an extreme price outlier.

Scenario "reversal": the minimal 4x2 matrix where removing one candidate
reverses the TOPSIS order of the survivors, while anchored WSM is immune.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import (
    Alternative,
    Criterion,
    Decision,
    MetricValue,
    Scenario,
    WeightSet,
)

VENDOR = {
    "key": "vendor",
    "name": "云平台供应商选型（含审计陷阱）",
    "description": (
        "四个候选平台。数据中故意包含：常量列（可用性都是 99.9%）、"
        "缺失值（磐石未提交性能压测）、重复指标（延迟与 SLA 响应时间排名完全一致）、"
        "极端异常值（磐石报价 240 万）。观察规范化与审计警告如何逐格暴露这些问题。"
    ),
    "decision_name": "2026Q4 云平台供应商",
    "criteria": [
        {"key": "throughput", "label": "峰值吞吐量", "unit": "千 req/s",
         "kind": "benefit"},
        {"key": "latency", "label": "P95 响应延迟", "unit": "ms",
         "kind": "cost"},
        {"key": "availability", "label": "服务可用性", "unit": "%",
         "kind": "benefit"},
        {"key": "price", "label": "年度总价", "unit": "万元",
         "kind": "cost"},
        {"key": "sla_minutes", "label": "SLA 故障响应时长", "unit": "分钟",
         "kind": "cost"},
        {"key": "maint_window", "label": "每月计划停机时长", "unit": "小时",
         "kind": "target", "target_low": 0.0, "target_high": 2.0},
    ],
    "alternatives": [
        {"key": "lingyun", "label": "凌云云"},
        {"key": "hanhai", "label": "瀚海云"},
        {"key": "xingchen", "label": "星辰云"},
        {"key": "panshi", "label": "磐石云"},
    ],
    # rows aligned to alternatives above, None = missing
    "values": [
        # throughput latency availability price  sla  maint
        [120.0,       45.0,  99.9,         72.0,  30.0, 1.5],
        [128.0,       72.0,  99.9,         58.0,  60.0, 0.8],
        [135.0,       52.0,  99.9,         65.0,  38.0, 4.5],
        [None,        80.0,  99.9,        240.0,  75.0, 2.2],
    ],
    "manual_weights": {
        # Deliberately weights BOTH latency and sla_minutes (duplicate pair):
        # the audit flags the resulting double counting.  Sum = 1.00.
        "throughput": 0.20,
        "latency": 0.20,
        "availability": 0.10,
        "price": 0.25,
        "sla_minutes": 0.10,
        "maint_window": 0.15,
    },
    "manual_source": (
        "技术选型委员会 2026-09-28 会议纪要第 3 条：成本与性能并重；"
        "可用性权重 0.10 为合规底线值。"
    ),
}

REVERSAL = {
    "key": "reversal",
    "name": "排名逆转最小示例（增删候选）",
    "description": (
        "四个方案 A/B/C/D、两个指标（性能=收益，成本=成本），权重各 0.5。"
        "完整集合下 TOPSIS 排序为 B>C>D>A；删掉 B 之后幸存者变为 C>A>D——"
        "A 与 D 的相对顺序被一个已离场的方案改变。等价地，向 {A,C,D} 加入 B "
        "也会让 A、D 互换。切换到固定锚点 + WSM 可看到分数不随候选集合变化。"
    ),
    "decision_name": "逆转演示",
    "criteria": [
        {"key": "performance", "label": "性能评分", "unit": "分",
         "kind": "benefit"},
        {"key": "cost", "label": "实施成本", "unit": "万元",
         "kind": "cost"},
    ],
    "alternatives": [
        {"key": "A", "label": "方案 A（高性能高成本）"},
        {"key": "B", "label": "方案 B（均衡偏优）"},
        {"key": "C", "label": "方案 C（均衡）"},
        {"key": "D", "label": "方案 D（低成本低性能）"},
    ],
    "values": [
        [10.0, 9.0],
        [7.0, 4.5],
        [6.0, 4.0],
        [1.0, 0.5],
    ],
    "manual_weights": {"performance": 0.5, "cost": 0.5},
    "manual_source": "教学示例：委员会对性能与成本无差异偏好，等权设定。",
}


def _seed_decision(db: Session, spec: dict) -> None:
    scenario = db.scalar(select(Scenario).where(Scenario.key == spec["key"]))
    if scenario is not None:
        return
    scenario = Scenario(key=spec["key"], name=spec["name"],
                        description=spec["description"])
    db.add(scenario)
    db.flush()
    decision = Decision(scenario_id=scenario.id, name=spec["decision_name"])
    db.add(decision)
    db.flush()

    crit_rows = {}
    for c in spec["criteria"]:
        row = Criterion(decision_id=decision.id, **c)
        db.add(row)
        crit_rows[c["key"]] = row
    alt_rows = {}
    for a in spec["alternatives"]:
        row = Alternative(decision_id=decision.id, **a)
        db.add(row)
        alt_rows[a["key"]] = row
    db.flush()

    for i, a in enumerate(spec["alternatives"]):
        for j, c in enumerate(spec["criteria"]):
            v = spec["values"][i][j]
            db.add(MetricValue(
                alternative_id=alt_rows[a["key"]].id,
                criterion_id=crit_rows[c["key"]].id,
                value=v,
                note="未提交压测数据" if v is None else "",
            ))
    db.add(WeightSet(
        decision_id=decision.id,
        name="委员会人工权重",
        method="manual",
        source=spec["manual_source"],
        weights=spec["manual_weights"],
    ))


def seed_all(db: Session) -> int:
    _seed_decision(db, VENDOR)
    _seed_decision(db, REVERSAL)
    db.commit()
    return 2
