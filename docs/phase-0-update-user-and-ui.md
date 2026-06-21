# Phase 0 — Perubahan UI & Konfigurasi Deployment

Dokumen ini mencatat **semua perubahan** yang dilakukan pada phase-0, mencakup
folder, nama file, dan cara perubahannya. Tujuannya agar perubahan bisa
direproduksi di branch baru atau server baru.

---

## Daftar Perubahan

| # | Kategori | File | Jenis |
|---|----------|------|-------|
| 1 | Branding Docker | `deploy/phase-0/docker-compose.yml` | Edit |
| 2 | Konfigurasi Runtime | `deploy/phase-0/.env` | Edit |
| 3 | Docker Build | `deploy/phase-0/Dockerfile` | Baru (rewrite) |
| 4 | Docker Context | `deploy/phase-0/Dockerfile.dockerignore` | Baru |
| 5 | License Backend | `packages/@n8n/backend-common/src/license-state.ts` | Edit |
| 6 | License Backend | `packages/cli/src/workflows/workflows.controller.ts` | Edit |
| 7 | License Frontend | `packages/frontend/editor-ui/src/app/stores/settings.store.ts` | Edit |
| 8 | Welcome Screen | `packages/frontend/editor-ui/src/features/ai/chatHub/components/ChatStarter.vue` | Edit |
| 9 | Logo Asset | `packages/frontend/editor-ui/src/app/mst-logo.svg` | Baru |
| 10 | Build Fix | `packages/@n8n/mcp-browser/src/vendor.d.ts` | Edit |
| 11 | WSL2 Config | `C:\Users\{user}\.wslconfig` | Baru |

---

## 1. Branding Docker

**File:** `deploy/phase-0/docker-compose.yml`

Ganti semua kemunculan nama `asuralab` menjadi `mstworkflow` — mencakup
nama network dan nama image.

```yaml
# SEBELUM
image: asuralab/n8n:phase-0
networks:
  - asuralab

networks:
  asuralab:

# SESUDAH
image: mstworkflow/n8n:phase-0
networks:
  - mstworkflow

networks:
  mstworkflow:
```

---

## 2. Konfigurasi Runtime

**File:** `deploy/phase-0/.env`

> ⚠️ File ini TIDAK boleh di-commit ke git. Berisi kredensial sensitif.

Perubahan utama dari konfigurasi default:

```env
# Identitas owner instance
N8N_INSTANCE_OWNER_EMAIL=admin@mst.co.id
N8N_INSTANCE_OWNER_FIRST_NAME=Admin
N8N_INSTANCE_OWNER_LAST_NAME=Mst

# Hash password menggunakan bcrypt (single $, BUKAN $$)
# Generate dengan: node -e "console.log(require('bcryptjs').hashSync('PASSWORD',12))"
N8N_INSTANCE_OWNER_PASSWORD_HASH=$2a$12$xxxx...

# Matikan PostHog telemetry (mencegah error ENOTFOUND ph.n8n.io)
N8N_DIAGNOSTICS_ENABLED=false
```

**Catatan penting — format hash password:**
- Di `env_file` Docker Compose, nilai dibaca **literal**
- Gunakan `$2a$12$...` (single dollar), BUKAN `$$2a$$12$$...`
- `$$` hanya valid di bagian `environment:` YAML (bukan `env_file:`)

---

## 3. Docker Build — Dockerfile

**File:** `deploy/phase-0/Dockerfile`

Multi-stage build dari source fork. Menggantikan pendekatan lama yang
meng-patch official image `n8nio/n8n:latest`.

**Mengapa diperlukan:**
Pendekatan patch tidak menyertakan perubahan backend dari fork (license bypass,
RBAC, dll). Build dari source memastikan semua perubahan fork masuk ke image.

**Ringkasan 3 stage:**

