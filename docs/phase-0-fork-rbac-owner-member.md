# Phase 0 — Custom RBAC: Owner & Member

Dokumen ini menjelaskan implementasi sistem Role-Based Access Control (RBAC)
custom pada fork n8n ini. Sistem ini memiliki dua role:

| Role | Akses |
|---|---|
| **Owner** | Full access ke semua workflow, settings, dan user management |
| **Member** | Hanya bisa akses workflow yang di-share oleh Owner. Pada workflow tersebut: view, edit, hapus, dan tambah node |

---

## Gambaran Umum

```
Owner
 ├── Kelola semua workflow (buat, edit, hapus, archive)
 ├── Invite/hapus user Member
 ├── Share workflow ke Member tertentu
 └── Akses semua Settings

Member
 └── Hanya melihat workflow yang di-share kepadanya
      ├── View workflow
      ├── Edit workflow (tambah/ubah/hapus node)
      ├── Hapus workflow (yang sudah di-share)
      └── Jalankan workflow
```

---

## File yang Diubah

| No | File | Aksi | Dampak |
|---|---|---|---|
| 1 | `packages/frontend/editor-ui/src/features/settings/users/users.store.ts` | Dimodifikasi | Hapus batas kuota user |
| 2 | `packages/frontend/editor-ui/src/app/stores/settings.store.ts` | Dimodifikasi | Aktifkan fitur Sharing selalu |
| 3 | `packages/frontend/editor-ui/src/features/settings/users/views/SettingsUsersView.vue` | Dimodifikasi | Hapus banner Upgrade, aktifkan tombol Invite |
| 4 | `packages/cli/src/controllers/invitation.controller.ts` | Dimodifikasi | Hapus license check untuk undang user |
| 5 | `packages/@n8n/permissions/src/roles/scopes/workflow-sharing-scopes.ee.ts` | Dimodifikasi | Member dapat permission hapus workflow |

---

## Detail Perubahan per File

---

### File 1 — `users.store.ts`

**Path:** `packages/frontend/editor-ui/src/features/settings/users/users.store.ts`

**Lokasi:** Computed property `usersLimitNotReached` (~baris 124)

**Sebelum:**
```typescript
const usersLimitNotReached = computed(
    (): boolean => userQuota.value === -1 || userQuota.value > allUsers.value.length,
);
```

**Sesudah:**
```typescript
// Custom RBAC fork: always allow unlimited users
const usersLimitNotReached = computed((): boolean => true);
```

**Mengapa:** `userQuota` dikirim dari backend berdasarkan lisensi. Nilai selain `-1`
akan membatasi jumlah user. Dengan mengembalikan `true` selalu, tombol Invite
dan fitur user management tidak pernah diblokir oleh quota.

---

### File 2 — `settings.store.ts`

**Path:** `packages/frontend/editor-ui/src/app/stores/settings.store.ts`

**Lokasi:** Computed property `isEnterpriseFeatureEnabled` (~baris 68)

**Sebelum:**
```typescript
const isEnterpriseFeatureEnabled = computed(() => settings.value.enterprise ?? {});
```

**Sesudah:**
```typescript
// Custom RBAC fork: always enable sharing so owner can share workflows with members
const isEnterpriseFeatureEnabled = computed(() => ({
    ...(settings.value.enterprise ?? {}),
    sharing: true,
}));
```

**Mengapa:** Fitur Share Workflow (`EnterpriseEditionFeature.Sharing = 'sharing'`)
secara default hanya aktif pada lisensi Enterprise. Dengan memaksa `sharing: true`,
Owner bisa membuka modal Share Workflow dan membagikan workflow ke Member tanpa
lisensi berbayar.

---

### File 3 — `SettingsUsersView.vue`

**Path:** `packages/frontend/editor-ui/src/features/settings/users/views/SettingsUsersView.vue`

**Perubahan A — Hapus banner Upgrade**

Blok `<div v-if="!usersStore.usersLimitNotReached">` beserta `<N8nActionBox>`
di dalamnya dan `<N8nNotice v-if="!isAdvancedPermissionsEnabled">` dihapus seluruhnya.

Banner ini sebelumnya muncul saat quota tercapai dan meminta user membeli lisensi.

**Perubahan B — Tombol Invite selalu aktif**

**Sebelum:**
```vue
:disabled="isSSOEnabled || !usersStore.usersLimitNotReached || isInstanceRoleProvisioningEnabled"
```

