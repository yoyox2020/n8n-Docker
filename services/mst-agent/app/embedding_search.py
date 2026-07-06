"""
Embedding Search — cari node n8n yang paling relevan secara semantik.

Versi 3: Bilingual + Category-Aware + Query Expansion

Cara kerja:
  1. Setiap node diembedding dengan teks BILINGUAL (EN + ID) agar query
     Bahasa Indonesia bisa cocok dengan node berbahasa Inggris.
  2. Saat startup, query user di-expand dengan sinonim EN agar semantic
     similarity lebih tinggi (tanpa perlu ubah embedding).
  3. Pencarian dipisah: find_best_trigger() untuk trigger, find_best_tools()
     untuk action — LLM tidak perlu menebak mana trigger mana action.
  4. Semua vektor disimpan di PostgreSQL tabel node_embeddings (persistent).

Mengapa bilingual?
  Embedding lama: "schedule trigger: triggers workflow at time intervals"
  Query user    : "setiap hari jam 8 pagi"
  Similarity    : rendah (beda bahasa)

  Embedding baru: "schedule trigger: ... | Jadwal berkala harian mingguan jam cron"
  Query expanded: "setiap hari jam 8 pagi schedule daily interval time every"
  Similarity    : tinggi ✓

Untuk menambah bahasa baru atau term baru: cukup tambah ke _ID_EN_EXPANSION
atau _INDONESIAN_TRIGGER_DESC. Tidak perlu ubah algoritma.
"""

import hashlib
import json
import logging
import math

import httpx
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

_EMBED_MODEL = "nomic-embed-text"
_CORE_NODE_TYPES = {
    # Hanya action nodes — trigger nodes TIDAK masuk di sini
    # (trigger sudah disaring keluar dari action_catalog sebelum core lookup)
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.set",
    "n8n-nodes-base.if",
    "n8n-nodes-base.code",
}
_ALWAYS_TRIGGER_TYPES = {
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.manualTrigger",
    "@n8n/n8n-nodes-langchain.chatTrigger",
}

# Bump versi ini untuk memaksa regenerasi embedding (misal saat teks berubah)
_EMBEDDING_VERSION = "v3-bilingual"
_MIN_SCORE = 0.25

# Cache di memori
_embeddings: list[tuple[dict, list[float]]] = []
_ready: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Query Expansion — Indonesia → English
# Setiap kata Indonesia di-map ke term English yang relevan untuk embedding search.
# Tambahkan entri baru di sini saat ada kasus baru — tidak perlu ubah algoritma.
# ─────────────────────────────────────────────────────────────────────────────

