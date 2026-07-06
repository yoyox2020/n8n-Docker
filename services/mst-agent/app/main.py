import asyncio
import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Pastikan semua logger app tampil di stdout
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

from app.config import settings
from app.database import init_db
from app.nodes_registry import init_registry, get_catalog
from app.embedding_search import init_embeddings
from app.routers import memory, plan, tools, workflow_builder, runtime, approval

# --------------------------------------------------------------------------- #
# Rate limiter sederhana (tanpa library tambahan)                               #
# Batas: 30 request / menit per IP — cukup untuk penggunaan normal,            #
# tapi mencegah abuse / flooding dari satu sumber.                             #
# --------------------------------------------------------------------------- #
_RATE_LIMIT = 30        # max request per window
_RATE_WINDOW = 60       # detik
_rate_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    """True = boleh lanjut, False = terlalu banyak request."""
    now = time.monotonic()
    timestamps = _rate_store[ip]
    # Buang timestamp yang sudah di luar window
    _rate_store[ip] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_rate_store[ip]) >= _RATE_LIMIT:
        return False
    _rate_store[ip].append(now)
    return True


# --------------------------------------------------------------------------- #
# Lifespan                                                                      #
# --------------------------------------------------------------------------- #

logger = logging.getLogger(__name__)

_startup_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _startup_time
    t0 = time.monotonic()

    await init_db()
    await init_registry()

    catalog = get_catalog()
    logger.info("=" * 60)
    logger.info("MST Agent Service STARTUP")
    logger.info("  Node/tools loaded  : %d", len(catalog))
    logger.info("  Embedding mode     : loading dari DB / generate jika pertama kali")
    logger.info("=" * 60)

    # Probe LLM + warm-up Ollama jika perlu (background, tidak block startup)
    asyncio.create_task(_probe_and_warmup())

    # Embedding dijalankan di background agar startup tidak menunggu lama.
    asyncio.create_task(_init_embeddings_with_log(catalog))

    _startup_time = time.monotonic() - t0
    yield


async def _probe_and_warmup() -> None:
    from app.llm_router import probe_on_startup
    await probe_on_startup()


async def _init_embeddings_with_log(catalog: list) -> None:
    from app.embedding_search import _ready as emb_ready
    await init_embeddings(catalog)
    from app.embedding_search import _ready as emb_ready_after, _embeddings
    count = len(_embeddings)
    logger.info("=" * 60)
    if emb_ready_after:
        logger.info("✅ SIAP — %d node/tools ter-embed dan siap digunakan", count)
    else:
        logger.info("⚠️  Embedding belum siap (catalog terlalu kecil / n8n belum ready)")
    logger.info("=" * 60)


# --------------------------------------------------------------------------- #
# App                                                                           #
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="MST Agent Service",
    description="Planner, Memory, dan Tool Registry untuk MST Workflow",
    version="2.1.0",
    lifespan=lifespan,
    # Nonaktifkan docs di production untuk keamanan
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS — hanya izinkan origin dari n8n dan localhost
_ALLOWED_ORIGINS = [
    "http://localhost:5678",
    "http://127.0.0.1:5678",
    "http://n8n:5678",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Ambil IP client (support proxy)
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    client_ip = client_ip.split(",")[0].strip()

    if not _check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Terlalu banyak permintaan. Coba lagi dalam 1 menit."},
        )
    return await call_next(request)


# --------------------------------------------------------------------------- #
# Routers                                                                       #
# --------------------------------------------------------------------------- #

app.include_router(plan.router)
app.include_router(memory.router)
app.include_router(tools.router)
app.include_router(workflow_builder.router)
app.include_router(runtime.router)
app.include_router(approval.router)


@app.get("/health", tags=["health"])
async def health():
    from app.nodes_registry import get_catalog
    from app.embedding_search import _ready as emb_ready, _embeddings
    catalog = get_catalog()
    return {
        "status": "ok",
        "service": "mst-agent-service",
        "version": "2.1.0",
        "nodes_loaded": len(catalog),
        "embedding_ready": emb_ready,
        "embedding_count": len(_embeddings),
    }


@app.get("/status", tags=["health"])
async def status():
    """Informasi lengkap tentang kondisi service — nodes, embedding, LLM backend, uptime."""
    from app.nodes_registry import get_catalog
    from app.embedding_search import _ready as emb_ready, _embeddings
    from app.llm_router import get_router_info

    catalog = get_catalog()
    emb_count = len(_embeddings)
    node_count = len(catalog)

    triggers = sum(1 for n in catalog if n["node_type"].lower().endswith("trigger"))
    actions = node_count - triggers

    return {
        "status": "ready" if emb_ready else "loading",
        "service": "mst-agent-service",
        "version": "2.1.0",
        "nodes": {
            "total": node_count,
            "triggers": triggers,
            "actions": actions,
        },
        "embedding": {
            "ready": emb_ready,
            "vectors_in_memory": emb_count,
            "coverage": f"{round(emb_count / node_count * 100)}%" if node_count else "0%",
        },
        "llm": get_router_info(),
        "message": (
            f"✅ Siap — {emb_count} dari {node_count} node/tools ter-embed dan siap digunakan"
            if emb_ready
            else "⏳ Embedding masih loading, fallback ke text search untuk sementara"
        ),
    }


@app.get("/llm/status", tags=["health"])
async def llm_status():
    """Cek status LLM router — backend aktif, Mistika tersedia, probe loop."""
    from app.llm_router import get_router_info
    return get_router_info()


@app.get("/llm/probe", tags=["health"])
async def force_llm_probe():
    """Force re-probe Mistika-AI sekarang. Buka di browser untuk cek koneksi."""
    import app.llm_router as router
    router._LAST_PROBE = 0.0
    router._PRIMARY_HEALTHY = None
    cfg = await router._get_active_config()
    return {
        "probed": True,
        "active_backend": cfg.name,
        "mistika_available": router._PRIMARY_HEALTHY,
        "url": cfg.chat_url,
    }


@app.get("/llm/test", tags=["health"])
async def test_llm_call():
    """Test kirim prompt ke LLM aktif. Buka di browser untuk verifikasi."""
    from app.llm_router import call_llm
    import time as _time
    t0 = _time.monotonic()
    try:
        reply = await call_llm([{"role": "user", "content": "Balas hanya dengan kata: OK"}], max_tokens=10)
        elapsed = round(_time.monotonic() - t0, 2)
        return {"success": True, "reply": reply.strip(), "elapsed_seconds": elapsed}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
