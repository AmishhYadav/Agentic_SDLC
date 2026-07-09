"""FastAPI app entrypoint.

Opens AsyncSqliteSaver exactly once in the app's lifespan (Pattern 1) — never
per-request — compiles the graph once with that checkpointer, and stores the
compiled graph on app.state.graph. D-04 (locked): file-backed SQLite
checkpointer only; a non-durable, in-process-only checkpointer must never
appear here, since that would silently break ORCH-02 restart survival.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.db import run_metadata
from app.graph.build import build_graph
from app.routers.runs import router as runs_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_path = os.environ.get("CHECKPOINT_DB_PATH", "./checkpoints.sqlite")
    run_metadata.init_db()
    async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
        await checkpointer.setup()
        graph = build_graph().compile(checkpointer=checkpointer)
        app.state.graph = graph
        yield
    # connection closed automatically on app shutdown when the `async with` exits


app = FastAPI(lifespan=lifespan)
app.include_router(runs_router)
