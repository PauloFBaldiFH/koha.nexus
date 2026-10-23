# 9. Sorun giderme ve günlükler

[İçindekiler](README.md)

İşlem/saat/tam hata ve çalışan bölümleri kaydedin. Açık sayfa, hizmet ve başarılı arama ayrı denetimler. Yeniden kurulum/restore evrensel ilk çözüm değil.

**Control Dashboard** yenile. **Diagnostics & maintenance center > Detailed server & Koha status**, **Full system health check**, raporu oku. **View latest validation report** yeniden açar; **Export diagnostics** destek klasörü. Maskelense de kişi/ad/adresleri paylaşmadan inceleyin, tüm kurulumu kopyalamayın. Textual klasik yedeği önceki işleri geri almaz; mesaj/log tutun.

| Yol | İçerik |
| --- | --- |
| `/var/log/koha-easy-install/` | Ana Linux |
| `apt.log` | Paket/aşamalar |
| `validacao-*.log` | Tarihli rapor |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/çıktı |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | İndeks/arama |
| `/var/log/koha-easy-install/tools/` | Araçlar |
| `C:\Koha\logs`, eski `C:\KohaEasy\logs` | Windows kurulumuna göre |

`*` tarihli dosya, ilk çalışmadan önce olmayabilir. Tam gösterilen yol öncelikli. **Library tools > View tool logs** tarih/görev, kişisel veri nedeniyle sınırlı. Rapor bağlam/tarih/sürüm/OK/uyarı/hata tek tek okunur. **No critical failures** uyarı içerebilir, eski backup veritabanı arızası değildir. Sonra yeniden denetle/karşılaştır.

**Real-time Apache log auditing** staff/OPAC/eski alternatifler. Textual **Pause/p** görünümü durdurur, Apache değil; **Continue**, **Back/Esc** kapatır. Klasik `Ctrl+C` bu izlemeye ait, her göreve değil. `error/fatal/denied/fail` saat/bağlam; renk neden kanıtı değil.

- OPAC/staff erişilmez: Apache/MariaDB/Plack/cache, yerel/ağ/VPN/tünel. `localhost` tarayıcı bilgisayarı. **Restart / repair Koha services (Memcached, Plack)** kesebilir; sonucu oku/denetle.
- Kayıt bulunmaz: motor/kuyruk/indeks-veritabanı; **Search engine & indexing > Repair / rebuild indexing**, oku/bekle. Elasticsearch zorunlu ilk adım değil.
- Backup yok: zaman/sonuç/alan/sistem cron sırasında, `.part` bitmemiş. `backup_sql.log`, test/elle; başka güvenli kopyasız son geçerliyi silmeyin, görevleri çakıştırmayın.
- Import/sayılar: Magic Import/MARC, giriş/hazırlık/yazma, mod/kod/barcode/ret/çiftler. Küçük önizleme tümünü doğrulamaz; tam test/bitmiş aşamalar tekrar öncesi.
- Restore: aşamayı bulun, indeks veritabanından sonra başarısız olabilir, rollback de; veritabanı/arama/denetim.
- AI/zenginleştirme yavaş: Ollama/seçim/bellek veya iş/sunucu/sınır; gecikmeden büyük işi çoğaltmayın. Dış hizmet/yerel RAM farklı araştırılır.

## Windows simgesi

Giriş yapmış kullanıcının PowerShell’i, **yönetici olmadan**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Kısayol/tray yenileyebilir, yalnız okuma değil. Bulunan `logs` içinde `diagnose-<date>.txt`, yol/hata saklanır. Yönetici kurulumundan farklıdır.

**Deep database optimization & log cleanup** bakım/başlatma yapar, yararlı geçmişi silebilir. Teşhisi önce saklayın, hatayı gizlemeyin. Destek için sürüm/Windows-WSL-dağıtım/işlem-saat-tam hata/OPAC-staff-arama/önceki işlem ve gizlilik denetimli alıntı.

**Doğrulanacak:** tam mesaj/log olmadan neden, otomatik ağ/kurulum değildir.

## Kontrol edilen kaynaklar

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
