"""
Node Registry — sumber kebenaran tentang node apa saja yang ada di n8n.

Saat service pertama kali hidup, kita login ke n8n dan ambil daftar semua
node yang terinstall (termasuk community node).  Kalau n8n belum siap atau
credentials salah, kita jatuh ke static catalog sebagai cadangan.

Kenapa perlu ini?
  Static catalog hanya punya ~73 node.  n8n asli punya 400+ node (ServiceNow,
  Zendesk, Jira, dst).  Dengan registry dinamis, LLM tahu semua node yang
  BENAR-BENAR terinstall — tanpa perlu update manual setiap kali node baru
  ditambahkan.
"""

import logging
from typing import Optional

import httpx

from app.config import settings
from app.nodes_catalog import NODES_CATALOG as _STATIC

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# State                                                                         #
# --------------------------------------------------------------------------- #

_registry: list[dict] = []


# --------------------------------------------------------------------------- #
# Internal helpers                                                              #
# --------------------------------------------------------------------------- #

async def _login() -> Optional[str]:
    """Login ke n8n sebagai admin, kembalikan cookie session-nya."""
    if not settings.n8n_admin_email or not settings.n8n_admin_password:
        logger.warning("[NodeRegistry] n8n admin credentials tidak dikonfigurasi — skip fetch")
        return None

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.post(
                f"{settings.n8n_base_url}/rest/login",
                json={
                    "emailOrLdapLoginId": settings.n8n_admin_email,
                    "password": settings.n8n_admin_password,
                },
            )
            if resp.status_code == 200:
                cookie_str = "; ".join(f"{k}={v}" for k, v in resp.cookies.items())
                logger.debug("[NodeRegistry] Login n8n berhasil")
                return cookie_str or None
            else:
                logger.warning(
                    "[NodeRegistry] Login n8n gagal: status=%s body=%s",
                    resp.status_code,
                    resp.text[:200],
                )
    except Exception as exc:
        logger.warning("[NodeRegistry] Login n8n error: %s", exc)

    return None


def _enrich_description(base_desc: str, properties: list[dict]) -> str:
    """
    Bangun deskripsi yang lebih kaya dengan mengekstrak resources dan operations
    dari properties node.

    Contoh hasil:
      "Consume Slack API. Resources: Channel, Message, File, Reaction, User.
       Operations: Archive, Create, Delete, Get, Invite, Post, Update, Upload."

    Deskripsi yang lebih panjang ini membuat embedding search jauh lebih akurat
    karena model bisa mencocokkan berdasarkan operasi spesifik, bukan hanya nama.
    """
    resources: list[str] = []
    operations: list[str] = []

    for prop in properties:
        prop_name = prop.get("name", "")
        if prop_name not in ("resource", "operation"):
            continue

        options = prop.get("options", [])
        names = [
            opt["name"]
            for opt in options
            if isinstance(opt, dict) and opt.get("name") and not opt.get("hidden")
        ]

        if prop_name == "resource":
            resources = names
        elif prop_name == "operation":
            operations = names

    parts = [base_desc.rstrip(".")]

    if resources:
        # Batasi 10 resource agar tidak terlalu panjang
        res_str = ", ".join(resources[:10])
        if len(resources) > 10:
            res_str += f", +{len(resources) - 10} more"
        parts.append(f"Resources: {res_str}")

    if operations:
        ops_unique = list(dict.fromkeys(operations))  # deduplikasi jaga urutan
        ops_str = ", ".join(ops_unique[:12])
        if len(ops_unique) > 12:
            ops_str += f", +{len(ops_unique) - 12} more"
        parts.append(f"Operations: {ops_str}")

    return ". ".join(parts)


async def _fetch_nodes(cookie: str) -> list[dict]:
    """Ambil /types/nodes.json dari n8n dan parsing jadi list node yang diperkaya."""
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(
            f"{settings.n8n_base_url}/types/nodes.json",
            headers={"Cookie": cookie},
        )
        resp.raise_for_status()

    raw = resp.json()
    source = raw if isinstance(raw, list) else raw.get("data", [])

    nodes: list[dict] = []
    for item in source:
        name: str = item.get("name", "").strip()
        display: str = (
            item.get("displayName")
            or item.get("display_name")
            or name
        ).strip()
        base_desc: str = (item.get("description") or "").strip()

        # Lewati node internal / deprecated
        if not name:
            continue
        if name in {"n8n-nodes-base.n8n", "n8n-nodes-base.noOp"}:
            continue

        # Ekstrak properties untuk memperkaya deskripsi dengan resources + operations
        properties: list[dict] = item.get("properties", [])
        rich_desc = _enrich_description(base_desc, properties)

        nodes.append({
            "node_type": name,
            "display_name": display,
            "description": rich_desc[:400],  # diperlebar karena deskripsi lebih kaya
        })

    # Deduplikasi — n8n kadang daftarkan node yang sama lebih dari sekali
    seen: set[str] = set()
    unique: list[dict] = []
    for n in nodes:
        if n["node_type"] not in seen:
            seen.add(n["node_type"])
            unique.append(n)

    return unique


# --------------------------------------------------------------------------- #
# Public API                                                                    #
# --------------------------------------------------------------------------- #

_MIN_NODES_FROM_N8N = 500  # n8n penuh harusnya 800+ node; < 500 = n8n belum selesai startup


_MIN_NODES_FROM_N8N = 500   # n8n penuh harusnya 800+ node; < 500 = n8n belum selesai startup
_MAX_RETRIES = 8            # maksimal percobaan
_RETRY_DELAY = 15           # detik antar percobaan


async def init_registry() -> None:
    """
    Dipanggil sekali saat startup. Retry sampai n8n benar-benar siap.

    n8n butuh 30-60 detik untuk fully load semua node. Jika mst-agent mulai
    lebih dulu dan fetch terlalu cepat, n8n hanya mengembalikan node parsial
    yang menyebabkan hash mismatch dan embedding diregenerasi setiap restart.

    Solusi: retry dengan delay sampai mendapat >= 500 node, baru simpan ke registry.
    """
    global _registry
    import asyncio

    for attempt in range(1, _MAX_RETRIES + 1):
        cookie = await _login()
        if not cookie:
            logger.warning("[NodeRegistry] Login n8n gagal (attempt %d/%d)", attempt, _MAX_RETRIES)
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY)
            continue

        try:
            nodes = await _fetch_nodes(cookie)
            if len(nodes) >= _MIN_NODES_FROM_N8N:
                _registry = nodes
                logger.info(
                    "[NodeRegistry] ✓ Loaded %d nodes dari n8n (attempt %d)",
                    len(nodes), attempt,
                )
                return
            else:
                logger.warning(
                    "[NodeRegistry] n8n baru kembalikan %d node (min=%d, attempt %d/%d) — "
                    "tunggu n8n selesai startup...",
                    len(nodes), _MIN_NODES_FROM_N8N, attempt, _MAX_RETRIES,
                )
        except Exception as exc:
            logger.warning("[NodeRegistry] Fetch error attempt %d: %s", attempt, exc)

        if attempt < _MAX_RETRIES:
            await asyncio.sleep(_RETRY_DELAY)

    # Fallback ke static catalog setelah semua retry habis
    _registry = list(_STATIC)
    logger.warning(
        "[NodeRegistry] ⚠ Semua retry habis — menggunakan static catalog (%d nodes). "
        "n8n mungkin tidak tersedia.",
        len(_registry),
    )


def get_catalog() -> list[dict]:
    """Kembalikan daftar node yang aktif (live atau static)."""
    return _registry if _registry else list(_STATIC)
