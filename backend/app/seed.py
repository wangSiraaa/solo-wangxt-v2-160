"""演示数据（技术选型委员会场景）。内置教学性边界情况：
- perf_qps：D 方案 20000 为极端异常值（MAD 修正 z）
- sec_score：B 缺失（不能自动得满分）
- sso_support：所有候选=1，常量列（不能自动得满分，应被剔除/中性化）
- license_cost 与 tco_year 高度相关 → 疑似重复指标
- 人工权重合计=110（≠100），用于展示"原始权重→有效权重"的归一与核对
"""
from __future__ import annotations

from .models import CandidateIn, CriterionIn, ValueIn, VersionIn

CRITERIA = [
    CriterionIn(code="perf_qps", name="峰值吞吐 QPS", unit="req/s", ctype="benefit",
                weight=20, source="架构组人工设定(评审会 2026-09)"),
    CriterionIn(code="avail_pct", name="可用性", unit="%", ctype="benefit",
                weight=15, source="SRE 组人工设定"),
    CriterionIn(code="sec_score", name="安全评分", unit="分(0-100)", ctype="benefit",
                weight=15, source="安全委员会人工设定"),
    CriterionIn(code="eco_index", name="生态成熟度", unit="指数", ctype="benefit",
                weight=15, source="架构组人工设定"),
    CriterionIn(code="tco_year", name="年度总拥有成本", unit="万元/年", ctype="cost",
                weight=20, source="财务模型 v3"),
    CriterionIn(code="license_cost", name="年许可费用", unit="万元/年", ctype="cost",
                weight=10, source="财务模型 v3（与 TCO 口径重叠，待委员会确认）"),
    CriterionIn(code="delivery_wk", name="交付周期", unit="周", ctype="cost",
                weight=10, source="PMO 人工设定"),
    CriterionIn(code="rto_h", name="目标恢复时间", unit="小时", ctype="target",
                weight=5, source="容灾规范：最佳区间 [2,4]h", target_low=2, target_high=4),
    CriterionIn(code="sso_support", name="SSO 支持", unit="0/1", ctype="benefit",
                weight=0, source="占位指标：本轮所有方案均满足，权重 0"),
]

CANDIDATES = [
    CandidateIn(code="A", name="方案A 单体+商业库", description="成熟商业中间件，团队熟悉"),
    CandidateIn(code="B", name="方案B 云原生托管", description="弹性好、生态强，费用偏高"),
    CandidateIn(code="C", name="方案C 开源自研", description="成本最低，安全与成熟度弱"),
    CandidateIn(code="D", name="方案D 高性能混合", description="性能激进，交付慢"),
]

# (candidate_code, criterion_code, value); None=缺失
VALUES = [
    ("A", "perf_qps", 1200), ("A", "avail_pct", 99.5), ("A", "sec_score", 88),
    ("A", "eco_index", 85), ("A", "tco_year", 42), ("A", "license_cost", 8),
    ("A", "delivery_wk", 8), ("A", "rto_h", 4), ("A", "sso_support", 1),

    ("B", "perf_qps", 3500), ("B", "avail_pct", 99.95), ("B", "sec_score", None),
    ("B", "eco_index", 92), ("B", "tco_year", 78), ("B", "license_cost", 30),
    ("B", "delivery_wk", 12), ("B", "rto_h", 3), ("B", "sso_support", 1),

    ("C", "perf_qps", 800), ("C", "avail_pct", 99.0), ("C", "sec_score", 60),
    ("C", "eco_index", 55), ("C", "tco_year", 20), ("C", "license_cost", 0),
    ("C", "delivery_wk", 6), ("C", "rto_h", 8), ("C", "sso_support", 1),

    ("D", "perf_qps", 20000), ("D", "avail_pct", 99.9), ("D", "sec_score", 75),
    ("D", "eco_index", 70), ("D", "tco_year", 60), ("D", "license_cost", 22),
    ("D", "delivery_wk", 21), ("D", "rto_h", 1), ("D", "sso_support", 1),
]

VERSIONS = [
    VersionIn(label="v1 基线（人工权重）", note="默认：中位数插补、异常仅标记、常量剔除、人工权重归一"),
    VersionIn(label="v2 剔除疑似重复指标", note="去掉 license_cost（与 tco_year 信息重复），观察排名逆转",
              drop_criterion_ids=[]),  # id 在播种时按 code 注入
    VersionIn(label="v3 裁剪极端异常值", note="MAD 裁剪 D 的 20000 QPS", clip_outliers=True),
    VersionIn(label="v4 熵权（纯数据推得）", note="人工权重完全不参与，对比话语权差异", weight_basis="entropy"),
    VersionIn(label="v5 人工+熵权 50/50", note="组合口径", weight_basis="combined", combined_alpha=0.5),
]


def seed(repo) -> dict:
    crit_id, cand_id = {}, {}
    for c in CRITERIA:
        crit_id[c.code] = repo.add_criterion(c)
    for c in CANDIDATES:
        cand_id[c.code] = repo.add_candidate(c)
    for cc, kc, v in VALUES:
        repo.set_value(cand_id[cc], crit_id[kc], v)
    version_ids = []
    for v in VERSIONS:
        if v.label.startswith("v2"):
            v.drop_criterion_ids = [crit_id["license_cost"]]
        version_ids.append(repo.create_version(v))
    return {"criteria": crit_id, "candidates": cand_id, "versions": version_ids}
