"""
LLM Router — auto-routing antara Mistika-AI (primary) dan Ollama (fallback).

Perilaku:
  - Mistika-AI STICKY: sekali terhubung, tidak pernah switch kecuali request gagal.
  - Ketika Mistika-AI terputus → fallback ke Ollama, probe ulang setiap 5 menit.
  - Ketika Mistika-AI kembali online → pindah balik otomatis.
  - OLLAMA_ENABLED=false → nonaktifkan Ollama (untuk production, wajib Mistika-AI).
"""

import asyncio
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# State                                                                         #
# --------------------------------------------------------------------------- #

_PRIMARY_HEALTHY: bool | None = None   # None = belum pernah dicek
_LAST_PROBE: float = 0.0
_LAST_SWITCH_AT: float = 0.0           # kapan terakhir kali backend berubah
_CURRENT_BACKEND: str = "unknown"
_PROBE_INTERVAL = 300.0                # re-probe setiap 5 menit HANYA saat Mistika down
_PROBE_TIMEOUT = 5.0
_background_probe_task: asyncio.Task | None = None


# --------------------------------------------------------------------------- #
# Config helper                                                                 #
# --------------------------------------------------------------------------- #

class LLMConfig:
    def __init__(self, base_url: str, api_key: str, model: str, chat_path: str, auth_header: str, name: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.chat_path = chat_path
        self.auth_header = auth_header
        self.name = name

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}{self.chat_path}"

    @property
    def auth_value(self) -> str:
        if self.auth_header.lower() == "authorization":
            return f"Bearer {self.api_key}"
        return self.api_key


def _primary_config() -> LLMConfig:
    return LLMConfig(
        base_url=settings.mistika_base_url,
        api_key=settings.mistika_api_key,
        model=settings.mistika_model,
        chat_path=settings.mistika_chat_path,
        auth_header=settings.mistika_auth_header,
        name="Mistika-AI",
    )


def _fallback_config() -> LLMConfig:
    return LLMConfig(
        base_url=settings.ollama_base_url,
        api_key=settings.ollama_api_key,
        model=settings.ollama_model,
        chat_path=settings.ollama_chat_path,
        auth_header=settings.ollama_auth_header,
        name="Ollama",
    )


def _ollama_enabled() -> bool:
    return getattr(settings, "ollama_enabled", True)


# --------------------------------------------------------------------------- #
# Health probe                                                                  #
# --------------------------------------------------------------------------- #

async def _probe_primary() -> bool:
    """Coba koneksi ke Mistika-AI. Return True jika bisa dijangkau."""
    cfg = _primary_config()
    if not cfg.api_key:
        return False
    try:
        async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT) as client:
            resp = await client.post(
                cfg.chat_url,
                headers={cfg.auth_header: cfg.auth_value, "Content-Type": "application/json"},
                json={"model": cfg.model or "default", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1},
            )
            reachable = resp.status_code < 500
            if reachable:
                logger.info("[LLMRouter] ✅ Mistika-AI tersedia (HTTP %d)", resp.status_code)
            else:
                logger.warning("[LLMRouter] ⚠ Mistika-AI server error %d", resp.status_code)
            return reachable
    except Exception as exc:
        logger.debug("[LLMRouter] Mistika-AI tidak terjangkau: %s", exc)
        return False


def _set_backend(healthy: bool) -> None:
    """Update state backend dan log jika ada perubahan."""
    global _PRIMARY_HEALTHY, _LAST_PROBE, _CURRENT_BACKEND, _LAST_SWITCH_AT
    prev = _PRIMARY_HEALTHY
    _PRIMARY_HEALTHY = healthy
    _LAST_PROBE = time.monotonic()
    new_name = "Mistika-AI" if healthy else "Ollama (fallback)"
    if prev != healthy:
        _LAST_SWITCH_AT = time.monotonic()
        if prev is None:
            logger.info("[LLMRouter] 🚀 Backend awal: %s", new_name)
        elif healthy:
            logger.info("[LLMRouter] 🔁 SWITCH → Mistika-AI (kembali online)")
        else:
            logger.warning("[LLMRouter] 🔁 SWITCH → Ollama fallback (Mistika-AI terputus)")
    _CURRENT_BACKEND = new_name


# --------------------------------------------------------------------------- #
# Background probe loop (hanya aktif saat Mistika-AI down)                     #
# --------------------------------------------------------------------------- #

async def _probe_loop() -> None:
    """Loop background yang probe Mistika-AI setiap 5 menit saat sedang down."""
    while True:
        await asyncio.sleep(_PROBE_INTERVAL)
        if _PRIMARY_HEALTHY:
            # Sudah healthy — tidak perlu probe lagi, hentikan loop
            break
        logger.info("[LLMRouter] Background probe Mistika-AI...")
        healthy = await _probe_primary()
        _set_backend(healthy)
        if healthy:
            # Mistika kembali online — warm-up tidak diperlukan lagi
            break


def _ensure_probe_loop() -> None:
    """Pastikan background probe berjalan saat Mistika-AI sedang down."""
    global _background_probe_task
    if _PRIMARY_HEALTHY:
        return  # Mistika sehat, tidak perlu loop
    if _background_probe_task is None or _background_probe_task.done():
        _background_probe_task = asyncio.create_task(_probe_loop())
        logger.info("[LLMRouter] Background probe loop dimulai (interval %ds)", int(_PROBE_INTERVAL))


