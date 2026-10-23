# 1. 安装

[目录](README.md)

## 选择运行环境

Windows 通过 WSL 2 中的 Debian 运行 Koha；Windows 工具负责准备环境、启动面板和系统集成。Debian 或 Ubuntu 则直接安装服务。已有馆藏应打开面板，而不是重新安装。

Windows 需要 64 位 Windows 10 2004（build 19041）或更新版本，或 Windows 11，并在 BIOS/UEFI 开启虚拟化。内存至少 8 GB，建议 12 GB；安装盘至少空闲 10 GB，建议 20 GB。由于硬件预留内存，检查采用 7.5 GB 和 11.5 GB 阈值。馆藏、附件、索引及 backup 还会占用额外空间。

Linux 安装器识别 Debian 11、12、13 和 Ubuntu 22.04、24.04，架构为 amd64、arm64。空闲空间低于 5 GB 会阻止安装，5 GB 至不足 10 GB 会警告。专用服务器建议最低 4 GB 内存、推荐 8 GB，桌面或虚拟环境建议 8/12 GB；目前 Linux 预检没有强制执行这一数值下限，正式内存要求仍待确认。通过预检并不保证容量充足。

WSL 必须为支持 systemd 的 WSL 2；该流程拒绝 WSL 1。Linux 需要管理员权限、仓库网络访问以及端口 80、8080。只有确认可以中断占用端口的服务时，才允许安装器停止它们。

## Windows：PowerShell

使用将来运行 Koha 的 Windows 管理员账户登录，在同一账户下以管理员身份打开 PowerShell。若提权要求使用另一个人的账户，应取消并改用合适的管理员账户。确认信任脚本来源后执行：

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

阅读预检结果，解决虚拟化等错误。在安装窗口回答 Debian 账户问题；该账户与 Koha 图书馆账户不同。需要重启时，流程会登记下次登录后的继续操作。重新登录同一 Windows 用户并等待面板打开，选择语言和 **Install Koha server**。

安装后正常退出面板，再等候 Windows 集成完成。默认路径为 `C:\Koha`，旧安装可能仍在 `C:\KohaEasy`；不要手动移动目录。中断后重新运行安装器可以根据已完成阶段继续，但不能据此忽略重新安装的数据删除警告。

## Windows：MSIX

在普通、非管理员 PowerShell 中运行现有安装辅助工具：

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

辅助工具检查来源并在必要时申请管理员授权；遇到拒绝应阅读错误。包安装成功不表示 Koha 服务已经配置完成。首次启动后完成面板中的安装，正常退出并等待快捷方式、后台任务及网络配置结束。若提前关闭，应重新打开应用继续。

Microsoft Store 的公开可用性和链接待确认。当前生成的 manifest 为 x64，不能从 Linux 支持 arm64 推断 MSIX 支持 ARM64。manifest 的较低 Windows 最低版本也不能代替完整 WSL 安装要求。

## Debian 或 Ubuntu

在目标服务器终端执行：

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

如需同时保留仓库与翻译，可改用：

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

选择语言并打开 **Install Koha server**。阅读检查报告，先解决关键错误，再确认目标机器和时区。检测到现有实例时，重新安装会删除数据库及配置，并要求输入精确的 `REINSTALL`；继续前必须保留服务器外可恢复的 backup。

安装预计 10 至 30 分钟，实际取决于硬件和网络。该阶段不可在面板中取消，不要强行关窗。结束时阅读完整报告；带问题完成不等于所有服务正常。不要把结果中的私人信息复制到公开求助材料。

## 已核对的源码

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
