"""API 端到端测试（内存仓储）：验证路由、响应结构与关键场景。"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    h = client.get("/health").json()
    assert h["status"] == "ok"
    assert "backend" in h


def test_seed_data_present():
    assert len(client.get("/criteria").json()) == 9
    assert len(client.get("/candidates").json()) == 4
    versions = client.get("/versions").json()
    assert len(versions) == 5
    assert versions[3]["weight_basis"] == "entropy"


def test_analyze_structure_and_invariants():
    r = client.post("/analyze", json={}).json()
    assert [s["name"].startswith(f"{i}.") for i, s in enumerate(r["steps"], 1)]
    # WSM 与 TOPSIS 都在 [0,1]
    for row in r["wsm_rank"]:
        assert 0 <= row["wsm_score"] <= 1
    for row in r["topsis_rank"]:
        assert 0 <= row["closeness_ideal"] <= 1
    # 权重有效份额合计 = 1
    shares = [a["effective_share"] for a in r["weight_audit"] if not a["excluded"]]
    # 响应中份额四舍五入到 6 位，合计误差为舍入量级
    assert sum(shares) == pytest.approx(1.0, abs=1e-5)
    # 常量列 sso_support 被剔除；缺失值与异常值都有告警
    excl = {a["criterion_code"] for a in r["weight_audit"] if a["excluded"]}
    assert "sso_support" in excl
    assert any("B/sec_score" in w for w in r["warnings"])
    assert any("20000" in w for w in r["warnings"])
    # 重复指标被检出
    pairs = [(d["criterion_a"], d["criterion_b"]) for d in r["duplicate_criteria"]]
    assert ("tco_year", "license_cost") in pairs


def test_weight_basis_changes_ranking():
    manual = client.post("/analyze", json={"weight_basis": "manual"}).json()
    entropy = client.post("/analyze", json={"weight_basis": "entropy"}).json()
    m = [(r["candidate_code"], round(r["wsm_score"], 4)) for r in manual["wsm_rank"]]
    e = [(r["candidate_code"], round(r["wsm_score"], 4)) for r in entropy["wsm_rank"]]
    assert m != e
    # 熵权口径下 audit 中人工权重列与熵权列都存在且不同口径被标注
    assert all(a["basis"] == "entropy" for a in entropy["weight_audit"] if not a["excluded"])


def test_version_report_reproducible():
    v3 = client.get("/versions/3/report").json()
    # v3 开启裁剪
    assert v3["version"]["clip_outliers"] is True
    notes = " ".join(v3["steps"][1]["notes"])
    assert "perf_qps" in notes and "裁剪" in notes


def test_drop_candidate_reversal_endpoint():
    crits = {c["code"]: c["id"] for c in client.get("/criteria").json()}
    cands = {c["code"]: c["id"] for c in client.get("/candidates").json()}
    r = client.post("/reversal", json={
        "drop_criterion_ids": [crits["license_cost"]],
        "drop_candidate_ids": [cands["D"]],
    }).json()
    by_code = {x["candidate_code"]: x for x in r["rows"]}
    assert by_code["B"]["rank_full"] == 3 and by_code["B"]["rank_reduced"] == 1
    assert by_code["B"]["shift"] == 2
    assert "参照系" in r["note"]
    assert r["drivers"][0]["criterion"] == "perf_qps"


def test_missing_worst_strategy():
    r = client.post("/analyze", json={"missing_strategy": "worst"}).json()
    # B/sec_score 插补为 0，步骤3规范化仍为 0
    rows = r["steps"][0]["rows"]
    cols = r["steps"][2]["columns"]
    bi, sj = rows.index("B"), cols.index("sec_score")
    assert r["steps"][2]["matrix"][bi][sj] == 0.0


def test_add_candidate_value_roundtrip():
    cid = client.post("/candidates", json={"code": "E", "name": "方案E"}).json()["id"]
    krid = client.get("/criteria").json()[0]["id"]
    resp = client.post("/values", json={"candidate_id": cid, "criterion_id": krid, "value": 999})
    assert resp.status_code == 201
    vals = client.get("/values").json()
    assert any(v["candidate_id"] == cid and v["value"] == 999 for v in vals)
