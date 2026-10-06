"""
仓储层：优先 PostgreSQL（psycopg3）；连接失败时降级到同构内存仓储。
降级会在 /health 显式标注，避免把演示数据误当成已持久化。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

from .models import CandidateIn, CriterionIn, VersionIn

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "db", "schema.sql")


class PostgresRepo:
    def __init__(self, dsn: str):
        import psycopg
        self._psycopg = psycopg
        self.dsn = dsn
        with psycopg.connect(dsn, autocommit=True) as conn:
            with open(SCHEMA_PATH) as f:
                conn.execute(f.read())
        self.backend = "postgresql"

    # ---- criteria ----
    def list_criteria(self):
        with self._psycopg.connect(self.dsn) as conn:
            return [self._crit(r) for r in conn.execute(
                "SELECT id,code,name,unit,ctype,weight,source,target_low,target_high FROM criteria ORDER BY id")]

    def add_criterion(self, c: CriterionIn):
        with self._psycopg.connect(self.dsn) as conn:
            r = conn.execute(
                "INSERT INTO criteria(code,name,unit,ctype,weight,source,target_low,target_high)"
                " VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                (c.code, c.name, c.unit, c.ctype.value, c.weight, c.source, c.target_low, c.target_high)).fetchone()
            return r[0]

    def delete_criterion(self, cid: int):
        with self._psycopg.connect(self.dsn) as conn:
            conn.execute("DELETE FROM criteria WHERE id=%s", [cid])

    # ---- candidates ----
    def list_candidates(self):
        with self._psycopg.connect(self.dsn) as conn:
            return [self._cand(r) for r in conn.execute(
                "SELECT id,code,name,description FROM candidates ORDER BY id")]

    def add_candidate(self, c: CandidateIn):
        with self._psycopg.connect(self.dsn) as conn:
            r = conn.execute(
                "INSERT INTO candidates(code,name,description) VALUES(%s,%s,%s) RETURNING id",
                (c.code, c.name, c.description)).fetchone()
            return r[0]

    def delete_candidate(self, cid: int):
        with self._psycopg.connect(self.dsn) as conn:
            conn.execute("DELETE FROM candidates WHERE id=%s", [cid])

    # ---- measurements ----
    def matrix(self):
        with self._psycopg.connect(self.dsn) as conn:
            return {(r[0], r[1]): r[2] for r in conn.execute(
                "SELECT candidate_id,criterion_id,value FROM measurements")}

    def set_value(self, candidate_id: int, criterion_id: int, value: Optional[float]):
        with self._psycopg.connect(self.dsn) as conn:
            conn.execute(
                "INSERT INTO measurements(candidate_id,criterion_id,value) VALUES(%s,%s,%s)"
                " ON CONFLICT (candidate_id,criterion_id) DO UPDATE SET value=EXCLUDED.value",
                (candidate_id, criterion_id, value))

    # ---- versions ----
    def list_versions(self):
        with self._psycopg.connect(self.dsn) as conn:
            rows = conn.execute(
                "SELECT id,label,note,options,created_at FROM decision_versions ORDER BY id").fetchall()
        out = []
        for vid, label, note, opts, created in rows:
            d = {"id": vid, "label": label, "note": note, "created_at": created.isoformat(), **opts}
            out.append(d)
        return out

    def create_version(self, v: VersionIn) -> int:
        with self._psycopg.connect(self.dsn) as conn:
            opts = v.model_dump()
            opts.pop("label", None); opts.pop("note", None)
            vid = conn.execute(
                "INSERT INTO decision_versions(label,note,options) VALUES(%s,%s,%s) RETURNING id",
                (v.label, v.note, json.dumps(opts))).fetchone()[0]
            vals = conn.execute("SELECT candidate_id,criterion_id,value FROM measurements").fetchall()
            conn.executemany(
                "INSERT INTO version_snapshots(version_id,candidate_id,criterion_id,value)"
                " VALUES(%s,%s,%s,%s)",
                [(vid, a, b, x) for a, b, x in vals])
            return vid

    @staticmethod
    def _crit(r):
        return {"id": r[0], "code": r[1], "name": r[2], "unit": r[3], "ctype": r[4],
                "weight": r[5], "source": r[6], "target_low": r[7], "target_high": r[8]}

    @staticmethod
    def _cand(r):
        return {"id": r[0], "code": r[1], "name": r[2], "description": r[3]}


class MemoryRepo:
    """与 PostgresRepo 同构的内存实现——仅用于无数据库的开发/测试/演示。"""
    backend = "memory (未持久化)"

    def __init__(self):
        self.criteria: list[dict] = []
        self.candidates: list[dict] = []
        self.values: dict[tuple[int, int], Optional[float]] = {}
        self.versions: list[dict] = []
        self._cid = self._krid = self._vid = 0

    def list_criteria(self):
        return list(self.criteria)

    def add_criterion(self, c: CriterionIn):
        self._cid += 1
        self.criteria.append({"id": self._cid, **c.model_dump()})
        self.criteria[-1]["ctype"] = c.ctype.value
        return self._cid

    def delete_criterion(self, cid):
        self.criteria = [c for c in self.criteria if c["id"] != cid]
        self.values = {k: v for k, v in self.values.items() if k[1] != cid}

    def list_candidates(self):
        return list(self.candidates)

    def add_candidate(self, c: CandidateIn):
        self._krid += 1
        self.candidates.append({"id": self._krid, **c.model_dump()})
        return self._krid

    def delete_candidate(self, cid):
        self.candidates = [c for c in self.candidates if c["id"] != cid]
        self.values = {k: v for k, v in self.values.items() if k[0] != cid}

    def matrix(self):
        return dict(self.values)

    def set_value(self, candidate_id, criterion_id, value):
        self.values[(candidate_id, criterion_id)] = value

    def list_versions(self):
        return [dict(v) for v in self.versions]

    def create_version(self, v: VersionIn):
        self._vid += 1
        opts = v.model_dump()
        label, note = opts.pop("label"), opts.pop("note")
        self.versions.append({"id": self._vid, "label": label, "note": note,
                              "created_at": datetime.now(timezone.utc).isoformat(), **opts})
        return self._vid


def get_repo():
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        try:
            return PostgresRepo(dsn)
        except Exception as exc:  # 显式降级，不静默
            print(f"[repo] PostgreSQL 不可用，降级内存仓储: {exc}")
    repo = MemoryRepo()
    print("[repo] 未配置 DATABASE_URL，使用内存仓储（重启数据丢失）")
    return repo
