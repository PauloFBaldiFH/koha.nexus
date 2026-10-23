# 7. Yerel yapay zekâ

[İçindekiler](README.md)

**AI**, `a`: sağlayıcı, Ollama, MARC Replace fotoğraf kataloglaması, staff asistanı. Yapılandırma araçları otomatik kurmaz.

CPU/RAM uyarısını okuyun: Koha yavaşlayabilir. **Ollama on this server > Check Ollama**, yoksa **Install Ollama**. Seçim/**Download** ağ/disk ister; model adları değişebildiği için sabitlenmez. **Local Ollama**, URL (normalde `http://127.0.0.1:11434`), **Use for chat/Use for cataloguing**. Fotoğrafa görme gerekir, yalnız metin yetmez. **Test connection/Save**, **F5/Ctrl+S**; alan doldurmak kaydetmez. Boş sohbet görme seçimini kullanır. **Load models** sağlayıcıya sorar, yerleşik yedek listeyi belirtir.

Kurulmuş diskte, yüklenmiş RAM’dedir. **Free memory** silmeden boşaltır, sonra tekrar yüklenebilir. Ollama başka sağlayıcıyla da görünür: kaydedilmiş URL/sağlayıcıyı denetleyin, kurulu olması yerellik kanıtı değildir.

## Araçlar

MARC Replace kur/güncelle, Koha derleme/staff kısayolları denetlenir. Bir kayıt: `.mrc/.xml` veya metin, `biblionumber`, **Preview**, karşılaştır/onay. Boş yeni oluşturur, mükerrerden kaçının. Mevcut nüsha kalır, gelen nüsha alanları çıkarılır. Önceki MARCXML indirilebilir/aynı ID’ye yeniden gönderilebilir, tam backup yerine değil.

**AI cataloguing**: okunur kapak/başlık sayfası/arkası, JPEG/PNG/WebP, en az bir. Framework/hedef, **Read the photos**, bekleyip başlık/sorumluluk/yayın/ISBN/sınıf/eksik karşılaştırın. Yazmadan MARC düzeltin, sınıfı tablolardan denetleyin; ISBN kontrol basamağı baskı kanıtı değil. Taslak nüsha alanlarını yazmaz.

**Install, update or remove the assistant** staff başlangıç haberini değiştirir, OPAC’ı değil. Koha araması/tanımlı okumalar, serbest SQL değil. **Öneri uygulanmış değişiklik değildir:** kayıt/önce-sonra/etki, kendi yetkileriyle **Approve & Execute** gerekir. Ara değişiklik reddedebilir/yeni öneri isteyebilir. Onaylı işlemler incelenir; sohbet/asistan silmek geri almaz. Kaldırma sohbetleri siler, onay geçmişini tutar.

Donanım/Koha izleyin; yavaşken yeni fotoğraf başlatmayın, uygun bellek boşaltın. Süre garantisi yok. Dış sağlayıcı isteği alır: veri/resim politikası, gerçek okuyucuyla test etmeyin. Fiyat etiketi ücretsizliği garanti etmez.

**Doğrulanacak:** seçime/donanıma göre RAM/disk/yanıt; Koha minimumu AI garantisi değil.

## Kontrol edilen kaynaklar

- [ai.py](../../../panel/kei_panel/views/ai.py).
- [marcreplace.py](../../../panel/kei_panel/marcreplace.py).
- [installer](../../../installer).
