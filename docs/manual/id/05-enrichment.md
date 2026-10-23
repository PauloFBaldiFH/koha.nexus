# 5. Pengayaan dan Z39.50/SRU

[Daftar isi](README.md)

## Pengayaan

Impor mengambil ekspor, pengayaan menambah data atau menemukan buku baru. Judul sama perlu pemeriksaan bibliografis. **Library tools > On-demand enrichment**, `n`; layar batch lama bukan jalur menu kini.

`all` atau `biblionumbers`, misalnya `101, 102, 500-510`, **Search**. Pantau tugas/server; besar di latar, dapat lanjut setelah restart bila mesin tersedia. **Pause/Resume** tidak membatalkan perubahan. Laporan: subjek/klasifikasi/catatan/deskripsi fisik. **Search more servers** sumber belum dipakai, **Choose donor** donor kelompok bidang. **Apply** sesudah tinjau/konfirmasi; pencarian/laporan tidak menulis.

Z39.50 langsung punya batas/gangguan; tanpa hasil bukan bukti buku tidak ada. Tidak ada batas umum 50 rekaman: ambang proteksi penerapan, salinan rekaman untuk kecil, backup penuh terverifikasi untuk besar. **Revert** mengembalikan versi sesuai proteksi, mempertahankan suntingan setelahnya; bukan restore global atau pembatalan seluruh perubahan orang lain.

## Baru dan otoritas

ISBN/judul, pengarang/tahun membantu, **Find**, tinjau/pilih. **Import as new record** menambah dengan konfirmasi tanpa mengganti ISBN sama. Menghapus `9XX` lokal donor, mencatat asal, agar eksemplar pihak lain tidak menjadi milik sendiri. Periksa dan buat eksemplar lokal normal; batch via **Undo a MARC import**.

**Enrich & standardize authorities**, `h`: cakupan/bentuk tepat/dekat. Dekat bisa menyarankan ejaan/otoritas sementara, teliti. Koha sendiri dahulu, lalu basis pengayaan/server langsung; Brasil diprioritaskan, subjek hanya darinya, bukan jaminan kebijakan lokal. **Apply** membuat otoritas/relasi dengan backup dan mempertahankan perubahan sejak laporan. Revert menyimpan otoritas baru yang masih terhubung.

## Server

**Z39.50 / SRU servers**, `z`: masuk mengizinkan pencarian luar dan mengubah port firewall. Jaringan komunitas berbeda dari sumber langsung. **Reset/Reset all** mengizinkan percobaan, tidak memperbaiki server jauh. Spasi memilih, **Scan** mencari rekaman nyata, **Add to Koha** mendaftarkan yang dipilih/berfungsi. Pengaturan SRU tidak berarti setiap kueri memakai SRU; mencari keluar tidak perlu membuka masuk.

**Perlu dikonfirmasi:** ketersediaan/cakupan/syarat setiap sumber dari jaringan lokal saat digunakan.

## Sumber yang diperiksa

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
