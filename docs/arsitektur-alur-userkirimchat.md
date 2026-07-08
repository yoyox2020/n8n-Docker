# Arsitektur Alur: User Kirim Chat → Respons Diterima

Dokumen ini menjelaskan apa yang terjadi secara teknis dari saat user mengetik
pesan di chat n8n hingga respons muncul di layar — termasuk perbedaan alur
untuk chat biasa vs permintaan buat workflow.

---

## Gambaran Besar

```
┌──────────────┐         WebSocket/SSE (Push)        ┌──────────────┐
│  Browser     │◄────────────────────────────────────│  n8n Server  │
│  (Vue/React) │────── POST /chat/message ───────────►│  (Express)   │
└──────────────┘                                      └──────┬───────┘
                                                             │
                                    ┌────────────────────────▼────────────────────────┐
                                    │           chat-hub.service.ts                    │
                                    │                                                   │
                                    │  1. Terima pesan user                             │
                                    │  2. isWorkflowRequest()? → cek kata kunci        │
                                    │     "buatkan workflow", "buat workflow", dll      │
                                    └────────┬──────────────────┬──────────────────────┘
                                             │ YA               │ TIDAK
                              ┌──────────────▼───┐   ┌──────────▼──────────────┐
                              │ handleAgentWorkflow│   │ executeChatWorkflow     │
                              │ Request()          │   │ WithCleanup()           │
                              │ (Agent Service)    │   │ (LLM biasa / n8n flow)  │
                              └──────────────┬────┘   └─────────────────────────┘
                                             │
                                             ▼
                              (lihat detail alur di bawah)
```

---

## Alur Detail: Permintaan Buat Workflow

Dipanggil ketika pesan user mengandung kata seperti "buatkan workflow".

```
┌─────────────────────────────────────────────────────────────────────┐
│  handleAgentWorkflowRequest()  [chat-hub.service.ts]                │
│                                                                      │
│  A. startExecution()                                                 │
│     → Kirim event ke browser: ExecutionBegin                        │
│     → Browser: tampilkan indikator loading                          │
│                                                                      │
│  B. startStream()                                                    │
│     → Kirim event ke browser: StreamBegin                           │
│     → Browser: siapkan bubble chat AI (masih kosong)                │
│                                                                      │
│  C. buildWorkflow(message)    [mst-agent.service.ts]                │
│     → POST http://mst-agent:8001/workflow/build                     │
│     → Tunggu respons (timeout 180 detik)                            │
│                                                                      │
│         ┌─────────────────────────────────────────────────────┐     │
│         │  MST Agent Service (Python / FastAPI)               │     │
│         │                                                      │     │
│         │  1. find_relevant_nodes(prompt)                      │     │
│         │     - Text search: cocokkan kata dari prompt         │     │
│         │       ke node_type, display_name, description        │     │
│         │     - Embedding search: embed prompt → cosine sim    │     │
│         │       vs 849 vektor di DB → ambil top relevan        │     │
│         │     - Node hasil match diberi label ★ GUNAKAN INI    │     │
│         │                                                      │     │
│         │  2. LLM (Ollama llama3.2:3b / Mistika)              │     │
│         │     - Terima: system prompt + daftar node            │     │
│         │     - Generate: JSON task_graph                      │     │
│         │     - extract_json_from_response(): 3 lapis parser   │     │
│         │       (direct → markdown block → bracket search)     │     │
│         │                                                      │     │
│         │  3. Validasi node_type                               │     │
│         │     - Cek setiap node_type ada di catalog 849 node   │     │
│         │     - Tidak ada → HTTP 422 + pesan ramah ke user     │     │
│         │     - Ada → POST ke n8n API → workflow terbuat       │     │
│         └─────────────────────────────────────────────────────┘     │
│                                                                      │
│  D. sendChunk(content)                                              │
│     → Kirim event ke browser: StreamChunk                          │
│     → Browser: teks muncul di bubble chat (efek ketik)             │
│                                                                      │
│  E. endStream('success')                                            │
│     → Kirim event ke browser: StreamEnd                            │
│     → Browser: bubble selesai, tidak loading lagi                  │
│                                                                      │
│  F. endExecution('success')                                         │
│     → Kirim event ke browser: ExecutionEnd                         │
│     → Browser: selesai, tidak ada notifikasi tambahan              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Event Push ke Browser dan Artinya

Komunikasi dari server ke browser menggunakan WebSocket / SSE (Server-Sent Events).
Setiap event punya efek berbeda di UI.

| Event dari Server       | Aksi di Browser                                     |
|-------------------------|-----------------------------------------------------|
| `ExecutionBegin`        | Tampilkan indikator loading, nonaktifkan input chat |
| `StreamBegin`           | Buat bubble chat AI baru (masih kosong)             |
| `StreamChunk`           | Append teks ke bubble — efek mengetik satu per satu |
| `StreamEnd (success)`   | Bubble selesai, tidak loading lagi                  |
| `StreamEnd (error)`     | Bubble ditandai error (warna merah/berbeda)         |
| `ExecutionEnd (success)`| Selesai normal, aktifkan kembali input chat         |
| `ExecutionEnd (error)`  | **Toast "Unknown error" muncul** ← lihat catatan   |

> **Catatan `ExecutionEnd (error)`:** Status `'error'` di sini diartikan browser
> sebagai "sistem gagal" — browser menampilkan toast generic karena tidak tahu
> isi pesan errornya. Berbeda dengan isi bubble yang bisa berupa teks error ramah.

---

## Kenapa Dulu Muncul "Unknown error" Toast

Sebelum perbaikan, alur saat `buildWorkflow()` gagal adalah:

```
❌ Alur LAMA:

  buildWorkflow() → GAGAL (HTTP 422)
       │
       ▼
  catch (error)
       │
       ├─ log error
       │
       └─ endExecution('error')   ← langsung ke sini
                                     tanpa sendChunk() dulu
       │
       ▼
  Browser terima ExecutionEnd { status: 'error' }
  Bubble chat KOSONG — tidak ada teks yang pernah dikirim
       │
       ▼
  Browser tidak tahu apa yang salah
       │
       ▼
  Tampilkan toast: "Unknown error — Execution failed"
