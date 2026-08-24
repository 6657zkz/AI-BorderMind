"""出海参谋 · 后端入口。

运行期系统只做「查询、编排、监控与分析」，不处理数据导入（采集在 ingestion/ 离线完成）。

模块（已接入，按依赖顺序）：
  llm/  →  db/  →  operators/  →  agents/  →  graph/  →  session/ + project/  →  monitor/  →  evidence/  →  api/
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chuhai")


def create_app():
    import os
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from .api import api_router

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 可选：配置 MONITOR_PROJECT_ID 后，启动时开启持续监控调度（时间触发）
        if os.getenv("MONITOR_PROJECT_ID"):
            from .db import SessionLocal
            from .monitor import setup_monitor
            from .project import build_context

            with SessionLocal() as db:
                ctx = build_context(db, os.getenv("MONITOR_PROJECT_ID"))
            setup_monitor(ctx, interval_minutes=int(os.getenv("MONITOR_INTERVAL_MINUTES", "60")))
        yield
        from .monitor import shutdown_monitor

        shutdown_monitor()

    app = FastAPI(title="AI-BorderMind", version="0.2.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8088, reload=True)