_ID_EN_EXPANSION: dict[str, str] = {
    # Waktu / Jadwal
    "setiap": "every schedule interval",
    "tiap": "every each interval",
    "jam": "time hour schedule hourly",
    "pagi": "morning daily schedule AM",
    "siang": "noon afternoon daily schedule",
    "malam": "night evening daily schedule PM",
    "hari": "day daily",
    "harian": "daily schedule",
    "minggu": "week weekly",
    "mingguan": "weekly schedule",
    "bulan": "month monthly",
    "bulanan": "monthly schedule",
    "terjadwal": "scheduled interval cron trigger",
    "jadwal": "schedule cron interval",
    "berkala": "periodic interval schedule",
    "rutin": "routine schedule interval periodic",
    "interval": "interval schedule cron",
    "menit": "minute interval schedule",
    "detik": "second interval",

    # Tindakan
    "kirim": "send post notify",
    "terima": "receive listen read incoming",
    "ambil": "fetch get retrieve read",
    "simpan": "save store insert write",
    "hapus": "delete remove",
    "tambah": "add create insert",
    "perbarui": "update modify edit",
    "buat": "create build generate",
    "cari": "search find query",
    "baca": "read get fetch",
    "tulis": "write create post",
    "proses": "process transform convert",
    "generate": "generate create build",
    "gabung": "merge combine join",
    "pecah": "split batch chunk",

    # Komunikasi
    "pesan": "message notification send",
    "notifikasi": "notification alert notify",
    "email": "email send receive",
    "whatsapp": "WhatsApp message send receive wa",
    "wa": "WhatsApp message",
    "telegram": "Telegram bot message send",
    "slack": "Slack message channel workspace",
    "sms": "SMS text message Twilio",
    "chat": "chat message conversation",

    # Data
    "data": "data record",
    "database": "database postgres mysql MongoDB NoSQL",
    "tabel": "table database spreadsheet",
    "baris": "row record",
    "kolom": "column field",
    "file": "file document attachment",
    "dokumen": "document file",
    "laporan": "report document generate",
    "ringkasan": "summary aggregate report",

    # Logic
    "jika": "if condition branch",
    "cek": "check validate condition",
    "filter": "filter condition branch",
    "kondisi": "condition if branch",
    "pilih": "select choose switch branch",
    "validasi": "validate check condition",
    "percabangan": "branch condition if switch",
    "loop": "loop iterate batch",
    "ulangi": "loop iterate repeat",
    "batch": "batch loop split",

    # HTTP / API
    "webhook": "webhook HTTP trigger endpoint receive",
    "api": "API HTTP request endpoint REST",
    "http": "HTTP request API endpoint",
    "url": "URL HTTP request fetch",
    "panggil": "call request invoke API",
    "endpoint": "endpoint URL HTTP API",

    # Form
    "form": "form submission input",
    "formulir": "form submission input",
    "submit": "submit form input",
    "isi": "fill input form",

    # Google
    "google": "Google workspace",
    "sheets": "Google Sheets spreadsheet",
    "drive": "Google Drive storage file",
    "docs": "Google Docs document",
    "calendar": "Google Calendar event schedule",

    # Services umum (tidak ada duplicate key lagi)
    "crm": "CRM HubSpot Salesforce contact",
    "tiket": "ticket ServiceNow Jira Zendesk support",
    "kontak": "contact CRM customer",
    "customer": "customer contact CRM",

    # AI
    "agent": "AI agent LangChain tool",
    "agen": "AI agent LangChain tool",
    "model": "LLM model AI chat",
    "memori": "memory context conversation",
    "riwayat": "history memory context",

    # Umum
    "otomatis": "automatic automated trigger",
    "manual": "manual trigger click",
    "mulai": "start trigger begin",
    "selesai": "end finish complete",
    "hasil": "result output response",
    "input": "input data receive",
    "output": "output result send",
    "jawab": "respond reply answer",
    "pertanyaan": "question query chat",
}


def _expand_query(prompt: str) -> str:
    """
    Perluas query Indonesia dengan term Inggris agar semantic search bekerja.

    Contoh:
      "kirim email setiap hari jam 8"
      → "kirim email setiap hari jam 8 send post notify schedule interval daily time hour"
    """
    words = prompt.lower().split()
    extra: list[str] = []
    seen_expansions: set[str] = set()

    for word in words:
        # Hapus tanda baca dari kata sebelum lookup
        clean_word = word.strip(".,!?;:")
        expansion = _ID_EN_EXPANSION.get(clean_word)
        if expansion and expansion not in seen_expansions:
            extra.append(expansion)
            seen_expansions.add(expansion)

    if extra:
        expanded = f"{prompt} {' '.join(extra)}"
        logger.debug("[QueryExpand] '%s…' → '%s…'", prompt[:40], expanded[:80])
        return expanded
    return prompt


# ─────────────────────────────────────────────────────────────────────────────
# Deskripsi Indonesia per node — ditambahkan ke teks embedding (bilingual)
# Pattern-based: otomatis menutup semua 849+ node tanpa hardcode satu per satu.
# ─────────────────────────────────────────────────────────────────────────────

