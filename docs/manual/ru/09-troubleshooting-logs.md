# 9. Диагностика и журналы

[Содержание](README.md)

Запишите действие/время/полную ошибку и рабочие части. Страница, служба и успешный поиск разные проверки. Переустановка/restore не универсальный первый ответ.

## Диагностика

Обновите **Control Dashboard**. **Diagnostics & maintenance center > Detailed server & Koha status**, затем **Full system health check**, читайте отчёт. **View latest validation report** повторно открывает, **Export diagnostics** показывает папку поддержки. Даже после маскирования проверьте личные данные/имена/адреса, не копируйте всю установку. Классический резерв Textual не отменяет предыдущие операции; сохраните ошибку/журнал.

| Путь | Содержание |
| --- | --- |
| `/var/log/koha-easy-install/` | Главная Linux |
| `apt.log` | Пакеты/этапы |
| `validacao-*.log` | Датированные отчёты |
| `new-panel.log` | Textual/traceback |
| `backup_sql.log`, `backup_marc.log` | Backup/экспорт |
| `restore.log`, `restore-import.log` | Restore/SQL |
| `zebra-rebuild.log`, `search-engine.log` | Индекс/поиск |
| `/var/log/koha-easy-install/tools/` | Инструменты |
| `C:\Koha\logs`, раньше `C:\KohaEasy\logs` | Windows по установке |

`*` означает файлы с датой, до первого запуска возможен их пропуск. Точный показанный путь предпочтителен. **Library tools > View tool logs** по дате/задаче, доступ ограничен личными данными. Контекст/дата/версия/OK/предупреждения/ошибки читать по одному. **No critical failures** может содержать предупреждения; старый backup не равен сбою базы. После ремонта проверять/сравнивать.

**Real-time Apache log auditing** выбирает staff/OPAC со старыми альтернативами. Textual **Pause/p** останавливает показ, не Apache; **Continue** дальше, **Back/Esc** закрывает. Классический `Ctrl+C` только для такого наблюдения, не любой задачи. Время/контекст `error/fatal/denied/fail`; цвет не устанавливает причину.

## Симптомы

- OPAC/staff недоступны: Apache/MariaDB/Plack/cache и локальный/сетевой/VPN/туннельный адрес. `localhost` компьютер браузера. **Restart / repair Koha services (Memcached, Plack)** прерывает, читайте итог/проверяйте снова.
- Запись не находится: движок/очередь/индекс-база. **Search engine & indexing > Repair / rebuild indexing**, читайте/ждите; Elasticsearch не обязательный первый шаг.
- Нет backup: время/итог/место и система при cron, `.part` незавершённый. `backup_sql.log`, тест/ручной; последнюю верную копию не удалять без другой надёжной, не пересекать задачи.
- Импорт/числа: Magic Import/MARC, вход/подготовка/запись, режим/коды/barcode/отказы/дубли. Малый просмотр не проверяет всё; полный тест и завершённые этапы перед повтором.
- Restore: выяснить этап; индекс может упасть после базы, rollback тоже. Проверить базу/поиск/валидацию.
- ИИ/обогащение медленно: Ollama/выбор/память либо задача/серверы/лимиты; большие задачи не дублировать ради задержки. Внешний сбой/местный RAM исследуются различно.

## Значок Windows

PowerShell вошедшего пользователя, **без администратора**:

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

Может создавать ярлыки/перезапускать tray, не только читать. `diagnose-<date>.txt` в найденном `logs`, сохраните путь/ошибку. Не как административная установка.

**Deep database optimization & log cleanup** обслуживает/перезапускает, может стереть полезную историю. Диагностику сохранить до обслуживания, не скрывать ошибки. Для помощи: версия, Windows/WSL/дистрибутив, действие/время/полная ошибка, OPAC/staff/поиск, предыдущая операция и проверенные на приватность выдержки.

**Требует подтверждения:** причина без полного сообщения/журнала; не автоматически сеть/установка.

## Проверенные источники

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
