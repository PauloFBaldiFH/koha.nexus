# 9. 故障排查与日志

[目录](README.md)

## 先收集证据

记录操作、时间、完整错误和仍正常的部分。网页可开、服务运行、搜索成功是不同检查。不要每次先重新安装或 restore。刷新 **Control Dashboard**，在 **Diagnostics & maintenance center** 看 **Detailed server & Koha status**、**Full system health check** 和 **View latest validation report**。需要时 **Export diagnostics** 并记住路径。

导出虽会隐藏部分秘密，仍须检查读者资料、文件名和基础设施地址再分享。不要复制整安装目录。Textual 回退经典界面不等于前一操作撤销。

## 日志位置与读取

Linux 根目录为 `/var/log/koha-easy-install/`，其中 `apt.log` 是包安装，`validacao-*.log` 是按日期验证，`new-panel.log` 是面板错误，`backup_sql.log`/`backup_marc.log` 是副本结果，`restore.log`/`restore-import.log` 是恢复，`zebra-rebuild.log`/`search-engine.log` 是搜索。工具在 `/var/log/koha-easy-install/tools/`。Windows 当前通常为 `C:\Koha\logs`，旧版为 `C:\KohaEasy\logs`。

星号不是要创建的字面文件名，首次运行前日志可能不存在。优先用错误给出的精确路径。**Library tools > View tool logs** 按日期和任务选择；日志可能含个人数据。验证报告要逐条读 OK、警告、失败，不只读总数。**No critical failures** 仍可能有警告。修复后再验证比较。

**Real-time Apache log auditing** 可选 OPAC/staff。Textual 的 **Pause** 或 p 只暂停显示，不停止 Apache；**Continue** 恢复，**Back**/Esc 退出。经典模式 Ctrl+C 只用于退出这种日志跟踪，不能推广到所有任务。高亮 `error`、`fatal`、`denied`、`fail` 并不单独证明原因，要结合时间和上下文。

## 按症状排查

打不开网页时检查 Apache、MariaDB、Plack、缓存及本机/网络/VPN/隧道地址。localhost 属于浏览器所在机器。**Restart / repair Koha services (Memcached, Plack)** 可能短暂中断，结束后仍要验证。

记录存在却搜不到，检查搜索引擎、队列、索引与数据库；**Search engine & indexing > Repair / rebuild indexing** 需读问题、确认并等待。无需一开始就切换 Elasticsearch。

backup 缺失先核对时间、空间、cron 和 Linux 是否运行；`.part` 不是完成。不要并行重复，也不要未保留另一份就删除最后有效副本。导入数量异常要比对输入、准备与实际写入，检查模式、代码、条码、拒绝和重复政策。小预览不代替全文件验证，重试前查是否已部分写入。

restore 看失败阶段；索引失败可能发生在数据库替换后，rollback 也可能失败，必须查数据库、搜索和验证。AI 慢查本地内存与选择，补充慢查任务和外部限制，不要因等待就重复大任务。

## Windows 与求助

登录用户的普通、非管理员 PowerShell 可运行：

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

此工具并非只读，可重建快捷方式并重启托盘；结果为安装 `logs` 中的 `diagnose-<date>.txt`。保留实际路径和错误。深度优化及日志清理可能删除有用历史，先保存诊断并安排维护，不用清理掩盖问题。

求助提供版本、Windows/WSL 或发行版、操作、时间、完整消息、OPAC/staff/搜索状态及之前的导入、restore、更新。先去掉私人数据。具体故障原因在缺完整日志时仍待确认，不应直接归因网络或安装。

## 已核对的源码

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
