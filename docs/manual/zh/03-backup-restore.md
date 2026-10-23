# 3. Backup 与 restore

[目录](README.md)

## 统一入口与副本类型

主屏按 b 打开 **Backup center**。**Download latest backup** 下载已存在的最新文件；**Generate manual backup and download to PC** 立即生成数据库副本；**Export MARC21 records now** 导出书目和规范记录；**Restore database** 替换数据库；**Configure cloud backup** 设置外部上传；**Test integrity of latest backup** 在临时数据库测试文件。

restore 是中心内的卡片，不是顶栏按钮或单独的主菜单。夜间结果与最新文件指标可能指向不同运行，必须分别阅读。

SQL backup 包含 Koha 数据库，不是 Windows、Debian 或整机镜像。MARC `.tar.gz` 包含书目和规范记录，不能恢复完整读者与流通数据。自动 SQL 和安全副本默认在 `/var/backups/koha_sql`，MARC 在 `/var/backups/koha_marc`。手动保存有独立目录，默认是面板识别的主目录下 `backups`，不要假定与自动副本同处。

大文件先写 `.part`，检查后才成为最终文件；不要把 `.part` 当完整 backup。**Compression** 选择 gz、zst、xz 后自动保存，只影响新文件，不重新压缩旧文件。所需工具无法安装时会提示并回退到 gzip。restore 可读取支持的 `.sql`、`.sql.gz`、`.sql.zst`、`.sql.xz`，不受当前压缩选项限制；扩展名本身不是有效性证明。

## 创建、传输、测试

打开手动生成卡片，检查服务器目录，按 **Save backup**，等待生成与核验结束。记录文件名、大小、路径。WSL 可用 **Save to Windows Downloads** 或 **Choose folder in Windows**；远程连接则将面板生成的传输命令放到自己的电脑执行。确认文件到达后使用 **Finish and exit**。保存或复制期间不能关窗。共享锁提示其他任务进行时应等待，不要绕过锁并行运行。

下载最新文件不会生成新副本。需要操作前的当前副本时，应手动生成。完整性测试可选 **Choose another file**，导入临时数据库并检查表、书目和读者数量，不替换生产数据库。成功只适用于测试过的那个文件及环境，仍须核验外部传输。

MARC 导出期间 Koha 可继续运行；核对归档内容、路径及云端上传结果。它适合记录交换，而完整数据库恢复仍需 SQL。

## 云端与时间

云端流程提供两种 Google Drive 快速路线，以及 OneDrive、MEGA、S3。根据在服务器还是另一台电脑授权选择路线；只遵循当前安装显示的地址。S3 要核对服务、region、endpoint、bucket。必须阅读真实上传测试结果，并确认目标确实存在副本。私人授权信息不能写入公开报告。

默认 SQL 每日 23:00、MARC 每周日 03:00，均为服务器时间；已有 cron 配置可能不同。机器和 Linux 必须在运行。

## 替换数据库的风险

**Restore database 会替换当前数据库。** 事先安排维护窗口并在服务器外保留副本，这是操作建议，不是面板自动执行的额外复制。选择正确文件，按提示传到服务器；WSL 可能先把 Windows 文件复制到 Linux。检查可读性、内容、完整性和空间，对可疑文件先调查。最终确认前可退出，确认后不可取消。

流程先导入临时库并检查必要表与数量。当前数据库有表时，会生成并验证 `pre_restore_safety_backup_` 开头的副本；失败应在替换前停止，空库可能跳过。随后停止数据库客户端，重建并导入数据库、升级结构、同步搜索、重建索引、重启服务，并尝试恢复已保存的外观。

临时测试或安全副本失败不同于替换后的失败。重建、导入或结构升级失败时可能尝试 rollback，但 rollback 也会失败，不能保证自动恢复。索引报错时数据库可能已替换，不能据此声称旧数据已回来。

阅读 `/var/log/koha-easy-install/restore.log`、`/var/log/koha-easy-install/restore-import.log` 和 `/var/log/koha-easy-install/zebra-rebuild.log`。完成后检查 staff、OPAC、记录和搜索；数据库成功并不代表 SQL 之外的文件已恢复。状态不确定时先求助，不要盲目重复。

## 已核对的源码

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
