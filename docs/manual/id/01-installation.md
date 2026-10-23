# 1. Instalasi

[Daftar isi](README.md)

## Lingkungan dan persyaratan

Di Windows, Koha berjalan dalam Debian melalui WSL 2. Alat Windows menyiapkan lingkungan, membuka panel, dan mengintegrasikan aplikasi. Pada Debian/Ubuntu, panel dan layanan dipasang langsung. Buka katalog yang sudah ada melalui panel, bukan mengulang instalasi.

| Lingkungan | Pemeriksaan dalam kode |
| --- | --- |
| Windows | Windows 10 versi 2004, build 19041 atau lebih baru, atau Windows 11; 64 bit, virtualisasi aktif; RAM 8 GB, disarankan 12 GB; ruang kosong 10 GB pada drive instalasi, disarankan 20 GB. |
| Debian/Ubuntu | Debian 11/12/13 atau Ubuntu 22.04/24.04; amd64/arm64 yang disebutkan; di bawah 5 GB diblokir, 5 hingga kurang dari 10 GB peringatan, minimal 10 GB lolos pemeriksaan ini. |

Katalog, lampiran, indeks, dan backup memerlukan ruang tambahan. **RAM Linux perlu dikonfirmasi:** panduan menyarankan server khusus 4 GB, lebih baik 8 GB; desktop/virtualisasi 8 GB, lebih baik 12 GB. Pemeriksaan Linux saat ini tidak memaksakan minimum RAM numerik. Lolos bukan jaminan untuk setiap beban. Windows memperhitungkan memori cadangan perangkat keras dengan ambang terdeteksi 7,5 dan 11,5 GB.

Linux memerlukan hak administratif dan akses repositori paket Koha. TCP 80/8080 untuk OPAC/staff. Jika terpakai, panel menawarkan penghentian layanan terkait. **Setujui hanya jika layanan boleh terputus.**

## Windows: PowerShell

Masuk ke akun administrator Windows yang akan menggunakan Koha, buka PowerShell sebagai administrator pada akun yang sama:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Jika peningkatan hak meminta akun orang lain, batalkan lalu masuk dengan benar: WSL melekat pada akun pemasang. Baca pemeriksaan, perbaiki virtualisasi nonaktif. Jawab pertanyaan akun Debian di jendela; akun ini berbeda dari akun pustakawan Koha.

Tunggu WSL 2/Debian. Restart yang diminta mencatat kelanjutan pada login Windows berikutnya. Pilih bahasa/**Install Koha server**. Selesai di panel, keluar normal dan tunggu integrasi Windows.

Standar `C:\Koha`; instalasi lama mungkin mempertahankan `C:\KohaEasy`. Jangan memindahkan folder untuk memperbaiki interupsi. Simpan pesan: tahap selesai dicatat, menjalankan lagi dapat melanjutkan atau membuka panel untuk penyelesaian. Ini tidak membuat instalasi ulang destruktif aman.

## MSIX

Paket menyiapkan WSL yang sama; paket terpasang bukan server/database siap. Gunakan **PowerShell biasa tanpa peningkatan hak terlebih dahulu**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

Pembantu mengunduh paket sesuai kode, memeriksa asal, meminta izin administratif, memasang untuk pengguna saat ini. Jangan abaikan penolakan. Tunggu persiapan, selesaikan panduan server, keluar normal, tunggu pintasan/tugas/jaringan Windows. Menutup lebih awal tidak menyelesaikan Koha; buka lagi.

**Perlu dikonfirmasi:** ketersediaan dan URL publik Microsoft Store; kode pengemasan bukan bukti publikasi. MSIX ARM64 penuh juga belum terbukti: manifest x64, dukungan Linux arm64 tidak cukup. Manifest mengizinkan Windows lebih lama daripada seluruh alur WSL; gunakan persyaratan penuh di atas.

## Debian/Ubuntu

Pada terminal server:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Dengan repositori lokal dan terjemahan:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Bahasa/**Install Koha server**. Perbaiki kegagalan kritis dahulu; peringatan bukan jaminan kapasitas. WSL 2 dan systemd berjalan diperlukan, WSL 1 ditolak. Pada Windows disarankan persiapan terpandu tadi.

## Instalasi melalui panel

Buka **Install Koha server**, tunggu pemeriksaan/laporan dan pertimbangkan dampak membebaskan port. Pastikan komputer tujuan dan zona waktu atau wilayah/kota. **Instans sudah ada: berhenti dan periksa.** Instalasi ulang menghapus database/konfigurasi, memerlukan konfirmasi tambahan dan persis `REINSTALL`. Bukan untuk sekadar membuka/memperbarui panel.

Jangan tutup; tidak dapat dibatalkan. Perkiraan 10–30 menit bergantung perangkat/jaringan. Baca hasil/laporan: selesai dengan masalah bukan layanan sehat. Pertimbangkan restart ditawarkan, untuk MSIX tunggu kelanjutan Windows. Jangan salin data pribadi hasil ke dokumen publik/permintaan bantuan.

## Sumber yang diperiksa

- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [installer](../../../installer).
- [README.md](../../../README.md).
- [install.ps1](../../../windows/install.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [instalar_msix.ps1](../../../windows/msix/instalar_msix.ps1).
- [KohaMsixEntry.cs](../../../windows/msix/KohaMsixEntry.cs).
- [KohaMsixPanel.ps1](../../../windows/KohaMsixPanel.ps1).
- [compilar_msix.ps1](../../../windows/msix/compilar_msix.ps1).
- [install.py](../../../panel/kei_panel/routines/install.py).
