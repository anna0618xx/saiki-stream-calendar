# 佐伯イッテツ 配信アーカイブ — 公開可能なGitHub版

**公開するフォルダはこの `PUBLIC_GITHUB_UPLOAD` の中身だけ。**

これは静的UIと2026年の公開動画メタデータだけを含みます。個人のOSHI貯金履歴・写真・非公開JSON・Google API秘密鍵は含みません。

## 使い始める手順

1. GitHubで `saiki-stream-calendar` の **Public** リポジトリを作成。
2. このフォルダの**中身だけ**をアップロードし、mainブランチにコミット（フォルダごと上げない）。
3. GitHubリポジトリの `Settings → Pages → Build and deployment → Source → GitHub Actions` を設定。
4. `Settings → Secrets and variables → Actions → New repository secret` で `YOUTUBE_API_KEY` を登録。**キーをHTML/JSONに貼らない**。
5. `channels.json` に、実際に確認した本人・公式・Oriens・ヒーローズのチャンネルID（UCではじまる24文字）を登録。正しいIDが未確認の欄は空欄のままにする。
6. `Actions → Saiki public feed and Pages → Run workflow` で最初の手動実行。
7. `Settings → Pages` に出るサイトURLへアクセス。
8. 個人記録は公開リポジトリへ一切入れない。プライベート側の `PRIVATE_IMPORT_OSHI_DO_NOT_UPLOAD.json` を**ブラウザの「バックアップ読込」**で一度だけ取り込み、Google Drive接続後に「Driveへ保存」を実行。

## 自動更新

- 新規動画・配信状況: 15分おきに確認（GitHub Actionsは遅れることがあり、厳密な時間保証なし）。
- 非公式Wiki掲載: 1日2回取り込む（更新頻度と負荷を抑えるため）。
- 実際の配信時刻: YouTube Data API `liveStreamingDetails` から取得できた場合のみ反映。
- 緑系のサムネイル: 判定結果を雑談候補にする。既存手動タグは変更しない。
- **映像10分時点のスクショ取得は未搭載**。公式サムネイルは表示できる。YouTube映像のコピー保存には権利・利用条件上の制約があり、別途方法と許可確認が必要。

## 写真とバックアップ

- GitHub Pagesでアップロードされた個人スクショは、**端末のブラウザ内**に保存される。
- 初回に私用JSONを読み込むと、OSHI既存スクショの画像データもブラウザ内へ取り込まれる。
- Google DriveはOAuth接続後の **保存/復元ボタン式**（リアルタイム自動同期ではない）。別端末で編集する前にDriveから復元し、編集後はDriveへ保存する。
- Google Cloud Consoleで OAuth 2.0「ウェブアプリケーション」のクライアントを用意し、承認済みJavaScript生成元に `https://<GitHubユーザー名>.github.io` を登録。Drive APIを有効化し、同意画面のテストユーザーに自分を追加。アプリ上の入力欄にクライアントIDを入力する。

※ Google OAuthクライアントIDは公開してよい識別子、YouTube APIキーは必ずGitHub Secret。
