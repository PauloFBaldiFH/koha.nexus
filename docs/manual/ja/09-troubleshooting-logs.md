# 9. トラブルシューティングとログ

[目次](README.md)

## まず調査する

操作、時刻、完全なエラー、まだ動く部分を記録します。ページ表示、サービス稼働、検索成功は別の確認です。毎回の最初の対処に再インストールや restore を使わないでください。

**Control Dashboard** を更新し、**Diagnostics & maintenance center** で **Detailed server & Koha status**、**Full system health check**、**View latest validation report** を読みます。必要なら **Export diagnostics** の保存先を控えます。機密の一部は隠されますが、利用者、ファイル名、設備アドレスを共有前に確認し、設置先全体を公開しないでください。従来型パネルへの切替は、以前の処理の取り消しではありません。

## ファイルと読み方

Linux の `/var/log/koha-easy-install/` に `apt.log`、日付別 `validacao-*.log`、パネルの `new-panel.log`、`backup_sql.log` と `backup_marc.log`、`restore.log` と `restore-import.log`、検索用 `zebra-rebuild.log` と `search-engine.log` があります。ツールは `/var/log/koha-easy-install/tools/`、Windows は通常 `C:\Koha\logs`、旧版は `C:\KohaEasy\logs` です。

`*` は日付などの変動部分であり、文字どおりの名前を作りません。初回実行前にファイルがないこともあります。処理の表示した正確なパスを優先し、**View tool logs** で日付・仕事を選びます。個人情報を含み得るため扱いを制限します。

報告は版・時刻と各 OK、警告、失敗を読みます。合計だけでは原因不明です。**No critical failures** でも警告はあり得ます。修正後は再検証し比較します。

**Real-time Apache log auditing** で OPAC か staff を選びます。Textual の **Pause**／p は表示を止めるだけで Apache を止めず、**Continue**、**Back**／Esc で再開・退出します。従来型の Ctrl+C はこのログ追跡からの終了で、全処理に流用しません。強調された error/fatal/denied/fail は時間と前後関係も確認します。

## 症状に合わせる

開けない場合は Apache、MariaDB、Plack、キャッシュとローカル・LAN・VPN・トンネルを切り分けます。localhost はブラウザーの端末です。**Restart / repair Koha services (Memcached, Plack)** は一時中断を伴い、最後に再検証が必要です。

書誌が検索されない場合はエンジン、キュー、索引と DB を確認し、**Search engine & indexing > Repair / rebuild indexing** の説明を読んで待ちます。最初から Elasticsearch に変える必要はありません。

backup は時刻、結果、容量、Linux と cron を確認します。`.part` は未完了です。競合処理を避け、別の安全なコピーなしに最後の有効な backup を消しません。取り込みは入力・準備・登録数、モード、館・種別、バーコード、拒否、重複方針を調べます。小さなプレビューでは全体を保証せず、再試行前に部分登録を確認します。

restore の索引失敗は DB 置換後かもしれず、rollback も失敗します。DB・検索・検証まで見て復旧を判断してください。AI の RAM と外部補完の通信制限は別問題で、遅延だけを理由に大仕事を重複実行しません。

## Windows の診断と相談

ログイン中ユーザーの、管理者として開いていない PowerShell で実行します。

```powershell
irm https://raw.githubusercontent.com/PauloFBaldiFH/koha.nexus/main/windows/diagnose.ps1 | iex
```

この診断は完全な読み取り専用ではなく、ショートカット再作成やトレイ再起動を行えます。検出した設置先 `logs` の `diagnose-<date>.txt` と表示パスを保管します。

**Deep database optimization & log cleanup** は調査に役立つ履歴を消す場合があるため、先に診断を保存し保守時間を取ります。相談には版、OS/WSL、操作、時刻、全文、OPAC/staff/検索、直前の取り込み・restore・更新を添え、私的情報を除きます。完全なログなしの具体的原因は要確認のままです。

## 確認したソース

- [diagnostics.py](../../../panel/kei_panel/routines/diagnostics.py).
- [logtail.py](../../../panel/kei_panel/screens/logtail.py).
- [search.py](../../../panel/kei_panel/routines/search.py).
- [installer](../../../installer).
- [diagnose.ps1](../../../windows/diagnose.ps1).
- [KohaEasy.Core.psm1](../../../windows/KohaEasy.Core.psm1).
