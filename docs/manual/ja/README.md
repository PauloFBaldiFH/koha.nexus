# Koha.Nexus ユーザーマニュアル

全九章で Koha.Nexus の導入とパネルを説明します。Koha の完全な目録・貸出マニュアルの代わりではありません。ポルトガル語と英語の資料から手作業で執筆し、2a78bfa のソースと照合しました。コード確認は実機での導入試験ではありません。操作名はコードと対応させるため英語を保持し、実画面では翻訳される場合があります。コマンドとパスは翻訳しません。置換・削除の確認を読み、古いメニュー番号に頼らないでください。

## 目次

1. [インストール](01-installation.md).
2. [初めての操作とパネル](02-panel.md).
3. [Backup と restore](03-backup-restore.md).
4. [マジックインポート](04-magic-import.md).
5. [レコードの補完と Z39.50/SRU](05-enrichment.md).
6. [OPAC と staff の外観](06-appearance.md).
7. [ローカル AI](07-local-ai.md).
8. [管理、通知、VPN](08-administration.md).
9. [トラブルシューティングとログ](09-troubleshooting-logs.md).

[English](../en/README.md) · [Português brasileiro](../pt-BR/README.md) · [हिन्दी](../hi/README.md) · [বাংলা](../bn/README.md) · [Tiếng Việt](../vi/README.md) · [中文（简体）](../zh/README.md) · [日本語](../ja/README.md)

## 要確認事項

- Microsoft Store の一般公開状況と URL。
- 数値条件として強制されていない Linux の正式な最低 RAM。
- ARM64 での MSIX 全体の動作。manifest は x64。
- サンプルと結果レビューのない独自出力形式・版への適合。
- 自館ネットワークからの外部出典の可用性と条件。
- ハードウェアと選択による AI の RAM、ディスク、応答時間。
- 公開に必要なドメイン、ネットワーク、機関の方針。
- 完全なメッセージとログがない特定障害の原因。
