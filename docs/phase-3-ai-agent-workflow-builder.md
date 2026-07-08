# Phase 3 — AI Agent Workflow Builder

Dokumen ini menjelaskan implementasi fitur **build AI Agent workflow otomatis**
dari prompt user. Dibuat agar developer bisa menelusuri alur, melacak error,
dan memahami keputusan desain tanpa perlu membaca kode dari awal.

---

## Daftar Isi

1. [Gambaran Fitur](#gambaran-fitur)
2. [File yang Diubah](#file-yang-diubah)
3. [Alur Teknis Lengkap](#alur-teknis-lengkap)
4. [Struktur Workflow n8n yang Dihasilkan](#struktur-workflow-n8n-yang-dihasilkan)
5. [Contoh Prompt dan Hasilnya](#contoh-prompt-dan-hasilnya)
6. [Logika Deteksi Agent Request](#logika-deteksi-agent-request)
7. [LLM Prompt yang Dipakai](#llm-prompt-yang-dipakai)
8. [Fallback dan Validasi](#fallback-dan-validasi)
9. [Panduan Tracing Error](#panduan-tracing-error)

---

## Gambaran Fitur

Sebelum Phase 3, sistem hanya bisa membuat **linear workflow** (Step 1 → Step 2 → Step 3).
Node-node terhubung secara berurutan dengan koneksi `main`.

Phase 3 menambahkan kemampuan membuat **AI Agent workflow** — struktur yang
berbeda dari linear, di mana satu node AI Agent punya sub-node yang terhubung
melalui koneksi khusus (`ai_languageModel`, `ai_memory`, `ai_tool`).

```
Linear workflow (sebelum):         AI Agent workflow (sesudah):
  A → B → C → D                     Trigger → AI Agent → Output
                                                ↑
                                         Chat Model (ai_languageModel)
                                         Memory     (ai_memory)
                                         Tool 1     (ai_tool)
                                         Tool 2     (ai_tool)
```

User cukup mengetik:
> "buatkan agent ai untuk chatbot whatsapp, bisa jawab pertanyaan, simpan ke google sheets"

Sistem akan otomatis:
- Deteksi ini adalah permintaan AI Agent
- Minta LLM analisa komponen yang dibutuhkan (trigger, tools, output)
- Bangun JSON workflow n8n dengan koneksi yang benar
- POST ke n8n API → workflow langsung tersedia di canvas

---

## File yang Diubah

### Backend — Agent Service (Python/FastAPI)

```
services/mst-agent/app/routers/workflow_builder.py   ← FILE UTAMA
```

**Perubahan:**
- Tambah fungsi `is_agent_request(prompt)` — deteksi kata kunci agent
- Tambah routing di `build_workflow()` — jika agent request, panggil `build_agent_workflow()`
- Tambah konstanta `_AGENT_KEYWORDS` — daftar kata kunci trigger
- Tambah konstanta `_AGENT_FIXED` — node default (Chat Model + Memory)
- Tambah `AGENT_ANALYZER_PROMPT` — system prompt khusus untuk analisa komponen agent
- Tambah fungsi `_build_agent_workflow_json()` — bangun n8n JSON dengan koneksi AI
- Tambah fungsi `build_agent_workflow()` — orkestrasi full (embedding search → LLM → n8n API)

### Frontend/Gateway — n8n CLI (TypeScript)

```
packages/cli/src/modules/chat-hub/mst-agent.service.ts
```

**Perubahan (dari Phase sebelumnya, masih relevan):**
- `WORKFLOW_KEYWORDS` ditambah kata kunci agent:
  `'buatkan agent'`, `'buat agent'`, `'buatkan ai agent'`, `'buat ai agent'`,
  `'create agent'`, `'build agent'`
- Parse JSON `detail` dari HTTP 422 response FastAPI

---

## Alur Teknis Lengkap

```
User ketik di chat:
"buatkan agent ai untuk helpdesk IT dengan ServiceNow"
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  chat-hub.service.ts                                     │
│                                                          │
│  isWorkflowRequest("buatkan agent ai...")               │
│  → cek WORKFLOW_KEYWORDS                                │
│  → "buatkan agent" ✓ → TRUE                            │
│                                                          │
│  handleAgentWorkflowRequest()                           │
│  → startExecution() → StreamBegin → bubble loading     │
│  → mstAgentService.buildWorkflow(prompt)               │
└─────────────────────┬───────────────────────────────────┘
                      │ POST /workflow/build
                      ▼
┌─────────────────────────────────────────────────────────┐
│  workflow_builder.py → build_workflow()                  │
│                                                          │
│  is_agent_request(prompt)?                              │
│  → "buatkan agent" ada di _AGENT_KEYWORDS → TRUE       │
│  → return await build_agent_workflow(...)              │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│  build_agent_workflow()                                  │
│                                                          │
│  1. Ambil catalog (849 node dari n8n instance)          │
│     get_catalog()                                       │
│                                                          │
│  2. Pisahkan catalog berdasarkan peran:                 │
│     - trigger_nodes: node yang diakhiri "Trigger"       │
│     - tool_nodes   : node yang diakhiri "Tool"          │
│     - output_nodes : sisanya (bukan trigger/tool/       │
│                      bukan langchain)                   │
│                                                          │
│  3. find_relevant_nodes(prompt, top_k=30)               │
│     → hybrid search (text + embedding)                  │
│     → filter ke trigger/tool/output masing-masing      │
│                                                          │
│  4. Format sebagai AGENT_ANALYZER_PROMPT                │
│     → kirim ke LLM (llama3.2:3b via Ollama)            │
│                                                          │
│  5. LLM kembalikan JSON:                                │
│     {                                                    │
│       "trigger": { node_type, display_name, desc },    │
│       "tools":   [ { node_type, display_name, desc }   │
│                     ... ],                              │
│       "output":  { node_type, display_name, desc },    │
│       "has_branch": false                               │
│     }                                                   │
│                                                          │
│  6. Validasi: tiap node_type ada di known_types?        │
│     → Tidak ada → fallback ke default (webhook/http/set)│
│                                                          │
│  7. _build_agent_workflow_json(...)                     │
│     → bangun dict n8n workflow dengan:                  │
│       - nodes[] dengan posisi canvas                    │
│       - connections{} dengan tipe koneksi yang benar   │
│                                                          │
│  8. POST ke n8n API → workflow dibuat                   │
│     → kembalikan workflow_id + url                      │
└─────────────────────┬───────────────────────────────────┘
                      │ response JSON
                      ▼
┌─────────────────────────────────────────────────────────┐
│  chat-hub.service.ts                                     │
│                                                          │
│  formatResponse(result) → teks markdown                 │
│  sendChunk(teks) → bubble chat terisi                   │
│  endStream('success')                                    │
│  endExecution('success') → tidak ada toast error        │
└─────────────────────────────────────────────────────────┘
```

---

## Struktur Workflow n8n yang Dihasilkan

### Node dan Posisi Canvas

```
Y=300  [Trigger]──────►[AI Agent]──────►[Output]
         x=250           x=550           x=900

Y=540              [Chat Model][Memory][Tool1][Tool2...]
                     x=350      x=550   x=750  x=930
```

### Koneksi (connections JSON)

```json
{
  "NamaTrigger": {
    "main": [[ {"node": "AI Agent", "type": "main", "index": 0} ]]
  },
  "Mistika-AI Chat Model": {
    "ai_languageModel": [[ {"node": "AI Agent", "type": "ai_languageModel", "index": 0} ]]
  },
  "Simple Memory": {
    "ai_memory": [[ {"node": "AI Agent", "type": "ai_memory", "index": 0} ]]
  },
  "NamaTool": {
    "ai_tool": [[ {"node": "AI Agent", "type": "ai_tool", "index": 0} ]]
  },
  "AI Agent": {
    "main": [[ {"node": "NamaOutput", "type": "main", "index": 0} ]]
  }
}
```

### Node Default (tidak bisa diubah user)

| Node | node_type | Koneksi ke AI Agent |
|------|-----------|---------------------|
| Mistika-AI Chat Model | `@n8n/n8n-nodes-langchain.lmChatMistikaAi` | `ai_languageModel` |
| Simple Memory | `@n8n/n8n-nodes-langchain.memoryBufferWindow` | `ai_memory` |

### Jika Ada Percabangan (`has_branch: true`)

```
Trigger → AI Agent → If Node → Output (true branch)
                             → (kosong, false branch — user isi)
```

---

## Contoh Prompt dan Hasilnya

### Contoh 1 — Chatbot WhatsApp sederhana

**Prompt:**
```
buatkan agent ai untuk chatbot whatsapp, bisa jawab pertanyaan pelanggan,
dan simpan percakapan ke google sheets
```

**Hasil:**
- Trigger: `Webhook WhatsApp`
- Tools: `HTTP Request` (kirim balasan WA)
- Output: `Google Sheets` (simpan log)
- Chat Model: `Mistika-AI Chat Model` (fixed)
- Memory: `Simple Memory` (fixed)

---

### Contoh 2 — Helpdesk IT dengan ServiceNow

**Prompt:**
```
buatkan agent ai, trigger dari webhook, tools: ServiceNow untuk buat tiket
dan HTTP Request untuk cek data, kirim hasilnya ke email
```

**Hasil:**
- Trigger: `Webhook`
- Tools: `ServiceNow API`, `HTTP Request`
- Output: `Send Email`

---

### Contoh 3 — Chatbot dengan kondisi/percabangan

**Prompt:**
```
buatkan agent ai untuk helpdesk, jika pertanyaan IT buat tiket di ServiceNow,
jika HR kirim ke email HRD
```

**Hasil:**
- Trigger: webhook / chat trigger
- Tools: `ServiceNow`, `Email Send`
- Output: `If Node` (cabang IT vs HR)
- `has_branch: true` → If node disisipkan otomatis

---

### Contoh 4 — Agent dengan jadwal

**Prompt:**
```
buat agen ai yang berjalan setiap pagi, ambil data dari API, ringkas dengan AI,
lalu kirim laporan ke Slack
```

**Hasil:**
- Trigger: `Schedule Trigger`
- Tools: `HTTP Request`
- Output: `Slack`

---

## Logika Deteksi Agent Request

**File:** `services/mst-agent/app/routers/workflow_builder.py`

```python
_AGENT_KEYWORDS = {
    "buatkan agent", "buat agent", "buatkan ai agent", "buat ai agent",
    "create agent", "build agent", "buatkan agen", "buat agen",
}

def is_agent_request(prompt: str) -> bool:
    lower = prompt.lower()
    return any(kw in lower for kw in _AGENT_KEYWORDS)
```

**Titik panggil di `build_workflow()`:**

```python
if is_agent_request(prompt):
    return await build_agent_workflow(prompt, payload.user_id, payload.session_id, db)
# ... lanjut ke logika linear workflow
```

Kata kunci yang memicu routing ke agent builder (pencocokan substring, bukan exact):

| Kata Kunci | Contoh Prompt yang Cocok |
|------------|--------------------------|
| `buatkan agent` | "buatkan agent ai untuk..." |
| `buat agent` | "buat agent yang bisa..." |
| `buatkan ai agent` | "buatkan ai agent helpdesk" |
| `buat ai agent` | "buat ai agent untuk..." |
| `create agent` | "create agent that can..." |
| `build agent` | "build agent for..." |
| `buatkan agen` | "buatkan agen whatsapp" |
| `buat agen` | "buat agen chatbot" |

---

## LLM Prompt yang Dipakai

**Konstanta:** `AGENT_ANALYZER_PROMPT` di `workflow_builder.py`

Prompt ini dikirim sebagai system message ke LLM (llama3.2:3b via Ollama).
Berisi 3 bagian node yang diformat dari catalog:

```
Available TRIGGER nodes (choose ONE):
- n8n-nodes-base.whatsappBusinessCloudTrigger (...): ...
- n8n-nodes-base.scheduleTrigger (...): ...
...

Available TOOL nodes (choose multiple as needed):
- n8n-nodes-base.serviceNowTool (...): ...
- n8n-nodes-base.httpRequest (...): ...
...

Available OUTPUT nodes (choose ONE or more):
- n8n-nodes-base.emailSend (...): ...
- n8n-nodes-base.slack (...): ...
...
```

LLM diminta kembalikan JSON dengan format:

```json
{
  "summary": "deskripsi satu kalimat",
  "trigger": {
    "node_type": "n8n-nodes-base.xxx",
    "display_name": "Nama Trigger",
    "description": "apa yang memulai workflow"
  },
  "tools": [
    {
      "node_type": "n8n-nodes-base.xxx",
      "display_name": "Nama Tool",
      "description": "apa yang dilakukan tool ini"
    }
  ],
  "output": {
    "node_type": "n8n-nodes-base.xxx",
    "display_name": "Nama Output",
    "description": "apa yang dilakukan dengan hasil agent"
  },
  "has_branch": false
}
```

---

## Fallback dan Validasi

Setiap node yang dikembalikan LLM divalidasi terhadap `known_types` (set dari catalog n8n).

```python
for component in [trigger, output] + tools:
    nt = component.get("node_type", "")
    if nt not in known_types:
        if component is trigger:
            component["node_type"] = "n8n-nodes-base.webhook"
            component["display_name"] = "Webhook Trigger"
        elif component in tools:
            component["node_type"] = "n8n-nodes-base.httpRequest"
            component["display_name"] = "HTTP Request"
        else:
            component["node_type"] = "n8n-nodes-base.set"
            component["display_name"] = "Set Output"
```

| Komponen | Fallback Default |
|----------|-----------------|
| Trigger | `n8n-nodes-base.webhook` |
| Tool | `n8n-nodes-base.httpRequest` |
| Output | `n8n-nodes-base.set` |

---

## Panduan Tracing Error

### 1. Routing tidak masuk ke agent builder

**Gejala:** Prompt "buatkan agent ai..." menghasilkan linear workflow biasa, bukan AI Agent.

**Cek:**
1. Apakah kata kunci ada di `WORKFLOW_KEYWORDS` di `mst-agent.service.ts`?
   ```
   packages/cli/src/modules/chat-hub/mst-agent.service.ts
   ```
2. Apakah kata kunci ada di `_AGENT_KEYWORDS` di `workflow_builder.py`?
   ```
   services/mst-agent/app/routers/workflow_builder.py
   ```
3. Test langsung di container:
   ```bash
   docker exec mst-agent-service python -c "
   import sys; sys.path.insert(0,'/app')
   from app.routers.workflow_builder import is_agent_request
   print(is_agent_request('buatkan agent ai untuk ...'))
   "
   ```

---

### 2. Workflow terbuat tapi struktur tidak benar (tidak ada sub-node)

**Gejala:** Canvas n8n hanya menampilkan linear chain, bukan AI Agent dengan sub-node.

**Cek:**
- Pastikan node type yang dipakai benar:
  - AI Agent: `@n8n/n8n-nodes-langchain.agent`
  - Chat Model: `@n8n/n8n-nodes-langchain.lmChatMistikaAi`
  - Memory: `@n8n/n8n-nodes-langchain.memoryBufferWindow`
- Cek koneksi di JSON yang dikirim ke n8n:
  ```bash
  docker logs mst-agent-service --tail 50
  ```
- Tipe koneksi harus `ai_languageModel`, `ai_memory`, `ai_tool` — bukan `main`

---

### 3. LLM memilih node type yang tidak ada di catalog

**Gejala:** Log menunjukkan fallback ke `webhook`/`httpRequest`/`set` meski user minta node spesifik.

**Penyebab:** LLM mengarang node_type yang tidak ada di n8n instance ini.

**Cek:**
```bash
# Lihat apa yang LLM kembalikan sebelum validasi
docker logs mst-agent-service --tail 30
```

**Solusi jangka panjang:** Tambahkan node ke n8n instance (install community node),
atau tambahkan sinonim di `_AGENT_KEYWORDS` agar embedding search menemukan node yang tepat.

---

### 4. Error saat membuat workflow di n8n API

**Gejala:** `POST /api/v1/workflows` mengembalikan error 4xx/5xx.

**Cek:**
```bash
docker logs mst-agent-service --tail 20
```

**Kemungkinan penyebab:**
- `typeVersion` tidak sesuai untuk node yang dipilih LLM
  → Tambahkan ke `NODE_VERSIONS` dict di `workflow_builder.py`
- n8n credential `mistikaAiApi` tidak ditemukan
  → Cek: `docker exec mst-agent-service curl http://n8n:5678/api/v1/credentials`
- Token API n8n expired
  → Cek variabel `N8N_API_KEY` di `docker-compose.yml`

---

### 5. "Unknown error" toast di browser

Lihat [docs/arsitektur-alur-userkirimchat.md](arsitektur-alur-userkirimchat.md) — bagian "Kenapa Dulu Muncul Unknown Error".

**Cek cepat:**
```bash
docker logs phase-0-n8n-1 --tail 30
docker logs mst-agent-service --tail 30
```

---

### 6. Kata kunci agent terdeteksi tapi LLM timeout

**Gejala:** Request ke `/workflow/build` timeout setelah 180 detik.

**Cek:**
- Ollama jalan? `docker logs ollama --tail 10`
- Model llama3.2:3b tersedia? `docker exec ollama ollama list`
- Embedding berjalan bersamaan (memakan resource GPU/CPU)?
  ```bash
  docker exec ollama ollama ps
  ```

---

## Ringkasan Lokasi File

```
n8n-Docker/
├── services/
│   └── mst-agent/
│       └── app/
│           ├── routers/
│           │   └── workflow_builder.py   ← SEMUA logika AI Agent builder
│           ├── embedding_search.py       ← Hybrid search (filter *Tool untuk agent)
│           └── nodes_registry.py        ← Dedup node list dari n8n
│
├── packages/
│   └── cli/
│       └── src/
│           └── modules/
│               └── chat-hub/
│                   └── mst-agent.service.ts   ← Keyword routing + parse error
│
└── docs/
    ├── phase-3-ai-agent-workflow-builder.md   ← FILE INI
    ├── phase-2-mst-agent-node-registry-embedding.md
    └── arsitektur-alur-userkirimchat.md
```

---

## Fungsi-Fungsi Kunci di workflow_builder.py

| Fungsi | Baris | Tugas |
|--------|-------|-------|
| `is_agent_request(prompt)` | ~295 | Cek apakah prompt minta AI Agent |
| `_build_agent_workflow_json(...)` | ~380 | Bangun dict n8n JSON dengan koneksi AI |
| `build_agent_workflow(...)` | ~445 | Orkestrasi: embedding → LLM → validasi → n8n |
| `build_workflow(...)` | ~157 | Entry point — routing ke agent atau linear |
| `_task_graph_to_workflow_json(...)` | ~41 | Builder untuk linear workflow (tetap ada) |