def _make_indonesian_desc(node_type: str, display_name: str) -> str:
    """
    Hasilkan deskripsi Bahasa Indonesia untuk node berdasarkan tipe-nya.
    Digunakan saat GENERATE embedding — tidak tampil di UI.
    """
    nt = node_type.lower()

    # === TRIGGER NODES ===
    if "scheduletrigger" in nt:
        return "pemicu jadwal terjadwal berkala harian mingguan bulanan setiap jam menit cron interval otomatis rutin"
    if "manualtrigger" in nt:
        return "pemicu manual jalankan sekali klik test mulai"
    if "webhook" in nt:
        return "pemicu webhook HTTP API request masuk panggilan eksternal endpoint"
    if "gmail" in nt and "trigger" in nt:
        return "pemicu email gmail baru masuk notifikasi email diterima"
    if "emailread" in nt or ("email" in nt and "trigger" in nt):
        return "pemicu email baru masuk imap notifikasi terima email"
    if "whatsapp" in nt and "trigger" in nt:
        return "pemicu pesan whatsapp masuk terima pesan wa notifikasi"
    if "telegram" in nt and "trigger" in nt:
        return "pemicu pesan telegram masuk terima bot notifikasi"
    if "slack" in nt and "trigger" in nt:
        return "pemicu pesan slack masuk notifikasi channel workspace"
    if "form" in nt and "trigger" in nt:
        return "pemicu formulir form isi kirim submission submit input"
    if "chattr" in nt or ("chat" in nt and "trigger" in nt):
        return "pemicu chat pesan masuk percakapan pengguna"
    if "microsoftteams" in nt and "trigger" in nt:
        return "pemicu Microsoft Teams pesan masuk notifikasi"
    if "discord" in nt and "trigger" in nt:
        return "pemicu Discord pesan channel server"
    if "notion" in nt and "trigger" in nt:
        return "pemicu Notion halaman database berubah"
    if "jira" in nt and "trigger" in nt:
        return "pemicu Jira issue tiket baru berubah"
    if "github" in nt and "trigger" in nt:
        return "pemicu GitHub commit PR issue baru"
    if "stripe" in nt and "trigger" in nt:
        return "pemicu Stripe pembayaran baru event"
    if "shopify" in nt and "trigger" in nt:
        return "pemicu Shopify order produk baru event"
    if nt.endswith("trigger"):
        svc = display_name.replace("Trigger", "").strip()
        return f"pemicu {svc} mulai workflow dari {svc} event baru"

    # === CORE / LOGIC NODES ===
    if nt.endswith(".if") or nt.endswith("nodes-base.if"):
        return "kondisi jika percabangan pilihan cek validasi if else cabang"
    if nt.endswith(".code"):
        return "kode script javascript python transformasi proses data fungsi"
    if nt.endswith(".set"):
        return "atur nilai set data mapping transformasi ubah"
    if "merge" in nt:
        return "gabungkan data merge kombinasi join"
    if "splitin" in nt or "splitout" in nt:
        return "pecah data batch loop iterasi split"
    if "wait" in nt:
        return "tunggu delay jeda waktu pause"
    if "switch" in nt:
        return "switch pilihan banyak cabang kondisi multiple"
    if "filter" in nt:
        return "filter saring pilih kondisi exclude"
    if "aggregate" in nt:
        return "agregasi kumpulkan ringkasan summary total"
    if "noop" in nt or "no-op" in nt:
        return "tidak ada operasi placeholder dummy"
    if "httprequest" in nt:
        return "HTTP request panggil API ambil data URL fetch REST GET POST"

    # === EMAIL ===
    if "gmail" in nt:
        return "kirim email Gmail Google Mail baca tulis"
    if "emailsend" in nt or "sendemail" in nt:
        return "kirim email SMTP outgoing"
    if "microsoftoutlook" in nt or "outlook" in nt:
        return "email Outlook Microsoft kirim baca"

    # === KOMUNIKASI ===
    if "slack" in nt:
        return "Slack kirim pesan channel notifikasi workspace"
    if "telegram" in nt:
        return "Telegram kirim pesan bot notifikasi channel"
    if "whatsapp" in nt:
        return "WhatsApp kirim pesan wa notifikasi"
    if "twilio" in nt:
        return "Twilio SMS kirim SMS telepon"
    if "discord" in nt:
        return "Discord kirim pesan server channel"
    if "microsoftteams" in nt:
        return "Microsoft Teams kirim pesan channel notifikasi"
    if "sendgrid" in nt:
        return "SendGrid kirim email massal marketing"
    if "mailchimp" in nt:
        return "Mailchimp kirim email marketing newsletter"

    # === PRODUKTIVITAS ===
    if "googlesheet" in nt or "sheets" in nt:
        return "Google Sheets spreadsheet tabel data simpan baca tulis"
    if "googledri" in nt or "drive" in nt:
        return "Google Drive file penyimpanan upload download"
    if "googledoc" in nt:
        return "Google Docs dokumen tulis baca"
    if "googlecal" in nt or "calendar" in nt:
        return "Google Calendar kalender event jadwal"
    if "notion" in nt:
        return "Notion database halaman catatan simpan"
    if "airtable" in nt:
        return "Airtable database tabel spreadsheet"
    if "trello" in nt:
        return "Trello card task todo list board"
    if "asana" in nt:
        return "Asana task project management tugas"
    if "todoist" in nt:
        return "Todoist task todo daftar tugas"
    if "microsofttodo" in nt:
        return "Microsoft Todo task tugas daftar"
    if "clickup" in nt:
        return "ClickUp project task management"

    # === CRM / SUPPORT ===
    if "hubspot" in nt:
        return "HubSpot CRM kontak deal pipeline sales marketing"
    if "salesfor" in nt:
        return "Salesforce CRM kontak deal opportunity sales"
    if "zendesk" in nt:
        return "Zendesk tiket support helpdesk customer service"
    if "serviceno" in nt:
        return "ServiceNow tiket ITSM incident IT service"
    if "jira" in nt:
        return "Jira issue tiket project bug track"
    if "freshdesk" in nt:
        return "Freshdesk tiket support helpdesk"
    if "intercom" in nt:
        return "Intercom chat customer support"

    # === DATABASE ===
    if "postgres" in nt:
        return "PostgreSQL database simpan query baca tulis data relasional"
    if "mysql" in nt:
        return "MySQL database simpan query baca tulis"
    if "mongodb" in nt:
        return "MongoDB database NoSQL simpan dokumen"
    if "redis" in nt:
        return "Redis cache simpan sementara key-value"
    if "elasticsearch" in nt:
        return "Elasticsearch search index pencarian"
    if "supabase" in nt:
        return "Supabase database PostgreSQL real-time"

    # === FILE / STORAGE ===
    if "ftp" in nt or "sftp" in nt:
        return "FTP SFTP transfer file upload download"
    if "s3" in nt or "aws" in nt:
        return "AWS S3 storage file cloud upload"
    if "dropbox" in nt:
        return "Dropbox file storage cloud"
    if "onedrive" in nt:
        return "OneDrive Microsoft file storage cloud"
    if "box" in nt:
        return "Box file storage cloud enterprise"

    # === AI / LANGCHAIN ===
    if "agent" in nt and "langchain" in nt:
        return "AI Agent agen cerdas otomatis tool LLM pengambil keputusan"
    if "lmchat" in nt:
        return "model bahasa chat LLM AI OpenAI GPT"
    if "mistika" in nt:
        return "Mistika AI model bahasa chat lokal"
    if "memory" in nt and "langchain" in nt:
        return "memori percakapan context simpan riwayat chat window"
    if "tool" in nt and "langchain" in nt:
        return "tool alat AI Agent fungsi kemampuan"
    if "outputparser" in nt:
        return "parse output LLM ekstrak JSON text"
    if "textsplitter" in nt:
        return "pecah teks chunk dokumen"
    if "embeddings" in nt:
        return "embedding vektor representasi teks"
    if "retrieval" in nt or "vectorstore" in nt:
        return "vector store retrieval RAG dokumen"
    if "chain" in nt and "langchain" in nt:
        return "chain LLM rangkaian proses AI"

    # === DEVELOPER / MISC ===
    if "github" in nt:
        return "GitHub repo kode commit PR issue"
    if "gitlab" in nt:
        return "GitLab repo kode CI/CD"
    if "openai" in nt:
        return "OpenAI GPT ChatGPT AI model bahasa"
    if "anthropic" in nt:
        return "Anthropic Claude AI model bahasa"
    if "google" in nt and "ai" in nt:
        return "Google AI Gemini model bahasa"
    if "stripe" in nt:
        return "Stripe pembayaran payment kartu kredit"
    if "paypal" in nt:
        return "PayPal pembayaran payment"
    if "shopify" in nt:
        return "Shopify e-commerce toko online produk order"

    # Default
    return f"node {display_name} integrasi otomatis"


