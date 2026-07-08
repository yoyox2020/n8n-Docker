# Phase 2 — MST Agent: Node Registry Dinamis & Embedding Semantic Search

> **Periode:** Juni 2026  
> **Tujuan:** Agar LLM (Mistika / Ollama) bisa mengenali SEMUA node n8n yang
> terinstall — bukan hanya 73 node yang ditulis manual — dan bisa menemukan
> node yang tepat meskipun user tidak menyebut nama exaknya.

---

## Masalah yang Diselesaikan

| # | Masalah | Solusi |
|---|---------|--------|
| 1 | Static catalog hanya 73 node, ServiceNow/Zendesk/dll tidak dikenal | Node Registry: ambil 912+ node langsung dari n8n |
| 2 | Filter pakai keyword hardcoded → tidak scalable | Embedding Semantic Search: cari berdasarkan makna |
| 3 | LLM menambahkan teks sebelum JSON → error 422 | JSON extractor 3 lapis (parse → code block → bracket search) |
| 4 | Timeout saat generate workflow JSON | Kurangi max_tokens, filter node relevan saja |
| 5 | Tidak ada rate limiting / validasi input | Rate limiter 30 req/menit, validasi prompt max 500 karakter |
| 6 | CORS terbuka ke semua origin | Batasi ke localhost:5678 dan n8n:5678 |
| 7 | Timeout workflow builder di n8n 90 detik | Naikkan ke 180 detik |
| 8 | LLM buat node dengan nama duplikat | Auto-dedup: tambah suffix angka jika nama sama |

---

## Cara Kerja Sistem Lengkap

```
┌─────────────────────────────────────────────────────────────────┐
│                        SAAT STARTUP                             │
│                                                                  │
│  1. init_registry()                                             │
│     Login ke n8n → ambil /types/nodes.json → 912 node di cache │
│     (fallback: pakai nodes_catalog.py jika n8n belum siap)     │
│                                                                  │
│  2. init_embeddings()  [background, tidak blokir startup]       │
│     Ambil 912 node → minta Ollama (nomic-embed-text) buat       │
│     vektor tiap node → simpan ke /app/data/embeddings_cache.json│
│     Restart berikutnya: load dari cache → langsung siap         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      SAAT ADA REQUEST                           │
│                                                                  │
│  User: "buatkan workflow sistem tiket IT kirim notif Slack"     │
│     │                                                            │
│     ▼                                                            │
│  find_relevant_nodes(prompt)                                    │
│     │                                                            │
│     ├─ Embedding siap?                                          │
│     │   YA: Ollama ubah prompt jadi vektor                     │
│     │       Hitung kemiripan dengan 912 vektor node            │
│     │       "sistem tiket" → ServiceNow ✓ (makna mirip)        │
│     │       Ambil top-15 node paling mirip                      │
│     │   TIDAK: fallback ke text search (kata per kata)          │
│     │                                                            │
│     ▼                                                            │
│  System prompt = "Node tersedia: ServiceNow, Slack, ..."        │
│     │                                                            │
│     ▼                                                            │
│  LLM (Ollama llama3.2:3b / Mistika) generate JSON workflow     │
│     │                                                            │
│     ▼                                                            │
│  extract_json_from_response() → parse → validasi → buat di n8n │
└─────────────────────────────────────────────────────────────────┘
```

---

## File yang Dibuat atau Diubah

### `services/mst-agent/` — Agent Service Python (FastAPI)

```
services/mst-agent/
├── app/
│   ├── nodes_registry.py        ← BARU: ambil node dari n8n saat startup
│   ├── embedding_search.py      ← BARU: semantic search dengan vektor Ollama
│   ├── config.py                ← DIUBAH: tambah n8n_admin_email, n8n_admin_password
│   ├── main.py                  ← DIUBAH: init registry + embedding, rate limiting, CORS
│   └── routers/
│       ├── plan.py              ← DIUBAH: semantic search, JSON extractor, validasi input
│       └── workflow_builder.py  ← DIUBAH: semantic search, dedup node, validasi node type
```

#### `nodes_registry.py` — Node Registry (BARU)
- Login ke n8n dengan akun admin (`/rest/login`)
- Fetch semua node dari `/types/nodes.json` (912+ node)
- Simpan di memori sebagai cache
- Fallback ke `nodes_catalog.py` (73 node statis) jika n8n belum siap

#### `embedding_search.py` — Semantic Search (BARU)
- Generate embedding untuk setiap node menggunakan `nomic-embed-text` via Ollama
- Simpan hasil ke `/app/data/embeddings_cache.json` agar tidak perlu generate ulang
- Saat ada prompt: embed prompt → hitung cosine similarity → ambil top-15 node
- Fallback ke text search jika embedding belum siap

#### `config.py` — Konfigurasi (DIUBAH)
Tambahan:
```python
n8n_admin_email: str = ""      # dari N8N_ADMIN_EMAIL di .env
n8n_admin_password: str = ""   # dari N8N_ADMIN_PASSWORD di .env
```

#### `main.py` — Entry Point FastAPI (DIUBAH)
- Panggil `init_registry()` saat startup
- Jalankan `init_embeddings()` di background (tidak blokir startup)
- Rate limiting: 30 request/menit per IP address
- CORS: hanya izinkan `localhost:5678` dan `n8n:5678`
- Sembunyikan `/docs` dan `/redoc` di production (`DEBUG=false`)

