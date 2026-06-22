# Phase 4 — Agent Runtime: Implementasi & Fix

> Tanggal: 2026-06-22
> Branch: modifikasi
> Status: Implementasi selesai, siap test

---

## Ringkasan Perubahan

Sesi ini mengerjakan Phase 4 (Agent Runtime) dari roadmap secara penuh, sekaligus memperbaiki beberapa bug yang ditemukan saat testing.

---

## 1. Agent Service (C:\Users\Acer\n8n-mst-Agent)

### File Baru

#### `app/models/workflow_history.py`
Tabel baru untuk menyimpan setiap workflow yang berhasil dibuat user via chat.

| Kolom | Tipe | Keterangan |
|-------|------|-----------|
| user_id | String | Siapa yang membuat |
| workflow_id | String | ID workflow di n8n |
| workflow_name | String | Nama workflow |
| workflow_url | Text | Link langsung ke workflow |
| steps | JSONB | Detail langkah-langkah |
| original_prompt | Text | Prompt asli dari user |
| created_at | DateTime | Waktu dibuat |

#### `app/models/approval.py`
Tabel approval request — dipakai saat Agent Node menilai aksi terlalu berisiko dan membutuhkan persetujuan user sebelum dilanjutkan.

Status yang mungkin: `pending` → `approved` / `rejected` / `expired`

#### `app/routers/runtime.py`
Endpoint baru: `POST /runtime/decide`

Alur kerja:
```
Agent Node kirim konteks + instruksi + daftar aksi
        ↓
LLM analisa dan putuskan
        ↓
Risiko rendah/sedang → langsung "proceed"
Risiko tinggi/kritis → buat ApprovalRequest → kembalikan approval_id
Tidak bisa putuskan  → kembalikan "cannot_decide"
```

#### `app/routers/approval.py`
CRUD untuk approval:
- `GET  /approval/{id}` — cek status (dipakai Agent Node untuk polling)
- `POST /approval/{id}/respond` — user kirim keputusan (approved/rejected)
- `GET  /approval/user/{user_id}` — semua approval milik user

### File Dimodifikasi

#### `app/routers/memory.py`
Tambah endpoint: `GET /memory/{user_id}/last-activity`

Mengembalikan:
```json
{
  "recent_workflows": [...],   // 5 workflow terakhir yang dibuat
  "pending_approvals": [...]   // approval yang masih menunggu
}
```

Dipakai oleh sidebar frontend untuk menampilkan aktivitas user.

#### `app/routers/workflow_builder.py`
Fix: setelah workflow berhasil dibuat, simpan ke tabel `workflow_history` agar user bisa melihat riwayat pembuatan workflow.

#### `app/config.py`
Tambah konfigurasi untuk mendukung dua mode LLM:

```env
# Mode Mistika (production)
MISTIKA_BASE_URL=https://misstika.mst.co.id/llm-router
MISTIKA_CHAT_PATH=/chat/streamchat
MISTIKA_AUTH_HEADER=x-api-key

# Mode OpenRouter (testing sementara)
MISTIKA_BASE_URL=https://openrouter.ai/api/v1
MISTIKA_CHAT_PATH=/chat/completions
MISTIKA_AUTH_HEADER=Authorization
```

---

## 2. n8n Fork (packages/)

### File Baru

#### `packages/nodes-base/nodes/AgentMST/AgentMST.node.ts`
Custom n8n node baru: **MST Agent**

Cara kerja:
- Diletakkan di tengah workflow, bukan sebagai trigger
- Mengirim instruksi + data input ke Agent Service (`/runtime/decide`)
- Memiliki **3 output branch**:

| Output | Kapan aktif |
|--------|-------------|
| `decided` | AI berhasil memutuskan, aksi aman |
| `needs_approval` | AI nilai risiko tinggi, menunggu user setuju |
| `error` | AI tidak bisa memutuskan / error teknis |

Konfigurasi di node:
- **Instruksi untuk Agent** — deskripsi apa yang harus diputuskan
- **Aksi yang Tersedia** — daftar pilihan aksi untuk AI
- **URL Agent Service** — default: `http://mst-agent-service:8000`
- **User ID** — untuk notifikasi approval
- **Timeout Approval** — berapa detik menunggu (default 300 detik / 5 menit)

#### `packages/nodes-base/nodes/AgentMST/AgentMST.node.json`
Metadata node (kategori AI, alias untuk search).

### File Dimodifikasi

#### `packages/cli/src/modules/chat-hub/mst-agent.service.ts`
Tambah method-method baru:

| Method | Fungsi |
|--------|--------|
| `getApproval(id)` | Ambil detail satu approval |
| `respondApproval(id, decision, note)` | User approve atau reject |
| `listPendingApprovals(userId)` | Daftar approval yang pending |
| `getLastActivity(userId)` | Workflow terakhir + approval pending |

#### `packages/nodes-base/package.json`
Daftarkan `AgentMST` node agar n8n mengenalinya:
```json
"dist/nodes/AgentMST/AgentMST.node.js"
```

### File Baru di Frontend

#### `packages/frontend/editor-ui/src/features/ai/chatHub/activity.store.ts`
Pinia store untuk data aktivitas user. Fetch dari `GET /memory/{user_id}/last-activity`.

