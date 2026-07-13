# Template Workflow — Referensi untuk LLM

Folder ini tempat mengumpulkan template workflow n8n (format JSON) yang nantinya
dipakai sebagai **referensi/contoh** buat LLM saat membangun workflow baru.

## Kenapa ini dibutuhkan

Sekarang, saat user minta "buatkan workflow X", `workflow_builder.py` menyuruh LLM
generate `task_graph` dari nol — tanpa contoh sama sekali. Kalau kita punya kumpulan
template nyata (hasil kerja orang lain yang sudah teruji), kita bisa:

1. Saat user minta workflow, cari dulu template yang paling mirip (pencarian semantik,
   sama seperti pencarian node yang sudah ada di `embedding_search.py`).
2. Kalau ketemu yang mirip, suntikkan JSON template itu ke prompt LLM sebagai contoh —
   supaya hasil generate-nya lebih akurat & konsisten, bukan asal tebak node.

Ini tahap **pengumpulan bahan** dulu. Kode pencarian/penyuntikan ke prompt belum
dibuat — nanti dibangun setelah template-nya cukup banyak terkumpul di sini.

## Ke mana naruh file-nya

Taruh setiap template sebagai satu file `.json` langsung di folder ini (folder
`examples/` isinya cuma contoh format, bukan tempat naruh template asli kamu).

Nama file bebas, tapi disarankan pakai format:
```
<kategori>-<nama-singkat>.json
```
Contoh: `email-laporan-mingguan.json`, `slack-notifikasi-order.json`

## Format file yang dibutuhkan

Setiap file berisi **satu objek JSON** dengan dua bagian: `metadata` (dipakai buat
pencarian semantik) dan `workflow` (JSON hasil export asli dari n8n, apa adanya —
tidak usah diedit).

```json
{
  "metadata": {
    "name": "Reminder Meeting via Telegram",
    "description_id": "Kirim pengingat meeting ke peserta lewat Telegram beberapa menit sebelum jadwal dimulai",
    "description_en": "Sends a meeting reminder to attendees via Telegram a few minutes before the scheduled time",
    "category": "notification",
    "tags": ["telegram", "reminder", "calendar", "meeting"],
    "source_url": "https://github.com/contoh/n8n-templates/blob/main/telegram-meeting-reminder.json"
  },
  "workflow": {
    "name": "Reminder Meeting via Telegram",
    "nodes": [ /* ...JSON asli dari n8n export, jangan diubah... */ ],
    "connections": { /* ... */ }
  }
}
```

Lihat contoh lengkap di [`examples/contoh-template.json`](examples/contoh-template.json).

### Field `metadata` — wajib diisi manual

| Field | Wajib? | Keterangan |
|---|---|---|
| `name` | Ya | Nama singkat workflow |
| `description_id` | Ya | Deskripsi Bahasa Indonesia — ini yang paling menentukan akurasi pencarian nanti |
| `description_en` | Disarankan | Deskripsi Bahasa Inggris (banyak prompt user pakai campuran ID/EN) |
| `category` | Disarankan | Satu kata: `notification`, `email`, `crm`, `social-media`, `data-sync`, `reporting`, dll |
| `tags` | Disarankan | Kata kunci tambahan yang mungkin diketik user |
| `source_url` | Disarankan | Link asal template, buat jejak lisensi/atribusi |

### Field `workflow` — ambil apa adanya dari n8n

Ini JSON hasil **Export → Download** dari editor n8n (atau file `.json` yang kamu
unduh dari situs template). Jangan diedit strukturnya — cukup tempel apa adanya
di bawah key `"workflow"`.

## Cara dapat template

1. **Resmi**: [n8n.io/workflows](https://n8n.io/workflows) — banyak dikategorikan
   per use-case, tinggal klik "Use for free" → "Download".
2. **Komunitas**: cari repo GitHub seperti `awesome-n8n-templates`,
   `n8n-io/n8n-workflows`, atau search `n8n workflow json` di GitHub.
3. Kalau kamu sudah pernah bikin workflow bagus di instance ini sendiri, tinggal
   export dari editor (⋯ menu → **Download**).

## Sebelum commit — checklist wajib

- [ ] **Hapus semua credential/API key/token** yang mungkin ikut ke-export
      (cek field `credentials` di tiap node — biasanya cuma berisi `{id, name}`
      referensi, aman; tapi cek juga tidak ada value rahasia nyelip di `parameters`).
- [ ] Isi `description_id` dengan kalimat natural — bayangkan gimana user beneran
      akan mengetik permintaannya di chat.
- [ ] Kalau tahu node yang dipakai template itu **tidak ada** di 849 node yang
      sudah terdaftar di sistem ini (`GET http://localhost:8001/status` bagian
      `nodes.total`), sebaiknya jangan dimasukkan dulu — nanti malah bikin LLM
      nyontoh node yang tidak valid. Belum ada alat otomatis buat cek ini — kalau
      butuh, bilang saja, saya buatkan skrip validasinya.

## Status

- [ ] Template mulai dikumpulkan (kamu)
- [ ] Skrip embed `metadata` template ke pgvector (belum dibuat)
- [ ] Endpoint pencarian template mirip prompt user (belum dibuat)
- [ ] Suntik template hasil pencarian ke prompt LLM di `workflow_builder.py` (belum dibuat)

Kabari saya kalau template sudah lumayan banyak (misal 15-20+) — saya lanjutkan
ke tahap bikin infrastrukturnya.
