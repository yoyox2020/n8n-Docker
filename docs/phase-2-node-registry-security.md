# Phase 2.1 — Node Registry Dinamis & Keamanan Dasar

> **Kapan?** Juni 2026  
> **Kenapa?** MST Agent Service sebelumnya hanya tahu 73 node yang ditulis manual.
> Akibatnya, saat user minta "buatkan workflow ServiceNow" atau node lain yang
> tidak ada di daftar, LLM tidak bisa membuat workflow yang benar.

---

## Masalah yang Diselesaikan

### Sebelumnya
```
User: "buatkan workflow ServiceNow kirim tiket ke Slack"
       ↓
Agent Service buka nodes_catalog.py  ← hanya 73 node hardcoded
       ↓
LLM tidak kenal ServiceNow → workflow salah / gagal
```

### Sekarang
```
Agent Service startup
       ↓
Login ke n8n (pakai akun admin)
       ↓
Ambil /types/nodes.json  ← semua 400+ node yang terinstall di n8n
       ↓
Simpan di memori (cache)
       ↓
User: "buatkan workflow ServiceNow kirim tiket ke Slack"
       ↓
Filter node relevan: serviceNow, slack, webhook, dll
       ↓
LLM mendapat konteks yang tepat → workflow benar
```

---

## File yang Berubah

### Baru
| File | Fungsi |
|------|--------|
| `services/mst-agent/app/nodes_registry.py` | Ambil daftar node dari n8n saat startup, fallback ke catalog statis jika gagal |

### Diubah
| File | Perubahan |
|------|-----------|
| `services/mst-agent/app/config.py` | Tambah `n8n_admin_email` dan `n8n_admin_password` |
| `services/mst-agent/app/main.py` | Panggil `init_registry()` saat startup; tambah rate limiting |
| `services/mst-agent/app/routers/workflow_builder.py` | Pakai `get_catalog()` dari registry; validasi input & node type |
| `services/mst-agent/app/routers/plan.py` | Pakai `get_catalog()` dari registry; validasi panjang prompt |
| `deploy/phase-0/.env` | Tambah `N8N_ADMIN_EMAIL` dan `N8N_ADMIN_PASSWORD` |

---

## Cara Kerja Node Registry

```
Startup
   │
   ├─ Login POST /rest/login  →  dapat session cookie
   │
   ├─ GET /types/nodes.json   →  list semua node (400+)
   │         dengan cookie
   │
   ├─ Parse: ambil node_type, display_name, description
   │
   └─ Simpan di _registry (memori)
          │
          ├─ BERHASIL: LLM tahu semua node terinstall
          └─ GAGAL:    Pakai nodes_catalog.py (73 node) sebagai cadangan
```

Tidak ada restart yang diperlukan untuk menyegarkan cache — cukup restart
container agent service jika ada node baru yang dipasang di n8n.

---

## Keamanan Dasar yang Diterapkan

### 1. Rate Limiting
- **Batas:** 30 request per menit per IP address
- **Respons:** HTTP 429 jika terlampaui
- **Tujuan:** Mencegah flooding / penyalahgunaan endpoint

### 2. Validasi Input
- Prompt maksimal **500 karakter**
- Prompt tidak boleh kosong
- Diterapkan di `/plan/` dan `/workflow/build`

### 3. Validasi Node Type
- Node type yang dihasilkan LLM dicek terhadap registry
- Jika tidak dikenal, harus sesuai pola `n8n-nodes-base.namaNode`
- Mencegah LLM menyisipkan node type sembarangan ke workflow

### 4. CORS Terbatas
- Sebelumnya: izinkan semua origin (`*`)
- Sekarang: hanya `http://localhost:5678`, `http://n8n:5678`, `http://localhost:3000`

### 5. API Docs Tersembunyi di Production
- `/docs` dan `/redoc` hanya muncul jika `DEBUG=true`
- Di production (`DEBUG=false`), endpoint ini tidak ada

---

## Catatan Keamanan Penting

`N8N_ADMIN_EMAIL` dan `N8N_ADMIN_PASSWORD` disimpan di `.env`.
File ini **tidak boleh di-commit ke git** (sudah ada di `.gitignore`).

Kredensial ini hanya dipakai untuk satu tujuan: login ke n8n
sekali saat startup untuk mengambil daftar node.  Setelah itu
koneksi ditutup dan session tidak disimpan ke disk.

---

## Cara Deploy Ulang Setelah Perubahan Ini

```powershell
# 1. Dari folder deploy/phase-0 — recreate container dengan env baru
docker compose --env-file .env up -d

# 2. Deploy file Python yang berubah
docker cp services/mst-agent/app/nodes_registry.py  mst-agent-service:/app/app/nodes_registry.py
docker cp services/mst-agent/app/config.py          mst-agent-service:/app/app/config.py
docker cp services/mst-agent/app/main.py             mst-agent-service:/app/app/main.py
docker cp services/mst-agent/app/routers/plan.py     mst-agent-service:/app/app/routers/plan.py
docker cp services/mst-agent/app/routers/workflow_builder.py mst-agent-service:/app/app/routers/workflow_builder.py

# 3. Restart
docker restart mst-agent-service

# 4. Cek health (lihat nodes_loaded)
curl http://localhost:8001/health
```

Kalau `nodes_loaded` di response health > 73, artinya registry berhasil
ambil dari n8n. Kalau sama dengan 73, artinya pakai static catalog (fallback).

---

## Troubleshooting

**`nodes_loaded` tetap 73 (fallback)**
- Cek apakah `N8N_ADMIN_EMAIL` dan `N8N_ADMIN_PASSWORD` sudah ada di `.env`
- Pastikan password benar (default: `MstAdmin2024#`)
- Cek log: `docker logs mst-agent-service | grep NodeRegistry`

**Error 429 saat test**
- Rate limit kena — tunggu 1 menit atau restart container agent
- Di development, set `DEBUG=true` untuk menonaktifkan rate limit (belum diimplementasi, tapi bisa ditambahkan)

**Node baru di n8n tidak muncul**
- Registry hanya di-load saat startup
- Restart agent service: `docker restart mst-agent-service`
