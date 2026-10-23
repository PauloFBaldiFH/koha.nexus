# 2. İlk adımlar ve panel

[İçindekiler](README.md)

## Açma ve gezinme

Hazırlanmış Debian/Ubuntu üzerinde:

```bash
sudo config.sh
```

Windows: **Koha** simgesi veya MSIX. İlk açılış dil sorabilir; Textual hazırlığı başarısızsa klasik panel sunulabilir. Bu kılavuz eski menü numaralarını değil öncelikle Textual’ı anlatır.

Yan bölümü oklarla seçip **Enter** ya da tıklamayla açın. İşaretlemek tek başına çalıştırmaz. Görev kartını açıp soruları okuyun. **Tab** odağı taşır; harf kısayollarından önce metin alanından çıkın.

| Tuş | İşlem |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | Debian terminali |
| `Ctrl+B` | Yan çubuğu göster/gizle |
| `q` | Panelden çık |

Boş panelden çıkmak sunucuyu kapatmaz. Çalışan görevin iptal yönergelerine uyun. Kurulum/restore iptal edilemeyen aşamalar içerir; zorla kapatmak güvenli değildir.

## Durum ve adresler

Dashboard Koha/kullanılabilir bellek, tarih/yaş/dosyalı son backup, boş disk, adresler, MariaDB, Apache, RabbitMQ, Memcached, Koha ve HTTP denetimlerini gösterir. Backup dosya yaşıyla son gece sonucunu birlikte değerlendirir; yeni dosya ve gece hatası birlikte olabilir. İkisini okuyun; iyi gösterge restore testini yerine geçmez. HTTP, web kurulumunun ya da bütün kütüphane işlevlerinin tamamlandığını kanıtlamaz.

**Refresh** yeniden okur; **Restart Koha** kullanıcıları gözeterek hizmet onarımı/yeniden başlatma ister; **Export diagnostics** destek bilgisi hazırlar. Yüklü kurucu görevi desteklemiyorsa düğmeler kullanılamayabilir.

Adres kartları URL açar/kopyalar; tarayıcı açılamıyorsa kendi tarayıcınıza yapıştırın. Sunucuda OPAC `http://localhost/`, staff `http://localhost:8080/`, portlar 80/8080. Başka bilgisayarda onun `localhost` adresini değil gösterilen ağ adresini kullanın. WSL NAT/LAN uyarısında Windows hazırlığını sorumluyla denetleyin, her yerden erişim varsaymayın.

Koha web kurucusu görünürse işletime başlamadan tamamlayın; ekranlar sürüme bağlıdır. **Koha settings & parameters > Create super librarian** hesap oluşturur, özel değerler yalnız orada.

İşletimden önce dashboard/komponent/adresleri denetleyin, OPAC/staff’ı doğru yerden açın, backup oluşturup test edin; dış kopyayı ve geri getirecek kişiyi doğrulayın. Son madde işletim önerisidir: tamamlanmış ve denetlenmiş aktarım gerekir.

## Kontrol edilen kaynaklar

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
