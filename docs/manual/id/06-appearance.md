# 6. Tampilan OPAC dan staff

[Daftar isi](README.md)

**OPAC and Staff Appearance**, `o`, mengatur OPAC publik dan staff/intranet terpisah.

**Sync current OPAC settings** membaca tanpa menerapkan. Ubah per kelompok. **Preview** menunjukkan CSS/JavaScript/isi, bukan rendering browser penuh. **Apply** ringkasan/konfirmasi dengan backup dahulu. Periksa beranda/pencarian/rekaman/login, layar kecil juga.

Blok di `OpacUserCSS/OpacUserJS`, bila perlu `IntranetUserCSS/IntranetUserJS`; milik sendiri tetap, konflik visual dengan penyesuaian lain mungkin.

Tekstur/blur/opasitas/sudut/warna/latar, terang/gelap/tema awal: pertahankan kontras terhadap gambar/transparansi. Staff bilah atas/cari cepat/modul/kepadatan tabel/teks/kontras. Aktifkan **Apply color theme to Staff Client**; **Copy OPAC preset** hanya mengisi, **Apply** menulis.

File server, layanan gambar ditawarkan atau HTTPS-URL langsung. PNG/JPEG/GIF/WebP/ICO diterima, SVG ditolak. File hanya komputer sendiri perlu dijangkau server. Hak gambar/deskripsi aksesibel login; halaman hosting tidak selalu alamat gambar. Konfigurasi layanan luar tanpa menerbitkan pribadi.

Karusel baru/daftar Koha dengan `shelfnumber=`; judul/jumlah/gaya/kecepatan/autoplay/**Refresh carousel**. Tanpa sampul bukan rekaman dihapus; tergantung data/sampul/jaringan. Tombol OPAC/staff terpisah teks/alamat/tujuan/urutan, **Add a button**, hapus baris sebelum terapkan.

Login gambar/deskripsi/HTML menyaring skrip/gaya/peristiwa, bukan instruksi rahasia. Berita masing-masing punya judul/teks/tombol tanpa mengganti berita perpustakaan. Footer `Field: value`, tautan tambahan teks `|` alamat, maksimal enam, publik saja.

**Remove** konfirmasi/backup sebelum menghapus tema, mengembalikan Koha dengan penyesuaian sendiri. Bukan restore penuh/pembatalan administrasi lain. Betulkan kelompok dan terapkan, simpan error untuk diagnosis.

## Sumber yang diperiksa

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
