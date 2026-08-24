"""数据库连接：engine + SessionLocal + FastAPI 依赖注入。

连接串来自 backend/.env 的 DATABASE_URL（PostgreSQL + psycopg 驱动）。
engine 懒连接：import 本模块不建立连接，首次真正执行 SQL 才连。
"""

from __future__ import annotations

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/chuhai",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级会话，用后即关。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
