# Phase 2 — Status Implementasi

> Agent Service — external AI service untuk planning, memory, dan workflow generation.

---

## Ringkasan

| Kategori | Status |
|----------|--------|
| Agent Service repository | ❌ Belum ada |
| FastAPI API layer | ❌ Belum ada |
| Planner | ❌ Belum ada |
| Memory | ❌ Belum ada |
| Tool Registry | ❌ Belum ada |

**Phase 2 seluruhnya belum dimulai.**

---

## Scope

Phase 2 adalah service terpisah — **bukan** modifikasi fork n8n.
Agent Service berjalan sebagai microservice independen yang berkomunikasi dengan n8n via API.

---

## 1. Technology Stack

Berdasarkan roadmap:

| Komponen | Teknologi |
|----------|-----------|
| API | FastAPI (Python) |
| Database | PostgreSQL |
| Cache | Redis |

---

## 2. Struktur Repository

Berdasarkan roadmap:

```
agent-service/
├── api/                  # FastAPI endpoints
├── planner/              # Konversi prompt → Task Graph
├── memory/               # Conversation + Workflow history
├── runtime/              # Eksekusi runtime decision
├── tools/                # Tool definitions (Gmail, Slack, dll)
└── workflow-generator/   # Konversi Task Graph → n8n JSON
```

Repository ini akan terpisah dari fork n8n.

---

## 3. Planner

Tugas Planner:

- **Input:** Natural language prompt dari user
- **Output:** Task Graph (DAG berisi node-node tugas)

**Contoh dari roadmap:**

Prompt: `"Save invoice attachment to Google Drive and notify WhatsApp"`

Task Graph:
```
Email Trigger
    ↓
Extract Attachment
    ↓
Upload Drive
    ↓
Send WhatsApp
```

**Belum ada implementasi.** Butuh:
1. Integrasi dengan Mistika LLM untuk reasoning
2. Prompt engineering untuk konversi kalimat → task graph
3. Schema validasi task graph

---

## 4. Memory

Menyimpan:
- Conversation History (konteks percakapan per user)
- Workflow History (workflow apa yang pernah dibuat/dieksekusi)
- Planning History (keputusan planner sebelumnya)

**Belum ada implementasi.** Butuh:
1. Schema database PostgreSQL untuk ketiga tipe memori
2. Redis cache untuk session aktif
3. API endpoint GET/POST/DELETE memory

---

## 5. Tool Registry

Tools yang didefinisikan di roadmap:

| Tool | Status |
|------|--------|
| Gmail | ❌ Belum |
| WhatsApp | ❌ Belum |
| HTTP | ❌ Belum |
| PostgreSQL | ❌ Belum |
| Jira | ❌ Belum |
| Slack | ❌ Belum |

Tool Registry adalah katalog capabilities yang bisa digunakan planner
saat membuat task graph.

---

## Deliverables Phase 2

- [ ] Repository `agent-service` dibuat
- [ ] Planner Service (LLM → Task Graph)
- [ ] Memory Service (conversation + workflow history)
- [ ] Tool Registry (definisi tools yang tersedia)
- [ ] Runtime Foundation (API gateway ke n8n)

---

## Ketergantungan

Phase 2 dapat dimulai **paralel** dengan Phase 1 karena merupakan service terpisah.
Namun Phase 3 (Chat To Workflow) membutuhkan Phase 2 selesai.

---

## Apakah Perlu Konfirmasi?

**Ya — sebelum memulai Phase 2, perlu konfirmasi:**

1. **Bahasa pemrograman:** Apakah benar menggunakan Python + FastAPI, atau ada preferensi lain?
2. **Lokasi repository:** Apakah `agent-service/` di dalam monorepo n8n ini, atau repository terpisah?
3. **Mistika integration:** Bagaimana cara agent service berkomunikasi dengan Mistika? (API key? internal?)
4. **Prioritas:** Apakah Phase 1 harus selesai penuh dulu sebelum mulai Phase 2?

---

> **Tidak ada perubahan kode dilakukan.** Dokumen ini hanya analisa scope Phase 2.
