# 8. 管理、通知、VPN

[目次](README.md)

## 定期処理と管理設定

変更前に現状と最近の backup を確認します。s で **Schedules & cron tasks** を開き、**Reload**、必要な有効化・頻度・`HH:MM`、曜日や式を設定、**Preview**、**Save** と確認、再読込の順です。**Defaults** は欄を埋めるだけで保存が必要です。

`/etc/cron.d/koha_tasks` を管理し、旧版は `koha_tasks.bak`。無効な仕事も時刻をコメントで保持し、手書き行は残します。既定 SQL は毎夜 23:00、MARC は日曜 03:00 のサーバー時刻です。Linux とマシンが動いている必要があり、Windows を自動起動する保証はありません。Koha 自身の通知機構と区別します。

**Koha settings & parameters** は RAM、worker、強い権限のアカウント、時刻を扱います。**Koha languages** の取得と有効化は別です。**Update center** の OS・構造更新と GitHub のパネル更新も別で、backup と保守時間を確保します。セッション終了はあり得ますが、構造移行失敗は再起動だけで解決したと判断しません。

## VPN と安全な接続

**Security & access hub > WireGuard VPN**、または v で公開アドレスと UDP ポートを確認します。**Set up the VPN** の変更を読み、ルーターで UDP を転送します。デバイスごとに **Add device**、**QR code & profile** を使い、接続・staff・通信量を試験します。

プロファイルと QR は非公開です。**Revoke** はその設定を無効にし、再接続には新規設定が必要です。**Turn off** は切断して設定を保持します。分割トンネルは `10.66.0.0/24` のみ通し、通常のインターネットと DNS は端末の回線です。staff は `http://10.66.0.1:8080`。WSL が mirrored でない場合は直接到達できず、この VPN は無効になります。

Cloudflare Tunnel、UFW、8080 制限、HTTPS、Fail2ban は到達範囲が異なります。遠隔ファイアウォール変更前に管理経路を確保してください。ドメイン、回線、ルーター、機関の公開方針は要確認で、全環境共通の公開手順はありません。

## 通知と連携

m の **Messaging & interoperability** は **E-mail**、**WhatsApp & Telegram**、**SMS**、**Alerts**、**SIP2**、**Z39.50** の六タブです。メール有効化だけで SMTP、図書館アドレス、通知文、延滞規則、利用者設定が完成するわけではありません。

**Set up WhatsApp and Telegram** はサービス、国・地域番号、試験、電話確認などを扱います。WhatsApp はゲートウェイ、Telegram は bot と宛先設定に依存します。許可された相手に試験し、一括番号修正の前はプレビューします。SMS は `SMSSendDriver` だけでなく互換サービスとドライバーが必要です。

**Alerts** の期限・延滞・反復・日次要約とチャネルを選び、**Dry run (sends nothing)** で送らず確認します。有効化後は cron と重複する Koha 通知を点検します。SIP2 はポート、ネットワーク、館、権限、対応する Koha アカウントが必要です。例を削除し、ローカル試験のため全ネットワークに公開しないでください。Z39.50 の外部検索と受信公開も別です。

## 図書館のデータ作業

**Library tools** の典拠同期、重複著者、SQL 報告、利用者区分、品質、プライバシーを慎重に使います。区分変更は異なる移行元・先と館を指定し、試行結果と backup を確認します。品質調査は読み取り専用で自動全修復ではありません。匿名化は過去と利用者のリンクを外し、全書誌を消す操作ではありません。古い利用者の削除はフィルター・試行・件数確認が必要で破壊的です。保存方針を確認します。同名は同一人物の証明ではなく、非表示カードも利用可能とはみなしません。

## 確認したソース

- [menus.py](../../../panel/kei_panel/menus.py).
- [crons.py](../../../panel/kei_panel/views/crons.py).
- [cron.py](../../../panel/kei_panel/cron.py).
- [vpn.py](../../../panel/kei_panel/views/vpn.py).
- [hub.py](../../../panel/kei_panel/views/hub.py).
- [settings.py](../../../panel/kei_panel/routines/settings.py).
- [security.py](../../../panel/kei_panel/routines/security.py).
- [tools.py](../../../panel/kei_panel/routines/tools.py).
- [installer](../../../installer).
