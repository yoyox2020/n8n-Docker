# Phase 0 — Kustomisasi Halaman Login & Logo Sidebar

Dokumen ini menjelaskan seluruh perubahan yang dilakukan untuk mengganti tampilan
halaman login n8n dengan desain bermerek MST (Mitra Solusi Telematika), serta
mengganti logo kecil di pojok kiri atas sidebar aplikasi.

---

## Gambaran Umum Perubahan

| Area | Perubahan |
|---|---|
| Halaman login | Desain ulang penuh — layout kartu, warna biru-teal, logo MST inline SVG |
| Logo sidebar (kiri atas) | Logo n8n (ikon bulat orange) diganti logo MST dari file `MST-PL.svg` |
| Aset logo | File SVG MST disalin ke direktori source frontend |
| TypeScript | Deklarasi tipe untuk import `*.svg?url` ditambahkan |
| Docker | Image di-rebuild ulang dengan dist frontend yang sudah dikompilasi |

---

## Bagian 1 — Halaman Login

### File yang Diubah

```
packages/
└── frontend/
    └── editor-ui/
        └── src/
            └── features/
                └── core/
                    └── auth/
                        └── views/
                            └── SigninView.vue   ← DITULIS ULANG SELURUHNYA
```

**Path lengkap:**
`packages/frontend/editor-ui/src/features/core/auth/views/SigninView.vue`

### Apa yang Diubah

File ini **sebelumnya** merender login via komponen `AuthView.vue` → `N8nFormBox`
(tampilan default n8n dengan logo n8n dan form minimalis).

**Setelah perubahan**, file ini:

- **Tidak lagi** menggunakan `AuthView.vue` atau `N8nFormBox`
- Menampilkan halaman login **custom penuh** dengan:
  - Latar belakang gradient biru muda ke putih
  - Kartu putih di tengah dengan bayangan halus
  - Logo MST berupa SVG inline (bentuk huruf `m` dan `+` dengan gradient cyan → hijau → emas)
  - Teks branding: `mitra solusi telematika`
  - Judul: **Selamat Datang**
  - Subjudul: *Silakan masuk ke akun Anda*
  - Input email dengan ikon amplop
  - Input password dengan ikon gembok + toggle show/hide
  - Tautan "Lupa Kata Sandi?" di baris label password
  - Tombol **Masuk** warna teal gelap (`#1a5f7a`)
  - Footer: *Dilindungi enkripsi enterprise*

### Logika yang Dipertahankan

Seluruh logika autentikasi **tidak diubah** — hanya lapisan tampilan yang diganti:

| Fungsi | Status |
|---|---|
| `login()` — kirim kredensial ke backend | Dipertahankan |
| `onEmailPasswordSubmitted()` | Dipertahankan |
| `onMFASubmitted()` | Dipertahankan |
| Redirect setelah login berhasil | Dipertahankan |
| Tampilan MFA (`MfaView`) | Dipertahankan — muncul menggantikan form login |
| Deteksi MFA error code | Dipertahankan |
| Telemetry tracking | Dipertahankan |

Fungsi baru yang ditambahkan:

```typescript
// Menghubungkan form custom ke fungsi login yang sudah ada
const handleSubmit = async (e: Event) => {
    e.preventDefault();
    await onEmailPasswordSubmitted({
        emailOrLdapLoginId: localEmail.value,
        password: localPassword.value,
    });
};
```

### Logo SVG di Halaman Login (Inline)

Logo MST di halaman login dibuat sebagai **SVG inline** langsung di template —
bukan file terpisah. Ini membuat halaman login tidak memiliki dependensi aset
eksternal.

```
Bentuk:   m  +
Warna:    Gradient linear dari kiri-bawah ke kanan-atas
          Cyan (#14C2DA) → Hijau (#7ABF3E) → Emas (#E8A020)
ViewBox:  0 0 175 95
```

### Tidak Ada Dependensi Baru

Halaman login tidak menambahkan import library atau package baru. Semua import
sudah ada di project sebelumnya:

```typescript
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import MfaView from './MfaView.vue';
import { useToast } from '@/app/composables/useToast';
import { useI18n } from '@n8n/i18n';
import { useTelemetry } from '@/app/composables/useTelemetry';
import { useUsersStore } from '@/features/settings/users/users.store';
import { useSettingsStore } from '@/app/stores/settings.store';
import { MFA_AUTHENTICATION_REQUIRED_ERROR_CODE, VIEWS, MFA_FORM } from '@/app/constants';
import type { LoginRequestDto } from '@n8n/api-types';
```

---

## Bagian 2 — Logo Kecil di Kiri Atas Sidebar

### File yang Diubah

```
packages/
└── frontend/
    └── editor-ui/
        └── src/
            └── app/
                ├── mst-logo.svg                      ← FILE BARU (aset logo MST)
                ├── components/
                │   └── MainSidebarHeader.vue          ← DIMODIFIKASI
                └── ...

src/
└── shims-global.d.ts                                 ← DIMODIFIKASI (deklarasi tipe)
```

### `MainSidebarHeader.vue`

**Path lengkap:**
`packages/frontend/editor-ui/src/app/components/MainSidebarHeader.vue`

**Sebelum:**
```vue
import { N8nLogo } from '@n8n/design-system';
import { useSettingsStore } from '@/app/stores/settings.store';

<N8nLogo
    size="small"
    :collapsed="isCollapsed"
    :release-channel="settingsStore.settings.releaseChannel"
/>
```

