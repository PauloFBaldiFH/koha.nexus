# 1. Kurulum

[İçindekiler](README.md)

## Ortam ve gereksinimler

Windows üzerinde Koha, WSL 2 içindeki Debian’da çalışır. Windows araçları ortamı hazırlar, paneli açar ve uygulamayı bütünleştirir. Debian/Ubuntu üzerinde panel ve hizmetler doğrudan kurulur. Mevcut kataloğu yeniden kurarak değil panelden açın.

| Ortam | Koddaki denetimler |
| --- | --- |
| Windows | Windows 10 sürüm 2004, yapı 19041 veya sonrası ya da Windows 11; 64 bit, sanallaştırma açık; 8 GB RAM, 12 GB önerilir; kurulum sürücüsünde 10 GB boş, 20 GB önerilir. |
| Debian/Ubuntu | Debian 11/12/13 veya Ubuntu 22.04/24.04; belirtilen amd64/arm64; 5 GB altı engeller, 5 ile 10 GB altı uyarır, en az 10 GB bu denetimi geçer. |

Katalog, ekler, dizinler ve backup ek alan ister. **Linux RAM doğrulanacak:** kılavuz adanmış sunucuya 4 GB, tercihen 8 GB; masaüstü/sanallaştırmaya 8 GB, tercihen 12 GB önerir. Linux ön denetimi sayısal RAM alt sınırı uygulamaz; geçmek her yükü kaldırma garantisi değildir. Windows donanımın ayırdığı belleği hesaba katar: algılanan eşikler 7,5 ve 11,5 GB.

Linux yönetici yetkisi ve Koha paket deposuna erişim ister. TCP 80/8080 OPAC/staff içindir. Doluysa ilgili hizmetleri durdurma önerilir. **Yalnız kesilmeleri uygunsa onaylayın.**

## Windows: PowerShell

Koha’yı kullanacak Windows yönetici hesabında oturum açıp aynı hesapta PowerShell’i yönetici olarak açın:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

Yetki yükseltme başkasının hesabını isterse iptal edip doğru hesapla girin: WSL kuran hesaba bağlıdır. Denetimleri okuyup kapalı sanallaştırmayı düzeltin. Pencerede Debian hesabı sorularını yanıtlayın; bu hesap Koha kütüphaneci hesabından ayrıdır.

WSL 2/Debian’ı bekleyin. İstenen yeniden başlatma, sonraki Windows girişine devam kaydı bırakır. Dil ve **Install Koha server** seçin. Panelde bitince normal çıkıp Windows bütünleştirmesini bekleyin.

Varsayılan `C:\Koha`, eski kurulum `C:\KohaEasy` olabilir. Kesintiyi onarmak için klasörü taşımayın. Hatayı kaydedin: bitmiş aşamalar saklanır, yeniden çalıştırma sürdürebilir veya tamamlamak için paneli açabilir. Bu, yıkıcı yeniden kurulumu güvenli kılmaz.

## MSIX

Paket aynı WSL’yi hazırlar; kurulmuş paket, hazır sunucu/veritabanı demek değildir. **Önceden yükseltilmemiş normal PowerShell** kullanın:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

Yardımcı, kodda ayarlı paketi indirir, kaynağı denetler, yönetici onayı ister ve geçerli kullanıcıya kurar. Retleri göz ardı etmeyin. Hazırlığı bekleyip sunucu sihirbazını bitirin, panelden normal çıkıp kısayol/görev/ağ işlemlerini bekleyin. Erken kapatmak Koha’yı bitirmez; yeniden açın.

**Doğrulanacak:** Microsoft Store herkese açık kullanılabilirliği/adresi; paketleme kodu yayın kanıtı değildir. MSIX ARM64 tam çalışması da doğrulanmadı: bildirim x64, Linux arm64 desteği kanıt olmaz. Bildirim tüm WSL sürecinden eski Windows’a izin verir; yukarıdaki tam gereksinimleri esas alın.

## Debian/Ubuntu

Sunucu terminalinde:

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

Yerel depo ve çevirilerle:

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

Dil/**Install Koha server**. Kritik hataları önce düzeltin; uyarı kapasite garantisi değildir. WSL 2 ve çalışan systemd gerekir; WSL 1 reddedilir. Windows’ta yönlendirmeli hazırlık önerilir.

## Panelden kurulum

**Install Koha server**, ön denetim/rapor ve port açmanın etkisini okuyun. Hedef bilgisayarı ve saat dilimini doğrulayın veya bölge/şehir seçin. **Mevcut örnek varsa durup inceleyin:** yeniden kurulum veritabanını/yapılandırmayı siler, ek onay ve tam `REINSTALL` ister. Sadece paneli açmak/güncellemek için değildir.

Kapatmadan bekleyin, iptal edilemez. Tahmini 10–30 dakika donanım/ağa bağlıdır. Sonucu/raporu okuyun: sorunlu tamamlanma sağlıklı hizmet demek değildir. Önerilen yeniden başlatmayı değerlendirin; MSIX’te Windows devamını da bekleyin. Sonuçtaki özel bilgileri herkese açık belgelere/destek taleplerine koymayın.

## Kontrol edilen kaynaklar

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
