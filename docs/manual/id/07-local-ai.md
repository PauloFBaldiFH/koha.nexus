# 7. AI lokal

[Daftar isi](README.md)

**AI**, `a`: penyedia, Ollama, foto MARC Replace, asisten staff. Konfigurasi tidak otomatis memasang alat.

Baca peringatan CPU/RAM, Koha dapat lambat. **Ollama on this server > Check Ollama**, bila belum **Install Ollama**. Pilih/**Download** memerlukan jaringan/disk; nama model tidak ditetapkan karena daftar berubah. **Local Ollama**, URL (standar `http://127.0.0.1:11434`), **Use for chat/Use for cataloguing**. Foto membutuhkan penglihatan, teks saja tidak cukup. **Test connection/Save**, **F5/Ctrl+S**; mengisi tidak menyimpan. Chat kosong memakai pilihan penglihatan. **Load models** bertanya penyedia, memberi tahu daftar cadangan bawaan.

Terpasang memakai disk, termuat RAM. **Free memory** membongkar tanpa menghapus, bisa dimuat lagi. Ollama terlihat dengan penyedia lain: periksa URL/penyedia tersimpan, pemasangan bukan bukti proses lokal.

## Alat

Pasang/perbarui MARC Replace; pemeriksaan kompilasi/pintasan staff. Satu rekaman: `.mrc/.xml` atau teks, `biblionumber`, **Preview**, banding/konfirmasi. Kosong membuat baru, hindari duplikat. Eksemplar lama tetap, bidang eksemplar masuk dikeluarkan. MARCXML lama bisa diunduh/dikirim ke ID sama, bukan pengganti backup penuh.

**AI cataloguing**: foto jelas sampul/halaman judul/baliknya, JPEG/PNG/WebP, minimal satu. Framework/target, **Read the photos**, tunggu dan banding judul/tanggung jawab/publikasi/ISBN/kelas/kekurangan. Koreksi MARC sebelum menulis, klasifikasi diperiksa tabel; digit ISBN bukan bukti edisi. Draf tidak menulis bidang eksemplar.

**Install, update or remove the assistant** mengganti berita beranda staff, bukan OPAC. Pencarian Koha/bacaan ditetapkan, bukan SQL bebas. **Usulan belum dieksekusi:** rekaman/sebelum-sesudah/efek, **Approve & Execute** dengan hak sendiri. Perubahan di antaranya bisa menolak/minta baru. Tindakan disetujui dapat dilihat; hapus percakapan/asisten tidak mengurungkan. Penghapusan membuang percakapan, mempertahankan riwayat persetujuan.

Pantau perangkat/Koha, jangan mulai foto baru saat lambat, bebaskan memori sesuai kebutuhan. Tanpa jaminan waktu. Penyedia jauh menerima permintaan: kebijakan data/gambar, jangan uji pemustaka nyata. Label harga bukan jaminan gratis.

**Perlu dikonfirmasi:** RAM/disk/latensi per pilihan/perangkat; minimum Koha tidak menjamin AI.

## Sumber yang diperiksa

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
