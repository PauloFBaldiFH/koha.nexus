# Koha.Nexus 用户手册

本手册共九章，介绍 Koha.Nexus 安装器和控制面板，不代替 Koha 的完整编目及流通手册。依据葡萄牙语和英语资料手工编写，并与 2a78bfa 的源码核对。阅读源码不等于实际安装测试。操作名保留英语以对应代码，面板可能显示译文。命令和路径不翻译；替换或删除数据前须阅读确认，不依赖旧菜单编号。

## 目录

1. [安装](01-installation.md).
2. [入门与控制面板](02-panel.md).
3. [Backup 与 restore](03-backup-restore.md).
4. [智能导入](04-magic-import.md).
5. [记录补充与 Z39.50/SRU](05-enrichment.md).
6. [OPAC 与 staff 外观](06-appearance.md).
7. [本地 AI](07-local-ai.md).
8. [管理、消息与 VPN](08-administration.md).
9. [故障排查与日志](09-troubleshooting-logs.md).

[English](../en/README.md) · [Português brasileiro](../pt-BR/README.md) · [हिन्दी](../hi/README.md) · [বাংলা](../bn/README.md) · [Tiếng Việt](../vi/README.md) · [中文（简体）](../zh/README.md) · [日本語](../ja/README.md)

## 待确认事项

- Microsoft Store 的公开可用性及 URL。
- Linux 官方最低 RAM；目前预检没有数值强制条件。
- ARM64 上完整 MSIX 功能；manifest 为 x64。
- 没有样本与结果审查的私有导出布局及版本。
- 本馆网络访问外部来源的可用性与条件。
- 各硬件及选择所需 AI 内存、磁盘与响应时间。
- 发布所需域名、网络与机构政策。
- 缺完整消息及日志时，具体故障的原因。
