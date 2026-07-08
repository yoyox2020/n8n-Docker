# Cross-Session Memory — Dokumentasi Implementasi

**Tanggal implementasi:** 2026-06-29  
**Status:** ✅ Selesai & terdeploy  
**Scope:** MST Agent Service (Python FastAPI)

---

## Masalah yang Dipecahkan

Sebelum fitur ini, sistem sudah memiliki:

| Komponen | Fungsi |
|----------|--------|
| `AgentMemory` | Menyimpan 10 pesan terakhir per sesi — LLM ingat konteks *dalam* satu sesi |
| `WorkflowHistory` | Mencatat setiap workflow yang pernah dibuat user (nama, prompt, kapan) |
| `/memory/{user_id}/last-activity` | Endpoint untuk sidebar frontend menampilkan aktivitas terakhir |

**Yang tidak berjalan:** Ketika user membuka sesi baru, LLM memulai dari kosong meskipun data `WorkflowHistory` sudah tersimpan di database. LLM tidak bisa berkata _"sebelumnya kamu pernah buat workflow Slack, mau yang serupa?"_

---

## Solusi yang Diterapkan

Saat LLM dipanggil untuk membangun workflow atau plan, riwayat workflow user diambil dari database dan disisipkan ke **awal system prompt** sebagai blok konteks.

```
[Riwayat Workflow User] ← baru (cross-session)
        ↓
[Instruksi Utama LLM + Katalog Node]
        ↓
[Chat History Sesi Ini] ← sudah ada sebelumnya (in-session)
        ↓
[Pesan User Saat Ini]
```

---

## File yang Dibuat / Diubah

### File Baru

#### `services/mst-agent/app/cross_session_memory.py`

Modul utama fitur ini. Bertanggung jawab satu hal: mengambil data `WorkflowHistory` dari database dan memformatnya menjadi teks konteks.

**Fungsi utama:**
```python
async def get_cross_session_context(
    user_id: str,
    db: AsyncSession,
    limit: int = 5,
) -> str
```

**Aturan desain:**
- Mengembalikan string kosong jika user belum punya riwayat → tidak mengubah prompt sama sekali
- Tidak pernah melempar exception → error di-log sebagai `WARNING`, fitur utama tidak terganggu
- Menampilkan maksimal 5 workflow terakhir (parameter `limit`)
- Setiap baris menampilkan: nama workflow, cuplikan prompt (maks 100 karakter), dan label waktu relatif dalam Bahasa Indonesia

**Contoh output yang dihasilkan:**
```
--- RIWAYAT WORKFLOW PENGGUNA ---
1. "Slack to Gmail" — prompt: "kirim notifikasi email ketika ada pesan Slack baru" (3 hari lalu)
2. "Webhook to Notion" — prompt: "simpan data dari webhook ke database Notion" (1 minggu lalu)
3. "Jadwal Email Mingguan" — prompt: "kirim laporan email setiap Senin pagi" (kemarin)
Gunakan riwayat ini jika relevan: rekomendasikan pola serupa, hindari duplikasi, atau tawarkan peningkatan dari workflow sebelumnya.
--- END RIWAYAT ---
```

---

### File yang Diubah

#### `services/mst-agent/app/routers/workflow_builder.py`

Penambahan di **2 tempat**:

**1. Fungsi `build_workflow()` — untuk workflow linear:**

```python
# Setelah system_prompt dibangun dari PLANNER_SYSTEM_PROMPT
if payload.user_id:
    cross_ctx = await get_cross_session_context(payload.user_id, db)
    if cross_ctx:
        system_prompt = cross_ctx + "\n\n" + system_prompt
```

Dipanggil ketika user meminta workflow biasa (bukan AI Agent), misalnya:  
_"buatkan workflow Slack ke Gmail"_

**2. Fungsi `build_agent_workflow()` — untuk AI Agent workflow:**

```python
# Setelah system_prompt dibangun dari AGENT_ANALYZER_PROMPT
if user_id:
    cross_ctx = await get_cross_session_context(user_id, db)
    if cross_ctx:
        system_prompt = cross_ctx + "\n\n" + system_prompt
```

Dipanggil ketika user meminta AI Agent, misalnya:  
_"buatkan agent AI yang bisa cari data di Google"_

