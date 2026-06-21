# Phase 3 — Status Implementasi

> Chat To Workflow — user bisa generate workflow dari natural language.

---

## Ringkasan

| Kategori | Status |
|----------|--------|
| Agent Builder UI | ❌ Belum ada |
| Workflow Generator | ❌ Belum ada |
| Canvas Integration | ❌ Belum ada |
| Workflow Import Engine | ❌ Belum ada |

**Phase 3 seluruhnya belum dimulai.**

---

## Ketergantungan

Phase 3 membutuhkan Phase 2 selesai:

```
Phase 2 (Agent Service + Planner)
    ↓
Phase 3 (Chat → Workflow → Canvas)
```

---

## 1. Flow Lengkap

Berdasarkan roadmap:

```
User mengetik prompt
    ↓
Planner (Phase 2) → Task Graph
    ↓
Workflow Generator
    ↓
n8n Workflow JSON
    ↓
Import ke MST Workflow
    ↓
Canvas terbuka dengan workflow siap pakai
```

---

## 2. Contoh End-to-End

**Input user:**
> "When invoice email arrives, save attachment to Google Drive and send WhatsApp notification."

**Task Graph (dari Planner):**
```
Email Trigger
    ↓
Extract Attachment
    ↓
Upload Drive
    ↓
Send WhatsApp
```

**Output:** n8n Workflow JSON yang langsung diimport ke canvas editor.

---

## 3. Workflow Generator

Komponen ini ada di dalam `agent-service` (Phase 2) tapi berinteraksi dengan n8n frontend.

Tugasnya: mengkonversi Task Graph → n8n Workflow JSON format.

**n8n Workflow JSON format:**
```json
{
  "name": "Invoice Processing",
  "nodes": [
    { "type": "n8n-nodes-base.emailTrigger", "name": "Email Trigger", ... },
    { "type": "n8n-nodes-base.googleDrive", "name": "Upload Drive", ... }
  ],
  "connections": {
    "Email Trigger": { "main": [[{ "node": "Upload Drive" }]] }
  }
}
```

Generator harus tahu schema semua n8n nodes untuk membuat JSON yang valid.

---

## 4. Agent Builder UI (di dalam n8n fork)

Modifikasi yang perlu dilakukan di fork n8n:

### 4.1 Panel Baru di Canvas

Tambah panel sidebar atau floating button dengan aksi:

| Aksi | Deskripsi |
|------|-----------|
| Generate | Kirim prompt ke Agent Service, import workflow ke canvas |
| Explain | Minta Agent Service jelaskan workflow yang aktif |
| Regenerate | Hapus workflow saat ini, generate ulang dari prompt |

### 4.2 Import Engine

Mekanisme untuk mengimport Workflow JSON dari Agent Service ke canvas tanpa reload halaman.

n8n sudah punya `useWorkflowHelpers` composable dengan fungsi import,
tapi perlu diintegrasikan dengan chat panel.

---

## 5. Komponen yang Butuh Dibuat di Fork n8n

| File | Deskripsi |
|------|-----------|
| `src/features/agent-builder/AgentBuilderPanel.vue` | Panel input prompt + tombol aksi |
| `src/features/agent-builder/agent-builder.store.ts` | State: loading, prompt, last result |
| `src/features/agent-builder/agent-builder.api.ts` | HTTP call ke Agent Service |
| `src/app/stores/canvas.store.ts` (modifikasi) | Tambah method importFromJson |

---

## Deliverables Phase 3

- [ ] Agent Builder Panel (UI di dalam n8n canvas)
- [ ] Workflow Generator (di agent-service, konversi Task Graph → JSON)
- [ ] Canvas Integration (import JSON langsung ke canvas)
- [ ] Workflow Import Engine (tanpa reload)

---

## Apakah Perlu Konfirmasi?

**Ya — sebelum memulai Phase 3:**

1. **Posisi UI:** Di mana panel Generate muncul? (sidebar kiri/kanan, floating button, atau modal?)
2. **Format komunikasi:** n8n frontend → Agent Service melalui REST API atau WebSocket?
3. **Autentikasi ke Agent Service:** Apakah Agent Service membutuhkan token n8n user?

---

> **Tidak ada perubahan kode dilakukan.** Dokumen ini hanya analisa scope Phase 3.