```dockerfile
# Stage 1: builder — compile TypeScript semua packages
FROM node:24-alpine AS builder
RUN apk add --no-cache python3 make g++ git
RUN corepack enable && corepack prepare pnpm@10.32.1 --activate
WORKDIR /build
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json .npmrc ./
COPY scripts/ ./scripts/
COPY patches/ ./patches/
COPY packages/ ./packages/
RUN git init .   # diperlukan agar lefthook bisa install git hooks
RUN pnpm install --frozen-lockfile
RUN NODE_OPTIONS=--max-old-space-size=4096 \
    pnpm exec turbo run build --filter=n8n...
RUN pnpm deploy --filter=n8n --prod --legacy /compiled

# Stage 2: native-builder — compile ulang native addon untuk Alpine musl
FROM node:24-alpine AS native-builder
RUN apk add --no-cache python3 make g++
COPY --from=builder /compiled /usr/local/lib/node_modules/n8n
RUN cd /usr/local/lib/node_modules/n8n && npm rebuild sqlite3
RUN if [ -d .../isolated-vm ]; then ... node-gyp rebuild; fi

# Stage 3: runtime — image final yang ringan
FROM node:24-alpine
# copy dari native-builder, setup user node, entrypoint
```

**Hal-hal yang perlu diperhatikan saat build:**

| Masalah | Penyebab | Solusi |
|---------|----------|--------|
| `block-npm-install.js not found` | `scripts/` tidak di-copy | `COPY scripts/ ./scripts/` |
| `lefthook install` gagal | Tidak ada `.git` dir | `RUN git init .` |
| TypeScript error `@lezer/common` | `.npmrc` tidak di-copy | `COPY .npmrc ./` |
| `jsdom` type error | `@types/jsdom` tidak ada | Tambah deklarasi di `vendor.d.ts` |
| OOM saat compile `packages/cli` | Default heap Node.js ~2GB | `NODE_OPTIONS=--max-old-space-size=4096` |
| `pnpm deploy` error v10 | Breaking change pnpm v10 | Tambah flag `--legacy` |
| `@n8n/playwright-janitor` not found | `packages/testing` di-exclude | Hapus dari Dockerignore |
| `TS5083: Cannot read file '/build/tsconfig.json'` | Root `tsconfig.json` tidak di-copy | Tambah `tsconfig.json` ke COPY line |

---

## 4. Docker Context Filter

**File:** `deploy/phase-0/Dockerfile.dockerignore`

File baru yang mengontrol apa yang masuk ke Docker build context.
Digunakan otomatis oleh BuildKit ketika nama file mengikuti format
`<Dockerfile>.dockerignore`.

```
.git
node_modules
**/node_modules
packages/*/dist
packages/frontend/editor-ui/dist
deploy/
!deploy/phase-0/Dockerfile
packages/**/__tests__
packages/**/*.spec.ts
packages/**/*.test.ts
**/*.md
docs/
.github
.circleci
```

**Catatan:** `packages/testing` TIDAK di-exclude karena pnpm workspace
resolution membutuhkan `package.json` dari packages di sana
(contoh: `@n8n/playwright-janitor`).

---

## 5. License Backend — LicenseState

**File:** `packages/@n8n/backend-common/src/license-state.ts`

Hardcode fitur `sharing` agar selalu aktif tanpa perlu license enterprise.

```typescript
// SEBELUM
isSharingLicensed(): boolean {
    return this.license.isLicensed('feat:sharing');
}

// SESUDAH
isSharingLicensed(): boolean {
    return true;  // fork: aktifkan sharing tanpa license
}
```

---

## 6. License Backend — Workflow Controller

**File:** `packages/cli/src/workflows/workflows.controller.ts`

Hapus decorator `@Licensed('feat:sharing')` dari endpoint share workflow.
Decorator ini menyebabkan error 403 "Plan lacks license for this feature"
saat user mencoba share workflow ke member lain.

```typescript
// SEBELUM
@Licensed('feat:sharing')
async shareWorkflow(...) { ... }

// SESUDAH
async shareWorkflow(...) { ... }
```

---

## 7. License Frontend — Settings Store

**File:** `packages/frontend/editor-ui/src/app/stores/settings.store.ts`

Hardcode fitur `sharing` di frontend agar UI menampilkan tombol share
tanpa pengecekan license.

```typescript
// Lokasi: computed property isEnterpriseFeatureEnabled
const isEnterpriseFeatureEnabled = computed(() => ({
    ...(settings.value.enterprise ?? {}),
    sharing: true,  // fork: selalu aktif
}));
```

---

## 8. Welcome Screen Chat Hub

