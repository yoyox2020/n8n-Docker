from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import memory, plan, tools, workflow_builder, runtime, approval


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist
    await init_db()
    yield
    # Shutdown: nothing to clean up


app = FastAPI(
    title="MST Agent Service",
    description="Planner, Memory, and Tool Registry for MST Workflow platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plan.router)
app.include_router(memory.router)
app.include_router(tools.router)
app.include_router(workflow_builder.router)
app.include_router(runtime.router)
app.include_router(approval.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "service": "mst-agent-service", "version": "2.0.0"}
