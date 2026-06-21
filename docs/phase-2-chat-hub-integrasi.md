# Phase 2 — Chat Hub ↔ Agent Service Integration

## Tujuan

User mengetik perintah di Chat Hub (contoh: *"buatkan workflow pengiriman email dari whatsapp"*)
→ n8n secara otomatis membuatkan workflow tanpa konfigurasi manual.

---

## Arsitektur

```
Browser (Chat Hub UI)
        │ POST /api/v1/chat-hub/sessions/:id/messages
        ▼
n8n Backend (chat-hub.service.ts)
        │ deteksi keyword workflow
        ▼
MstAgentService (mst-agent.service.ts)
        │ POST http://mst-agent-service:8000/workflow/build
        ▼
Agent Service (FastAPI — C:\Users\Acer\n8n-mst-Agent)
        │ LLM → task_graph → n8n API
        ▼
n8n Public API  POST /api/v1/workflows
        │
        ▼
Workflow terbentuk otomatis di n8n
```

---

## Perubahan di n8n-Docker

### 1. File Baru

| File | Keterangan |
|------|-----------|
| `packages/cli/src/modules/chat-hub/mst-agent.service.ts` | Service yang mendeteksi keyword workflow dan memanggil Agent Service via HTTP |

**Isi utama:**
- `WORKFLOW_KEYWORDS` — list kata kunci: `"buatkan workflow"`, `"buat automasi"`, `"create workflow"`, dll.
- `isWorkflowRequest(message)` — return `true` jika pesan mengandung keyword
- `buildWorkflow(prompt, userId, sessionId)` — POST ke Agent Service `/workflow/build`
- `formatResponse(result)` — format balasan dengan nama workflow + steps + link

---

### 2. File Dimodifikasi

#### `packages/cli/src/modules/chat-hub/chat-hub.service.ts`

**Perubahan:**
```typescript
// Import baru
import { MstAgentService } from './mst-agent.service';

// Tambah di constructor
private readonly mstAgentService: MstAgentService,

// Interceptor di sendHumanMessage() — SEBELUM dikirim ke LLM
if (this.mstAgentService.isWorkflowRequest(message)) {
    void this.handleAgentWorkflowRequest(user, sessionId, messageId, message, model);
    return;
}

// Method baru
private async handleAgentWorkflowRequest(...) {
    // 1. startExecution + startStream
    // 2. Panggil Agent Service
    // 3. Simpan AI message ke DB
    // 4. sendChunk + endStream + endExecution
}
```

---

#### `packages/cli/src/modules/chat-hub/chat-hub-workflow.service.ts`

**Perubahan:** Tambah `case 'misikaAi'` di switch statement provider (baris ~907).

```typescript
case 'misikaAi': {
    return {
        ...common,
        parameters: { model, options: {} },
    };
}
```

Tanpa ini → error *"Unsupported model provider"* saat chat.

---

#### `packages/@n8n/nodes-langchain/credentials/MisikaAiApi.credentials.ts`

**Perubahan:** Ubah default `Base URL` dari URL Mistika lama ke OpenRouter:

```typescript
// Sebelum
default: 'https://misstika.mst.co.id/llm-router',

// Sesudah
default: 'https://openrouter.ai/api/v1',
```

---

#### `deploy/phase-0/.env`

**Perubahan:** Tambah environment variable:

```env
AGENT_SERVICE_URL=http://mst-agent-service:8000
```

---

### 3. File Frontend (dari Phase 1 yang mendukung Phase 2)

| File | Perubahan |
|------|-----------|
| `packages/@n8n/api-types/src/chat-hub.ts` | Tambah `'misikaAi'` ke `ChatHubLLMProvider` union dan `PROVIDER_CREDENTIAL_TYPE_MAP` |
| `packages/frontend/editor-ui/src/features/ai/chatHub/constants.ts` | Tambah `MST_ALLOWED_LLM_PROVIDERS = ['misikaAi']` dan entry di `providerDisplayNames` |
| `packages/frontend/editor-ui/src/features/ai/chatHub/model-selector.utils.ts` | Filter provider list hanya ke `MST_ALLOWED_LLM_PROVIDERS` |

---

## Agent Service (Proyek Terpisah)

**Lokasi:** `C:\Users\Acer\n8n-mst-Agent\`

### Struktur

```
n8n-mst-Agent/
├── app/
│   ├── main.py              # FastAPI entry point, CORS, lifespan
│   ├── config.py            # Pydantic Settings (env vars)
│   ├── models.py            # SQLAlchemy models (memory)
│   ├── database.py          # Async DB init
│   ├── nodes_catalog.py     # Catalog 54 n8n nodes (statis)
│   └── routers/
│       ├── plan.py          # POST /plan/ → LLM streaming
│       ├── memory.py        # GET/POST /memory/
│       ├── tools.py         # GET /tools/ → node catalog
│       └── workflow_builder.py  # POST /workflow/build
├── docker-compose.yml       # agent-service + agent-db
├── .env                     # API keys (DO NOT COMMIT)
├── Dockerfile
└── requirements.txt
```

### Endpoints

| Endpoint | Method | Fungsi |
|----------|--------|--------|
| `/health` | GET | Health check |
| `/tools/` | GET | List node catalog (54 nodes, filter by category/search) |
| `/plan/` | POST | Generate rencana task via LLM (streaming) |
| `/memory/` | GET/POST | Read/write memory ke PostgreSQL |
| `/workflow/build` | POST | Build workflow otomatis: LLM → task_graph → n8n API |

### `/workflow/build` — Alur Kerja

```
POST { "prompt": "buatkan workflow kirim email dari whatsapp" }
        │
        ▼
