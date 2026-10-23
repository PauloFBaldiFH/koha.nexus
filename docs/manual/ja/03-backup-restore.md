# 3. Backup と restore

[目次](README.md)

## Backup center の役割

主画面の b またはサイドバーから開きます。**Download latest backup** は既存の最新ファイルを転送し、**Generate manual backup and download to PC** は現在のデータベースを保存します。**Export MARC21 records now** は書誌・典拠を、**Configure cloud backup** は外部送信を扱います。**Test integrity of latest backup** は一時データベースへの試験、**Restore database** は現在のデータベースの置換です。restore はこのセンターのカードで、上部の専用ボタンではありません。

SQL backup は Koha データベースで、OS や Debian 全体のイメージではありません。MARC の `.tar.gz` は書誌と典拠で、利用者と貸出を含む完全復旧の代わりにはなりません。自動 SQL と安全コピーは `/var/backups/koha_sql`、MARC は `/var/backups/koha_marc` が標準です。手動保存は画面で選ぶ別の宛先で、既定は識別されたホームの `backups` です。

`.part` は書き込み途中であり、検査後に最終名になります。完成した backup として選ばないでください。圧縮は gz、zst、xz から選ぶと保存され、新規ファイルだけに適用されます。必要なプログラムが導入できなければ通知され gzip に戻ります。restore は選択中の圧縮形式とは別に対応する `.sql`、`.sql.gz`、`.sql.zst`、`.sql.xz` を読みます。拡張子だけでは有効と判断できません。

## 保存と試験

手動カードでサーバーの宛先を確認し、**Save backup** を実行します。生成と確認中は閉じられません。名前・サイズ・パスを確認し、WSL なら **Save to Windows Downloads** または **Choose folder in Windows**、遠隔接続なら表示された転送コマンドを自分の端末で実行します。到着を確認して **Finish and exit**。別環境の転送例を流用しないでください。

共有ロックが他の backup や restore を示す場合は待ち、別プロセスで回避しないでください。最新のダウンロードは新規生成ではありません。必要なら直前の手動コピーを作ります。

整合性カードで対象日時を確認し、必要なら **Choose another file**。一時データベースに取り込み、表・書誌・利用者の数を確認します。本番を置換せず、成功は試験したファイルと環境に限られます。MARC は Koha 稼働中に出力でき、内容と転送・クラウド結果を確認します。

## クラウドとスケジュール

Google Drive の二つの簡易経路と OneDrive、MEGA、S3 などがあります。認可をサーバー自身で行うか別端末で行うかに合った経路を選び、設置先の案内に従います。S3 はサービス、region、endpoint、bucket を確認します。実アップロードの試験結果と宛先ファイルを必ず確認し、認可情報を公開しないでください。

既定はサーバー時刻の毎日 23:00 に SQL、日曜 03:00 に MARC です。変更済み cron の時刻とは限らず、サーバーと Linux が稼働している必要があります。最新ファイルと夜間結果の表示も別々に読みます。

## restore はデータ置換

**Restore database は現在のデータを置換します。** 保守時間を確保し、サーバー外の安全なコピーを準備してください。これは運用上の推奨であり、自動的に外部転送される手順ではありません。遠隔ファイルは案内どおりサーバーへ、WSL の Windows ファイルは必要に応じ Linux 側へコピーします。

読み取り、内容、整合性、容量を確認し、不審なファイルは調査します。置換の最終確認までは撤回できますが、その後はパネルで中止できません。

最初に一時データベースへ取り込み、必須表と数を確認します。現在の表がある場合は `pre_restore_safety_backup_` で始まる安全コピーを生成・検証します。失敗なら置換前に停止し、空のデータベースでは省略される場合があります。その後クライアント停止、再作成・取り込み、構造更新、検索同期、索引再構築、サービス再起動と保存済みテーマの再適用を試みます。

失敗した段階を見分けてください。復旧を試みる場合も rollback 自体が失敗し得ます。索引エラーはデータベース置換後かもしれず、旧内容が戻った証拠ではありません。`/var/log/koha-easy-install/restore.log`、`/var/log/koha-easy-install/restore-import.log`、`/var/log/koha-easy-install/zebra-rebuild.log` を確認します。

最後に staff、OPAC、レコード、検索を検証します。SQL 外のファイルまで復旧したとは限りません。状態不明なら全処理を繰り返さず支援を求めてください。

## 確認したソース

- [menus.py](../../../panel/kei_panel/menus.py).
- [backup.py](../../../panel/kei_panel/views/backup.py).
- [backup.py](../../../panel/kei_panel/routines/backup.py).
- [installer](../../../installer).
- [save_backup.py](../../../panel/kei_panel/save_backup.py).
- [save_backup.py](../../../panel/kei_panel/screens/save_backup.py).
