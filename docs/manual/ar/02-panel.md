<div dir="rtl" lang="ar">

# 2. الخطوات الأولى واللوحة

[المحتويات](README.md)

## الفتح والتنقل

في Debian/Ubuntu المجهز:

<div dir="ltr">

```bash
sudo config.sh
```

</div>

في Windows افتح أيقونة **Koha** أو تطبيق MSIX. قد يطلب البدء اللغة؛ عند فشل تجهيز Textual قد تظهر اللوحة التقليدية. يشرح الدليل Textual أساساً، وليس أرقام قوائم قديمة.

حدد القسم بالأسهم وافتح بـ**Enter** أو النقر. التحديد وحده لا ينفذ. افتح بطاقة المهمة واقرأ الأسئلة. ينقل **Tab** التركيز؛ غادر حقل النص قبل الاختصارات الحرفية.

| المفتاح | الإجراء |
| --- | --- |
| `d` | Control Dashboard |
| `b` | Backup center |
| `c` | طرفية Debian |
| `Ctrl+B` | إظهار الشريط الجانبي أو إخفاؤه |
| `q` | مغادرة اللوحة |

الخروج من لوحة ساكنة لا يطفئ الخادم. اتبع إمكان الإلغاء الخاص بالمهمة. يتضمن التثبيت وrestore مراحل غير قابلة للإلغاء؛ الإغلاق القسري غير آمن.

## الحالة والعناوين

يعرض dashboard حالة Koha والذاكرة المتاحة وbackup الأخير بتاريخ وعمر وملف ومساحة القرص والعناوين وMariaDB وApache وRabbitMQ وMemcached وKoha وفحوص HTTP. يجمع مؤشر backup عمر الملف وآخر نتيجة ليلية؛ قد يجتمع ملف حديث وفشل ليلي. اقرأ الاثنين؛ المؤشر الجيد لا يغني عن اختبار restore. لا يثبت HTTP اكتمال معالج الويب أو جميع وظائف المكتبة.

**Refresh** يعيد القراءة، و**Restart Koha** يطلب إصلاح الخدمات وإعادتها مع مراعاة المستخدمين، و**Export diagnostics** يجهز الدعم. قد تتعطل الأزرار إن لم يدعم المثبت الموجود المهمة.

تفتح بطاقات العنوان URL أو تنسخه؛ عند تعذر المتصفح الصقه في جهازك. على الخادم OPAC `http://localhost/` وstaff `http://localhost:8080/`، المنفذان 80/8080. في جهاز آخر استخدم عنوان الشبكة لا `localhost` الخاص به. عند تحذير WSL NAT وعدم بلوغ LAN تحقق من إعداد Windows مع المسؤول؛ لا تفترض الوصول من كل الأجهزة.

أكمل مثبت Koha الويب إن ظهر؛ تختلف الشاشات حسب النسخة. ينشئ **Koha settings & parameters > Create super librarian** الحساب؛ القيم الخاصة هناك فقط.

قبل التشغيل تحقق من dashboard والمكونات والعناوين، وافتح OPAC/staff من الموقع الصحيح، وأنشئ واختبر backup وتأكد من النسخة الخارجية والمسؤول عن استعادتها. الأخيرة نصيحة تشغيلية تتطلب نقلاً مكتملاً ومتحققاً منه.

## المصادر التي جرى فحصها

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

</div>
