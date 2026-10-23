# 9. Pemecahan masalah dan log

[Daftar isi](README.md)

Catat tindakan/waktu/error lengkap dan bagian berfungsi. Halaman, layanan, pencarian sukses berbeda. Instal ulang/restore bukan jawaban awal universal.

**Control Dashboard** perbarui. **Diagnostics & maintenance center > Detailed server & Koha status**, **Full system health check**, baca laporan. **View latest validation report** membuka kembali, **Export diagnostics** folder bantuan. Meski disamarkan, periksa orang/nama/alamat sebelum berbagi, jangan salin seluruh instalasi. Cadangan klasik Textual tidak mengurungkan pekerjaan lama; simpan error/log.

| Jalur | Isi |
| --- | --- |
| `/var/log/koha-easy-install/` | Utama Linux |
| `apt.log` | Paket/tahap |
| `validacao-*.log` | Laporan bertanggal |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/ekspor |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | Indeks/pencarian |
| `/var/log/koha-easy-install/tools/` | Alat |
| `C:\Koha\logs`, lama `C:\KohaEasy\logs` | Windows sesuai instalasi |

`*` file bertanggal, mungkin belum ada sebelum pertama. Jalur tepat yang ditampilkan diutamakan. **Library tools > View tool logs** tanggal/tugas, terbatas karena data pribadi. Laporan konteks/tanggal/versi/OK/peringatan/error dibaca masing-masing. **No critical failures** bisa punya peringatan; backup lama bukan kerusakan database. Verifikasi/bandingkan lagi setelah perbaikan.

**Real-time Apache log auditing** staff/OPAC/alternatif lama. Textual **Pause/p** menghentikan tampilan, bukan Apache; **Continue**, **Back/Esc** tutup. Klasik `Ctrl+C` untuk mengikuti log ini, bukan semua tugas. `error/fatal/denied/fail` waktu/konteks; warna bukan penyebab.

- OPAC/staff tidak terjangkau: Apache/MariaDB/Plack/cache, lokal/jaringan/VPN/tunnel. `localhost` komputer browser. **Restart / repair Koha services (Memcached, Plack)** dapat memutus; baca/cek ulang.
- Rekaman tidak ditemukan: mesin/antrian/indeks-database; **Search engine & indexing > Repair / rebuild indexing**, baca/tunggu. Elasticsearch bukan langkah awal wajib.
- Backup tidak ada: waktu/hasil/ruang/sistem saat cron, `.part` belum selesai. `backup_sql.log`, test/manual; jangan hapus valid terakhir tanpa aman lain, hindari tumpang tindih.
- Import/jumlah: Magic Import/MARC, masuk/persiapan/tulis, mode/kode/barcode/penolakan/ganda. Sampel kecil tidak memvalidasi semua; test penuh/tahap selesai sebelum ulang.
- Restore: temukan tahap, indeks dapat gagal sesudah database, rollback juga; database/pencarian/validasi.
- AI/pengayaan lambat: Ollama/pilihan/memori atau tugas/server/batas, jangan gandakan besar karena terlambat. Eksternal dan RAM lokal diagnosis berbeda.

## Ikon Windows

PowerShell pengguna masuk, **bukan administrator**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Dapat membuat pintasan/restart tray, bukan hanya baca. `diagnose-<date>.txt` dalam `logs` terdeteksi; simpan jalur/error. Berbeda instalasi administratif.

**Deep database optimization & log cleanup** memelihara/restart, dapat menghapus riwayat berguna. Simpan diagnosis dahulu, bukan menyembunyikan error. Bantuan: versi/Windows-WSL-distribusi/tindakan-waktu-pesan lengkap/OPAC-staff-pencarian/operasi sebelumnya dan kutipan ditinjau privasi.

**Perlu dikonfirmasi:** penyebab tanpa pesan/log lengkap; bukan otomatis jaringan/instalasi.

## Sumber yang diperiksa

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
