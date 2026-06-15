# Phase 0 — Fitur Hapus Workflow Langsung dari List

Dokumen ini menjelaskan perubahan yang dilakukan untuk mengaktifkan fitur
**hapus workflow langsung dari halaman Overview** tanpa harus melalui tahap
archive terlebih dahulu.

---

## Latar Belakang

Perilaku default n8n mengharuskan dua langkah untuk menghapus workflow:

```
Workflow aktif → Archive → (baru bisa) Delete
```

Ini membuat owner tidak bisa langsung menghapus workflow dari list.
Perubahan ini menambahkan opsi **Delete** langsung di menu titik tiga (⋮)
pada setiap kartu workflow, baik yang aktif maupun yang sudah di-archive.

---

## Ringkasan Perubahan

| No | File | Aksi | Dampak |
|---|---|---|---|
| 1 | `packages/frontend/editor-ui/src/app/components/WorkflowCard.vue` | Dimodifikasi | Opsi Delete muncul langsung di menu workflow list |

Tidak ada file baru yang dibuat. Tidak ada perubahan backend, API, atau
permission — logika permission (`workflowPermissions.value.delete`) tetap
digunakan sebagai penjaga akses.

---

## Detail Perubahan

### File yang Diubah

```
packages/
└── frontend/
    └── editor-ui/
        └── src/
            └── app/
                └── components/
                    └── WorkflowCard.vue   ← DIMODIFIKASI
```

**Path lengkap:**
`packages/frontend/editor-ui/src/app/components/WorkflowCard.vue`

---

### Lokasi Perubahan

Perubahan berada di dalam computed property `actions` yang membangun daftar
item menu titik tiga (⋮) pada setiap kartu workflow.

**Sekitar baris 233–249**

---

### Sebelum (Kode Asli)

```typescript
if (workflowPermissions.value.delete && !props.readOnly) {
    if (!props.data.isArchived) {
        // Workflow aktif: hanya tampilkan Archive
        items.push({
            label: locale.baseText('workflows.item.archive'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.ARCHIVE,
        });
    } else {
        // Workflow archived: baru muncul Delete + Unarchive
        items.push({
            label: locale.baseText('workflows.item.delete'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.DELETE,
        });
        items.push({
            label: locale.baseText('workflows.item.unarchive'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.UNARCHIVE,
        });
    }
}
```

**Perilaku lama:**
- Workflow aktif → menu hanya ada: `Archive`
- Workflow archived → menu ada: `Delete`, `Unarchive`
- Delete **tidak bisa** diakses dari workflow yang masih aktif

---

### Sesudah (Kode Baru)

```typescript
if (workflowPermissions.value.delete && !props.readOnly) {
    if (!props.data.isArchived) {
        // Workflow aktif: tampilkan Archive
        items.push({
            label: locale.baseText('workflows.item.archive'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.ARCHIVE,
        });
    } else {
        // Workflow archived: tampilkan Unarchive
        items.push({
            label: locale.baseText('workflows.item.unarchive'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.UNARCHIVE,
        });
    }
    // Delete selalu muncul untuk semua workflow (aktif maupun archived)
    items.push({
        label: locale.baseText('workflows.item.delete'),
        value: WORKFLOW_LIST_ITEM_ACTIONS.DELETE,
    });
}
```

**Perilaku baru:**
- Workflow aktif → menu ada: `Archive`, `Delete`
- Workflow archived → menu ada: `Unarchive`, `Delete`
- Delete **selalu tersedia** selama user punya permission `workflow:delete`

---

### Yang Tidak Berubah

| Komponen | Status |
|---|---|
| Handler `deleteWorkflow()` | Tidak diubah — sudah ada konfirmasi dialog |
| Permission check `workflowPermissions.value.delete` | Tidak diubah — tetap menjaga akses |
| API endpoint delete di backend | Tidak diubah |
| Logic archive dan unarchive | Tidak diubah |
| MFA, LDAP, autentikasi | Tidak diubah |

---

### Keamanan

Delete tidak langsung terjadi. Handler yang sudah ada menampilkan dialog
konfirmasi sebelum eksekusi:

```
Apakah Anda yakin ingin menghapus workflow "[nama workflow]"?
Tindakan ini tidak dapat dibatalkan.

[ Batal ]  [ Hapus ]
```

Selain itu, akses delete tetap dijaga oleh permission backend
(`workflow:delete` scope) — user tanpa permission tidak akan melihat
opsi ini sama sekali.

---

## Cara Menerapkan Perubahan Ini dari Awal

Jika perlu menerapkan ulang perubahan ini secara manual pada instalasi baru:

### Langkah 1 — Buka file

```
packages/frontend/editor-ui/src/app/components/WorkflowCard.vue
```

### Langkah 2 — Cari blok kode ini (sekitar baris 233)

```typescript
if (workflowPermissions.value.delete && !props.readOnly) {
    if (!props.data.isArchived) {
        items.push({
            label: locale.baseText('workflows.item.archive'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.ARCHIVE,
        });
    } else {
        items.push({
            label: locale.baseText('workflows.item.delete'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.DELETE,
        });
        items.push({
            label: locale.baseText('workflows.item.unarchive'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.UNARCHIVE,
        });
    }
}
```

### Langkah 3 — Ganti dengan kode berikut

```typescript
if (workflowPermissions.value.delete && !props.readOnly) {
    if (!props.data.isArchived) {
        items.push({
            label: locale.baseText('workflows.item.archive'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.ARCHIVE,
        });
    } else {
        items.push({
            label: locale.baseText('workflows.item.unarchive'),
            value: WORKFLOW_LIST_ITEM_ACTIONS.UNARCHIVE,
        });
    }
    items.push({
        label: locale.baseText('workflows.item.delete'),
        value: WORKFLOW_LIST_ITEM_ACTIONS.DELETE,
    });
}
```

### Langkah 4 — Build dan deploy

```powershell
# Dari root repo
cd c:\Users\Acer\n8n-Docker

# Build frontend
pnpm --filter=n8n-editor-ui... build > deploy\phase-0\frontend-build.log 2>&1
Get-Content deploy\phase-0\frontend-build.log -Tail 10

# Build Docker image
docker build -f deploy/phase-0/Dockerfile -t asuralab/n8n:phase-0 .

# Deploy ulang container
cd deploy\phase-0
docker compose up -d --force-recreate
```

---

## Hasil Akhir

Setelah perubahan diterapkan, menu titik tiga (⋮) pada setiap kartu
workflow di halaman Overview akan menampilkan opsi **Hapus** secara
langsung tanpa perlu archive terlebih dahulu.
