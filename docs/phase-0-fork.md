# Phase 0 — Remove Registration & Auto-Provision Owner

**Goal:** Fork n8n into "Asuralab Agentic Workflow Engine" with zero registration
wizard, auto-provisioned owner account, and suppressed personalization survey.
All achieved via Docker environment configuration — **no n8n source code was
modified**.

---

## Perubahan yang Dilakukan

### Pendekatan

n8n v2.x menyediakan env var bawaan `N8N_INSTANCE_OWNER_MANAGED_BY_ENV` yang
secara otomatis membuat/mengupdate owner account saat startup. Seluruh Phase 0
memanfaatkan fitur ini tanpa menyentuh source code n8n.

### Apa yang dihilangkan

| Fitur n8n Default | Status |
|---|---|
| Setup wizard (registration page) | Dihilangkan — owner di-provision otomatis |
| "Customize n8n to you" survey | Dihilangkan — flag + API workaround |
| Manual password setup di browser | Dihilangkan — hash di-generate oleh script |

---

## File dan Folder yang Ditambahkan

```
deploy/
└── phase-0/
    ├── docker-compose.yml        # Stack Postgres 16 + n8n
    ├── .env.example              # Template (committed to git)
    ├── .env                      # Secret file — GITIGNORED, dibuat oleh provision script
    └── scripts/
        ├── provision.ps1         # Provisioning untuk Windows (PowerShell)
        ├── provision.sh          # Provisioning untuk Linux/macOS/WSL
        └── dismiss-survey.ps1    # Workaround survey popup (jalankan sekali)
```

---

## Penjelasan Setiap File

### `deploy/phase-0/docker-compose.yml`

Stack dua service: `postgres` dan `n8n`, terhubung lewat jaringan Docker
internal bernama `asuralab`.

**Desain kritis:**

- `postgres` punya `healthcheck` dan n8n `depends_on: condition: service_healthy`
  — n8n tidak start sebelum Postgres siap menerima koneksi.
- n8n menggunakan **`env_file: .env`** (bukan hanya `environment:` block) agar
  nilai yang mengandung karakter `$` (seperti bcrypt hash) tidak diinterpretasi
  oleh Docker Compose sebagai variable reference.
- Variabel koneksi DB tetap di `environment:` block karena membutuhkan hostname
  Docker internal (`postgres`) yang tidak bisa diketahui saat `.env` digenerate.

```yaml
n8n:
  image: n8nio/n8n:latest
  env_file:
    - .env          # bcrypt hash aman dari interpolasi Compose di sini
  environment:
    DB_TYPE: postgresdb
    DB_POSTGRESDB_HOST: postgres   # Docker service name
    DB_POSTGRESDB_PORT: 5432
    DB_POSTGRESDB_USER: ${POSTGRES_USER:-n8n}
    DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}
    DB_POSTGRESDB_DATABASE: ${POSTGRES_DB:-n8n}
```

### `deploy/phase-0/.env.example`

Template yang di-commit ke git. Tidak mengandung nilai rahasia — hanya menampilkan
struktur variable yang dibutuhkan. Gunakan sebagai referensi saat setup manual.

### `deploy/phase-0/.env`

File rahasia yang **tidak boleh di-commit** (masuk `.gitignore`). Dibuat
otomatis oleh `provision.ps1` atau `provision.sh`.

Variabel kunci:

| Variable | Tujuan |
|---|---|
| `N8N_INSTANCE_OWNER_MANAGED_BY_ENV=true` | Aktifkan auto-provision owner di startup |
| `N8N_INSTANCE_OWNER_EMAIL` | Email login owner |
| `N8N_INSTANCE_OWNER_PASSWORD_HASH` | bcrypt hash password (rounds=12) |
| `N8N_INSTANCE_OWNER_FIRST_NAME` | Nama depan owner |
| `N8N_INSTANCE_OWNER_LAST_NAME` | Nama belakang owner |
| `N8N_ENCRYPTION_KEY` | Kunci enkripsi credential n8n (random 32 char) |
| `N8N_PERSONALIZATION_ENABLED=false` | Matikan survey di level backend |
| `POSTGRES_PASSWORD` | Password Postgres (random 32 char, alphanumeric) |

**Catatan encoding `$` di bcrypt hash:**
Bcrypt hash berbentuk `$2a$12$...`. Docker Compose menginterpretasi `$VAR`
sebagai variable reference meskipun di dalam `env_file`. Solusinya: setiap `$`
di-escape menjadi `$$` di file `.env`. Docker Compose mendecode `$$` → `$`
saat mengoper nilai ke container.

```
# Di .env (escaped):
N8N_INSTANCE_OWNER_PASSWORD_HASH=$$2a$$12$$p6pB7hhp...

# Yang diterima container (decoded):
N8N_INSTANCE_OWNER_PASSWORD_HASH=$2a$12$p6pB7hhp...
```

### `deploy/phase-0/scripts/provision.ps1`

Script PowerShell untuk Windows. Dijalankan **sekali** sebelum `docker compose up`.

**Yang dilakukan:**
1. Menerima parameter `Email`, `Password` (SecureString), `FirstName`, `LastName`
2. Jika password tidak diberikan, generate password random 20 karakter
3. Generate bcrypt hash menggunakan Node.js (`bcryptjs` dari node_modules n8n)
   — fallback ke Docker Python jika Node.js tidak tersedia
4. Escape `$` → `$$` di bcrypt hash
5. Generate `POSTGRES_PASSWORD` dan `N8N_ENCRYPTION_KEY` random 32 char (alphanumeric only)
6. Tulis `.env` ke `deploy/phase-0/.env`

