# 2. Langkah awal dan panel

[Daftar isi](README.md)

## Membuka dan menavigasi

Pada Debian/Ubuntu yang disiapkan:

```bash
sudo config.sh
```

Windows: ikon **Koha** atau MSIX. Awal mungkin menanyakan bahasa. Jika persiapan Textual gagal, panel klasik dapat ditawarkan. Panduan terutama menjelaskan Textual, bukan nomor menu lama.

Sorot bagian dengan panah, **Enter** atau klik membuka. Menyorot saja tidak menjalankan. Buka kartu tugas dan baca pertanyaan. **Tab** memindahkan fokus; keluar dari bidang teks sebelum pintasan huruf.

| Tombol | Tindakan |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Terminal Debian |
| `Ctrl+B` | Tampilkan/sembunyikan bilah samping |
| `q` | Keluar panel |

Keluar saat diam tidak mematikan server. Ikuti aturan pembatalan tugas aktif. Instalasi/restore memiliki tahap tidak dapat dibatalkan; memaksa tutup tidak aman.

## Status dan alamat

Dashboard menunjukkan Koha/memori tersedia, backup terakhir dengan tanggal/umur/file, disk kosong, alamat, MariaDB, Apache, RabbitMQ, Memcached, Koha dan HTTP. Indikator backup menggunakan umur dan hasil malam; file baru dapat berdampingan dengan kegagalan malam. Baca keduanya; indikator baik tidak menggantikan uji restore. HTTP tidak membuktikan pemasang web selesai atau semua fungsi pustaka.

**Refresh** membaca lagi. **Restart Koha** meminta perbaikan/restart sambil memperhatikan pengguna; **Export diagnostics** menyiapkan bantuan. Tombol bisa tidak tersedia jika pemasang terpasang tidak mendukung tugas.

Kartu alamat membuka/menyalin URL; tanpa browser lokal tempel di komputer sendiri. Pada server OPAC `http://localhost/`, staff `http://localhost:8080/`, port 80/8080. Komputer lain memakai alamat jaringan, bukan `localhost` miliknya. WSL NAT/LAN tidak terjangkau: periksa persiapan Windows dengan penanggung jawab, jangan asumsikan akses semua komputer.

Selesaikan pemasang web Koha jika muncul; layar tergantung versi. **Koha settings & parameters > Create super librarian** membuat akun, nilai pribadi hanya di sana.

Sebelum operasi: perbarui dashboard/komponen/alamat, buka OPAC/staff dari lokasi tepat, buat/uji backup dan pastikan salinan luar serta penanggung jawab pemulihan. Terakhir adalah saran operasional: transfer harus selesai dan diverifikasi.

## Sumber yang diperiksa

- [installer](../../../installer).
- [app.py](../../../panel/kei_panel/app.py).
- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [main.py](../../../panel/kei_panel/screens/main.py).
- [install.py](../../../panel/kei_panel/routines/install.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [dashboard.py](../../../panel/kei_panel/views/dashboard.py).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [menus.py](../../../panel/kei_panel/menus.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
