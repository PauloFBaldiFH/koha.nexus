# 1. インストール

[目次](README.md)

## 環境を決める

Windows では WSL 2 の Debian 内で Koha を動かします。Windows 側のツールが準備、パネル起動、ショートカットなどを担当します。Debian と Ubuntu ではサーバーへ直接インストールします。既存の蔵書を使うために再インストールする必要はありません。

Windows の条件は 64 ビットの Windows 10 バージョン 2004、build 19041 以降、または Windows 11 と、有効な仮想化です。RAM は最低 8 GB、推奨 12 GB、空き容量は最低 10 GB、推奨 20 GB です。ハードウェア予約分を考慮し、判定値は 7.5 GB と 11.5 GB です。蔵書、添付ファイル、索引、backup の増加分も確保してください。

Linux は Debian 11・12・13、Ubuntu 22.04・24.04 の amd64 と arm64 を識別します。空き容量 5 GB 未満は停止、5 GB 以上 10 GB 未満は警告です。専用サーバーは最低 4 GB、推奨 8 GB、デスクトップや仮想環境は 8/12 GB という既存ガイドの目安がありますが、Linux の事前確認はその RAM 最低値を数値で強制していません。正式な必要量は要確認です。

WSL 1 はこの手順では使えません。systemd が動く WSL 2 が必要です。Linux では管理権限、Koha リポジトリへの通信、80 と 8080 のポートを確認します。使用中サービスの停止を許可するのは、停止してよいと判断できる場合だけにしてください。

## PowerShell からの Windows 導入

実際に Koha を使う管理者権限の Windows ユーザーでログインし、同じユーザーの PowerShell を管理者として開きます。他人のアカウントでの昇格を要求されたら中止し、適切な管理者アカウントへログインし直してください。信頼する配布元であることを確認して実行します。

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/install.ps1 | iex
```

事前確認のエラーを解決し、Debian アカウントの質問にインストーラー内で答えます。これは Koha の図書館アカウントとは別です。再起動が必要な場合、次の Windows ログイン時に続行する処理が登録されます。同じユーザーで戻り、パネルで言語と **Install Koha server** を選びます。

サーバー導入後はパネルを通常終了し、Windows 側の統合が終わるまで待ちます。標準の `C:\Koha`、旧環境の `C:\KohaEasy` を手動移動しないでください。中断後の再実行は完了済み段階を使って続行できますが、破壊的な再インストールを無確認で繰り返してよいという意味ではありません。

## MSIX

次の補助スクリプトは、管理者として開いていない通常の PowerShell で実行します。

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/msix/instalar_msix.ps1 | iex
```

スクリプトが配布元を確認し、必要時に権限を要求します。拒否された場合はメッセージを確認してください。パッケージ導入だけでは Koha のサーバー設定は終わりません。初回起動後にパネルの導入を完了し、通常終了してネットワークやバックグラウンド処理の最終設定を待ちます。早く閉じた場合は再度起動して続けます。

Microsoft Store の公開状況と URL は要確認です。生成 manifest は x64 のため、Linux の arm64 対応から MSIX の ARM64 動作を推測しないでください。manifest にある古い Windows 最低値より、完全な WSL 手順の条件を優先します。

## Debian・Ubuntu とパネル内の導入

サーバーの端末で次を実行します。

```bash
wget https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/refs/heads/main/installer
sudo bash installer
```

リポジトリと翻訳も保持したい場合の別手順です。

```bash
git clone https://github.com/PauloFBaldiFH/koha.nexus.git
cd koha.nexus
sudo bash installer
```

言語と **Install Koha server** を選び、検査結果と対象マシンを確認します。重要な失敗を解決し、タイムゾーンを確認してください。既存インスタンスの再インストールはデータベースと設定を削除し、正確な `REINSTALL` の入力が必要です。必ずサーバー外に復元可能な backup を保管してから判断します。

表示目安は 10～30 分ですが機器と通信に左右されます。パネルでは取り消せない段階なので、窓を閉じないでください。完了時の問題一覧を読み、全サービスの正常動作を別途確認します。結果画面の私的情報を公開資料へ貼らないでください。

## 確認したソース

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