#### `packages/frontend/editor-ui/src/features/ai/chatHub/components/ActivitySidebar.vue`
Komponen sidebar kiri Chat Hub, tampil di bawah menu New Chat / Personal Agents / Workflow Agents.

Menampilkan:
1. **Approval pending** — tombol Setuju / Tolak langsung dari sidebar
2. **Workflow terakhir** — 5 workflow terbaru dengan link ke editor

---

## 3. Fix: Mistika Credential (x-api-key)

### Masalah
Credential `MisikaAiApi` menggunakan `Authorization: Bearer` dan URL OpenRouter sebagai default. Mistika resmi menggunakan header berbeda.

### Solusi
File: `packages/@n8n/nodes-langchain/credentials/MisikaAiApi.credentials.ts`

| Field | Sebelum | Sesudah |
|-------|---------|---------|
| Auth header | `Authorization: Bearer {key}` | `x-api-key: {key}` |
| Base URL default | `https://openrouter.ai/api/v1` | `https://misstika.mst.co.id/llm-router` |
| Chat Path | (tidak ada) | `/chat/streamchat` (field baru) |

### Cara isi credential untuk Mistika resmi
```
API Key   : sk-XeY...
Base URL  : https://misstika.mst.co.id/llm-router
Chat Path : /chat/streamchat
```

### Cara isi credential untuk OpenRouter (sementara)
```
API Key   : sk-or-v1-...
Base URL  : https://openrouter.ai/api/v1
Chat Path : /chat/completions
```

---

## 4. Fix: "Unsupported model provider" di Chat Hub

### Masalah
Error `Server error: Unsupported model provider` muncul saat user memilih Mistika-AI di Chat Hub. Penyebab: container Docker masih menggunakan image lama yang belum memiliki `case 'misikaAi'` di `chat-hub-workflow.service.ts`.

### Solusi
Copy file yang sudah diperbarui ke dalam container yang berjalan.

Sudah diintegrasikan ke dalam deploy script — setiap kali `deploy-custom-nodes.ps1` / `.sh` dijalankan, file `chat-hub-workflow.service.js` ikut ter-copy otomatis.

---

## 5. Fix: "Chat session not found"

### Masalah
Error muncul saat user memilih model di dropdown sebelum sesi chat dibuat.

### Solusi (cara pakai yang benar)
1. Klik **"New Chat"** terlebih dahulu
2. Pilih model di dropdown
3. Mulai ketik pesan

Jangan pilih model sebelum sesi chat terbentuk.

---

## 6. Deploy Script Update

### Windows: `deploy-custom-nodes.ps1`
### Linux: `deploy-custom-nodes.sh`

Lokasi: `deploy/phase-0/`

Kedua script sekarang otomatis meng-copy:
- `AgentMST.node.js` + `AgentMST.node.json`
- Node-definitions untuk AgentMST
- `package.json` (registrasi node)
- `chat-hub-workflow.service.js` (misikaAi fix)
- `chat-hub.service.js`
- `mst-agent.service.js`

### Cara pakai setelah `docker compose up -d`

**Windows:**
```powershell
cd deploy\phase-0
.\deploy-custom-nodes.ps1
```

**Linux:**
```bash
cd deploy/phase-0
./deploy-custom-nodes.sh
```

### Cara pakai setelah ubah kode

```powershell
# 1. Build paket yang berubah
cd packages\nodes-base && pnpm build   # jika ubah node
cd packages\cli && pnpm build          # jika ubah chat-hub service

# 2. Deploy ke container
cd deploy\phase-0
.\deploy-custom-nodes.ps1
```

---

## 7. Known Issues

### Docker build gagal (wa-sqlite)
**Error:** `ECONNRESET` saat download wa-sqlite dari GitHub CDN saat `docker compose up --build`

**Workaround:** Gunakan `docker compose up -d` (tanpa `--build`) lalu jalankan `deploy-custom-nodes.ps1`.

### Mistika model list kosong di dropdown
**Penyebab:** `misikaAi: { models: [] }` di `api-types/src/chat-hub.ts` — Mistika tidak punya `/models` endpoint standar.

**Workaround:** Setelah pilih credential Mistika-AI, model name bisa diketik manual atau pilih dari list yang muncul setelah credential terkonfigurasi.

---

## Catatan Deployment ke Server Linux

Saat migrasi ke server Linux:
1. Clone repo ke server
2. Install dependencies: `pnpm install`
3. Build: `pnpm build` (atau hanya paket yang diperlukan)
4. `docker compose up -d`
5. `chmod +x deploy/phase-0/deploy-custom-nodes.sh`
6. `./deploy/phase-0/deploy-custom-nodes.sh`
7. Update `.env` Agent Service dengan API key dan URL yang sesuai

---

## Referensi File Terkait

| Dokumen | Isi |
|---------|-----|
| [phase-2-chat-hub-integrasi.md](./phase-2-chat-hub-integrasi.md) | Arsitektur integrasi Chat Hub ↔ Agent Service |
| [phase-status-phase-2.md](./phase-status-phase-2.md) | Status Phase 2 |
| [phase-status-phase-4.md](./phase-status-phase-4.md) | Status Phase 4 (lama — sebelum implementasi) |