1. Kirim prompt ke OpenRouter (DeepSeek) → generate task_graph JSON
   Contoh: [{"node_type": "n8n-nodes-base.webhook", "display_name": "WhatsApp Trigger"},
             {"node_type": "n8n-nodes-base.emailSend", "display_name": "Send Email"}]
        │
        ▼
2. Konversi task_graph → n8n Workflow JSON
   - UUID untuk setiap node
   - Koneksi linear antar node
   - Position offset 250px per node
        │
        ▼
3. POST ke n8n Public API /api/v1/workflows dengan X-N8N-API-KEY
        │
        ▼
4. Return: { workflow_id, workflow_url, workflow_name, steps[] }
```

### Environment Variables (.env)

```env
# LLM provider (OpenRouter — sementara, nanti ganti Mistika)
MISTIKA_BASE_URL=https://openrouter.ai/api/v1
MISTIKA_API_KEY=sk-or-v1-...
MISTIKA_MODEL=deepseek/deepseek-v4-flash
MISTIKA_CHAT_PATH=/chat/completions

# Database
DATABASE_URL=postgresql+asyncpg://agentuser:agentpass@agent-db:5432/agentdb

# n8n instance
N8N_BASE_URL=http://n8n:5678
N8N_API_KEY=<n8n_public_api_key>

AGENT_PORT=8000
DEBUG=false
```

---

## Docker Network

Kedua stack (n8n + Agent Service) bergabung di network yang sama:

```yaml
# deploy/phase-0/docker-compose.yml
networks:
  mstworkflow:
    external: true
    name: mstworkflow

# n8n-mst-Agent/docker-compose.yml
networks:
  mstworkflow:
    external: true
    name: mstworkflow
```

Container `n8n` bisa reach `mst-agent-service:8000` lewat network `mstworkflow`.

---

## Cara Deploy

### Start/Stop

```powershell
# Start n8n
cd C:\Users\Acer\n8n-Docker\deploy\phase-0
docker compose up -d

# Start Agent Service
cd C:\Users\Acer\n8n-mst-Agent
docker compose up -d

# Rebuild n8n (jika ada perubahan kode)
cd C:\Users\Acer\n8n-Docker\deploy\phase-0
docker compose down
docker compose up -d --build

# Jika Docker rebuild gagal (wa-sqlite issue), compile manual:
cd C:\Users\Acer\n8n-Docker\packages\cli
pnpm build
# Lalu copy file ke container:
docker cp dist/modules/chat-hub/mst-agent.service.js phase-0-n8n-1:/usr/local/lib/node_modules/n8n/dist/modules/chat-hub/
docker cp dist/modules/chat-hub/chat-hub.service.js phase-0-n8n-1:/usr/local/lib/node_modules/n8n/dist/modules/chat-hub/
docker cp dist/modules/chat-hub/chat-hub-workflow.service.js phase-0-n8n-1:/usr/local/lib/node_modules/n8n/dist/modules/chat-hub/
docker restart phase-0-n8n-1
```

### Setup Credential (sekali saja)

1. Buka `http://localhost:5678`
2. **Settings → Credentials → New → Mistika-AI**
3. Isi:
   - **API Key**: OpenRouter key (`sk-or-v1-...`)
   - **Base URL**: `https://openrouter.ai/api/v1`
4. Save

---

## Known Issues & Workarounds

### Docker Build Gagal — wa-sqlite

**Error:** `ECONNRESET` saat download `wa-sqlite` dari `codeload.github.com`

**Penyebab:** Docker container tidak bisa koneksi TLS ke GitHub CDN.

**Workaround saat ini:** Compile CLI lokal + copy ke container (lihat Cara Deploy di atas).

**Fix permanen (planned):** Vendor `wa-sqlite` ke build context di Dockerfile.

---

### Model Name Tampil "undefined"

**Penyebab:** stale localStorage dari sesi sebelumnya.

**Fix:** Buka DevTools (F12) → Console:
```javascript
Object.keys(localStorage).filter(k=>k.includes('chat')).forEach(k=>localStorage.removeItem(k))
```
Lalu refresh halaman.

---

## Test End-to-End

```
1. Buka http://localhost:5678/chat
2. Pilih model Mistika-AI dari dropdown
3. Ketik: "buatkan workflow pengiriman email dari whatsapp"
4. Ekspektasi:
   - Chat Hub membalas dengan nama workflow + steps + link
   - Workflow baru muncul di http://localhost:5678/workflows
```