**File:** `packages/frontend/editor-ui/src/features/ai/chatHub/components/ChatStarter.vue`

Mengganti tampilan welcome screen `/home/chat` dari 3 kartu agen (Workflow
Agents, Personal Agents, Base Agents) menjadi logo MST + sapaan personal.

**Perubahan utama:**

```typescript
// Tambah import
import { useUsersStore } from '@/features/settings/users/users.store';
import mstLogo from '@/app/mst-logo.svg?url';

// Computed untuk nama user yang login
const currentUserName = computed(() => {
    const user = usersStore.currentUser;
    if (!user) return '';
    const full = [user.firstName, user.lastName].filter(Boolean).join(' ');
    return full || user.email || '';
});
```

```html
<!-- Template baru — ganti cardGrid dengan logo + greeting -->
<img :src="mstLogo" alt="MST Logo" :class="$style.mstLogo" />
<div :class="$style.header">
    <N8nHeading tag="h2" bold size="xlarge">
        Selamat datang<span v-if="currentUserName">, {{ currentUserName }}</span>!
    </N8nHeading>
</div>
```

```scss
// CSS baru untuk logo
.mstLogo {
    height: 72px;
    width: auto;
    object-fit: contain;
}
```

**Import yang dihapus:** `N8nCard`, `N8nIcon`, `CredentialIcon` (tidak dipakai lagi)

---

## 9. Logo Asset

**File:** `packages/frontend/editor-ui/src/app/mst-logo.svg`

File SVG logo MST yang ditampilkan di welcome screen. Letakkan di path ini
dan import menggunakan:

```typescript
import mstLogo from '@/app/mst-logo.svg?url';
```

---

## 10. Build Fix — jsdom Type Declaration

**File:** `packages/@n8n/mcp-browser/src/vendor.d.ts`

Package `@n8n/mcp-browser` menggunakan `jsdom` tapi tidak punya
`@types/jsdom` di devDependencies. Tanpa deklarasi ini TypeScript 6.0
gagal compile dengan error TS7016.

```typescript
// Tambahkan di vendor.d.ts
declare module 'jsdom' {
    interface DOMWindow {
        document: Document;
        [key: string]: unknown;
    }
    interface JSDOMOptions {
        virtualConsole?: InstanceType<typeof VirtualConsole>;
        url?: string;
        // ... opsi lainnya
    }
    class JSDOM {
        constructor(html: string, options?: JSDOMOptions);
        readonly window: DOMWindow;
        serialize(): string;
    }
    class VirtualConsole {
        sendTo(console: Partial<Console>, options?: { omitJSDOMErrors?: boolean }): this;
        on(event: string, listener: (...args: unknown[]) => void): this;
    }
    export { JSDOM, VirtualConsole };
}
```

---

## 11. WSL2 Memory Config

**File:** `C:\Users\{username}\.wslconfig`

Diperlukan di Windows dengan Docker Desktop (WSL2 backend) agar build
TypeScript tidak OOM. Buat file baru jika belum ada.

```ini
[wsl2]
memory=10GB
processors=4
swap=4GB
```

Setelah membuat file, restart WSL2:
```powershell
wsl --shutdown
```

**Kapan diperlukan:** Saat compile `packages/cli` dengan TypeScript,
proses membutuhkan ~4GB heap. Default WSL2 pada sistem 16GB hanya
menyediakan 8GB, dan dengan proses Windows lain berjalan bisa kurang.

---

## Cara Build Docker Image

Dari root repo, jalankan:

```powershell
cd C:\Users\Acer\n8n-Docker
docker build -f deploy/phase-0/Dockerfile -t mstworkflow/n8n:phase-0 .
```

Estimasi waktu: **15–30 menit** (tergantung koneksi internet dan CPU).

Setelah berhasil, jalankan dengan:

```powershell
cd deploy/phase-0
docker compose up -d
```

---

## Catatan Penting

- File `.env` **JANGAN di-commit** ke git — berisi password dan encryption key
- Setiap kali ada perubahan source code di fork, image perlu **di-build ulang**
  dan di-push ke registry agar server customer mendapatkan versi terbaru
- Build hanya perlu dilakukan **sekali** — server customer cukup `docker pull`
