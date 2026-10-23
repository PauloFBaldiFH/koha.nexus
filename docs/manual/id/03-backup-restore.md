# 3. Backup dan restore

[Daftar isi](README.md)

## Pusat dan jenis salinan

**Backup center**, `b`: tanggal, ukuran, hasil, **Compression**, kartu.

| Kartu | Tujuan |
| --- | --- |
| Download latest backup | Salin file terbaru ditemukan |
| Generate manual backup and download to PC | Buat, periksa, transfer database |
| Export MARC21 records now | Bibliografi dan rekaman otoritas |
| Restore database | Ganti database saat ini |
| Configure cloud backup | Kirim eksternal |
| Test integrity of latest backup | Uji impor sementara |

**Restore database berupa kartu**, bukan tombol atas atau menu utama terpisah. Hasil mengacu malam, tanggal/ukuran file terbaru, mungkin operasi berbeda.

SQL berisi database Koha, bukan citra penuh Windows/Debian. MARC21 bibliografi/otoritas dalam `.tar.gz` bukan pengganti SQL untuk pemustaka/sirkulasi. Sebelum restore database bertabel, salinan keamanan terverifikasi dibuat; database kosong dapat melewati.

SQL otomatis/keamanan `/var/backups/koha_sql`, MARC `/var/backups/koha_marc`. Manual memiliki tujuan tersendiri, normal `backups` dalam direktori rumah terdeteksi. `.part` sementara sampai pemeriksaan/penggantian nama selesai.

## Kompresi dan transfer

**Compression**: gzip `.sql.gz` kompatibel, Zstandard `.sql.zst` cepat/lebih kecil untuk katalog besar, XZ/LZMA `.sql.xz` paling kecil/lambat. Pilihan langsung disimpan tanpa tombol lain, untuk salinan baru malam/manual/keamanan, tidak mengompresi ulang lama. Program tidak ada/gagal dipasang: baca format nyata, mungkin gzip. Restore mengenali `.sql/.sql.gz/.sql.zst/.sql.xz` terlepas pilihan; ekstensi bukan bukti isi.

**Generate manual backup and download to PC**: direktori server dapat ditulis, **Save backup**, tunggu pembuatan/verifikasi; layar tidak tutup saat menyimpan/menyalin. Periksa nama/ukuran/jalur. WSL **Save to Windows Downloads/Choose folder in Windows**; jarak jauh jalankan perintah ditampilkan pada komputer sendiri. Periksa diterima, **Finish and exit**.

Tombol Windows hanya WSL. Jangan pakai perintah instalasi lain, tergantung file/server. Tugas backup/restore lain: tunggu, jangan lewati kunci bersama dengan tugas luar serentak. **Download latest backup** mengambil yang ada, tidak membuat baru. Desktop-Linux/WSL mencoba Downloads, SSH dapat menampilkan perintah lokal. Tanpa file, buat manual.

## Uji, MARC, cloud

**Test integrity of latest backup**: tanggal/file, **Choose another file**, konfirmasi, impor sementara. Berhasil melaporkan tabel/rekaman/pemustaka tanpa mengganti produksi. Hanya file/lingkungan itu; pertahankan akses salinan sama setelah transfer.

**Export MARC21 records now** konfirmasi, tunggu paket bibliografi/otoritas, cek jalur/isi/transfer. Koha tetap berjalan; cloud terkonfigurasi melaporkan pengiriman. Simpan SQL untuk database lengkap.

**Configure cloud backup**: dua jalur Google Drive, juga OneDrive/MEGA/S3. Otorisasi server/komputer lain, hanya URL/instruksi ditampilkan. S3 membedakan layanan, wilayah/endpoint, bucket. Tunggu uji kirim nyata dan penerimaan; jangan andalkan pengaturan gagal. Data pribadi hanya dalam instalasi, bukan teks/gambar publik/bantuan; file penyimpannya tidak disebut. Baku SQL harian 23:00, MARC Minggu 03:00 waktu server, cron bisa berbeda.

## Restore destruktif

**Konfirmasi mengizinkan mengganti database sekarang.** Rencanakan pemeliharaan/salinan luar; panel tidak otomatis melakukan saran tambahan ini.

**Restore database**, file terjangkau server dengan transfer bila perlu. WSL dapat menyalin Windows ke Linux dahulu. Baca akses/isi/integritas/ruang, selidiki file mencurigakan/tidak lengkap meski ekstensi benar. Cek lagi saat konfirmasi; sebelum itu bisa mundur, sesudah tunggu tanpa tutup, tidak dapat dibatalkan.

SQL sementara dahulu dan cek tabel penting/jumlah; gagal berhenti sebelum ganti. Tabel sekarang dilindungi SQL terverifikasi `pre_restore_safety_backup_`, tanggal/waktu/kompresi. Gagal salinan tidak seharusnya menghapus database; kosong dapat melewati.

Lalu hentikan klien, buat/impor, tingkatkan skema, sinkronkan pencarian, bangun indeks, jalankan layanan. Tema tersimpan dicoba diterapkan jika tersedia. Kegagalan uji/salinan tidak membuktikan penggantian. Buat/impor/skema dapat mencoba kembali sesuai tahap/salinan, **rollback pun dapat gagal**. Indeks dapat gagal setelah database dipulihkan tanpa kembali ke katalog lama.

Simpan pesan lengkap, `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, indeks `/var/log/koha-easy-install/zebra-rebuild.log`. Kartu pusat, bukan nomor lama; bantuan teknis jika keadaan tidak pasti. Periksa dashboard/rekaman/pencarian OPAC-staff. SQL selesai tidak membuktikan file eksternal.

## Sumber yang diperiksa

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