**Sesudah:**
```vue
:disabled="isSSOEnabled || isInstanceRoleProvisioningEnabled"
```

**Perubahan C — Tabel user list selalu tampil**

**Sebelum:**
```vue
<div
    v-if="usersStore.usersLimitNotReached || usersStore.usersList.state.count > 1"
    :class="$style.usersContainer"
>
```

**Sesudah:**
```vue
<div :class="$style.usersContainer">
```

---

### File 4 — `invitation.controller.ts`

**Path:** `packages/cli/src/controllers/invitation.controller.ts`

**Lokasi:** Handler `POST /invitations/` (~baris 51-67)

**Sebelum:**
```typescript
const isWithinUsersLimit = this.license.isWithinUsersLimit();

// ... (SSO check) ...

if (!isWithinUsersLimit) {
    this.logger.debug(
        'Request to send email invite(s) to user(s) failed because the user limit quota has been reached',
    );
    throw new ForbiddenError(RESPONSE_ERROR_MESSAGES.USERS_QUOTA_REACHED);
}
```

**Sesudah:**
```typescript
// (Blok quota check dihapus — hanya SSO check yang dipertahankan)
```

**Mengapa:** Pengecekan `license.isWithinUsersLimit()` di backend akan menolak
request undangan meski frontend sudah dimodifikasi. Kedua lapisan (frontend +
backend) harus dibuka agar fitur invite berfungsi.

---

### File 5 — `workflow-sharing-scopes.ee.ts`

**Path:** `packages/@n8n/permissions/src/roles/scopes/workflow-sharing-scopes.ee.ts`

**Lokasi:** Constant `WORKFLOW_SHARING_EDITOR_SCOPES`

**Sebelum:**
```typescript
export const WORKFLOW_SHARING_EDITOR_SCOPES: Scope[] = [
    'workflow:read',
    'workflow:export',
    'workflow:update',
    'workflow:publish',
    'workflow:unpublish',
    'workflow:execute',
    'workflow:execute-chat',
];
```

**Sesudah:**
```typescript
export const WORKFLOW_SHARING_EDITOR_SCOPES: Scope[] = [
    'workflow:read',
    'workflow:export',
    'workflow:update',
    'workflow:delete',      // ← DITAMBAHKAN
    'workflow:publish',
    'workflow:unpublish',
    'workflow:execute',
    'workflow:execute-chat',
];
```

**Mengapa:** Secara default, Member yang mendapat akses editor ke workflow yang
di-share hanya bisa baca dan edit — tidak bisa hapus. Scope `workflow:delete`
ditambahkan agar Member bisa menghapus workflow yang sudah dibagikan kepadanya
(sesuai permintaan: "hapus, edit, dan view node").

---

## Cara Kerja Setelah Perubahan

### Langkah Owner

```
1. Settings → Users → klik "Invite"
2. Masukkan email Member, pilih role "Member"
3. Member menerima link undangan dan buat akun
4. Owner buka workflow yang ingin di-share
5. Klik tombol "Share" (pojok kanan atas editor atau dari menu ⋮)
6. Tambahkan Member ke daftar akses
7. Pilih level akses: Editor
```

### Yang Dilihat Member

```
- Halaman Overview: hanya workflow yang di-share oleh Owner
- Pada workflow tersebut: bisa view, edit, hapus, dan jalankan
- Settings: hanya Personal dan akses terbatas
- Tidak bisa: buat workflow baru di luar yang di-share, akses Settings global
```

---

## Cara Menerapkan Ulang dari Awal

Jika perlu menerapkan pada instalasi baru, urutannya:

```powershell
# 1. Edit kelima file sesuai detail di atas

# 2. Build frontend
cd c:\Users\Acer\n8n-Docker
pnpm --filter=n8n-editor-ui... build > deploy\phase-0\frontend-build.log 2>&1

# 3. Build Docker image
docker build -f deploy/phase-0/Dockerfile -t asuralab/n8n:phase-0 .

# 4. Deploy
cd deploy\phase-0
docker compose up -d --force-recreate
```

---

## Yang TIDAK Diubah

- Logika autentikasi (login, MFA, LDAP) — tidak berubah
- Struktur database — tidak berubah
- API endpoint — tidak berubah strukturnya, hanya dihapus 1 pengecekan quota
- Role `global:owner` dan `global:member` — tetap menggunakan definisi bawaan n8n
- Permission Owner — tetap full access (`GLOBAL_OWNER_SCOPES`, 154 scope)
