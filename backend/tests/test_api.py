"""End-to-end API tests on an isolated SQLite database."""
import os
import tempfile

import pytest

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_all  # noqa: E402


@pytest.fixture(scope="module")
def client():
    init_db()
    db = SessionLocal()
    seed_all(db)
    db.close()
    with TestClient(app) as c:
        yield c


def test_scenarios_and_decision_payload(client):
    scenarios = client.get("/api/scenarios").json()
    assert {s["key"] for s in scenarios} == {"vendor", "reversal"}
    d = client.get("/api/decisions/1").json()
    # Missing raw cell is JSON null, not NaN text.
    assert d["raw_values"][3][0] is None
    assert {c["key"] for c in d["criteria"]} >= {
        "throughput", "latency", "availability",
        "price", "sla_minutes", "maint_window",
    }
    assert len(d["weight_sets"]) == 1
    assert d["weight_sets"][0]["source"]  # provenance present


def test_analyze_reversal_scenario(client):
    r = client.post("/api/decisions/2/analyze",
                    json={"weight_set_id": 2}).json()
    assert r["weight_sum"] == pytest.approx(1.0)
    reversals = r["rank_reversal"]["dynamic_anchors"]["reversals"]
    assert any(x["removed"] == "B" and x["model"] == "topsis"
               for x in reversals)
    anchored = r["rank_reversal"]["fixed_anchors"]["reversals"]
    assert not [x for x in anchored if x["model"] == "wsm"]


def test_analyze_vendor_audits(client):
    r = client.post("/api/decisions/1/analyze",
                    json={"weight_set_id": 1}).json()
    keys = {(d["a"], d["b"]) for d in r["audits"]["duplicates"]}
    assert ("latency", "sla_minutes") in keys
    assert any(o["criterion"] == "price" for o in r["audits"]["outliers"])
    # constant column -> neutral 0.5 for everyone
    assert all(
        abs(row[2] - 0.5) < 1e-9
        for row in r["models"]["normalization"]["matrix"]
    )
    # missing cell imputed with neutral default
    assert r["models"]["normalization"]["matrix"][3][0] == 0.5


def test_manual_weight_validation_over_http(client):
    bad = client.post(
        "/api/decisions/1/weight-sets",
        json={"name": "x", "method": "manual",
              "weights": {"throughput": 1.0}, "source": "why"},
    )
    assert bad.status_code == 422
    no_source = client.post(
        "/api/decisions/1/weight-sets",
        json={"name": "x", "method": "manual",
              "weights": {c: 1 / 6 for c in [
                  "throughput", "latency", "availability",
                  "price", "sla_minutes", "maint_window"]},
              "source": ""},
    )
    assert no_source.status_code == 422


def test_derived_weights_are_allowed_and_labeled(client):
    r = client.post("/api/decisions/1/analyze",
                    json={"use_derived": "entropy"}).json()
    assert r["weight_provenance"]["origin"] == "derived"
    assert r["weight_provenance"]["method"] == "entropy"
    # Constant availability column carries zero derived weight.
    idx = [c["key"] for c in r["criteria"]].index("availability")
    assert r["weight_vector"][idx] == 0.0


def test_freeze_version_then_read_snapshot(client):
    resp = client.post(
        "/api/decisions/1/versions",
        json={"label": "会议冻结", "method": "wsm",
              "weight_set_id": 1, "comment": "备注"},
    )
    assert resp.status_code == 200
    vid = resp.json()["id"]
    snap = client.get(f"/api/versions/{vid}").json()
    assert snap["snapshot"]["comment"] == "备注"
    assert len(snap["snapshot"]["ranking"]) == 4
    assert snap["snapshot"]["raw_values"][3][0] is None