# --------------------------------------------------------------------------- #
# Warm-up Ollama                                                                #
# --------------------------------------------------------------------------- #

async def warmup_ollama() -> None:
    """Load model Ollama ke memori dengan keep_alive=-1 (tidak pernah expire)."""
    if not _ollama_enabled():
        return
    cfg = _fallback_config()
    # Derive native Ollama host dari base URL (/v1 → hapus suffix)
    host = cfg.base_url
    if host.endswith("/v1"):
        host = host[:-3]
    url = f"{host}/api/generate"
    try:
        logger.info("[LLMRouter] Warming up Ollama '%s'...", cfg.model)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json={"model": cfg.model, "prompt": "", "keep_alive": -1})
            if resp.status_code < 300:
                logger.info("[LLMRouter] ✅ Ollama '%s' siap di memori (tidak akan expire)", cfg.model)
            else:
                logger.warning("[LLMRouter] Ollama warm-up status %d", resp.status_code)
    except Exception as exc:
        logger.warning("[LLMRouter] Ollama warm-up gagal: %s", exc)


# --------------------------------------------------------------------------- #
# Active config                                                                 #
# --------------------------------------------------------------------------- #

async def _get_active_config() -> LLMConfig:
    """Kembalikan config LLM aktif. Probe hanya jika belum pernah dicek."""
    if _PRIMARY_HEALTHY is None:
        # Pertama kali — lakukan probe
        healthy = await _probe_primary()
        _set_backend(healthy)
        if not healthy:
            if not _ollama_enabled():
                raise RuntimeError("Mistika-AI tidak tersedia dan Ollama dinonaktifkan (OLLAMA_ENABLED=false)")
            _ensure_probe_loop()

    return _primary_config() if _PRIMARY_HEALTHY else _fallback_config()


# --------------------------------------------------------------------------- #
# Main LLM call                                                                 #
# --------------------------------------------------------------------------- #

async def call_llm(messages: list[dict], max_tokens: int = 800) -> str:
    """
    Panggil LLM dengan auto-routing dan auto-fallback.

    - Mistika-AI sticky: kalau sudah online, selalu pakai Mistika-AI.
    - Jika Mistika-AI gagal saat request: switch ke Ollama, mulai probe loop.
    - OLLAMA_ENABLED=false: tidak ada fallback, raise jika Mistika gagal.
    """
    from fastapi import HTTPException

    cfg = await _get_active_config()
    logger.info("[LLMRouter] ▶ %s", cfg.name)

    async def _do_call(c: LLMConfig) -> str:
        headers = {c.auth_header: c.auth_value, "Content-Type": "application/json"}
        payload: dict = {
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if c.model:
            payload["model"] = c.model
        async with httpx.AsyncClient(timeout=240) as client:
            resp = await client.post(c.chat_url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"LLM {c.name} error {resp.status_code}: {resp.text[:200]}")
            return resp.json()["choices"][0]["message"]["content"]

    try:
        result = await _do_call(cfg)
        return result
    except Exception as primary_exc:
        if cfg.name == "Mistika-AI":
            logger.warning("[LLMRouter] Mistika-AI gagal: %s", primary_exc)
            _set_backend(False)        # tandai Mistika down
            _ensure_probe_loop()       # mulai probe loop background

            if not _ollama_enabled():
                raise HTTPException(status_code=502, detail=f"Mistika-AI gagal dan Ollama dinonaktifkan: {primary_exc}")

            logger.info("[LLMRouter] Fallback ke Ollama...")
            try:
                result = await _do_call(_fallback_config())
                logger.info("[LLMRouter] ✅ Ollama fallback berhasil")
                return result
            except Exception as fb_exc:
                raise HTTPException(status_code=502, detail=f"Semua LLM gagal. Mistika: {primary_exc}. Ollama: {fb_exc}")
        raise


# --------------------------------------------------------------------------- #
# Startup                                                                       #
# --------------------------------------------------------------------------- #

async def probe_on_startup() -> None:
    """Probe Mistika-AI saat startup dan siapkan Ollama jika diperlukan."""
    healthy = await _probe_primary()
    _set_backend(healthy)

    if healthy:
        logger.info("[LLMRouter] 🚀 Primary: Mistika-AI aktif")
    else:
        if not _ollama_enabled():
            logger.warning("[LLMRouter] ⚠ Mistika-AI down dan OLLAMA_ENABLED=false — service tidak bisa process request LLM")
            _ensure_probe_loop()
            return
        logger.info("[LLMRouter] 🔄 Mistika-AI tidak tersedia — Ollama aktif sebagai fallback")
        await warmup_ollama()
        _ensure_probe_loop()


# --------------------------------------------------------------------------- #
# Info untuk endpoint /status                                                   #
# --------------------------------------------------------------------------- #

def get_router_info() -> dict:
    now = time.monotonic()
    next_probe = max(0, _PROBE_INTERVAL - (now - _LAST_PROBE)) if _LAST_PROBE and not _PRIMARY_HEALTHY else None
    return {
        "active_backend": _CURRENT_BACKEND,
        "mistika_available": _PRIMARY_HEALTHY,
        "ollama_enabled": _ollama_enabled(),
        "next_probe_seconds": round(next_probe) if next_probe is not None else "N/A (Mistika aktif)",
        "probe_loop_running": _background_probe_task is not None and not (_background_probe_task.done() if _background_probe_task else True),
    }