---

#### `services/mst-agent/app/routers/plan.py`

Penambahan di **1 tempat**:

**Fungsi `create_plan()` — untuk planning workflow:**

```python
# Setelah system_prompt dibangun dari PLANNER_SYSTEM_PROMPT
if payload.user_id:
    cross_ctx = await get_cross_session_context(payload.user_id, db)
    if cross_ctx:
        system_prompt = cross_ctx + "\n\n" + system_prompt
```

Ini memastikan endpoint `/plan/` (yang menghasilkan task_graph tanpa langsung membuat workflow) juga mendapat konteks lintas-sesi.

---

## Alur Teknis End-to-End

```
User buka sesi baru → ketik "buatkan workflow seperti yang kemarin"
         ↓
chat-hub.service.ts → isWorkflowRequest() = true
         ↓
MstAgentService.buildWorkflow() → POST /workflow/build
         ↓
workflow_builder.py::build_workflow()
    ├── find_relevant_nodes(prompt)       ← embedding search
    ├── get_cross_session_context(user_id, db)  ← BARU: ambil riwayat
    │       ├── SELECT WorkflowHistory WHERE user_id = ? ORDER BY created_at DESC LIMIT 5
    │       └── Format → string teks konteks
    ├── system_prompt = [riwayat] + "\n\n" + [instruksi + katalog node]
    └── _call_mistika(messages)           ← LLM dengan konteks lengkap
```

---

## Cara Kerja Label Waktu Relatif

Fungsi `_format_relative_time(dt)` di `cross_session_memory.py`:

| Selisih | Label |
|---------|-------|
| 0 hari | "hari ini" |
| 1 hari | "kemarin" |
| 2–6 hari | "X hari lalu" |
| 7–29 hari | "X minggu lalu" |
| 30+ hari | "X bulan lalu" |

---

## Keamanan & Isolasi Data

- Riwayat di-query dengan filter `WHERE user_id = ?` → user hanya melihat riwayat mereka sendiri
- Konteks hanya diinjeksikan ke prompt LLM internal — tidak pernah dikirim ke frontend
- Jika query DB gagal (timeout, koneksi putus, dll): sistem tidak crash, cross-session context diabaikan, workflow tetap dibangun

---

## Yang Sudah Ada Sebelumnya (Tidak Diubah)

| Komponen | Lokasi | Status |
|----------|--------|--------|
| `AgentMemory` model | `app/models/memory.py` | Tidak berubah |
| `WorkflowHistory` model | `app/models/workflow_history.py` | Tidak berubah |
| In-session history (10 pesan) | `plan.py::_get_history()` | Tidak berubah |
| Endpoint last-activity (sidebar) | `memory.py::get_last_activity()` | Tidak berubah |
| Penyimpanan workflow ke history | `workflow_builder.py` (akhir fungsi) | Tidak berubah |

---

## Cara Test Manual

1. Buat 1–2 workflow via chat UI (misalnya: _"buatkan workflow Slack ke Gmail"_)
2. Tutup tab chat, buka sesi baru
3. Ketik: _"buatkan workflow seperti yang tadi"_ atau _"buat workflow baru untuk email"_
4. LLM seharusnya merespons dengan konteks yang menyebut nama workflow sebelumnya

**Verifikasi di log container:**
```bash
docker logs mst-agent-service -f
```
Tidak ada baris `WARNING cross_session_context: gagal` → query DB berhasil.

---

## Troubleshooting

| Gejala | Kemungkinan Penyebab | Cara Atasi |
|--------|----------------------|------------|
| LLM tidak menyebut riwayat sama sekali | `user_id` tidak dikirim dari frontend | Cek payload `POST /workflow/build` — pastikan `user_id` terisi |
| Log: `WARNING cross_session_context: gagal` | DB connection issue | Cek container postgres: `docker ps`, `docker logs phase-0-postgres-1` |
| Riwayat tidak muncul padahal sudah pernah buat | Workflow gagal tersimpan ke `WorkflowHistory` | Cek apakah request sebelumnya sukses (HTTP 200), cek tabel `workflow_history` di DB |
| LLM mengabaikan riwayat | Model kecil, konteks terlalu panjang | Kurangi `limit` dari 5 ke 3 di `get_cross_session_context()` |
