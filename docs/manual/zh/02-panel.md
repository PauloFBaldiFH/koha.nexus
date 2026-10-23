# 2. 入门与控制面板

[目录](README.md)

## 启动与导航

已配置好的 Debian 或 Ubuntu 使用：

```bash
sudo config.sh
```

Windows 使用安装器建立的 **Koha** 图标，或打开 MSIX 应用。首次可能先选择语言。Textual 准备失败时可能提供经典面板；不要用旧菜单编号寻找当前卡片。

用方向键选中侧栏栏目，按 Enter 或点击打开。仅移动选中位置不会执行任务。在内容区打开卡片并阅读问题。Tab 切换控件焦点；输入文字时先退出输入框，再尝试字母快捷键。

| 按键 | 主屏操作 |
| --- | --- |
| d | 打开 Control Dashboard |
| b | 打开 Backup center |
| c | 打开 Debian 终端 |
| Ctrl+B | 显示或隐藏侧栏 |
| q | 退出面板 |

退出空闲面板不会关闭服务器。任务进行中应按该页规则取消；安装和 restore 有不可取消阶段，强行关闭窗口可能导致操作不完整。

## 阅读仪表板

**Control Dashboard** 显示 Koha 状态、可用内存、空闲磁盘、最近 backup 的日期和文件，以及本机、局域网和已配置的互联网地址。MariaDB、Apache、RabbitMQ、Memcached、Koha 和 HTTP 检查帮助定位问题，但不能代替实际业务测试。

最近文件的时间、大小与上次夜间任务结果可能来自不同运行。文件很新仍可能伴随夜间任务失败。HTTP 有响应也不证明 Koha 网页安装已完成。**Refresh** 重新读取；**Restart Koha** 请求修复或重启服务，可能短暂影响读者；**Export diagnostics** 导出诊断。旧安装器不支持的按钮可能不可用。

## 访问与首次检查

使用地址卡片打开或复制 URL。服务器本机默认 OPAC 为 `http://localhost/`，staff 为 `http://localhost:8080/`。另一台电脑的 localhost 指向那台电脑，不是服务器。应使用面板给出的网络地址；若 WSL 使用 NAT 且报告局域网不可达，先检查 Windows 网络准备结果。

staff 如显示网页安装器，应先完成；不同 Koha 版本的步骤可能不同。随后可在 **Koha settings & parameters** 中使用 **Create super librarian**，只在本机填写私人信息，并限制高权限账户的使用。

正式工作前刷新状态、打开 OPAC 与 staff、试查记录，并生成和测试 backup。确认服务器外副本的位置和负责恢复的人。面板可以提供复制流程，但外部副本是否可用取决于传输和核验确实完成。

## 已核对的源码

- [installer](../../../installer).
- [app.py](../../../panel/kei_panel/app.py).
- [KohaEasy.Install.psm1](../../../windows/KohaEasy.Install.psm1).
- [main.py](../../../panel/kei_panel/screens/main.py).
- [install.py](../../../panel/kei_panel/routines/install.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [dashboard.py](../../../panel/kei_panel/views/dashboard.py).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
- [menus.py](../../../panel/kei_panel/menus.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
