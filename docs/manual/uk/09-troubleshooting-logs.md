# 9. Діагностика та журнали

[Зміст](README.md)

Запишіть дію/час/повну помилку й робочі частини. Сторінка, служба, вдалий пошук є різними перевірками. Перевстановлення/restore не універсальна перша відповідь.

## Діагностика

Оновіть **Control Dashboard**. **Diagnostics & maintenance center > Detailed server & Koha status**, потім **Full system health check**, читайте звіт. **View latest validation report** знов відкриє, **Export diagnostics** покаже теку підтримки. Навіть після маскування перевірте особисті дані/імена/адреси, не копіюйте все встановлення. Класичний резерв Textual не скасовує попередніх операцій; збережіть повідомлення/журнал.

| Шлях | Вміст |
| --- | --- |
| `/var/log/koha-easy-install/` | Головна Linux |
| `apt.log` | Пакети/етапи |
| `validacao-*.log` | Датовані звіти |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/експорт |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | Індекс/пошук |
| `/var/log/koha-easy-install/tools/` | Інструменти |
| `C:\Koha\logs`, раніше `C:\KohaEasy\logs` | Windows за встановленням |

`*` означає датовані файли, до першого запуску можливі відсутні. Точний показаний шлях кращий. **Library tools > View tool logs** за датою/задачею, доступ обмежено через приватність. Контекст/дата/версія/OK/попередження/помилки читати окремо. **No critical failures** може містити попередження, старий backup не дорівнює збою бази. Після виправлення перевіряйте/порівнюйте.

**Real-time Apache log auditing** обирає staff/OPAC зі старими альтернативними шляхами. Textual **Pause/p** зупиняє показ, не Apache; **Continue** далі, **Back/Esc** закриває. Класичний `Ctrl+C` лише для такого стеження, не всіх задач. Час/контекст `error/fatal/denied/fail`, колір не визначає причину.

## Ознаки

- OPAC/staff недоступні: Apache/MariaDB/Plack/cache та місцева/мережева/VPN/тунельна адреса. `localhost` є комп’ютером браузера. **Restart / repair Koha services (Memcached, Plack)** перериває: читайте результат/перевіряйте.
- Запис не знаходиться: рушій/черга/індекс-база. **Search engine & indexing > Repair / rebuild indexing**, читайте/чекайте; Elasticsearch не обов’язковий перший крок.
- Нема backup: час/підсумок/місце і система при cron, `.part` незавершений. `backup_sql.log`, тест/ручний; останню правильну копію не видаляти без іншої надійної, не накладати задачі.
- Імпорт/кількості: Magic Import/MARC, вхід/підготовка/запис, режим/коди/barcode/відмови/дублікати. Малий перегляд не перевіряє все; повний тест і завершені етапи до повтору.
- Restore: з’ясуйте етап; індекс може впасти після бази, rollback також. Перевірте базу/пошук/валідацію.
- ШІ/збагачення повільно: Ollama/вибір/пам’ять або завдання/сервери/ліміти; великі не дублювати через затримку. Зовнішній збій/місцевий RAM досліджуйте окремо.

## Значок Windows

PowerShell користувача, що ввійшов, **без адміністратора**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Може створювати ярлики/перезапускати tray, не лише читати. `diagnose-<date>.txt` у визначеному `logs`, збережіть шлях/помилку. Не як адміністративне встановлення.

**Deep database optimization & log cleanup** обслуговує/перезапускає, може стерти корисну історію. Збережіть діагностику до обслуговування, не приховуйте помилку. Для допомоги: версія, Windows/WSL/дистрибутив, дія/час/повне повідомлення, OPAC/staff/пошук, попередня операція та перевірені на приватність уривки.

**Потребує підтвердження:** причина без повного повідомлення/журналу; не автоматично мережа/встановлення.

## Перевірені джерела

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
