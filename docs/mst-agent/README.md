# MST Agent Service

Layanan backend berbasis FastAPI yang menjadi otak AI di MST Workflow platform. Bertugas sebagai planner, memory manager, runtime decision engine, dan jembatan antara AI (Mistika/OpenRouter) dengan n8n workflow engine.

## Daftar Isi

- [Arsitektur](#arsitektur)
- [Struktur Direktori](#struktur-direktori)
- [Database](#database)
- [Konfigurasi](#konfigurasi)
- [API Endpoints](#api-endpoints)
- [Alur Kerja Utama](#alur-kerja-utama)
- [Deployment](#deployment)

---

## Arsitektur

```
Chat Hub (n8n frontend)
        │
        ▼
  n8n Workflow
        │
        ▼
MST Agent Node ──────► MST Agent Service (port 8001)
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
               Planner   Runtime    Approval
                    │         │         │
                    └────┬────┘         │
                         ▼             ▼
                    Mistika AI      PostgreSQL
                  (LLM Provider)  (agentdb)
                         │
                         ▼
                  n8n Public API
               (buat/simpan workflow)
```

Semua service berjalan dalam satu Docker network `mstworkflow` sehingga bisa saling berkomunikasi via nama service (tanpa IP/port publik).

---

## Struktur Direktori

```
services/mst-agent/
├── app/
│   ├── main.py              # Entry point FastAPI, setup CORS dan router
│   ├── config.py            # Settings dari environment variable
│   ├── database.py          # SQLAlchemy async engine dan session
│   ├── nodes_catalog.py     # Katalog node n8n yang dikenali planner
│   ├── models/
│   │   ├── memory.py        # Tabel agent_memory (histori percakapan)
│   │   ├── approval.py      # Tabel approval_requests
│   │   └── workflow_history.py  # Tabel workflow_history
│   └── routers/
│       ├── plan.py          # POST /plan — generate task graph
│       ├── workflow_builder.py  # POST /workflow/build — buat workflow di n8n
│       ├── runtime.py       # POST /runtime/decide — keputusan AI saat runtime
│       ├── approval.py      # GET/POST /approval — manajemen approval
│       ├── memory.py        # GET/POST/DELETE /memory — histori percakapan
│       └── tools.py         # GET /tools — daftar node yang tersedia
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Database

Database: `agentdb` di shared PostgreSQL (satu instance dengan n8n).

### Tabel

#### `agent_memory`
Menyimpan histori percakapan per user dan session. Digunakan sebagai konteks saat planner membuat plan baru.

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | integer | Primary key |
| user_id | varchar | ID user n8n |
| session_id | varchar | ID sesi percakapan (opsional) |
| role | varchar | `user` atau `assistant` |
| content | text | Isi pesan |
| meta | jsonb | Metadata tambahan |
| created_at | timestamptz | Waktu dibuat |

#### `approval_requests`
Menyimpan permintaan approval saat agent akan melakukan aksi berisiko tinggi.

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | varchar(64) | UUID, primary key |
| user_id | varchar | ID user yang meminta |
| execution_id | varchar | ID eksekusi workflow n8n |
| workflow_id | varchar | ID workflow n8n |
| node_name | varchar | Nama node yang meminta approval |
| action_description | text | Deskripsi aksi yang akan dilakukan |
| risk_level | varchar | `low` / `medium` / `high` / `critical` |
| context | jsonb | Data konteks tambahan |
| status | varchar | `pending` / `approved` / `rejected` / `expired` |
| response_note | text | Catatan dari user saat merespons |
| requested_at | timestamptz | Waktu permintaan |
| responded_at | timestamptz | Waktu respons user |

#### `workflow_history`
Menyimpan setiap workflow yang berhasil dibuat user via agent. Digunakan untuk sidebar "aktivitas terakhir".

| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | integer | Primary key |
| user_id | varchar | ID user pembuat |
| session_id | varchar | ID sesi |
| workflow_id | varchar | ID workflow di n8n |
| workflow_name | varchar | Nama workflow |
| workflow_url | text | URL langsung ke workflow di n8n |
| steps | jsonb | Daftar langkah (task graph) |
| original_prompt | text | Prompt asli dari user |
| created_at | timestamptz | Waktu dibuat |

---

## Konfigurasi

Semua konfigurasi dibaca dari environment variable (diset di `deploy/phase-0/.env`).

| Variable | Default | Keterangan |
|----------|---------|------------|
| `MISTIKA_BASE_URL` | `https://openrouter.ai/api/v1` | Base URL provider LLM |
| `MISTIKA_API_KEY` | — | API key provider LLM |
| `MISTIKA_MODEL` | `deepseek/deepseek-v4-flash` | Model yang digunakan |
| `MISTIKA_CHAT_PATH` | `/chat/completions` | Path endpoint chat |
| `MISTIKA_AUTH_HEADER` | `bearer` | Tipe auth: `bearer` atau `x-api-key` |
| `DATABASE_URL` | — | PostgreSQL connection string (dioverride compose) |
| `N8N_BASE_URL` | `http://n8n:5678` | URL n8n instance |
| `N8N_API_KEY` | — | API key n8n untuk buat workflow |
| `DEBUG` | `false` | Mode debug SQLAlchemy |

> `DATABASE_URL` dioverride langsung oleh `docker-compose.yml` menggunakan kredensial shared postgres. Tidak perlu diset manual.

---

## API Endpoints

Base URL: `http://localhost:8001`

Dokumentasi interaktif tersedia di: [http://localhost:8001/docs](http://localhost:8001/docs)

---

### Health

#### `GET /health`
Cek status service.

```json
{"status": "ok", "service": "mst-agent-service", "version": "2.0.0"}
```

---

### Plan — `/plan`

#### `POST /plan`
Generate **Task Graph** — daftar node n8n yang dibutuhkan untuk mengotomasi permintaan user.

**Request:**
```json
{
  "prompt": "Kirim email setiap kali ada row baru di Google Sheets",
  "user_id": "user-123",
  "session_id": "session-abc"
}
```

**Response:**
```json
{
  "summary": "Monitor Google Sheets dan kirim notifikasi email",
  "intent": "monitor_sheets_send_email",
  "task_graph": [
    {
      "step": 1,
      "node_type": "n8n-nodes-base.googleSheetsTrigger",
      "display_name": "Google Sheets Trigger",
      "description": "Trigger saat ada row baru di spreadsheet"
    },
    {
      "step": 2,
      "node_type": "n8n-nodes-base.emailSend",
      "display_name": "Send Email",
      "description": "Kirim email notifikasi dengan data dari Sheets"
    }
  ]
}
```

---

### Workflow Builder — `/workflow`

#### `POST /workflow/build`
Generate task graph **dan langsung buat workflow di n8n** via Public API.

**Request:**
```json
{
  "prompt": "Buat workflow untuk backup database setiap malam",
  "user_id": "user-123",
  "session_id": "session-abc"
}
```

**Response:**
```json
{
  "message": "Workflow berhasil dibuat! Berisi 3 langkah.",
  "workflow_name": "Backup database setiap malam",
  "workflow_id": "abc123",
  "workflow_url": "http://localhost:5678/workflow/abc123",
  "steps": [
    {"step": 1, "node": "Schedule Trigger", "description": "..."},
    {"step": 2, "node": "Postgres", "description": "..."},
    {"step": 3, "node": "Send Email", "description": "..."}
  ]
}
```

---

### Runtime Decision — `/runtime`

#### `POST /runtime/decide`
Dipakai oleh **MST Agent Node** di n8n saat workflow berjalan dan perlu keputusan AI.

LLM mengevaluasi instruksi dan memutuskan:
- `decided` → aksi langsung dijalankan (risiko low/medium)
- `needs_approval` → aksi ditahan, menunggu persetujuan user (risiko high/critical)
- `error` → tidak dapat memutuskan

**Request:**
```json
{
  "user_id": "user-123",
  "execution_id": "exec-456",
  "workflow_id": "wf-789",
  "node_name": "MST Agent Node",
  "instruction": "Hapus semua record di tabel orders yang lebih dari 1 tahun",
  "input_data": {"table": "orders", "cutoff_date": "2024-01-01"},
  "available_actions": ["delete_records", "archive_records", "skip"]
}
```

**Response (needs_approval):**
```json
{
  "output": "needs_approval",
  "chosen_action": "delete_records",
  "reason": "Menghapus data produksi membutuhkan persetujuan",
  "risk_level": "high",
  "approval_id": "uuid-approval-id"
}
```

**Tabel risiko:**

| Risk Level | Contoh Aksi | Keputusan |
|------------|-------------|-----------|
| `low` | Baca data, kirim notifikasi | Langsung dijalankan |
| `medium` | Tulis data baru, update non-kritis | Langsung dijalankan |
| `high` | Hapus data, update produksi | Wajib approval |
| `critical` | Transaksi keuangan, ubah kredensial | Wajib approval |

---

### Approval — `/approval`

#### `GET /approval/{approval_id}`
Cek status approval. Dipakai Agent Node untuk polling sampai user merespons.

```json
{
  "id": "uuid-approval-id",
  "user_id": "user-123",
  "node_name": "MST Agent Node",
  "action_description": "Agent ingin menghapus 1.200 record dari tabel orders",
  "risk_level": "high",
  "status": "pending",
  "context": {...},
  "requested_at": "2025-01-01T10:00:00Z",
  "responded_at": null,
  "response_note": null
}
```

#### `POST /approval/{approval_id}/respond`
User approve atau reject permintaan agent.

**Request:**
```json
{
  "decision": "approved",
  "note": "Sudah dicek, boleh dilanjutkan"
}
```

#### `GET /approval/user/{user_id}?status=pending`
Daftar semua approval milik seorang user. Query param `status` opsional (`pending`, `approved`, `rejected`).

---

### Memory — `/memory`

#### `POST /memory/save`
Simpan satu turn percakapan.

```json
{
  "user_id": "user-123",
  "session_id": "session-abc",
  "role": "user",
  "content": "Tolong buat workflow untuk ..."
}
```

#### `GET /memory/{user_id}?session_id=abc&limit=20`
Ambil histori percakapan user, diurutkan dari yang terlama.

#### `GET /memory/{user_id}/last-activity`
Ambil aktivitas terakhir user — digunakan sidebar frontend untuk menampilkan:
- Workflow terakhir yang dibuat
- Approval yang masih menunggu

```json
{
  "user_id": "user-123",
  "recent_workflows": [
    {
      "workflow_id": "abc123",
      "workflow_name": "Backup harian",
      "workflow_url": "http://n8n:5678/workflow/abc123",
      "step_count": 3,
      "original_prompt": "buat backup database ...",
      "created_at": "2025-01-01T10:00:00Z"
    }
  ],
  "pending_approvals": [
    {
      "id": "uuid",
      "node_name": "MST Agent Node",
      "action_description": "Hapus 1.200 record",
      "risk_level": "high",
      "requested_at": "2025-01-01T09:55:00Z"
    }
  ]
}
```

#### `DELETE /memory/{user_id}`
Hapus seluruh histori percakapan user.

---

### Tools — `/tools`

#### `GET /tools`
Daftar node n8n yang dikenali oleh planner AI.

---

## Alur Kerja Utama

### 1. User minta buat workflow via Chat Hub

```
User → Chat Hub → n8n Workflow → POST /workflow/build
                                        │
                              LLM generate task graph
                                        │
                              POST ke n8n /api/v1/workflows
                                        │
                              Simpan ke workflow_history
                                        │
                              Return URL workflow ← User
```

### 2. Agent Node butuh keputusan saat runtime

```
n8n Workflow berjalan
        │
MST Agent Node → POST /runtime/decide
                        │
              LLM evaluasi risiko
                        │
           ┌────────────┴────────────┐
        decided               needs_approval
           │                        │
  Lanjut ke output 1       Buat approval_request
                                    │
                         Agent Node polling GET /approval/{id}
                                    │
                         User buka notifikasi & respond
                                    │
                         POST /approval/{id}/respond
                                    │
                         Agent Node dapat hasil → lanjut/batal
```

---

## Deployment

Service ini dijalankan sebagai bagian dari stack `phase-0` bersama n8n dan PostgreSQL.

```bash
cd deploy/phase-0

# Pertama kali (atau setelah ada perubahan kode)
docker compose up -d --build

# Cek log
docker logs mst-agent-service -f

# Restart tanpa rebuild
docker compose restart mst-agent-service
```

**Catatan penting:**
- `DATABASE_URL` dioverride oleh `docker-compose.yml` — tidak perlu diset di `.env`
- Database `agentdb` dibuat otomatis saat postgres pertama kali dijalankan via `postgres-init/01-agent-db.sql`
- Tabel dibuat otomatis saat service startup (`init_db()` di lifespan)
- API docs tersedia di `http://localhost:8001/docs` saat service running
