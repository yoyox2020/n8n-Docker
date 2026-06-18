# Phase 0 — Setup Database

Dokumen ini menjelaskan konfigurasi database yang digunakan pada Phase 0,
mencakup pemilihan database, struktur docker-compose, variabel environment,
manajemen volume, dan prosedur operasional.

---

## Database yang Digunakan

| Properti | Nilai |
|---|---|
| Engine | **PostgreSQL 16** |
| Image Docker | `postgres:16-alpine` |
| Nama service (Docker) | `postgres` |
| Nama database default | `n8n` |
| User default | `n8n` |
| Port | `5432` (internal Docker network, tidak diekspos ke host) |

> **Mengapa PostgreSQL, bukan SQLite?**
> n8n mendukung dua database: SQLite (default, file-based) dan PostgreSQL.
> Phase 0 menggunakan PostgreSQL karena lebih siap untuk environment produksi:
> mendukung concurrent writes, lebih stabil untuk data besar, dan bisa
> di-scale secara horizontal di fase berikutnya.

---

## Struktur File

```
deploy/
└── phase-0/
    ├── docker-compose.yml     ← Definisi service postgres + n8n
    ├── .env.example           ← Template variabel (di-commit ke git)
    ├── .env                   ← File rahasia — JANGAN di-commit (dibuat oleh provision script)
    └── scripts/
        ├── provision.ps1      ← Generate .env (Windows PowerShell)
        └── provision.sh       ← Generate .env (Linux/macOS/WSL)
```

---

## Konfigurasi docker-compose.yml

**Path:** `deploy/phase-0/docker-compose.yml`

### Service `postgres`

```yaml
postgres:
  image: postgres:16-alpine
  restart: unless-stopped
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-n8n}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}
    POSTGRES_DB: ${POSTGRES_DB:-n8n}
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-n8n}"]
    interval: 5s
    timeout: 5s
    retries: 10
  networks:
    - asuralab
```

**Poin penting:**

- `restart: unless-stopped` — container otomatis restart jika crash atau host reboot,
  kecuali dihentikan secara manual.
- `${POSTGRES_PASSWORD:?...}` — Compose akan **error dan berhenti** jika variabel
  ini tidak di-set. Ini adalah safeguard agar database tidak pernah berjalan
  tanpa password.
- `healthcheck` — Compose menunggu sampai Postgres benar-benar siap menerima
  koneksi sebelum n8n dijalankan (lihat `depends_on` di service n8n).
- Port `5432` **tidak diekspos** ke host — hanya dapat diakses dari service n8n
  dalam Docker network internal `asuralab`.

### Service `n8n` — Koneksi ke Database

```yaml
n8n:
  depends_on:
    postgres:
      condition: service_healthy   # ← n8n hanya start setelah Postgres ready
  environment:
    DB_TYPE: postgresdb
    DB_POSTGRESDB_HOST: postgres   # nama service Docker, bukan localhost
    DB_POSTGRESDB_PORT: 5432
    DB_POSTGRESDB_USER: ${POSTGRES_USER:-n8n}
    DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}
    DB_POSTGRESDB_DATABASE: ${POSTGRES_DB:-n8n}
```

**Mengapa `DB_POSTGRESDB_HOST: postgres` (bukan `localhost`)?**

Di dalam Docker network, setiap service dikenali berdasarkan nama servicenya.
`localhost` di dalam container n8n merujuk ke container itu sendiri, bukan ke
container postgres. Hostname `postgres` secara otomatis diselesaikan oleh
Docker ke IP container postgres di dalam network `asuralab`.

### Docker Network

```yaml
networks:
  asuralab:
    driver: bridge
```

Network bernama `asuralab` dibuat sebagai bridge network yang mengisolasi
postgres dari traffic luar. Hanya container yang tergabung ke network ini
yang bisa menjangkau postgres.

---

## Volume dan Persistensi Data

```yaml
volumes:
  postgres_data:    # Data PostgreSQL
  n8n_data:        # (Didefinisikan, tidak dipakai di Phase 0 — untuk referensi fase berikutnya)
```

