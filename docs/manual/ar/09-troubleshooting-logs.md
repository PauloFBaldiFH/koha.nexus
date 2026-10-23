<div dir="rtl" lang="ar">

# 9. تشخيص المشكلات والسجلات

[المحتويات](README.md)

سجل الإجراء والوقت والخطأ كاملاً والأجزاء العاملة. الصفحة والخدمة والبحث الناجح فحوص مختلفة؛ إعادة التثبيت وrestore ليست حلاً أولاً لكل شيء.

حدث **Control Dashboard** ثم **Diagnostics & maintenance center > Detailed server & Koha status** و**Full system health check** واقرأ التقرير. **View latest validation report** يفتحه و**Export diagnostics** يعرض مجلد الدعم. رغم الإخفاء راجع الأشخاص والأسماء والعناوين قبل المشاركة ولا تنسخ التثبيت كله. بديل Textual التقليدي لا يتراجع عن الأعمال السابقة؛ احفظ الرسالة والسجل.

| المسار | المحتوى |
| --- | --- |
| `/var/log/koha-easy-install/` | رئيسي Linux |
| `apt.log` | حزم ومراحل |
| `validacao-*.log` | تقارير مؤرخة |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup وتصدير |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | فهرس وبحث |
| `/var/log/koha-easy-install/tools/` | أدوات |
| `C:\Koha\logs`, والقديم `C:\KohaEasy\logs` | Windows وفق التثبيت |

`*` ملفات مؤرخة قد تغيب قبل التشغيل الأول؛ قدم المسار المعروض الدقيق. **Library tools > View tool logs** حسب التاريخ والمهمة، الوصول مقيد لبيانات شخصية. التقرير سياق وتاريخ وإصدار وOK وتحذير وخطأ، اقرأ كلاً. **No critical failures** قد يصاحبه تحذير؛ backup قديم ليس عطل قاعدة. أعد الفحص والمقارنة بعد الإصلاح.

**Real-time Apache log auditing** يختار staff/OPAC وبدائل قديمة. Textual **Pause/p** يوقف العرض لا Apache؛ **Continue** ثم **Back/Esc** للخروج. التقليدي `Ctrl+C` لهذا التتبع لا لكل مهمة. `error/fatal/denied/fail` وقت وسياق، اللون ليس سبباً.

- تعذر OPAC/staff: Apache/MariaDB/Plack/cache وعنوان محلي/شبكة/VPN/نفق. `localhost` جهاز المتصفح. **Restart / repair Koha services (Memcached, Plack)** قد يقطع؛ اقرأ وأعد الفحص.
- التسجيل لا يظهر: محرك وطابور وفهرس/قاعدة، **Search engine & indexing > Repair / rebuild indexing**، اقرأ وانتظر؛ Elasticsearch ليس أول خطوة واجبة.
- غياب backup: وقت ونتيجة ومساحة والنظام عند cron، `.part` غير مكتمل. `backup_sql.log` واختبار أو يدوي؛ لا تمح آخر صحيح دون آخر آمن ولا تداخل مهام.
- استيراد أو أعداد: Magic Import/MARC، مدخل وإعداد وكتابة ونمط ورموز وbarcode ورفض وتكرار. العينة الصغيرة لا تفحص الجميع؛ اختبار كامل والمراحل المنتهية قبل التكرار.
- Restore: حدد المرحلة، قد يفشل الفهرس بعد القاعدة وrollback أيضاً؛ قاعدة وبحث وتحقق.
- بطء الإثراء والذكاء: Ollama واختيار وذاكرة أو مهمة وخادم وحدود؛ لا تكرر الكبير للتأخر. الخارجي وRAM المحلي تشخيصان مختلفان.

## أيقونة Windows

PowerShell للمستخدم الحالي **دون مسؤول**:

<div dir="ltr">

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

</div>

قد ينشئ الاختصارات ويعيد tray، ليس قراءة فقط. يكتب `diagnose-<date>.txt` في `logs` المكتشف، احفظ المسار والخطأ. مختلف عن التثبيت الإداري.

**Deep database optimization & log cleanup** صيانة وإعادة تشغيل قد تمحو تاريخاً مفيداً. احفظ التشخيص أولاً ولا تخف الخطأ. للدعم: نسخة وWindows/WSL/توزيعة وإجراء ووقت ورسالة كاملة وOPAC/staff/بحث وعملية سابقة ومقتطفات مراجعة للخصوصية.

**بحاجة إلى تأكيد:** السبب دون الرسالة والسجل كاملين؛ ليس تلقائياً شبكة أو تثبيتاً.

## المصادر التي جرى فحصها

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).

</div>
