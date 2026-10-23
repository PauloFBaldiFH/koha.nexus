<div dir="rtl" lang="fa">

# 1. نصب

[فهرست](README.md)

## پیش‌نیازها

برای نصب کامل در Windows به Windows 10 نسخهٔ 2004 با build برابر 19041 یا بالاتر، یا Windows 11، سیستم 64 بیتی و مجازی‌سازی فعال نیاز دارید. WSL 2 باید از systemd پشتیبانی کند؛ WSL 1 مناسب نیست. حداقل RAM برای رایانهٔ رومیزی یا WSL برابر 8 GB و مقدار پیشنهادی 12 GB است. بررسی برنامه برای جبران حافظهٔ رزروشده آستانه‌های 7,5 و 11,5 GB را به کار می‌برد. حداقل فضای آزاد Windows برابر 10 GB و مقدار پیشنهادی 20 GB است. فضای مجموعه، نمایه‌ها و backupهای آینده نیز باید جداگانه پیش‌بینی شود.

نصب Linux از Debian 11، 12 و 13 و Ubuntu 22.04 و 24.04، روی amd64 و arm64 پشتیبانی می‌کند. فضای کمتر از 5 GB مانع ادامه می‌شود؛ بین 5 و 10 GB هشدار داده می‌شود. برای سرور اختصاصی 4 GB RAM حداقل و 8 GB پیشنهاد شده است؛ برای دسکتاپ 8 و 12 GB. اعمال حداقل RAM در مسیر Linux به صورت شرط عددی قطعی، نیازمند تأیید است. پشتیبانی arm64 در Linux به معنی پشتیبانی MSIX روی ARM64 نیست؛ manifest فعلی بسته x64 است.

## نصب با PowerShell

PowerShell را با دسترسی مدیر، ولی با همان حساب Windows که قرار است از Koha استفاده کند، باز کنید. دستور پروژه را تنها پس از بررسی نشانی و اعتماد به منبع اجرا کنید:

<div dir="ltr">

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

</div>

حساب Debian با حساب Windows متفاوت است. اطلاعات درخواستی را در همان محیط وارد کنید و خروجی حاوی اطلاعات خصوصی را منتشر نکنید. پس از راه‌اندازی مجدد، با همان کاربر وارد شوید تا روند ادامه یابد. مسیر فعلی ممکن است C:\Koha و مسیر نصب‌های قدیمی C:\KohaEasy باشد؛ پوشه را دستی جابه‌جا نکنید.

## بستهٔ MSIX

دستور زیر را در PowerShell معمولی اجرا کنید. ابزار در مرحلهٔ لازم درخواست دسترسی مدیر می‌کند:

<div dir="ltr">

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

</div>

بازشدن نخستین پنل به معنی پایان نصب نیست. مراحل داخل آن را تمام کنید و برای نهایی‌شدن از آن خارج شوید. اگر زود بسته شد، دوباره برنامه را باز کنید. دسترسی عمومی و نشانی Microsoft Store و پشتیبانی ARM64 بسته نیازمند تأیید هستند. حداقل نسخهٔ درج‌شده در manifest جایگزین پیش‌نیازهای نصب کامل WSL نمی‌شود.

## نصب Debian یا Ubuntu

روی ماشین مقصد، یکی از این دو روش را انتخاب کنید:

<div dir="ltr">

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

</div>

یا:

<div dir="ltr">

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

</div>

نصب پورت‌های 80 و 8080 را بررسی می‌کند. توقف سرویس دیگری را تنها اگر نقش آن را می‌شناسید تأیید کنید. منطقهٔ زمانی درست را انتخاب کنید. نصب ممکن است 10 تا 30 دقیقه یا بیشتر طول بکشد؛ آن را قطع نکنید. هشدار پایانی را کامل بخوانید، زیرا پایان برنامه سلامت همهٔ سرویس‌ها را تضمین نمی‌کند.

گزینهٔ نصب دوباره می‌تواند داده‌های موجود را حذف کند و تأیید REINSTALL می‌خواهد. پیش از آن backup قابل‌بازیابی را بیرون از ماشین نگه دارید. نصب دوباره راه عمومی رفع هر خطا نیست.

## منابع بررسی‌شده

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