**Penggunaan:**
```powershell
cd deploy\phase-0
.\scripts\provision.ps1
# atau dengan parameter:
$pw = ConvertTo-SecureString "MyPassword123" -AsPlainText -Force
.\scripts\provision.ps1 -Email admin@example.com -Password $pw
```

### `deploy/phase-0/scripts/provision.sh`

Versi Bash dari provision script, untuk Linux/macOS/WSL/Git Bash.

**Penggunaan:**
```bash
cd deploy/phase-0
chmod +x scripts/provision.sh
./scripts/provision.sh admin@example.com MyPassword123
```

### `deploy/phase-0/scripts/dismiss-survey.ps1`

Workaround untuk "Customize n8n to you" survey yang muncul pada n8n v2.25.7
meskipun `N8N_PERSONALIZATION_ENABLED=false` sudah di-set.

**Mengapa perlu script ini:**
n8n v2.25.7 (image Docker) menampilkan survey berdasarkan dua kondisi:
1. `personalizationSurveyEnabled` — dikontrol oleh `N8N_PERSONALIZATION_ENABLED`
2. `personalizationAnswers === null` pada record user — **tidak** dikontrol flag tersebut

Compiled code di image Docker v2.25.7 memeriksa kedua kondisi secara independen.
Solusi: submit dummy survey answers via API sekali untuk mengisi
`personalizationAnswers`, sehingga survey tidak pernah muncul lagi.

**Dijalankan sekali** setelah `docker compose up -d`:
```powershell
cd deploy\phase-0
.\scripts\dismiss-survey.ps1 -Email admin@asuralab.io
# Script akan prompt password secara aman (SecureString)
```

---

## n8n Source Code yang Direferensikan (tidak dimodifikasi)

File-file ini menjelaskan _bagaimana_ fitur auto-provision bekerja di n8n:

| File | Peran |
|---|---|
| `packages/@n8n/config/src/configs/instance-settings-loader.config.ts` | Definisi env vars `N8N_INSTANCE_OWNER_*` |
| `packages/cli/src/instance-settings-loader/loaders/owner.instance-settings-loader.ts` | Dipanggil saat startup, trigger `setupOwner()` |
| `packages/cli/src/services/ownership.service.ts` | `setupOwner()` — upsert owner user, set `isInstanceOwnerSetUp=true` |
| `packages/@n8n/config/src/configs/personalization.config.ts` | `N8N_PERSONALIZATION_ENABLED` env var |
| `packages/cli/src/services/frontend.service.ts` | Mengembalikan `personalizationSurveyEnabled` ke frontend |

---

## Cara Menjalankan Phase 0 dari Nol

```powershell
# 1. Masuk ke direktori phase-0
cd deploy\phase-0

# 2. Generate .env (Windows)
.\scripts\provision.ps1

# 3. Jalankan stack
docker compose up -d

# 4. Tunggu ~15 detik sampai n8n siap, lalu suppress survey
.\scripts\dismiss-survey.ps1

# 5. Buka browser
# URL: http://localhost:5678
# Login: admin@asuralab.io / (password dari output provision script)
```

---

## Masalah yang Ditemukan dan Solusinya

### 1. `$` dalam bcrypt hash rusak oleh Docker Compose

**Masalah:** Docker Compose menginterpretasi `$2a$12$...` sebagai variable
reference `$2a`, `$12`, dll. Warning: `"The \"..\" variable is not set"`.

**Solusi:** Escape `$` → `$$` di file `.env`. Berlaku untuk `env_file` maupun
`environment:` block.

### 2. `docker compose restart` tidak memuat ulang env_file

**Masalah:** Setelah mengubah `.env`, `docker compose restart` tidak mengubah
environment variable di container yang sudah berjalan.

**Solusi:** Gunakan `docker compose up -d` — ini recreate container dan
membaca ulang `env_file`.

### 3. Survey masih muncul di incognito meskipun flag sudah di-set

**Masalah:** `N8N_PERSONALIZATION_ENABLED=false` sudah benar (API `/rest/settings`
mengembalikan `personalizationSurveyEnabled: false`), tapi survey tetap muncul.

**Solusi:** Jalankan `dismiss-survey.ps1` untuk submit dummy answers sekali.
n8n v2.25.7 memeriksa `personalizationAnswers` secara terpisah dari flag enabled.

### 4. Password authentication failed setelah re-provision

**Masalah:** `docker compose down` tanpa `-v` mempertahankan volume Postgres
dengan password lama.

**Solusi:** `docker compose down -v` untuk menghapus volume, lalu `docker compose up -d`.

### 5. Volume Postgres retain data lama

**Masalah:** Container name conflict atau data tidak sinkron setelah provision ulang.

**Solusi:**
```powershell
docker compose down --remove-orphans -v
docker compose up -d
```

---

## Lingkungan yang Digunakan

- Docker Desktop for Windows
- n8n image: `n8nio/n8n:latest` (v2.25.7 saat testing)
- PostgreSQL: `postgres:16-alpine`
- Node.js: digunakan untuk generate bcrypt hash (via `bcryptjs` dari node_modules n8n)
- PowerShell 5.1 (Windows)

---

## Yang TIDAK Berubah dari n8n

- Tidak ada source code n8n yang dimodifikasi
- Tidak ada patch atau override pada image Docker
- Semua fitur workflow n8n tetap berfungsi normal
- Update n8n cukup dengan mengganti tag image di `docker-compose.yml`
