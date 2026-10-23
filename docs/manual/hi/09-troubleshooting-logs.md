# 9. समस्या निवारण और लॉग

[विषय-सूची](README.md)

## साक्ष्य पहले रखें

कार्य, समय, पूरा संदेश और क्या चल रहा है लिखें। पृष्ठ खुलना, सेवा चलना और खोज सफल होना अलग हैं। हर त्रुटि में पहले पुनः स्थापना या restore न करें। **Control Dashboard** ताज़ा करें। **Diagnostics & maintenance center** में **Detailed server & Koha status**, **Full system health check**, **View latest validation report** पढ़ें। **Export diagnostics** का पथ रखें। कुछ रहस्य छिपने पर भी पाठक, फ़ाइल नाम और ढाँचे के पते साझा करने से पहले देखें। पूरी स्थापना सार्वजनिक न करें। पुराने पैनल में लौटना पिछला काम वापस नहीं करता।

## लॉग पढ़ना

Linux में `/var/log/koha-easy-install/` के भीतर `apt.log`, `validacao-*.log`, `new-panel.log`, `backup_sql.log`, `backup_marc.log`, `restore.log`, `restore-import.log`, `zebra-rebuild.log`, `search-engine.log` हैं। उपकरणों के लिए `/var/log/koha-easy-install/tools/` देखें। Windows का सामान्य स्थान `C:\Koha\logs`, पुराना `C:\KohaEasy\logs` है।

`*` बदलती तारीख का संकेत है, ऐसा नाम स्वयं न बनाएँ। पहली बार कार्य से पहले लॉग न हो सकता है। त्रुटि में दिया ठीक पथ लें। **View tool logs** में तारीख/कार्य चुनें; व्यक्तिगत सूचना होने से पहुँच सीमित रखें। रिपोर्ट में संस्करण, समय और हर OK/चेतावनी/विफलता पढ़ें, केवल कुल नहीं। **No critical failures** के साथ भी चेतावनी हो सकती है। सुधार बाद फिर जाँचकर तुलना करें।

**Real-time Apache log auditing** में staff/OPAC चुनें। Textual **Pause** या p केवल दृश्य रोकता है, Apache नहीं। **Continue** फिर दिखाता है, **Back**/Esc बाहर आता है। पुराने पैनल का Ctrl+C इस लॉग अनुकरण से बाहर निकलने के लिए है, हर कार्य में नहीं। error/fatal/denied/fail के आसपास का समय व संदर्भ पढ़ें; रंग अकेला कारण नहीं।

## लक्षण के अनुसार

न खुलने पर Apache, MariaDB, Plack, cache और स्थानीय/LAN/VPN/tunnel पते जाँचें। localhost ब्राउज़र के कंप्यूटर का है। **Restart / repair Koha services (Memcached, Plack)** थोड़ी रुकावट डाल सकता है; परिणाम फिर जाँचें।

रिकॉर्ड न मिलने पर इंजन, कतार, अनुक्रमणिका/डेटाबेस देखें। **Search engine & indexing > Repair / rebuild indexing** के प्रश्न पढ़कर पूरा होने दें। शुरुआत में Elasticsearch बदलना अनिवार्य नहीं।

backup न बने तो समय, जगह, cron, मशीन/Linux देखें। `.part` अधूरा है। एक साथ काम न दोहराएँ, दूसरी सुरक्षित प्रति बिना अंतिम सही backup न मिटाएँ। आयात में स्रोत/तैयारी/वास्तविक संख्या, मोड, कोड, बारकोड, अस्वीकृति व डुप्लिकेट नीति देखें। छोटा नमूना पूरे का प्रमाण नहीं; फिर चलाने से पहले आंशिक लेखन जाँचें।

restore में चरण देखें: अनुक्रमणिका विफलता डेटाबेस बदलने के बाद हो सकती है और rollback भी विफल हो सकता है। डेटाबेस, खोज, सत्यापन से ही बहाली कहें। स्थानीय AI की RAM और दूर की खोज सीमा अलग कारण हैं; धीमा होने पर बड़ा काम दोबारा न भेजें।

## Windows और सहायता

साइन-इन उपयोगकर्ता के सामान्य, गैर-व्यवस्थापक PowerShell में:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

यह केवल पढ़ने वाला उपकरण नहीं: शॉर्टकट बना और tray पुनः शुरू कर सकता है। पहचाने गए `logs` में `diagnose-<date>.txt` रखें। **Deep database optimization & log cleanup** उपयोगी इतिहास मिटा सकता है, पहले जाँच बचाएँ और रखरखाव समय लें।

सहायता में संस्करण, OS/WSL, कार्य, समय, पूरा संदेश, OPAC/staff/खोज स्थिति और ठीक पहले का आयात/restore/अपडेट दें। निजी सूचना हटाएँ। पूरा लॉग न हो तो विशिष्ट कारण की पुष्टि आवश्यक रहती है।

## जाँचे गए स्रोत

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