Volume `postgres_data` adalah **Docker named volume** — artinya data tersimpan
di area yang dikelola Docker (`/var/lib/docker/volumes/`) dan **tetap ada**
meskipun container dihapus.

### Operasi Volume

```powershell
# Lihat semua volume yang ada
docker volume ls | grep postgres

# Hentikan stack TANPA menghapus data
docker compose down

# Hentikan stack DAN hapus semua data (DESTRUCTIVE — tidak bisa dibatalkan)
docker compose down -v
```

> **Peringatan:** `docker compose down -v` menghapus volume secara permanen.
> Gunakan hanya saat ingin reset total (misalnya ganti password owner).

---

## Variabel Environment Database

### Di File `.env`

File `.env` dibuat otomatis oleh `provision.ps1`. Variabel yang relevan untuk
database:

| Variabel | Contoh Nilai | Deskripsi |
|---|---|---|
| `POSTGRES_USER` | `n8n` | Username untuk Postgres |
| `POSTGRES_PASSWORD` | `xK9mR2...` (32 char) | Password Postgres — random alphanumeric |
| `POSTGRES_DB` | `n8n` | Nama database |

### Dibaca Oleh Docker Compose

Variabel `POSTGRES_*` dibaca Docker Compose via **interpolasi** (bukan `env_file`)
karena dipakai di kedua service (postgres dan n8n). Ini aman karena nilainya
berupa string alphanumeric tanpa karakter spesial seperti `$`.

**Berbeda dengan** `N8N_INSTANCE_OWNER_PASSWORD_HASH` yang mengandung `$` dan
harus dibaca via `env_file` untuk menghindari interpolasi Compose.

### Variabel Koneksi n8n

Variabel `DB_POSTGRESDB_*` di-set via blok `environment:` di docker-compose.yml
(bukan dari `.env`), karena memerlukan hostname Docker internal (`postgres`) yang
tidak bisa ditentukan saat `.env` di-generate.

---

## Script Provision

### `scripts/provision.ps1` (Windows)

**Path:** `deploy/phase-0/scripts/provision.ps1`

Script ini dijalankan **sekali** sebelum `docker compose up` untuk menghasilkan
file `.env` dengan kredensial yang aman.

**Yang dilakukan untuk database:**

1. Generate `POSTGRES_PASSWORD` — string random 32 karakter alphanumeric
   (hanya A-Z, a-z, 0-9 — tanpa `$` agar aman dari interpolasi Compose)
2. Tulis ke `.env` dengan nama variabel yang langsung dipakai Docker Compose

```powershell
$chars32          = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
$PostgresPassword = -join ((1..32) | ForEach-Object { $chars32[(Get-Random -Maximum $chars32.Length)] })
```

**Cara penggunaan:**

```powershell
cd deploy\phase-0
.\scripts\provision.ps1
# atau dengan email kustom:
.\scripts\provision.ps1 -Email admin@perusahaan.com
```

### `scripts/provision.sh` (Linux/macOS/WSL)

Versi bash yang setara dengan `provision.ps1`. Dijalankan dengan cara:

```bash
cd deploy/phase-0
chmod +x scripts/provision.sh
./scripts/provision.sh admin@perusahaan.com MyPassword123
```

---

## Cara Kerja n8n dengan Database

### Inisialisasi Otomatis

n8n secara otomatis membuat skema database (tabel, index, relasi) pada startup
pertama jika database kosong. Tidak diperlukan migrasi manual.

Tabel utama yang dibuat n8n:

| Tabel | Isi |
|---|---|
| `user` | Akun pengguna (owner dan member) |
| `workflow_entity` | Definisi workflow |
| `credentials_entity` | Kredensial terenkripsi |
| `execution_entity` | Riwayat eksekusi workflow |
| `shared_workflow` | Relasi workflow ↔ user (untuk sharing) |
| `shared_credentials` | Relasi credential ↔ user |
| `settings` | Konfigurasi instance n8n |
| `webhook_entity` | Webhook aktif |

### Owner Auto-Provision