#### `routers/plan.py` — Endpoint Planner (DIUBAH)
- Ganti keyword map hardcoded → `find_relevant_nodes()` (semantic search)
- Tambah `extract_json_from_response()`: ekstrak JSON dari respons LLM yang berisi teks ekstra
- Tambah `filter_relevant_nodes()` sebagai text-search fallback
- Validasi: prompt tidak boleh kosong, maksimal 500 karakter

#### `routers/workflow_builder.py` — Endpoint Builder (DIUBAH)
- Pakai `find_relevant_nodes()` untuk pilih node relevan
- Auto-dedup nama node yang sama (suffix angka)
- Validasi node type: harus sesuai pola `n8n-nodes-base.*` atau `@n8n/*`
- Pakai registry live (`get_catalog()`) bukan static catalog

---

### `deploy/phase-0/` — Konfigurasi Docker

```
deploy/phase-0/
├── .env                        ← DIUBAH: switch Ollama, tambah admin credentials
└── deploy-custom-nodes.ps1     ← DIUBAH: tambah chat-hub-title.service.js
```

#### `.env` — Environment Variables (DIUBAH)
```ini
# LLM Backend: switch dari Mistika ke Ollama (tidak perlu VPN)
MISTIKA_BASE_URL=http://host.docker.internal:11434/v1
MISTIKA_API_KEY=ollama
MISTIKA_MODEL=llama3.2:3b
MISTIKA_CHAT_PATH=/chat/completions
MISTIKA_AUTH_HEADER=Authorization

# Untuk kembali ke Mistika (saat VPN aktif):
# MISTIKA_BASE_URL=https://misstika.mst.co.id/llm-router
# MISTIKA_API_KEY=sk-...
# MISTIKA_MODEL=
# MISTIKA_CHAT_PATH=/chat/streamchat
# MISTIKA_AUTH_HEADER=x-api-key

# Admin credentials untuk node registry
N8N_ADMIN_EMAIL=admin@mst.co.id
N8N_ADMIN_PASSWORD=MstAdmin2024#
```

#### `deploy-custom-nodes.ps1` — Deploy Script (DIUBAH)
Tambahan: `chat-hub-title.service.js` masuk ke daftar file yang di-copy otomatis.

---

### `packages/cli/src/modules/chat-hub/` — n8n Chat Hub (TypeScript)

```
packages/cli/src/modules/chat-hub/
├── mst-agent.service.ts         ← DIUBAH: timeout 90s → 180s
├── chat-hub-execution.service.ts← DIUBAH: debug logging, error handling
└── chat-hub-title.service.ts    ← DIUBAH: debug logging
```

#### `mst-agent.service.ts` (DIUBAH)
- Timeout workflow builder: 90.000ms → 180.000ms
- Mencegah error timeout saat LLM lambat generate JSON

#### `chat-hub-execution.service.ts` (DIUBAH)
- Tambah debug logging di `extractErrorMessage()` untuk trace error
- Type safety di akses `nodeRun.error`

#### `chat-hub-title.service.ts` (DIUBAH)
- Tambah debug logging di `runTitleWorkflowAndGetTitle()` untuk trace error

---

### Ollama — LLM Lokal

Model yang didownload:
| Model | Ukuran | Fungsi |
|-------|--------|--------|
| `llama3.2:3b` | 2.0 GB | Chat LLM: generate workflow JSON |
| `nomic-embed-text` | ~274 MB | Embedding: ubah teks jadi vektor untuk pencarian semantik |

---

## Cara Deploy Ulang (setelah `docker compose up -d`)

> **Penting:** `docker compose up -d` membuat ulang container dari image.
> File yang di-copy manual ke container akan hilang. Selalu jalankan
> script ini setelah `docker compose up -d`.

```powershell
# Dari folder deploy/phase-0:
.\deploy-custom-nodes.ps1

# Lalu copy file agent service:
$base = "C:\Users\Acer\n8n-Docker\services\mst-agent"
$files = @(
    "app/nodes_registry.py",
    "app/embedding_search.py",
    "app/config.py",
    "app/main.py",
    "app/routers/plan.py",
    "app/routers/workflow_builder.py"
)
foreach ($f in $files) {
    docker cp "$base/$f" "mst-agent-service:/app/$f"
    Write-Host "OK: $f"
}
docker restart mst-agent-service
```

---

## Cek Status Sistem

```powershell
# Health check — nodes_loaded harus > 73 (artinya dapat dari n8n)
Invoke-RestMethod http://localhost:8001/health

# Cek log embedding (pertama kali ~30 menit, berikutnya instan dari cache)
docker logs mst-agent-service 2>&1 | Select-String "Embedding|NodeRegistry"
```

**Arti `nodes_loaded`:**
- `912` (atau lebih) = berhasil ambil dari n8n ✓
- `73` = fallback ke static catalog (n8n belum siap saat agent start)

---

## Troubleshooting

**Embedding tidak jalan / nodes_loaded = 73**
```powershell
docker restart mst-agent-service
# Tunggu 10 detik, cek lagi
Invoke-RestMethod http://localhost:8001/health
```

**Embedding lama (>30 menit) pertama kali**
- Normal untuk 912 node
- Setelah selesai, cache disimpan → restart berikutnya instan
- Cek progress: `docker logs mst-agent-service 2>&1 | Select-String "Progress"`

**Kembali ke Mistika saat VPN aktif**
1. Edit `deploy/phase-0/.env` — ganti 5 baris MISTIKA_*
2. `docker compose --env-file .env up -d`
3. Jalankan deploy script di atas
4. Embedding tetap pakai Ollama (tidak berubah)