# ─────────────────────────────────────────────────────────────────────────────
# Utilitas embedding
# ─────────────────────────────────────────────────────────────────────────────

def _ollama_host() -> str:
    base = settings.ollama_base_url.rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


async def _get_embedding(text: str) -> list[float] | None:
    url = f"{_ollama_host()}/api/embeddings"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={"model": _EMBED_MODEL, "prompt": text})
            resp.raise_for_status()
            return resp.json().get("embedding")
    except Exception as exc:
        logger.warning("[Embedding] Gagal embed: %s", exc)
        return None


def _catalog_hash(catalog: list[dict]) -> str:
    """Hash catalog + versi — berubah = trigger regenerasi embedding."""
    content = json.dumps(
        [(_EMBEDDING_VERSION, n["node_type"], n.get("description", "")[:80]) for n in catalog],
        sort_keys=True,
    )
    return hashlib.md5(content.encode()).hexdigest()


def _build_node_text(node: dict) -> str:
    """
    Buat teks bilingual untuk embedding sebuah node.
    Format: "{EN display + description} | Bahasa Indonesia: {ID description}"
    """
    en_part = f"{node['display_name']}: {node.get('description', '')}"
    id_part = _make_indonesian_desc(node["node_type"], node["display_name"])
    return f"{en_part} | Bahasa Indonesia: {id_part}"


# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

async def _load_from_db(catalog: list[dict], db: AsyncSession) -> bool:
    from app.models.node_embedding import NodeEmbedding

    expected_hash = _catalog_hash(catalog)

    rows = (await db.execute(select(NodeEmbedding))).scalars().all()
    db_count = len(rows)

    # Catalog parsial (n8n belum selesai load) — pakai DB lama
    if db_count > 100 and len(catalog) < db_count * 0.7:
        logger.warning(
            "[Embedding] Catalog baru (%d) < 70%% DB (%d) — pakai DB lama",
            len(catalog), db_count,
        )
        result_list = [
            (
                {"node_type": r.node_type, "display_name": r.display_name, "description": r.description},
                list(r.embedding),
            )
            for r in rows if r.embedding is not None
        ]
        global _embeddings, _ready
        _embeddings = result_list
        _ready = True
        logger.info("[Embedding] ✓ Dimuat dari DB (mode fallback): %d vektor", len(result_list))
        return True

    # Cek jumlah minimal dulu sebelum hash (db_count < 10 hampir pasti DB kosong)
    if db_count < 10:
        return False

    # Cek versi/hash — jika berbeda, embedding perlu diregenerasi
    result = await db.execute(select(NodeEmbedding.catalog_hash).limit(1))
    stored_hash = result.scalar()

    if stored_hash != expected_hash:
        logger.info(
            "[Embedding] Hash berbeda (stored=%s expected=%s) — regenerasi bilingual...",
            stored_hash, expected_hash,
        )
        return False

    node_map = {n["node_type"]: n for n in catalog}
    result_list = []
    for row in rows:
        node = node_map.get(row.node_type)
        if node and row.embedding is not None:
            result_list.append((node, list(row.embedding)))

    _embeddings = result_list
    _ready = True
    logger.info("[Embedding] ✓ Dimuat dari DB: %d vektor bilingual", len(result_list))
    return True


async def _save_to_db(catalog: list[dict], db: AsyncSession) -> None:
    from app.models.node_embedding import NodeEmbedding

    cat_hash = _catalog_hash(catalog)
    seen: set[str] = set()
    rows = []
    for node, emb in _embeddings:
        nt = node["node_type"]
        if nt not in seen:
            seen.add(nt)
            rows.append({
                "node_type": nt,
                "display_name": node.get("display_name", ""),
                "description": node.get("description", ""),
                "embedding": emb,          # pgvector menerima list[float] langsung
                "catalog_hash": cat_hash,
            })

    if not rows:
        return

    stmt = pg_insert(NodeEmbedding).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["node_type"],
        set_={
            "display_name": stmt.excluded.display_name,
            "description":  stmt.excluded.description,
            "embedding":    stmt.excluded.embedding,
            "catalog_hash": stmt.excluded.catalog_hash,
        },
    )
    await db.execute(stmt)
    await db.commit()
    logger.info("[Embedding] ✓ %d vektor pgvector disimpan ke DB", len(rows))


# ─────────────────────────────────────────────────────────────────────────────
# Inisialisasi
# ─────────────────────────────────────────────────────────────────────────────

_MIN_CATALOG_FOR_SAVE = 500


async def init_embeddings(catalog: list[dict]) -> None:
    global _embeddings, _ready

    async with AsyncSessionLocal() as db:
        if await _load_from_db(catalog, db):
            return

        if len(catalog) < _MIN_CATALOG_FOR_SAVE:
            logger.warning(
                "[Embedding] Catalog hanya %d node — skip generate, n8n belum ready",
                len(catalog),
            )
            _ready = False
            return

        logger.info("[Embedding] Generate %d vektor BILINGUAL (EN+ID)...", len(catalog))

        results: list[tuple[dict, list[float]]] = []
        for i, node in enumerate(catalog):
            # Teks bilingual: deskripsi EN + deskripsi ID
            text = _build_node_text(node)
            emb = await _get_embedding(text)
            if emb:
                results.append((node, emb))
            if (i + 1) % 100 == 0:
                logger.info("[Embedding] Progress: %d/%d node", i + 1, len(catalog))

        _embeddings = results
        _ready = True
        await _save_to_db(catalog, db)
        await _ensure_hnsw_index()
        logger.info("[Embedding] ✓ Selesai: %d vektor pgvector tersimpan + HNSW index aktif", len(results))


