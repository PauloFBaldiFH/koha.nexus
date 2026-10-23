# 9. সমস্যা সমাধান ও লগ

[সূচিপত্র](README.md)

## আগে প্রমাণ রাখুন

কাজ, সময়, পুরো ত্রুটি ও কোন অংশ চলছে লিখুন। পৃষ্ঠা খোলা, সার্ভিস চলা ও অনুসন্ধান সফল আলাদা পরীক্ষা। প্রতিটি সমস্যায় প্রথমে পুনরায় ইনস্টল বা restore নয়। **Control Dashboard** তাজা করুন, **Diagnostics & maintenance center**-এ **Detailed server & Koha status**, **Full system health check**, **View latest validation report** পড়ুন। **Export diagnostics**-এর পথ রাখুন। কিছু গোপন তথ্য ঢাকলেও পাঠক, ফাইল ও অবকাঠামোর ঠিকানা শেয়ারের আগে যাচাই করুন। পুরো ইনস্টল প্রকাশ করবেন না। পুরোনো প্যানেলে ফেরা আগের কাজ ফেরায় না।

## লগের অবস্থান

Linux-এ `/var/log/koha-easy-install/`-এর মধ্যে `apt.log`, `validacao-*.log`, `new-panel.log`, `backup_sql.log`, `backup_marc.log`, `restore.log`, `restore-import.log`, `zebra-rebuild.log`, `search-engine.log` থাকে। সরঞ্জামের জন্য `/var/log/koha-easy-install/tools/`। Windows সাধারণত `C:\Koha\logs`, পুরোনো `C:\KohaEasy\logs`।

`*` পরিবর্তিত তারিখের অংশ, ওই নামে ফাইল বানাবেন না। প্রথমবার কাজের আগে লগ না-ও থাকতে পারে। ত্রুটিতে দেওয়া ঠিক পথ ধরুন। **View tool logs**-এ তারিখ ও কাজ বাছুন; ব্যক্তিগত তথ্য থাকতে পারে। প্রতিবেদন থেকে সংস্করণ, সময়, প্রতিটি OK/সতর্কতা/ব্যর্থতা পড়ুন। **No critical failures**-এর সঙ্গেও সতর্কতা থাকতে পারে। ঠিক করে আবার যাচাই ও তুলনা করুন।

**Real-time Apache log auditing**-এ staff/OPAC নিন। Textual-এর **Pause** বা p শুধু প্রদর্শন থামায়, Apache নয়। **Continue** আবার চালায়, **Back**/Esc বের করে। পুরোনো পর্দায় Ctrl+C এই অনুসরণ থেকে বেরোনোর জন্য, সব কাজে নয়। error/fatal/denied/fail দেখলে সময় ও আশপাশ পড়ুন; রং একা কারণ নয়।

## লক্ষণভেদে পরীক্ষা

খুলছে না: Apache, MariaDB, Plack, cache এবং স্থানীয়/LAN/VPN/tunnel ঠিকানা দেখুন। localhost ব্রাউজারের যন্ত্র। **Restart / repair Koha services (Memcached, Plack)** সাময়িক বাধা দিতে পারে; শেষে আবার যাচাই করুন।

রেকর্ড খুঁজে না পেলে engine, queue, সূচি/ডেটাবেস দেখুন। **Search engine & indexing > Repair / rebuild indexing**-এর প্রশ্ন পড়ে শেষ পর্যন্ত অপেক্ষা করুন। শুরুতেই Elasticsearch বদলানো বাধ্যতামূলক নয়।

backup না হলে সময়, ফল, স্থান, cron ও Linux চলা দেখুন। `.part` অসম্পূর্ণ। একই কাজ একসঙ্গে চালাবেন না, অন্য নিরাপদ কপি ছাড়া শেষ সঠিক backup মুছবেন না। আমদানিতে উৎস/প্রস্তুতি/লেখা সংখ্যা, মোড, কোড, বারকোড, প্রত্যাখ্যান ও সদৃশনীতি দেখুন। ছোট পূর্বদৃশ্য পুরো ফাইলের নিশ্চয়তা নয়; আবার চালানোর আগে আংশিক লেখা দেখুন।

restore-এ সূচির ত্রুটি ডেটাবেস বদলের পরে হতে পারে, rollback-ও ব্যর্থ হয়। ডেটাবেস, অনুসন্ধান ও পরীক্ষা ছাড়া সম্পূর্ণ ফেরার দাবি নয়। স্থানীয় AI-এর RAM আর বাইরের সার্ভারের সীমা আলাদা; ধীর হলেই বড় কাজ পুনরায় দেবেন না।

## Windows ও সহায়তা

প্রবেশ করা ব্যবহারকারীর সাধারণ, প্রশাসক নয় এমন PowerShell-এ:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

এটি শুধু পড়ে না; শর্টকাট তৈরি ও tray আবার চালু করতে পারে। শনাক্ত ইনস্টলের `logs`-এ `diagnose-<date>.txt`, দেখানো পথ ও ত্রুটি রাখুন। **Deep database optimization & log cleanup** উপকারী ইতিহাস মুছতে পারে; আগে প্রমাণ রাখুন, রক্ষণাবেক্ষণের সময় নিন, ত্রুটি চাপা দিতে চালাবেন না।

সাহায্য চাইলে সংস্করণ, OS/WSL, কাজ, সময়, পূর্ণ বার্তা, OPAC/staff/অনুসন্ধানের অবস্থা এবং ঠিক আগের আমদানি/restore/আপডেট দিন। ব্যক্তিগত তথ্য বাদ দিন। পূর্ণ লগ ছাড়া নির্দিষ্ট কারণ নিশ্চিত করা প্রয়োজন থেকে যায়।

## যাচাই করা উৎস

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
