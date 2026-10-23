# 4. Sihirli içe aktarma

[İçindekiler](README.md)

## Hazırlık ve biçimler

Magic Import bibliyografya, nüsha, okuyucu, otorite okur. Tanınan biçim özellikle başlıksız/yerel alanları garanti etmez. Özgün dosya/doğrulanmış backup saklayın; çok nüsha, aksan, boş değer/istisna örneklemi deneyin, kaynak sayılarıyla karşılaştırın. Okuyucu dışa aktarımlarını yayımlamayın.

**Magic Import Tool**, `i`, kart ve panelin Linux’una erişilir dosya/klasör. Sadece tarayıcı/terminal bilgisayarındaki dosya otomatik sunucuda değildir.

| Girdi | Denetim |
| --- | --- |
| MARC21 ISO 2709, MARCXML, MARC metni | Başlık/karakter/otorite/nüsha; MarcEdit `.mrk`, sırf uzantıdan dönüşüm gerektirmeden tanınır. |
| CSV/TSV, `.xlsx/.xls/.ods/.dbf` | Ayırıcı/başlık/değer/hedef. |
| Tablo JSON/XML | Yapı; rastgele XML mutlaka MARCXML değil. |
| Başlıksız olabilen tablo SQL | Veri/ilişki okur, göç programı çalıştırmaz; belirsizlikleri denetleyin. |
| ISIS | `acervo` içeren tanınmış PostgreSQL; CDS/ISIS `.mst` WinISIS’ten ISO 2709 çıkarılır. |
| Biblioteca Fácil | Tanınan backup/klasör, ilişkili tablolar beraber; kayıt/okuyucu/ödünç/rezervasyon ayrı denetlenir. |
| Tam Koha-backup | Ekleme değil restore yönlendirmesi. |

Başka PostgreSQL, özellikle ikili `pg_dump`, hazır MariaDB değildir. Ret varsa kaynaktan MARC/tablo çıkarın. Arşivin her üyesini denetleyin; PDF/resim/belge/program bu okuyucunun bibliyografik girdisi değildir.

## Eşleme ve kayıtlar

**Bibliographic/Patrons/Authorities** kontrolü. Izgara/hedef, ayırıcı veya **Ctrl+Up/Down** yüksekliği. Koru/yönlendir/sabit metin/yoksay; ID silmeden bağlantıları anlayın. **Values of this Koha** kodları, varsayılan kütüphane/tür/kategori ve kaynak/hedef değişimlerini gösterir. **Record preview** sonuç; **Check the whole file** tamamını Koha’ya yazmadan hazırlar/denetler. Profil ad/**Save**, seçim/**Use**, yapı değişiminde yeniden inceleme. **Apply/Ctrl+S** eşlemeyi kabul eder, son yazma onayı değil. **Skip: import as it is/Esc** eşlemeyi atlar, tümünü iptal etmez. Gruplama/metin düzeltmesi önizleme gerektirir, kısaltma/isim/kodları körlemesine değiştirmeyin.

Yerel `952` korunur, kütüphane/tür istenirse eşlenir; geçerli farklı kodu yalnız varsayılana uydurmayın. Barcode, sahip/güncel kütüphane, raf kodu, tür, konum, edinim denetlenir. `949/852/950/990` Pergamum/Biblivre’de farklı anlamlı olabilir. `DL`/tarih yasal teslim notu otomatik yerel nüsha yaratmaz; dışlamaları/bağımsız envanter kanıtını inceleyin. Eksik barcode normalde inceleme ister; üretim seçim ve kararlı göç/kaynak kimliği ister, çakışmayı sessiz numaralamaz. SQL ilişkisi sütun yeri/satır sırasından tahmin değil tanınmış olmalı; belirsizi önce düzeltin.

**Patrons**: ad/soyad/kart/iletişim/adres/tarihler/kütüphane/mevcut kategori. E-mail/CPF/tarih ipucu, doğum/kayıt/bitiş benzer olabilir. Mevcut güncellemesi kart eşlemesiyle sorulur, yalnız yeni eklemekten farklı; hak/kimlik doğrulamayı tahmin etmeyin. **Authorities**: ID, yetkili biçim, varyant, ilişki, tür; mod değişimi eksik bilgi yaratmaz.

Sayı/ret/soruları okuyun. Mevcudu yeni nüshalarla tut, gelenle değiştir veya karşılaştırmadan yeni oluştur seçimi. **Geç hata önceki aşamaları içe aktarılmış bırakabilir.** Özet/log ve bitmiş aşama/örnek/nüsha/kişi/bağlantıları tekrar öncesi denetleyin. **Library tools > Undo a MARC import** MARC içindir, tüm okuyucu/ödünç/rezervasyon değil. Tam veritabanı Backup center kurallarıyla.

**Doğrulanacak:** örneksiz/incelenmemiş özel dışa aktarım yapısı/sürümü.

## Kontrol edilen kaynaklar

- [menus.py](../../../panel/kei_panel/menus.py).
- [fieldmap.py](../../../panel/kei_panel/screens/fieldmap.py).
- [installer](../../../installer).
