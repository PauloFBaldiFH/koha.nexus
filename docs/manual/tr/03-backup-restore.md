# 3. Backup ve restore

[İçindekiler](README.md)

## Merkez ve kopyalar

**Backup center**, `b`: tarih, boyut, sonuç, **Compression**, kartlar.

| Kart | Amaç |
| --- | --- |
| Download latest backup | Bulunan en yeni dosyayı kopyala |
| Generate manual backup and download to PC | Veritabanı oluştur/denetle/aktar |
| Export MARC21 records now | Bibliyografya ve otorite kayıtları |
| Restore database | Geçerli veritabanını değiştir |
| Configure cloud backup | Dış gönderim |
| Test integrity of latest backup | Geçici içe aktarma testi |

**Restore database bir karttır**, üst düğme veya bağımsız ana menü değil. Sonuç gece çalışmasına, tarih/boyut en yeni dosyaya aittir; aynı iş olmayabilir.

SQL Koha veritabanıdır, tüm Windows/Debian görüntüsü değildir. MARC21 `.tar.gz` içinde bibliyografya/otoriteyi içerir; okuyucu/dolaşım için SQL yerine geçmez. Tablolu veritabanı restore öncesi doğrulanmış güvenlik kopyası alır; boş veritabanı atlayabilir.

Otomatik SQL/güvenlik `/var/backups/koha_sql`, MARC `/var/backups/koha_marc`. Elle backup ayrı hedefe, normalde saptanan ev dizininde `backups` içine gider. `.part` denetim/yeniden adlandırma bitene kadar geçicidir.

## Sıkıştırma ve aktarım

**Compression**: gzip `.sql.gz` uyumlu, Zstandard `.sql.zst` hızlı/küçük, büyük kataloglar; XZ/LZMA `.sql.xz` en küçük/yavaş. Seçim hemen kaydolur, ek düğme yok; yeni gece/elle/güvenlik kopyalarına uygulanır, eskileri yeniden sıkıştırmaz. Program yok/kurulamazsa gerçek biçimi okuyun, gzip kullanılabilir. Restore seçime bakmadan `.sql/.sql.gz/.sql.zst/.sql.xz` tanır; uzantı geçerlilik kanıtı değil.

**Generate manual backup and download to PC**: yazılabilir sunucu klasörü, **Save backup**, oluşturma/denetimi bekleyin. Yazma/kopyalamada ekran kapanmaz. Ad/boyut/yol; WSL **Save to Windows Downloads/Choose folder in Windows**; uzakta gösterilen komutu kendi bilgisayarınızda çalıştırın. Alınan dosyayı denetleyip **Finish and exit**.

Windows düğmeleri yalnız WSL. Başkasının komutunu kopyalamayın, sunucu/dosya hesaplanır. Başka backup/restore varsa bekleyin; ortak kilidi dış eşzamanlı görevle aşmayın. **Download latest backup** mevcut dosyayı alır, yeni üretmez. Desktop-Linux/WSL Downloads dener, SSH yerel komut gösterebilir; dosya yoksa elle oluşturun.

## Test, MARC, bulut

**Test integrity of latest backup**: tarih/dosya, gerekirse **Choose another file**, onay ve geçici import. Başarı tablo/kayıt/okuyucu sayısını verir, üretimi değiştirmez. Bu kopya/ortam için geçerlidir; aktarılan aynı kopyaya erişimi koruyun.

**Export MARC21 records now** onay, bibliyografya/otorite paketi, yol/içerik/aktarım denetimi. Koha çalışır; ayarlı bulut gönderimi de raporlar. Tüm veritabanı için SQL tutun.

**Configure cloud backup**: iki Google Drive yolu, ayrıca OneDrive/MEGA/S3. Sunucuda/başka bilgisayarda yetkilendirme, yalnız gösterilen URL/yönergeler. S3 hizmet/bölge/endpoint/bucket ayırır. Gerçek gönderim testini ve alımı denetleyin; başarısız ayara güvenmeyin. Özel veriler yalnız kurulumda, kamuya açık metin/resim/destek değil; saklama dosyaları belirtilmez. Varsayılan SQL her gün 23:00, MARC pazar 03:00 sunucu saati; cron değişebilir.

## Yıkıcı restore

**Onay geçerli veritabanını değiştirmeye izin verir.** Bakım aralığı ve dış kopya planlayın; panel bu ek tavsiyeyi sizin yerinize otomatik yapmaz.

**Restore database**, sunucuya erişilir dosya, gerekiyorsa aktarım. WSL önce Windows’tan Linux’a kopyalayabilir. Erişim/içerik/bütünlük/alanı okuyun, şüpheli/eksik dosyayı uzantıya rağmen araştırın. Onayda yeniden denetleyin: öncesinde vazgeçilebilir, sonra kapatmadan bekleyin; iptal yok.

Önce geçici SQL-import, temel tablo/sayı denetimi; hata değişimden önce durdurur. Mevcut tablolara doğrulanmış SQL kopyası `pre_restore_safety_backup_`, tarih/saat/sıkıştırma. Kopya hatası mevcut veritabanını silmemelidir; boş olan atlayabilir.

Sonra istemciler durur, veritabanı oluşturulur/içe alınır, şema güncellenir ve arama eşitlenir, indeks/hizmetler başlar. Kaydedilmiş tema varsa yeniden uygulama denenir. Test/kopya hatası değiştirildi demek değil. Oluşturma/import/şema hatasında aşama/kopyaya göre dönüş denenebilir, **rollback de başarısız olabilir**. İndeks hatası veritabanı restore sonrasında oluşabilir, eski katalog dönmüş olmaz.

Tam mesaj, `/var/log/koha-easy-install/restore.log`, `/var/log/koha-easy-install/restore-import.log`, indeks için `/var/log/koha-easy-install/zebra-rebuild.log` saklayın. Eski numaralar değil merkez kartı; belirsiz durumda teknik yardım. Dashboard/kayıt/OPAC-staff aramasını denetleyin. SQL bitmesi dış dosyaları kanıtlamaz.

## Kontrol edilen kaynaklar

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