**Sesudah:**
```vue
import mstLogo from '@/app/mst-logo.svg?url';

<img :src="mstLogo" alt="MST Logo" :class="$style.mstLogo" />
```

Perubahan detail:
- `N8nLogo` dihapus dari import `@n8n/design-system`
- `useSettingsStore` dihapus (tidak lagi dibutuhkan)
- Import `mstLogo` dari file SVG menggunakan suffix `?url` agar Vite
  mengembalikan URL string (bukan komponen Vue, karena project menggunakan
  plugin `vite-svg-loader`)
- CSS class `.mstLogo` ditambahkan: `height: 28px; width: auto; object-fit: contain`
- Class `.logo` diperbarui: `display: flex; align-items: center`

### `mst-logo.svg` (Aset Baru)

**Path lengkap:**
`packages/frontend/editor-ui/src/app/mst-logo.svg`

File ini adalah salinan dari `MST-PL.svg` yang disediakan oleh pengguna.

| Properti | Nilai |
|---|---|
| Format | SVG (XML-based vector) |
| Ukuran file | ±461 KB |
| Dimensi viewBox | 1400 × 667 |
| Jumlah baris | 1018 baris |
| Konten | Logo MST penuh dengan path kompleks (huruf `m` dan tanda `+`) |
| Warna | Dua zona: hijau dan kuning-emas |

> **Mengapa disimpan sebagai file terpisah (bukan inline)?**
> File SVG sebesar 461KB dengan 1018 baris path tidak praktis untuk di-inline
> dalam Vue template. Menyimpannya sebagai aset membuat template tetap bersih
> dan file SVG bisa di-cache oleh browser secara terpisah.

### `shims-global.d.ts`

**Path lengkap:**
`packages/frontend/editor-ui/src/shims-global.d.ts`

Ditambahkan deklarasi TypeScript untuk import SVG dengan query `?url`:

```typescript
// Sebelum: hanya ada ini
declare module '*.svg';

// Sesudah: ditambahkan deklarasi untuk ?url
declare module '*.svg?url' {
    const url: string;
    export default url;
}
```

**Mengapa perlu ini:**
Plugin `vite-svg-loader` secara default mengimpor SVG sebagai komponen Vue.
Dengan suffix `?url`, Vite mengimpornya sebagai string URL untuk dipakai di
atribut `src` pada tag `<img>`. TypeScript tidak mengenal query string `?url`
secara native, sehingga deklarasi ini diperlukan agar kompiler tidak error.

---

## Bagian 3 — Proses Build dan Deploy

### Urutan Perintah

```powershell
# 1. Kompilasi frontend
pnpm --filter=n8n-editor-ui... build

# 2. Rebuild Docker image
docker build -f deploy/phase-0/Dockerfile -t asuralab/n8n:phase-0 .

# 3. Redeploy container (recreate dengan image baru)
cd deploy\phase-0
docker compose up -d
```

### Dockerfile

**Path:** `deploy/phase-0/Dockerfile`

```dockerfile
FROM n8nio/n8n:latest
USER root
COPY packages/frontend/editor-ui/dist/ \
     /usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-editor-ui@file+packages+frontend+editor-ui/node_modules/n8n-editor-ui/dist/
USER node
```

Dockerfile menyalin seluruh folder `dist/` hasil build ke lokasi yang sama
di dalam image resmi n8n. Path tujuan panjang karena n8n menggunakan pnpm
workspace dengan path berbasis `@file+` di dalam image resmi.

### File Hasil Kompilasi (di `dist/assets/`)

Setelah build, Vite menghasilkan file dengan hash konten di namanya.
File yang relevan dengan perubahan ini:

| File (contoh nama dengan hash) | Isi |
|---|---|
| `MainSidebarHeader-[hash].js` | Komponen sidebar header dengan logo MST |
| `SigninView-[hash].js` | Halaman login custom MST |
| `SigninView-[hash].css` | Style halaman login |
| `mst-logo-[hash].svg` | Aset logo MST (di-copy dan diberi hash oleh Vite) |

> Hash berubah setiap kali konten file berubah, sehingga browser tidak
> meng-cache file lama.

---

## Ringkasan File yang Disentuh

| No | File | Aksi | Dampak |
|---|---|---|---|
| 1 | `packages/frontend/editor-ui/src/features/core/auth/views/SigninView.vue` | Ditulis ulang | Halaman login custom MST |
| 2 | `packages/frontend/editor-ui/src/app/components/MainSidebarHeader.vue` | Dimodifikasi | Logo sidebar diganti MST |
| 3 | `packages/frontend/editor-ui/src/app/mst-logo.svg` | Ditambahkan | Aset logo MST untuk sidebar |
| 4 | `packages/frontend/editor-ui/src/shims-global.d.ts` | Dimodifikasi | Deklarasi tipe `*.svg?url` |
| 5 | `deploy/phase-0/Dockerfile` | Digunakan | Build & deploy image custom |

---

## Yang TIDAK Diubah

- Tidak ada perubahan pada route/router
- Tidak ada perubahan pada API endpoint login
- Tidak ada perubahan pada logika autentikasi backend
- MFA (Multi-Factor Authentication) tetap berfungsi normal
- LDAP login tetap berfungsi normal
- Redirect setelah login tetap berfungsi
- Fitur "Lupa Kata Sandi" tetap menggunakan halaman n8n default
