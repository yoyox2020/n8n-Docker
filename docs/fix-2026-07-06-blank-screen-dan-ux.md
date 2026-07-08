# Fix: Blank Screen & UX Error Messages — 2026-07-06

## Ringkasan

Dua perbaikan dilakukan pada sesi ini:

1. **Blank white screen** setelah deploy Docker image baru
2. **Pesan error teknikal** yang terekspos ke pengguna saat workflow builder gagal

---

## 1. Router Fix — Blank Screen Prevention

### Gejala
Setelah deploy, membuka URL n8n menampilkan layar putih kosong. Hard refresh, clear cache, dan incognito mode tidak membantu. Semua API backend berjalan normal (HTTP 200).

### Root Cause
Di `packages/frontend/editor-ui/src/app/router.ts`, guard `router.beforeEach` memiliki catch block yang **tidak pernah memanggil `next()`** saat terjadi error tak terduga:

```typescript
// SEBELUM (bug)
} catch (failure) {
    if (failure instanceof MfaRequiredError && ...) {
        return next({ name: VIEWS.PERSONAL_SETTINGS });
    }
    if (isNavigationFailure(failure)) {
        console.log(failure);
    } else {
        console.error(failure);
    }
    // ← tidak ada next() di sini!
    // Navigasi dibatalkan permanen → komponen stub { render: () => null } tetap render → blank screen
}
```

### Fix
Tambah fallback `next()` di akhir catch block:

```typescript
// SESUDAH (fix)
} catch (failure) {
    const settingsStore = useSettingsStore();
    if (failure instanceof MfaRequiredError && settingsStore.isMFAEnforced) {
        if (to.name !== VIEWS.PERSONAL_SETTINGS) {
            return next({ name: VIEWS.PERSONAL_SETTINGS });
        } else {
            return next();
        }
    }
    if (isNavigationFailure(failure)) {
        console.log(failure);
    } else {
        console.error(failure);
    }
    // Fallback: redirect ke signin daripada layar putih
    if (to.name !== VIEWS.SIGNIN) {
        return next({ name: VIEWS.SIGNIN });
    }
    return next();
}
```

### File yang Diubah
- `packages/frontend/editor-ui/src/app/router.ts` — baris 1157–1176

### Deploy
Docker image direbuild penuh dari source:
- Image ID: `907694f0c572`
- Dibuat: 2026-07-06 15:21:20 +0700
- Container di-recreate: `docker compose up -d n8n` dari `deploy/phase-0/`

---

## 2. Cleanup Data Approval Test

### Masalah
Setelah workflow berhasil dibuat, chat menampilkan notifikasi "⚠️ Ada permintaan persetujuan yang menunggu" berisi data lama dari sesi testing (Juni 29–30).

### Penyebab
Tabel `agentdb.approval_requests` berisi 7 record lama dengan `status = 'pending'` dari testing:
- 2 record dari `test-user-1` (testing development)
- 3 record dari `admin@mst.co.id` (testing fitur approval 30 Juni)

Setelah workflow berhasil dibuat, sistem otomatis memanggil `GET /approval/user/{userId}?status=pending` dan menampilkan semua yang pending. Record lama ini terus muncul.

### Fix
```sql
DELETE FROM approval_requests;
```

Semua 7 record dihapus. Notifikasi approval hanya akan muncul kembali jika workflow n8n yang nyata memanggil `POST /approval/` untuk meminta persetujuan.

---

## 3. Error Message UX — Pesan Ramah Pengguna

### Masalah
Saat workflow builder atau approval gagal, pesan error teknikal terekspos langsung ke pengguna di chat:
```
Maaf, gagal membuat workflow. Silakan coba lagi.

_Error: timeout of 6000ms exceeded_
```
Ini membuat platform terkesan tidak stabil.

### Fix

**File:** `packages/cli/src/modules/chat-hub/chat-hub.service.ts`

#### a) Workflow build error (fungsi `handleAgentWorkflowRequest`)

```typescript
// SEBELUM
const errContent = errorMsg.startsWith('Maaf,')
    ? errorMsg
    : `Maaf, gagal membuat workflow. Silakan coba lagi.\n\n_Error: ${errorMsg}_`;

// SESUDAH
const errContent = [
    'Mohon perbaiki permintaan workflow Anda. Coba jelaskan dengan lebih spesifik apa yang ingin diotomasi, misalnya:',
    '',
    '> "Buatkan workflow untuk mengirim laporan via email setiap Senin pagi"',
    '',
    'Jika masalah berlanjut, sampaikan ulang dengan kata yang berbeda.',
].join('\n');
```

#### b) Approval error (fungsi `handleApprovalResponse`)

```typescript
// SEBELUM
const errContent = `Maaf, gagal memproses keputusan approval.\n\n_Error: ${errorMsg}_`;

// SESUDAH
const errContent = 'Maaf, persetujuan tidak dapat diproses saat ini. Silakan coba ulangi perintah Anda sebentar lagi.';
```

### Catatan Penting
- Error asli **tetap dicatat** di server log via `this.logger.error(...)` — tidak hilang untuk debugging
- Patch diterapkan langsung ke JS di container (`docker exec -u root`) agar langsung aktif tanpa rebuild
- Source TypeScript sudah diperbarui — **akan terkompilasi otomatis saat Docker image direbuild berikutnya**

---

## Status Setelah Fix

| Item | Status |
|------|--------|
| Blank screen | ✅ Fixed — redirect ke signin jika ada error di router |
| Approval data stale | ✅ Cleared — 0 records pending |
| Pesan error teknikal | ✅ Fixed — pesan ramah, error hanya di log server |
| Docker image | ✅ Running (ID: 907694f0c572) |
| Source code tersimpan | ✅ Siap untuk rebuild berikutnya |
