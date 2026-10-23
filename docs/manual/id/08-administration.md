# 8. Administrasi, pesan dan VPN

[Daftar isi](README.md)

Periksa keadaan/backup baru sebelum mengelola. Konfigurasi bukan bukti fungsi jaringan, periksa sesudahnya.

## Cron dan VPN

**Schedules & cron tasks**, `s`: aktif/frekuensi/waktu/hari/ekspresi. **Reload**, tugas perlu, `HH:MM`, **Preview**, **Save**/konfirmasi, baca ulang. `/etc/cron.d/koha_tasks`, lama `koha_tasks.bak`; nonaktif komentar dengan waktu, baris sendiri tetap. **Defaults** mengisi, masih perlu simpan. SQL harian 23:00/MARC Minggu 03:00, periksa zona/kustom. Server/Linux harus berjalan; cron tidak menjamin menyalakan Windows, notifikasi Koha terpisah.

**Security & access hub > WireGuard VPN**, `v`: nama/alamat publik/UDP. **Set up the VPN** menampilkan perubahan, router meneruskan UDP ke server. Nama/**Add device**, **QR code & profile**, cek koneksi/staff/lalu lintas. Jangan publikasikan profil/QR. **Revoke** perlu profil baru; **Turn off** memutus tetapi menyimpan. Split tunnel hanya `10.66.0.0/24`, internet/DNS sendiri, staff `http://10.66.0.1:8080`. WSL tanpa mirrored tidak dapat dijangkau langsung, VPN nonaktif.

## Pesan

**Messaging & interoperability**, `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. Aktifkan e-mail/cek SMTP; tombol SMTP/alamat perpustakaan/pemberitahuan-kuitansi/terlambat. Tidak mengisi setiap aturan/penerima/template, periksa preferensi/konfigurasi penyedia privat.

**Set up WhatsApp and Telegram** layanan/negara/kode/test/aktif/telepon. WhatsApp gateway, Telegram bot/penerima. Test diizinkan sebelum produksi, format/template sebelum koreksi massal. SMS `SMSSendDriver`/preferensi membutuhkan layanan/driver cocok, bukan nama saja.

**Alerts** jatuh tempo/terlambat/ulang/ringkasan/kanal, simpan/**Dry run (sends nothing)**. Mengaktifkan tugas: cek cron, hindari ganda Koha. SIP2 port/jaringan/perpustakaan/hak perangkat, hapus contoh dan buat akun Koha via tombol; cocok akun/server. Jangan buka seluruh jaringan demi uji lokal. Z39.50 bab 5, masuk/keluar berbeda.

## Administrasi lain

Hub Cloudflare Tunnel/UFW/staff-8080/HTTPS/Fail2ban, keadaan/ringkasan, bedakan VPN/tunnel/langsung. Jangan ubah firewall jauh tanpa jalur pengelolaan tersisa. **Perlu dikonfirmasi:** domain/router/penyedia/lembaga, kode bukan resep publikasi universal.

**Koha settings & parameters** memori/workers, pustakawan super, zona; batasi hak luas. **Koha languages** unduh/aktif, hanya unduh, aktifkan terpasang/daftar, cek panel/OPAC/staff. **Update center** sistem/skema terpisah GitHub-panel, backup/pemeliharaan; dapat mengakhiri sesi. Restart bukan bukti perbaikan migrasi.

**Library tools** tautan/sinkron otoritas, pengarang duplikat, SQL, kategori, mutu/privasi. Kategori asal/tujuan berbeda, filter/perpustakaan, simulasi sebelum persetujuan terlindung. Kualitas hanya membaca, tidak memperbaiki semuanya. Anonimisasi menghapus hubungan lama riwayat/pemustaka sesuai Koha, bukan seluruh bibliografi. Hapus pemustaka: filter/simulasi/jumlah, destruktif, cek retensi. Nama mirip bukan orang sama; kartu tersembunyi bukan alat tersedia.

## Sumber yang diperiksa

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