# ─────────────────────────────────────────────────────────────────────────────
# Pencarian — Category-Aware
# ─────────────────────────────────────────────────────────────────────────────

def _is_trigger_node(node_type: str) -> bool:
    nt = node_type.lower()
    return (
        nt.endswith("trigger")
        or node_type in _ALWAYS_TRIGGER_TYPES
    )


def _is_ai_agent_prompt(prompt: str) -> bool:
    keywords = {"agent", "ai agent", "tool", "langchain", "llm", "mistika", "agen"}
    lower = prompt.lower()
    return any(kw in lower for kw in keywords)


def _filter_tool_nodes(nodes: list[dict], allow_tools: bool) -> list[dict]:
    if allow_tools:
        return nodes
    return [n for n in nodes if not n["node_type"].endswith("Tool")]


async def _pgvector_search(
    query_emb: list[float],
    top_k: int = 20,
    filter_types: set[str] | None = None,
) -> list[tuple[dict, float]]:
    """
    Cari node paling mirip menggunakan pgvector operator <=> (cosine distance) di SQL.
    Lebih cepat dari Python loop karena kalkulasi dilakukan di dalam PostgreSQL.

    filter_types: jika diisi, hanya ambil node dengan node_type dalam set ini.
    Return: list (node_dict, similarity_score) diurutkan dari paling mirip.
    """
    from app.models.node_embedding import NodeEmbedding

    # Konversi embedding ke format string pgvector: '[0.1, 0.2, ...]'
    emb_str = "[" + ",".join(str(round(v, 6)) for v in query_emb) + "]"

    # cosine similarity = 1 - cosine_distance
    # operator <=> = cosine distance (0 = identik, 2 = berlawanan)
    async with AsyncSessionLocal() as db:
        if filter_types:
            # Filter node_type + order by cosine distance
            result = await db.execute(
                text(
                    """
                    SELECT node_type, display_name, description,
                           1 - (embedding <=> :emb ::vector) AS similarity
                    FROM node_embeddings
                    WHERE node_type = ANY(:types)
                    ORDER BY embedding <=> :emb ::vector
                    LIMIT :k
                    """
                ),
                {"emb": emb_str, "types": list(filter_types), "k": top_k},
            )
        else:
            result = await db.execute(
                text(
                    """
                    SELECT node_type, display_name, description,
                           1 - (embedding <=> :emb ::vector) AS similarity
                    FROM node_embeddings
                    ORDER BY embedding <=> :emb ::vector
                    LIMIT :k
                    """
                ),
                {"emb": emb_str, "k": top_k},
            )

        rows = result.fetchall()

    return [
        (
            {"node_type": r.node_type, "display_name": r.display_name, "description": r.description},
            float(r.similarity),
        )
        for r in rows
    ]


