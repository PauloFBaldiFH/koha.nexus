# 6. OPAC ve staff görünümü

[İçindekiler](README.md)

**OPAC and Staff Appearance**, `o`, genel OPAC ve staff/intraneti ayrı ayarlar.

**Sync current OPAC settings** uygulamadan okur. Grupları sırayla değiştirin. **Preview** CSS/JavaScript/içerik, tam tarayıcı çizimi değil. **Apply** özet/onay ve önce backup. Başlangıç/arama/kayıt/giriş, küçük ekran da denetlenir.

Bloklar `OpacUserCSS/OpacUserJS`, gerekirse `IntranetUserCSS/IntranetUserJS`. Kendinizinkiler korunur, başka özelleştirmeyle görsel çatışma mümkündür.

Doku/bulanıklık/opaklık/köşe/renk/fon, açık/koyu/başlangıç teması: resim/saydamlıkta karşıtlık koruyun. Staff üst çubuk/hızlı arama/modüller/tablo yoğunluğu/metin/karşıtlık. **Apply color theme to Staff Client** açın; **Copy OPAC preset** doldurur, **Apply** yazar.

Sunucuya erişilir dosya, önerilen resim hizmeti veya doğrudan HTTPS-URL. PNG/JPEG/GIF/WebP/ICO kabul, SVG ret. Sadece kullanıcı bilgisayarındaki dosya sunucuya açılmalı. Görsel hakkı/erişilebilir giriş betimi; barındırma sayfası her zaman resim adresi değil. Dış hizmetleri ayarlayın, özel bilgi yayımlamayın.

Karusel yeni eser/Koha-listesi ve `shelfnumber=`; başlık/sayı/stil/hız/autoplay/**Refresh carousel**. Kapak yokluğu silinmiş kayıt değil: veri/kapak/ağa bağlı. OPAC/staff düğmeleri ayrı: metin/adres/hedef/sıra, **Add a button**, uygulamadan önce satır silme.

Giriş resim/betim/HTML içerir, betik/stil/olaylar süzülür; gizli yönerge değil. İki tarafın haberleri ayrı başlık/metin/düğme, mevcut kütüphane haberi değişmez. Altbilgi `Field: value`, ek bağlar metin `|` adres, en çok altı, yalnız kamuya açık.

**Remove** tema bloklarını kaldırmadan onay/backup, kendi özelleştirmelerle Koha görünümüne döner. Tam restore/başka yönetimi geri alma değil. Yanlış grubu düzeltip uygulayın, hatayı teşhis için saklayın.

## Kontrol edilen kaynaklar

- [opac.py](../../../panel/kei_panel/views/opac.py).
- [menus.py](../../../panel/kei_panel/menus.py).
