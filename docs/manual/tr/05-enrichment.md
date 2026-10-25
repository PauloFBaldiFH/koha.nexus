# 5. Zenginleştirme ve Z39.50/SRU

[İçindekiler](README.md)

## Zenginleştirme

İçe aktarma dışa aktarımı taşır, zenginleştirme tamamlar veya yeni kitap bulur. Başlık eşleşmesi bibliyografik inceleme ister. **Library tools > Enrich from world catalogues**, `n`; eski toplu ekran güncel menü yolu değil.

`all` veya `biblionumbers`, örneğin `101, 102, 500-510`, **Search**. İş/sunucuları izleyin; büyük iş arka planda, yeniden başlatma sonrası erişilir makinede devam edebilir. **Pause/Resume** değişikliği geri almaz. Rapor: konu/sınıf/not/fiziksel betimleme karşılaştırın. **Search more servers** kullanılmamış kaynak, **Choose donor** alan grubu bağışçısı. **Apply** inceleme/onay sonrası; arama/rapor yazmaz.

Doğrudan Z39.50 sınır/arızaya tabidir; sonuç yokluğu kitap yokluğu değildir. Genel 50 kayıt sınırı yok: uygulama koruması eşiği, küçük iş kayıt kopyaları, büyük iş doğrulanmış tam backup. **Revert** korumalara göre önceki sürümleri getirir, sonradan düzenlenenleri tutar; genel restore veya başkasının her değişikliğini geri alma değil.

## Yeni kitap ve otoriteler

ISBN/başlık, yazar/yıl, **Find**, incele/seç. **Import as new record** onayla ekler, aynı ISBN’yi değiştirmez. Bağışçı yerel `9XX` kaldırılır, kaynak yazılır; başkasının nüshası sizin olmaz. Kaydı denetleyip yerel nüsha normal oluşturulur; parti **Undo a MARC import** ile.

**Enrich & standardize authorities**, `h`: kapsam/tam/yakın biçim. Yakınlar yazım/ön otorite önerebilir, dikkatle bakın. Önce kendi Koha, ardından zenginleştirme tabanı/doğrudan sunucular; Brezilya öncelikli, konular yalnız onlardan, yerel politika garantisi değil. **Apply** gerekli otorite/bağları backup ile oluşturur, rapordan sonra düzenleneni tutar. Revert hâlâ bağlı oluşturulmuş otoriteyi tutar.

## Sunucular

**Z39.50 / SRU servers**, `z`: gelen sunucu dış aramaya izin verir, firewall portunu değiştirir. Topluluk ağı doğrudan kaynaklardan farklıdır. **Reset/Reset all** yeni deneme, uzaktan onarım değil. Boşluk seçer, **Scan** gerçek kayıt arar, **Add to Koha** seçilmiş çalışanı kaydeder. SRU ayarı her sorgunun SRU olduğu demek değil; dış arama geleni açmayı gerektirmez.

**Doğrulanacak:** yerel ağdan kullanım anındaki her dış kaynak erişimi/kapsamı/koşulu.

## Kontrol edilen kaynaklar

- [menus.py](../../../panel/kei_panel/menus.py).
- [ondemand.py](../../../panel/kei_panel/views/ondemand.py).
- [enrich.py](../../../panel/kei_panel/views/enrich.py).
- [z3950.py](../../../panel/kei_panel/views/z3950.py).