Variabel `N8N_INSTANCE_OWNER_MANAGED_BY_ENV=true` membuat n8n otomatis
membuat atau memperbarui record owner di tabel `user` pada setiap startup,
menggunakan nilai dari:

```
N8N_INSTANCE_OWNER_EMAIL
N8N_INSTANCE_OWNER_PASSWORD_HASH
N8N_INSTANCE_OWNER_FIRST_NAME
N8N_INSTANCE_OWNER_LAST_NAME
```

### Enkripsi Kredensial

Semua credential workflow (API key, password layanan eksternal) **dienkripsi**
sebelum disimpan ke tabel `credentials_entity` menggunakan kunci:

```
N8N_ENCRYPTION_KEY=<32 char random>
```

> **Penting:** Jika `N8N_ENCRYPTION_KEY` berubah, semua credential yang
> tersimpan tidak bisa didekripsi dan harus dimasukkan ulang.

---

## Prosedur Operasional

### Menjalankan Stack untuk Pertama Kali

```powershell
# 1. Buat file .env
cd deploy\phase-0
.\scripts\provision.ps1

# 2. Jalankan stack
docker compose up -d

# 3. Verifikasi semua container running
docker compose ps
```

### Melihat Log Database

```powershell
# Log Postgres
docker compose logs postgres

# Log n8n (termasuk log koneksi DB)
docker compose logs n8n
```

### Restart Stack (Tanpa Hapus Data)

```powershell
docker compose down
docker compose up -d
```

### Reset Total (Hapus Semua Data)

```powershell
# PERINGATAN: Seluruh data workflow, credential, dan user akan hilang
docker compose down -v
.\scripts\provision.ps1    # generate .env baru
docker compose up -d
```

### Cek Koneksi Database dari Dalam Container

```powershell
# Masuk ke shell container postgres
docker exec -it phase-0-postgres-1 psql -U n8n -d n8n

# Lihat tabel yang ada
\dt

# Lihat daftar user n8n
SELECT email, role FROM "user";

# Keluar
\q
```

### Backup Database

```powershell
# Dump database ke file SQL
docker exec phase-0-postgres-1 pg_dump -U n8n n8n > backup-$(Get-Date -Format "yyyyMMdd").sql

# Restore dari backup
Get-Content backup-20240615.sql | docker exec -i phase-0-postgres-1 psql -U n8n -d n8n
```

---

## Masalah Umum dan Solusinya

### n8n tidak bisa konek ke database

**Gejala:** Log n8n menampilkan `ECONNREFUSED` atau `connection refused`

**Penyebab dan solusi:**
1. Postgres belum selesai start → tunggu beberapa detik, healthcheck akan
   mencoba ulang sampai 10 kali (interval 5s = max 50 detik)
2. `POSTGRES_PASSWORD` di `.env` tidak cocok dengan yang di-set ke container →
   jalankan `docker compose down -v` lalu `docker compose up -d`

### Password authentication failed

**Gejala:** `password authentication failed for user "n8n"`

**Penyebab:** Volume postgres masih menyimpan password lama dari provision
sebelumnya, sementara `.env` sudah diperbarui.

**Solusi:**
```powershell
docker compose down -v    # hapus volume
docker compose up -d      # recreate dengan password baru
```

### `POSTGRES_PASSWORD is required` error saat `docker compose up`

**Penyebab:** File `.env` tidak ada atau `POSTGRES_PASSWORD` kosong.

**Solusi:** Jalankan provision script:
```powershell
.\scripts\provision.ps1
```

---

## Keamanan Database

| Aspek | Implementasi |
|---|---|
| Password | Random 32 karakter alphanumeric, di-generate otomatis |
| Network isolation | Port 5432 tidak diekspos ke host — hanya aksesibel dari network Docker internal |
| Enkripsi data credential | `N8N_ENCRYPTION_KEY` 32 karakter random |
| File `.env` | Di-gitignore — tidak pernah masuk ke repository |
| Password hash owner | bcrypt rounds=12 — tidak disimpan plaintext di mana pun |
