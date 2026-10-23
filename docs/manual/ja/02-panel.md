# 2. 初めての操作とパネル

[目次](README.md)

## 開く、選ぶ、終了する

準備済みの Debian または Ubuntu では次を使います。

```bash
sudo config.sh
```

Windows では作成された **Koha** アイコン、または MSIX アプリを開きます。最初に言語選択が出る場合があります。Textual を準備できないときは従来型パネルが提示されることがありますが、古いメニュー番号で現行のカードを探さないでください。

矢印キーでサイドバーの項目を選び、Enter またはクリックで開きます。選択位置を動かすだけでは実行されません。内容領域のカードを開き、質問を読んで進めます。Tab はコントロール間の移動です。文字入力欄を離れてから主画面の文字ショートカットを使ってください。

| キー | 主画面での動作 |
| --- | --- |
| d | Control Dashboard を開く |
| b | Backup center を開く |
| c | Debian 端末を開く |
| Ctrl+B | サイドバーの表示切替 |
| q | パネルを終了 |

待機中のパネル終了はサーバー停止ではありません。実行中は各画面の中止手順に従います。インストールと restore は中止できない段階があるため、強制的なウィンドウ終了は安全な取り消し方法ではありません。

## 状態とアクセス先

**Control Dashboard** は Koha、利用可能メモリ、空きディスク、最新 backup の時刻・サイズ、ローカル・LAN・設定済みインターネットのアドレスを表示します。MariaDB、Apache、RabbitMQ、Memcached、Koha と HTTP 応答の確認は、業務全体の動作試験を代替しません。

最新ファイルと直近の夜間処理結果は別の実行に由来することがあります。新しいファイルがあっても夜間処理は失敗している可能性があります。HTTP 応答も Koha のウェブ導入完了を証明しません。**Refresh** は再取得、**Restart Koha** はサービス修復・再起動、**Export diagnostics** は診断出力です。旧インストーラーでは対応しないボタンがあります。再起動前に利用者への影響を考慮してください。

サーバー自身の OPAC は `http://localhost/`、staff は `http://localhost:8080/` が標準です。別の端末の localhost はその端末自身です。パネルの LAN アドレスを使い、WSL の NAT による到達不能が表示されたら Windows 側ネットワーク準備を確認します。アドレスカードは開くかコピーできます。

## 業務開始前

staff に Koha のウェブインストーラーが出た場合は先に完了します。手順は版により異なります。その後 **Koha settings & parameters > Create super librarian** で必要な管理アカウントを作成できます。詳細は設置先だけで入力し、強い権限の利用を限定します。

状態を更新し、適切なアドレスで staff と OPAC、検索を確認してください。backup を作成・試験し、サーバー外の保管場所と復旧担当を決めます。外部コピーが使えるかは転送と確認の完了に依存し、ダッシュボードが自動保証するものではありません。

## 確認したソース

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
