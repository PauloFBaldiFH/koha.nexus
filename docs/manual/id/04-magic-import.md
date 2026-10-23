# 4. Impor ajaib

[Daftar isi](README.md)

## Persiapan dan format

Magic Import membaca bibliografi, eksemplar, pemustaka, otoritas. Format dikenali tidak menjamin bidang, terutama tanpa judul/lokal. Simpan asli/backup terverifikasi, sampel representatif dengan banyak eksemplar, aksen, kosong/pengecualian, bandingkan jumlah sumber. Jangan publikasikan ekspor pemustaka.

**Magic Import Tool**, `i`, kartu dan file/folder terjangkau Linux panel; file hanya pada komputer browser/terminal tidak otomatis berada di server.

| Masukan | Pemeriksaan |
| --- | --- |
| MARC21 ISO 2709, MARCXML, teks MARC | Judul/karakter/otoritas/eksemplar; `.mrk` MarcEdit dikenali tanpa konversi semata ekstensi. |
| CSV/TSV, `.xlsx/.xls/.ods/.dbf` | Pemisah/judul/isi/tujuan. |
| Tabel JSON/XML | Struktur; XML sembarang bukan selalu MARCXML. |
| SQL tabel bahkan tanpa judul | Membaca data/relasi, tidak menjalankan program migrasi; tinjau ambigu. |
| ISIS | PostgreSQL dikenali dengan `acervo`; master CDS/ISIS `.mst` diekspor WinISIS ISO 2709. |
| Biblioteca Fácil | Backup/folder dikenali, tabel terkait bersama; rekaman/orang/pinjaman/pesanan diperiksa terpisah. |
| Backup Koha lengkap | Ke restore, bukan penambahan rekaman. |

PostgreSQL lain, terutama biner `pg_dump`, bukan MariaDB siap pakai. Ditolak: ekspor MARC/tabel dari sumber. Setiap anggota arsip diperiksa; PDF/gambar/dokumen/program bukan ekspor bibliografis pembaca ini.

## Pemetaan dan data

Periksa **Bibliographic/Patrons/Authorities**. Kisi/tujuan, tinggi dengan pembagi atau **Ctrl+Up/Down**. Pertahankan/alihkan/teks tetap/abaikan; pahami relasi sebelum membuang ID. **Values of this Koha** menunjukkan kode, default perpustakaan/jenis/kategori, penggantian sumber/tujuan. **Record preview** hasil, **Check the whole file** persiapan/validasi lengkap tanpa impor saat itu. Profil nama/**Save**, pilih/**Use**, periksa jika struktur berubah. **Apply/Ctrl+S** menerima pemetaan, bukan konfirmasi penulisan akhir. **Skip: import as it is/Esc** melewati pemetaan, tidak membatalkan semua. Pengelompokan/koreksi teks perlu preview, jangan ubah singkatan/nama/kode membabi buta.

`952` asli dipertahankan, perpustakaan/jenis dapat dipetakan jika diminta; kode valid berbeda tidak harus diganti default. Barcode, perpustakaan asal/saat ini, nomor panggil, jenis, lokasi, akuisisi. `949/852/950/990` lokal Pergamum/Biblivre dapat berbeda makna. Catatan deposit wajib `DL`/tanggal tidak otomatis membuat eksemplar lokal; tinjau pengecualian/bukti inventaris independen. Barcode kosong default perlu tinjauan; generasi meminta pilihan/identitas migrasi-sumber stabil, tanpa penomoran ulang benturan diam-diam. SQL harus punya hubungan dikenali, bukan dugaan posisi kolom/urutan; betulkan sebelum impor.

**Patrons**: nama/kartu/kontak/alamat/tanggal/perpustakaan/kategori ada. E-mail/CPF/tanggal petunjuk saja; lahir/daftar/kedaluwarsa tampak serupa. Pembaruan yang ada ditanya lewat kartu, berbeda dari hanya baru; hak/autentikasi jangan ditebak. **Authorities**: ID, bentuk sah, varian, hubungan, jenis; ganti mode tidak membuat data hilang.

Baca jumlah/penolakan/pertanyaan. Yang ada dipertahankan plus baru, diganti, atau baru tanpa banding. **Kegagalan belakangan bisa menyisakan impor tahap awal.** Simpan hasil/log, periksa tahap/sampel/eksemplar/orang/relasi sebelum ulang. **Library tools > Undo a MARC import** untuk MARC, bukan semua pemustaka/pinjaman/pesanan. Database penuh menurut Backup center.

**Perlu dikonfirmasi:** struktur/versi ekspor khusus tanpa sampel dan tinjauan hasil.

## Sumber yang diperiksa

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