async def _ensure_hnsw_index() -> None:
    """
    Buat HNSW index jika belum ada.
    HNSW jauh lebih cepat dari sequential scan untuk 1000+ vektor.
    Dipanggil sekali setelah embedding selesai dibuat.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(text(
            """
            CREATE INDEX IF NOT EXISTS node_embeddings_hnsw_idx
            ON node_embeddings
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """
        ))
        await db.commit()
        logger.info("[pgvector] ✅ HNSW index aktif di tabel node_embeddings")


def _text_overlap_score(node: dict, expanded_query: str) -> float:
    """
    Hitung skor overlap kata antara deskripsi bilingual node dan expanded query.
    Dipakai sebagai signal tambahan (bukan pengganti) untuk embedding cosine similarity.

    Semakin banyak kata query yang muncul di deskripsi node → skor lebih tinggi.
    Ini memanfaatkan deskripsi bilingual yang sudah ada — bukan static keyword map.
    """
    # Gunakan deskripsi bilingual yang sama dengan yang dipakai saat embed
    bilingual = (
        f"{node.get('display_name', '')} "
        f"{node.get('description', '')} "
        f"{_make_indonesian_desc(node['node_type'], node.get('display_name', ''))}"
    ).lower()
    bilingual_words = set(bilingual.split())
    query_words = set(expanded_query.lower().split())

    # Panjang term yang overlap lebih bermakna (exclude kata pendek)
    meaningful = {w for w in query_words if len(w) > 3}
    overlap = len(meaningful & bilingual_words)

    # Normalized: max 0.20 tambahan dari overlap
    return min(overlap * 0.015, 0.20)


async def find_best_trigger(prompt: str, top_k: int = 5) -> list[dict]:
    """
    Cari trigger TERBAIK untuk prompt menggunakan:
    1. Expanded query (Indonesia → English) sebelum embedding
    2. Cosine similarity pada trigger nodes saja
    3. Text overlap boost menggunakan deskripsi bilingual

    Hybrid approach: embedding (semantik) + text overlap (lexical).
    Tidak ada static keyword map — semua dinamis dari konten node itu sendiri.
    """
    from app.nodes_registry import get_catalog
    from app.routers.plan import _extract_search_terms, _node_matches

    catalog = get_catalog()
    trigger_catalog = [n for n in catalog if _is_trigger_node(n["node_type"])]

    # Expanded query agar kata Indonesia cocok dengan embedding EN
    expanded = _expand_query(prompt)

    prompt_emb = await _get_embedding(expanded)

    if not _ready or not prompt_emb:
        # Fallback: text search + overlap boost
        terms = _extract_search_terms(expanded)
        scored_fb = [
            (n, _text_overlap_score(n, expanded))
            for n in trigger_catalog
            if _node_matches(n, terms) or _text_overlap_score(n, expanded) > 0.03
        ]
        scored_fb.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in scored_fb[:top_k]] or trigger_catalog[:top_k]

    # Primary: pgvector SQL search (cepat, semua kalkulasi di DB)
    trigger_types = {n["node_type"] for n in trigger_catalog}
    try:
        pgv_results = await _pgvector_search(prompt_emb, top_k=top_k * 3, filter_types=trigger_types)
        # Hybrid scoring: 70% pgvector cosine + 30% text overlap
        scored: list[tuple[dict, float]] = [
            (node, sim * 0.70 + _text_overlap_score(node, expanded) * 0.30)
            for node, sim in pgv_results
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
    except Exception as exc:
        # pgvector belum siap — fallback ke Python cosine
        logger.debug("[TriggerSearch] pgvector fallback: %s", exc)
        scored = []
        for node, emb in _embeddings:
            if node["node_type"] not in trigger_types:
                continue
            cosine = _cosine_sim(prompt_emb, emb)
            overlap = _text_overlap_score(node, expanded)
            scored.append((node, cosine * 0.70 + overlap * 0.30))
        scored.sort(key=lambda x: x[1], reverse=True)

    logger.info(
        "[TriggerSearch] Top-3 untuk '%s': %s",
        prompt[:50],
        [(n["node_type"].split(".")[-1], round(sc, 3)) for n, sc in scored[:3]],
    )
    return [n for n, _ in scored[:top_k]]


async def find_best_tools(
    prompt: str,
    top_k: int = 12,
    exclude_trigger: str | None = None,
) -> list[dict]:
    """
    Cari action/tool nodes terbaik untuk prompt.
    Tidak mencakup trigger nodes (sudah ditangani find_best_trigger).
    exclude_trigger: node_type trigger yang sudah dipilih (skip versi actionnya jika ada)
    """
    from app.nodes_registry import get_catalog
    from app.routers.plan import _extract_search_terms, _node_matches, _node_score

    catalog = get_catalog()
    allow_tools = _is_ai_agent_prompt(prompt)

    # Hanya action nodes (bukan trigger)
    action_catalog = [
        n for n in catalog
        if not _is_trigger_node(n["node_type"])
        and (allow_tools or not n["node_type"].endswith("Tool"))
    ]

    expanded = _expand_query(prompt)

    core_types = set(_CORE_NODE_TYPES) - {exclude_trigger or ""}
    core = [n for n in action_catalog if n["node_type"] in core_types]

    prompt_emb = await _get_embedding(expanded)

    if not _ready or not prompt_emb:
        terms = _extract_search_terms(expanded)
        matches = [n for n in action_catalog if _node_matches(n, terms)]
        matches.sort(key=lambda n: _node_score(n, terms), reverse=True)
        return (core + matches)[:top_k]

    # Text search layer (tetap dipakai untuk exact match nama service)
    terms = _extract_search_terms(expanded)
    text_hits = [
        n for n in action_catalog
        if n["node_type"] not in core_types and _node_matches(n, terms)
    ]
    text_hits.sort(key=lambda n: _node_score(n, terms), reverse=True)
    text_hits = text_hits[:8]

    # Primary: pgvector SQL search
    action_types = {n["node_type"] for n in action_catalog}
    already = core_types | {n["node_type"] for n in text_hits}
    sem_hits: list[dict] = []
    try:
        pgv_results = await _pgvector_search(prompt_emb, top_k=top_k * 2)
        sem_slots = max(top_k - len(core) - len(text_hits), 4)
        sem_hits = [
            node for node, sim in pgv_results
            if node["node_type"] in action_types
            and node["node_type"] not in already
            and sim >= _MIN_SCORE
        ][:sem_slots]
    except Exception as exc:
        logger.debug("[ToolSearch] pgvector fallback: %s", exc)
        scored_fb: list[tuple[dict, float]] = [
            (node, _cosine_sim(prompt_emb, emb))
            for node, emb in _embeddings
            if node["node_type"] in action_types and node["node_type"] not in already
        ]
        scored_fb.sort(key=lambda x: x[1], reverse=True)
        sem_slots = max(top_k - len(core) - len(text_hits), 4)
        sem_hits = [n for n, sc in scored_fb[:sem_slots] if sc >= _MIN_SCORE]

    combined = core + text_hits + sem_hits

    # Deduplikasi
    seen: set[str] = set()
    result: list[dict] = []
    for n in combined:
        if n["node_type"] not in seen:
            seen.add(n["node_type"])
            result.append(n)

    logger.debug(
        "[ToolSearch] core=%d text=%d semantic=%d total=%d untuk '%s'",
        len(core), len(text_hits), len(sem_hits), len(result), prompt[:30],
    )
    return result[:top_k]


async def find_relevant_nodes(prompt: str, top_k: int = 20) -> list[dict]:
    """
    Hybrid search (backward compatible): gabungan trigger + tools.
    Dipakai ketika kita perlu semua node sekaligus (misal saat tool suggestion).
    """
    from app.nodes_registry import get_catalog
    from app.routers.plan import filter_relevant_nodes, _extract_search_terms, _node_matches, _node_score

    catalog = get_catalog()
    allow_tools = _is_ai_agent_prompt(prompt)
    working_catalog = _filter_tool_nodes(catalog, allow_tools)

    core_types = set(_CORE_NODE_TYPES)
    core = [n for n in working_catalog if n["node_type"] in core_types]

    if not _ready or not _embeddings:
        return filter_relevant_nodes(prompt, working_catalog, top_k)

    expanded = _expand_query(prompt)

    # Text search (exact/partial match)
    terms = _extract_search_terms(expanded)
    text_candidates = [
        n for n in working_catalog
        if n["node_type"] not in core_types and _node_matches(n, terms)
    ]
    text_candidates.sort(key=lambda n: _node_score(n, terms), reverse=True)
    text_hits = text_candidates[:10]

    # Primary: pgvector SQL search
    prompt_emb = await _get_embedding(expanded)
    sem_hits: list[dict] = []
    if prompt_emb:
        working_types = {n["node_type"] for n in working_catalog}
        already = core_types | {n["node_type"] for n in text_hits}
        try:
            pgv_results = await _pgvector_search(prompt_emb, top_k=top_k * 2)
            sem_slots = max(top_k - len(core) - len(text_hits), 5)
            sem_hits = [
                node for node, sim in pgv_results
                if node["node_type"] in working_types
                and node["node_type"] not in already
                and sim >= _MIN_SCORE
            ][:sem_slots]
        except Exception as exc:
            logger.debug("[HybridSearch] pgvector fallback: %s", exc)
            scored_fb: list[tuple[dict, float]] = [
                (node, _cosine_sim(prompt_emb, emb))
                for node, emb in _embeddings
                if node["node_type"] not in already and node["node_type"] in working_types
            ]
            scored_fb.sort(key=lambda x: x[1], reverse=True)
            sem_slots = max(top_k - len(core) - len(text_hits), 5)
            sem_hits = [n for n, sc in scored_fb[:sem_slots] if sc >= _MIN_SCORE]

    combined = core + text_hits + sem_hits

    seen: set[str] = set()
    result: list[dict] = []
    for n in combined:
        if n["node_type"] not in seen:
            seen.add(n["node_type"])
            result.append(n)

    logger.debug("[HybridSearch] core=%d text=%d semantic=%d total=%d",
                 len(core), len(text_hits), len(sem_hits), len(result))
    return result[:top_k]
