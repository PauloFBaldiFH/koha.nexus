# 8. Yönetim, mesajlar ve VPN

[İçindekiler](README.md)

Yönetimden önce durum/güncel backup. Ayar ağda çalıştığını kanıtlamaz, ardından denetleyin.

## Cron ve VPN

**Schedules & cron tasks**, `s`: açma/sıklık/zaman/gün/özel ifade. **Reload**, gerekli görevler, `HH:MM`, **Preview**, **Save**/onay, yeniden oku. `/etc/cron.d/koha_tasks`, önceki `koha_tasks.bak`; kapalılar saatiyle yorum, özel satırlar kalır. **Defaults** doldurur, kaydetmek gerekir. SQL günlük 23:00/MARC pazar 03:00; dilim/özel ayar denetleyin. Sunucu/Linux çalışmalı, cron Windows açma garantisi değil; Koha bildirimleri ayrı.

**Security & access hub > WireGuard VPN**, `v`: genel ad/adres/UDP. **Set up the VPN** değişiklikleri gösterir, yönlendirici UDP’yi sunucuya aktarır. Ad/**Add device**, **QR code & profile**, bağlantı/staff/trafik kontrol. Profil/QR yayımlamayın. **Revoke** yeni profil ister; **Turn off** bağlantıyı keser, tutar. Bölünmüş tünel yalnız `10.66.0.0/24`, kendi internet/DNS, staff `http://10.66.0.1:8080`. Mirrored olmayan WSL doğrudan erişilmez, VPN kapalı.

## Mesajlar

**Messaging & interoperability**, `m`: **E-mail**, **WhatsApp & Telegram**, **SMS**, **Alerts**, **SIP2**, **Z39.50**. E-mail aç/SMTP denetle, düğmeler SMTP/kütüphane adresi/bildirim-makbuz/gecikme kuralları. Her kural/alıcı/şablon dolmaz, tercihler/özel sağlayıcı ayarı denetlenir.

**Set up WhatsApp and Telegram** hizmet/ülke/alan kodu/test/açma/telefon. WhatsApp gateway, Telegram bot/alıcı ister. Üretim öncesi izinli test, toplu düzeltme öncesi biçim/şablon. SMS `SMSSendDriver`/okuyucu tercihleri uyumlu hizmet/sürücü ister, yalnız ad değil.

**Alerts** vade/gecikme/tekrar/günlük özet/kanal, kaydet/**Dry run (sends nothing)**. Görevi açar: cron kontrol, Koha çiftlerinden kaçının. SIP2 port/ağ/kütüphane/cihaz hakları; örnekleri kaldırıp düğmeyle Koha hesabı oluşturun, hesap/sunucu eşleşmeli. Yerel test için tüm ağları açmayın. Z39.50 bölüm 5, giriş/çıkış farklı.

## Yönetim

Hub Cloudflare Tunnel/UFW/staff-8080/HTTPS/Fail2ban, durum/özet; VPN/tünel/doğrudan ayrımı. Uzak firewall’u başka yönetim yolu kalmadan değiştirmeyin. **Doğrulanacak:** alan adı/yönlendirici/sağlayıcı/kurum, kod evrensel yayın tarifi vermez.

**Koha settings & parameters** bellek/workers, süper kütüphaneci, dilim; geniş hakları kısıtlayın. **Koha languages** indir/aç, yalnız indir, kurulu aç/listele ayrımı, panel/OPAC/staff kontrol. **Update center** sistem/şema ayrı GitHub-panel; backup/bakım, oturum kapanabilir. Yeniden başlatma şema göçü onarımı kanıtı değil.

**Library tools** otorite bağ/senkron, yazar çiftleri, SQL, kategoriler, kalite/gizlilik. Farklı kaynak/hedef kategori, filtre/kütüphane, korumalı onay öncesi benzetim. Kalite okur, her şeyi onarmaz. Anonimleştirme Koha’ya göre eski geçmiş/okuyucu bağını kaldırır, tüm bibliyografyayı değil. Okuyucu silme filtre/benzetim/sayı, yıkıcı, saklama politikası kontrol. Benzer adlar tek kişi kanıtı değil. Gizli kartlar kullanılabilir araç sayılmaz.

## Kontrol edilen kaynaklar

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
