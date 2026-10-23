<div dir="rtl" lang="ar">

# 1. التثبيت

[المحتويات](README.md)

## البيئة والمتطلبات

يعمل Koha في Windows داخل Debian باستخدام WSL 2. تجهز أدوات Windows البيئة وتفتح اللوحة وتدمج التطبيق. في Debian/Ubuntu تثبت اللوحة والخدمات مباشرة. افتح الفهرس الموجود من اللوحة، ولا تعاود التثبيت لمجرد الدخول إليه.

| البيئة | الفحوص الموجودة في الشفرة |
| --- | --- |
| Windows | Windows 10 الإصدار 2004 والبنية 19041 أو أحدث، أو Windows 11؛ نظام 64 بت وافتراضية مفعلة؛ RAM بسعة 8 GB والمستحسن 12 GB؛ مساحة حرة 10 GB على قرص التثبيت والمستحسن 20 GB. |
| Debian/Ubuntu | Debian 11/12/13 أو Ubuntu 22.04/24.04؛ المعماريتان المذكورتان amd64/arm64؛ أقل من 5 GB يمنع، ومن 5 إلى أقل من 10 GB يحذر، ومن 10 GB ينجح هذا الفحص. |

يحتاج الفهرس والمرفقات والفهارس البحثية وbackup مساحة إضافية. **RAM في Linux بحاجة إلى تأكيد:** توصي الإرشادات بخادم مخصص 4 GB والأفضل 8 GB، ولسطح المكتب/الافتراضية 8 GB والأفضل 12 GB. لا يفرض فحص Linux الحالي حداً رقمياً للذاكرة؛ نجاحه لا يضمن تحمل كل عبء. يراعي Windows الذاكرة المحجوزة للأجهزة بعتبتين مقاستين 7,5 و11,5 GB.

يحتاج Linux صلاحيات الإدارة والوصول إلى مستودع حزم Koha. يستخدم OPAC/staff المنفذين TCP 80/8080. عند انشغالهما تعرض اللوحة إيقاف الخدمات المعنية. **وافق فقط إن كان قطعها مقبولاً.**

## Windows وPowerShell

سجل الدخول بحساب إدارة Windows الذي سيستخدم Koha، وافتح PowerShell بصفة مسؤول في الحساب نفسه:

<div dir="ltr">

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

</div>

إذا طلب رفع الصلاحيات حساب شخص آخر، ألغ وأعد الدخول بالحساب المناسب؛ مكونات WSL تتبع حساب التثبيت. اقرأ الفحوص وعالج تعطيل الافتراضية. أجب في النافذة عن حساب Debian، وهو منفصل عن حساب أمين المكتبة في Koha.

انتظر WSL 2/Debian. يسجل طلب إعادة التشغيل الاستكمال عند الدخول التالي إلى Windows. اختر اللغة و**Install Koha server**. بعد اكتمال اللوحة اخرج بصورة عادية وانتظر تكامل Windows.

المجلد الافتراضي `C:\Koha`، وقد يحتفظ القديم بـ`C:\KohaEasy`. لا تنقل المجلد لإصلاح الانقطاع. احتفظ بالخطأ: تسجل المراحل المكتملة وقد يستأنف التشغيل أو يفتح اللوحة للإكمال. لا يجعل ذلك إعادة التثبيت المدمرة آمنة.

## حزمة MSIX

تجهز البيئة نفسها؛ تثبيت الحزمة لا يكمل الخادم وقاعدة البيانات. استخدم **PowerShell عادياً دون رفع مسبق للصلاحيات**:

<div dir="ltr">

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

</div>

ينزل المساعد الحزمة المحددة في الشفرة، ويتحقق من أصلها، ويطلب الإذن الإداري ويثبت للمستخدم الحالي. لا تتجاهل الرفض. انتظر التجهيز وأكمل معالج الخادم ثم اخرج عادياً وانتظر الاختصارات والمهام وشبكة Windows. الإغلاق المبكر لا يكمل Koha؛ افتحه مجدداً.

**بحاجة إلى تأكيد:** التوفر العام وعنوان Microsoft Store؛ شفرة التغليف ليست دليلاً على النشر. كذلك التشغيل الكامل لـMSIX على ARM64 غير مؤكد: التصريح x64، ودعم Linux arm64 لا يثبت التوافق. يسمح التصريح بـWindows أقدم من مسار WSL الكامل؛ اعتمد المتطلبات الكاملة أعلاه.

## Debian/Ubuntu

من طرفية الخادم:

<div dir="ltr">

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

</div>

للاحتفاظ بالمستودع والترجمات محلياً:

<div dir="ltr">

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

</div>

اختر اللغة و**Install Koha server**. أصلح الفشل الحرج أولاً؛ التحذير ليس ضمان سعة. يلزم WSL 2 مع systemd عامل؛ يرفض WSL 1. ينصح مستخدم Windows بالتجهيز الموجه السابق.

## التثبيت من اللوحة

افتح **Install Koha server** وانتظر الفحص والتقرير، وقيّم أثر تحرير المنافذ. تحقق من الجهاز المستهدف والمنطقة الزمنية أو اختر الإقليم والمدينة. **عند وجود نسخة مثبتة، توقف وتحقق:** تعيد العملية حذف القاعدة والإعداد، وتتطلب تأكيداً إضافياً والكلمة الدقيقة `REINSTALL`. ليست لفتح اللوحة أو تحديثها فقط.

انتظر دون إغلاق، فلا إلغاء. تقدير 10 إلى 30 دقيقة متعلق بالأجهزة والشبكة. اقرأ النتيجة والتقرير؛ الإكمال بمشكلات لا يعني خدمات سليمة. قيّم إعادة التشغيل وانتظر استكمال Windows مع MSIX. لا تنشر البيانات الخاصة من النتيجة في وثائق أو طلبات دعم عامة.

## المصادر التي جرى فحصها

- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [installer](../../../installer).
- [README.md](../../../README.md).
- [install.ps1](../../../windows/install.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [instalar_msix.ps1](../../../windows/msix/instalar_msix.ps1).
- [KohaMsixEntry.cs](../../../windows/msix/KohaMsixEntry.cs).
- [KohaMsixPanel.ps1](../../../windows/KohaMsixPanel.ps1).
- [compilar_msix.ps1](../../../windows/msix/compilar_msix.ps1).
- [install.py](../../../panel/kei_panel/routines/install.py).

</div>
