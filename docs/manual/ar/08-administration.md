<div dir="rtl" lang="ar">

# 8. الإدارة والرسائل وVPN

[المحتويات](README.md)

تحقق من الحالة وbackup حديث قبل الإدارة؛ الإعداد لا يثبت العمل عبر الشبكة، اختبر بعده.

## Cron وVPN

**Schedules & cron tasks** أو `s`: تفعيل وتكرار ووقت ويوم أو تعبير. **Reload** ثم المهام اللازمة و`HH:MM` و**Preview** و**Save** والموافقة ثم أعد القراءة. `/etc/cron.d/koha_tasks` والسابق `koha_tasks.bak`؛ المعطل تعليق مع وقته والأسطر الخاصة محفوظة. **Defaults** يملأ ويحتاج حفظاً. SQL يومي 23:00 وMARC الأحد 03:00، راجع المنطقة والتخصيص. يلزم الخادم وLinux يعملان؛ cron لا يضمن تشغيل Windows، وإشعارات Koha منفصلة.

**Security & access hub > WireGuard VPN** أو `v`: اسم/عنوان عام وUDP. **Set up the VPN** يظهر التغيير؛ يوجه الموجه UDP للخادم. اسم و**Add device** و**QR code & profile** ثم تحقق الاتصال وstaff والمرور. لا تنشر الملف أو QR. **Revoke** يلزم ملفاً جديداً، **Turn off** يفصل ويحفظ. نفق مقسم فقط `10.66.0.0/24` والإنترنت وDNS للجهاز، staff `http://10.66.0.1:8080`. WSL دون mirrored غير متاح مباشرة، VPN معطل.

## الرسائل

**Messaging & interoperability** أو `m`: **E-mail** و**WhatsApp & Telegram** و**SMS** و**Alerts** و**SIP2** و**Z39.50**. فعل البريد وافحص SMTP؛ أزرار SMTP وعنوان المكتبة والإشعارات والإيصالات والتأخر. لا تملأ جميع القواعد والمستلمين والقوالب؛ تحقق من التفضيلات وإعداد المزود الخاص.

**Set up WhatsApp and Telegram** خدمة وبلد ورمز واختبار وتفعيل وهواتف. يحتاج WhatsApp بوابة وTelegram بوتاً ومستلمين. اختبار مأذون قبل الإنتاج وقوالب وصيغ قبل تصحيح جماعي. SMS عبر `SMSSendDriver` والتفضيلات يحتاج خدمة وسائقاً متوافقين، لا الاسم فقط.

**Alerts** مواعيد وتأخر وتكرار وملخص يومي وقنوات، حفظ و**Dry run (sends nothing)**. يفعل المهمة: افحص cron وتجنب تكرار Koha. SIP2 منفذ وشبكة ومكتبة وحقوق جهاز؛ أزل الأمثلة وأنشئ حساب Koha بالزر، ويجب التطابق. لا تفتح كل الشبكات لاختبار محلي. Z39.50 في الفصل 5، الوارد والصادر مختلفان.

## الإدارة

Hub يجمع Cloudflare Tunnel/UFW/staff-8080/HTTPS/Fail2ban، اقرأ الحالة والملخص وميز VPN والنفق والمباشر. لا تغير firewall بعيداً دون سبيل إدارة باق. **بحاجة إلى تأكيد:** النطاق والموجه والمزود والمؤسسة؛ الشفرة ليست وصفة نشر شاملة.

**Koha settings & parameters** ذاكرة وworkers وأمين شامل ومنطقة زمنية؛ قيد الحقوق الواسعة. **Koha languages** ينزل ويفعل أو ينزل فقط أو يفعل المثبت ويسرد؛ تحقق من اللوحة وOPAC/staff. **Update center** يفرق النظام والمخطط عن GitHub-panel؛ backup وصيانة وقد تنتهي الجلسة. إعادة التشغيل لا تثبت إصلاح ترحيل المخطط.

**Library tools** روابط ومزامنة استناد وتكرار مؤلفين وSQL وفئات وجودة وخصوصية. فئتا المصدر والهدف مختلفتان، مرشح ومكتبة ومحاكاة قبل الموافقة المحمية. الجودة تقرأ ولا تصلح الكل. إخفاء الهوية يزيل روابط قديمة للتاريخ والقراء وفق Koha لا كل الببليوغرافيا. حذف القراء مرشحات ومحاكاة وعدد، مدمر، راجع الاحتفاظ. تشابه الاسم لا يثبت الشخص، والبطاقات المخفية ليست أدوات متاحة.

## المصادر التي جرى فحصها

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).

</div>
