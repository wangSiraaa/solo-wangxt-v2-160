"""FastAPI entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import SessionLocal, init_db
from .routers.api import router
from .seed import seed_all

app = FastAPI(
    title="MCDA 技术选型可审计评分服务",
    description=(
        "加权和模型 + TOPSIS，显式区分收益/成本/目标区间型指标；"
        "规范化、权重来源、排名逆转全程可核对。"
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.on_event("startup")
def _startup() -> None:
    init_db()
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