```

**Masalahnya:** `endExecution('error')` langsung dipanggil tanpa terlebih dahulu
mengirim isi pesan error ke bubble chat via `sendChunk()`.

---

## Setelah Perbaikan

Perubahan dilakukan di dua tempat:

### 1. `mst-agent.service.ts` — Parse detail dari respons error

FastAPI mengirim error dalam format JSON: `{"detail": "Maaf, node..."}`.
Sebelumnya, seluruh teks mentah diteruskan sebagai error message.
Sekarang field `detail` diambil langsung.

```
buildWorkflow() → HTTP 422
    body: {"detail": "Maaf, node berikut belum ada di n8n..."}
       │
       ▼
  Parse JSON → ambil json.detail
       │
       ▼
  throw new Error("Maaf, node berikut belum ada di n8n...")
```

### 2. `chat-hub.service.js` — Kirim teks ke bubble sebelum end

```
✅ Alur BARU:

  buildWorkflow() → GAGAL
       │
       ▼
  catch (error) → errorMsg = "Maaf, node berikut belum ada..."
       │
       ▼
  Cek: apakah errorMsg mulai dengan "Maaf,"?
    YA  → gunakan langsung (sudah ramah untuk user)
    TIDAK → bungkus: "Maaf, gagal membuat workflow...\n\n_Error: ..._"
       │
       ▼
  createAIMessage(errContent)   ← simpan ke DB
       │
       ▼
  sendChunk(errContent)         ← bubble chat terisi teks error
       │
       ▼
  endStream('error')            ← bubble selesai
       │
       ▼
  endExecution('success')       ← ← ← KUNCI: kirim 'success'
       │                                      bukan 'error'
       ▼
  Browser: bubble menampilkan pesan error dengan jelas
           TIDAK ada toast "Unknown error"
```

**Kenapa `endExecution('success')` bukan `'error'`?**

Karena `'error'` pada `endExecution` berarti "proses stream gagal secara sistem"
— browser merespons dengan toast karena tidak tahu apa yang terjadi. Padahal
dalam kasus ini *stream berjalan normal* — pesan berhasil terkirim, hanya
*isinya* adalah informasi error untuk user. Dari sisi protokol streaming,
semuanya sukses. Jadi status dikirim `'success'` agar browser tidak menampilkan
toast tambahan.

---

## File yang Terlibat

| File | Lokasi | Peran |
|------|--------|-------|
| `chat-hub.service.ts` | `packages/cli/src/modules/chat-hub/` | Routing pesan, orkestrasi alur |
| `mst-agent.service.ts` | `packages/cli/src/modules/chat-hub/` | Komunikasi ke Agent Service, parse error |
| `chat-stream.service.ts` | `packages/cli/src/modules/chat-hub/` | Kirim event push ke browser |
| `embedding_search.py` | `services/mst-agent/app/` | Cari node relevan secara semantik |
| `workflow_builder.py` | `services/mst-agent/app/routers/` | Bangun workflow, validasi node |
| `node_embeddings` | PostgreSQL DB (tabel) | Simpan 849 vektor node n8n |
