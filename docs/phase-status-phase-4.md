# Phase 4 — Status Implementasi

> Agent Runtime — workflow bisa membuat keputusan runtime menggunakan AI.

---

## Ringkasan

| Kategori | Status |
|----------|--------|
| Agent Node (n8n node baru) | ❌ Belum ada |
| Human Approval mechanism | ❌ Belum ada |
| Runtime Decision integration | ❌ Belum ada |

**Phase 4 seluruhnya belum dimulai.**

---

## Ketergantungan

```
Phase 2 (Agent Service + Memory + Tools)
    ↓
Phase 4 (Runtime execution — Agent Node calls Agent Service)
```

Phase 4 tidak tergantung pada Phase 3 secara teknis,
tapi secara produk lebih masuk akal dikerjakan setelah Phase 3.

---

## 1. Konsep: Agent Node

Agent Node adalah custom n8n node baru khusus untuk MST Workflow.

Ketika workflow berjalan dan mencapai Agent Node:

```
Workflow berjalan
    ↓
Agent Node dieksekusi
    ↓
Agent Node memanggil Agent Service (Phase 2)
    ↓
Agent Service membuat keputusan (pakai Planner + Memory + Tools)
    ↓
Agent Node menerima keputusan
    ↓
Workflow dilanjutkan berdasarkan keputusan
```

---

## 2. Runtime Components (di Agent Service)

| Komponen | Fungsi |
|----------|--------|
| Planner | Menentukan aksi berikutnya berdasarkan konteks |
| Memory | Memberikan konteks eksekusi (history, state) |
| Tools | Memungkinkan interaksi eksternal (Gmail, Slack, dll) |

---

## 3. Human Approval

Untuk operasi sensitif, Agent Node menunggu approval dari user sebelum melanjutkan.

**Contoh operasi yang butuh approval:**

| Operasi | Risiko |
|---------|--------|
| Delete Records | Data loss |
| Financial Transactions | Kerugian finansial |
| Credential Changes | Security breach |
| Production Changes | Downtime |

**Flow Human Approval:**
```
Agent Node ingin lakukan operasi sensitif
    ↓
Pause workflow
    ↓
Kirim notifikasi ke user (email/in-app)
    ↓
User approve/reject
    ↓
Workflow dilanjutkan atau dibatalkan
```

n8n sudah punya mekanisme "Wait" node — Agent Node bisa memanfaatkan ini
sebagai fondasi Human Approval.

---

## 4. Komponen yang Butuh Dibuat di Fork n8n

| Lokasi | Deskripsi |
|--------|-----------|
| `packages/nodes-base/nodes/AgentMST/` | Custom n8n node untuk Agent Runtime |
| `packages/cli/src/...` | API endpoint untuk Human Approval callbacks |
| Frontend | UI notifikasi + tombol Approve/Reject |

---

## 5. Core Principle (dari roadmap)

> Workflow is still the source of truth.
> Agent enhances workflows.
> Agent does not replace workflows.
> Users can always inspect, edit, and govern automation.

Ini berarti Agent Node harus:
- Bisa dinonaktifkan (bypass ke manual logic)
- Logging penuh semua keputusan yang dibuat
- Tidak bisa mengeksekusi aksi di luar scope workflow yang sudah didefinisikan

---

## Deliverables Phase 4

- [ ] Agent Node (custom n8n node baru)
- [ ] Human Approval UI (notifikasi + approve/reject)
- [ ] Runtime logging (audit trail keputusan agent)
- [ ] Workflow auditing (export log keputusan per eksekusi)

---

## Apakah Perlu Konfirmasi?

**Ya — sebelum memulai Phase 4:**

1. **Human Approval delivery:** Notifikasi via email, in-app, atau keduanya?
2. **Timeout:** Apa yang terjadi jika user tidak approve dalam X jam?
3. **Agent Node configuration:** Apa yang dikonfigurasi user di node? (prompt? tool list? memory scope?)

---

> **Tidak ada perubahan kode dilakukan.** Dokumen ini hanya analisa scope Phase 4.
