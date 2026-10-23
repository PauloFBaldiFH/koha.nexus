# 8. 管理、消息与 VPN

[目录](README.md)

## 时间与设置

管理前检查状态和近期 backup。按 s 打开 **Schedules & cron tasks**。**Reload** 读取，设启用、频率、`HH:MM` 和需要的星期或表达式，**Preview** 预览文件，**Save** 确认保存，再重读检查。**Defaults** 只填默认值，仍需保存。

文件为 `/etc/cron.d/koha_tasks`，旧版保留为 `koha_tasks.bak`。禁用任务保留为注释及原时间，自定义行也保留。默认 SQL 每日 23:00、MARC 周日 03:00，采用服务器时区。机器与 Linux 须运行，cron 不保证开机唤醒 Windows。Koha 自己的通知机制与这里附加任务不同。

**Koha settings & parameters** 调整内存、worker、时区和高权限账户。仅给需要者管理权限。**Koha languages** 区分下载、激活和列出，下载不必然激活。**Update center** 区分系统/Koha 结构更新与 GitHub 面板更新；先 backup，安排停机。面板可能结束会话，结构失败不能靠假定重启解决。

## VPN 与安全

在 **Security & access hub > WireGuard VPN** 或 v 填公网地址及 UDP 端口，**Set up the VPN** 后阅读网络变化。路由器须转发该 UDP 到服务器。为每台设备 **Add device**，用 **QR code & profile** 配客户端，再测试 staff 和流量。

配置与 QR 私密不可公开。**Revoke** 使旧配置失效，重新接入需新配置；**Turn off** 断开并保留配置。分流只把 `10.66.0.0/24` 送入 VPN，设备互联网及 DNS 仍走自身连接；staff 为 `http://10.66.0.1:8080`。WSL 无 mirrored 网络时不可直接达，当前代码禁用此 VPN。

中心还有 Cloudflare Tunnel、UFW、8080 限制、HTTPS、Fail2ban。直连、隧道、VPN 的范围不同。远程更改规则前确认仍能管理服务器。域名、路由器、运营商及机构发布要求待确认，没有通用的公开访问方案。

## 消息与互操作

按 m 打开 **Messaging & interoperability**，六个标签为 **E-mail**、**WhatsApp & Telegram**、**SMS**、**Alerts**、**SIP2**、**Z39.50**。启用邮件后还要核对 SMTP、馆地址、通知模板、读者偏好和逾期规则；不能以开关成功替代全部配置。

**Set up WhatsApp and Telegram** 涉及服务、国家/区号、测试和号码检查。WhatsApp 依赖网关，Telegram 依赖 bot 与收件人配置。先向授权对象测试，再启用正式发送；批量改号码前看预览。SMS 需兼容驱动与服务，单填 `SMSSendDriver` 不保证可发送。

**Alerts** 设置到期、逾期、重复间隔、每日摘要和渠道；**Dry run (sends nothing)** 模拟不发送。启用后核对 cron，避免与 Koha 原有通知重复。SIP2 核对端口、网络、馆、设备权限，去掉示例并创建对应 Koha 账户，不能为本地测试开放所有网络。Z39.50 入站与出站查询须分清。

## 馆务工具

**Library tools** 提供规范链接、重复作者、SQL 报表、类别、质量和隐私操作。改类别先选不同的来源/目标及馆，读模拟结果并 backup。质量检查只读，不自动修复全部异常。历史匿名化移除旧记录与读者的链接，不清空所有书目历史。删除旧读者需筛选、模拟及输入数量确认，有破坏性，须符合保留政策。名字相似不能证明同一人；隐藏卡片不当作已提供功能。

## 已核对的源码

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
