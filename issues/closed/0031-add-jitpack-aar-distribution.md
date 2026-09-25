# JitPack を webrtc-build に追加して Android の AAR を公開する

- Created: 2026-09-25
- Completed: 2026-09-25
- Branch: feature/add-jitpack-aar-distribution
- Polished: {YYYY-MM-DD}

## 目的

Android 向け libwebrtc の配布を `shiguredo-webrtc-build/webrtc-build` に統合し、 JitPack から `com.github.shiguredo-webrtc-build:webrtc-build` として AAR を公開する。

`shiguredo/shiguredo-webrtc-android` は AAR を再配布しているだけのリポジトリであり、 libwebrtc を更新するたびにタグ、 Release、 `CHANGES.md` の更新が発生している。 webrtc-build で JitPack ビルドを行えるようにして、配布専用リポジトリを不要にする。

対象リポジトリは `shiguredo-webrtc-build/webrtc-build` である。

## 現状

- webrtc-build には JitPack 用の設定ファイルが無い
- `.github/workflows/build.yml` の `create-release` ジョブは `tags/m` のときだけ Release を作成し、各プラットフォームのアーカイブだけをアップロードする
  - `webrtc.android_sdk.tar.gz` の中に `webrtc/aar/libwebrtc.aar` と `webrtc/NOTICE` が含まれているが、 AAR 単体は Release の成果物に含まれない
- `shiguredo/shiguredo-webrtc-android` の `jitpack.yml` と `prepareAar.sh` が AAR を JitPack に公開している
- webrtc-build の Release 成果物は全プラットフォームのビルド完了後に作られるため、タグ push から約 1 時間かかる
- JitPack には `com.github.shiguredo-webrtc-build:webrtc-build` のプロジェクトが既に存在し、過去に `m97.4692.0.4` 〜 `m155.8059.1.0` のビルド記録がある
  - いずれも失敗しており、直近の `m155.8059.1.0` は 2026-09-24 にリクエストされて `No build file found` (jitpack.yml が無い) で失敗している
  - 数秒差で複数バージョンがリクエストされた記録があり、オンデマンドのリクエストによるものとみられる

## 設計方針

- `jitpack.yml` を追加し、 `install` で AAR をローカルの Maven リポジトリに登録するスクリプトを実行する
  - スクリプトは JitPack が設定する環境変数 `VERSION` (タグ名) を使い、 `https://github.com/shiguredo-webrtc-build/webrtc-build/releases/download/${VERSION}/libwebrtc.aar` を取得して `mvn install:install-file` する
  - バージョンはタグ名そのものになり、下流は `m155.8059.1.0` のような `m` 付きのバージョンを指定する
- `create-release` ジョブで `webrtc.android_sdk.tar.gz` から `webrtc/aar/libwebrtc.aar` と `webrtc/NOTICE` を取り出し、 Release の成果物として追加する
  - AAR 単体を追加することで取得が単純になり、ダウンロードも約 105 MB から約 14 MB に減る
- Release は draft として作成し、全成果物をアップロードしてから publish する
  - webrtc-build の Release はタグ push から約 1 時間後に作られるため、 JitPack の自動検知に任せると成果物のアップロード完了前にビルドが始まるおそれがある
- publish 後にワークフローから JitPack のビルドを明示的にリクエストし、 artifact の公開を確認する
  - webrtc-build では新リリースの自動ビルドが観測されていないため、自動検知には依存しない
  - 起動は `https://jitpack.io/com/github/shiguredo-webrtc-build/webrtc-build/${VERSION}/build.log` への GET で行い、 `https://jitpack.io/api/builds/com.github.shiguredo-webrtc-build/webrtc-build/${VERSION}` で結果を確認する。認証は不要
- README に Android 向け AAR の利用方法 (座標とバージョンの形式) を追記する
- jitpack.yml はタグのコミットに含まれる必要があるため、新しい座標で公開できるのは jitpack.yml をマージした後に作られるタグからである
- `m` 付きのバージョンは semver として解釈されないため、 JitPack の latest や動的バージョンの対象にならない。下流はバージョンを明示するため影響しない

## 完了条件

- `m` 付きタグに対して `com.github.shiguredo-webrtc-build:webrtc-build:m<version>` の AAR が JitPack から取得できる
- webrtc-build の Release に `libwebrtc.aar` と `NOTICE` が単体で含まれる
- Release の publish 後にワークフローがビルドを起動し、人手を介さずに artifact が公開される
- Sora Android SDK を新しい座標でビルドできる
- README に AAR の利用方法が記載されている

## 確認済みの点

- ハイフン付き org 名の groupId (`com.github.shiguredo-webrtc-build`) は問題ない
  - JitPack に `com.github.shiguredo-webrtc-build:webrtc-build` の既存プロジェクトがある
  - 他にも `com.github.json-path:JsonPath` / `com.github.mock-server:mockserver` / `com.github.gradle-nexus:publish-plugin` / `com.github.ben-manes:caffeine` の成功例がある
- `m` 付きタグはバージョンとして通る
  - `m155.8059.1.0` は JitPack がタグのコミット `cebf2e2` を解決してビルドを試行した記録があり、失敗理由は jitpack.yml が無いことである
- JitPack のビルドは認証不要の HTTP リクエストで起動できる
  - `https://jitpack.io/com/github/<owner>/<repo>/<version>/build.log` への GET で起動する方法が公開されている

## 未検証の点

- `jitpack.yml` のカスタム install で実際に AAR が公開できるかは、タグ push 後の実ビルドで確認する
  - カスタム install の方式自体は `shiguredo/shiguredo-webrtc-android` で実績がある
- `m155.8059.1.0` は JitPack に失敗ビルドの記録が残っている。失敗ビルドは 7 日以内なら削除して再リクエストできる (削除には JitPack の認証とリポジトリへの push 権限が必要)。新しいタグを使う移行では通常影響しない

## 解決方法

`jitpack.yml` と `scripts/prepare_aar.sh` を追加し、 `m` 付きタグで JitPack から AAR を公開できるようにした。あわせて `create-release` ジョブで Release の publish 後に JitPack のビルドを起動するようにした。

- `jitpack.yml` の `install` で `scripts/prepare_aar.sh` を実行し、 Release の `libwebrtc.aar` を取得して `mvn install:install-file` でローカルの Maven リポジトリに登録する
- `create-release` ジョブで `webrtc.android_sdk.tar.gz` から `libwebrtc.aar` と `NOTICE` を取り出し、 Release の成果物に追加する
- Release は draft として作成し、全成果物のアップロード後に publish する
- publish 後に JitPack のビルドを起動し、 POM の取得で artifact の公開を確認する
- README に JitPack の利用方法、 CHANGES.md に変更履歴を追記する

次の Release で `com.github.shiguredo-webrtc-build:webrtc-build:m<version>` の AAR が取得できることを確認する。確認できない場合は reopened にする。

## 補足

- AAR の取得元として、 JitPack のビルドが Release の `webrtc.android_sdk.tar.gz` から `webrtc/aar/libwebrtc.aar` を取り出す案も検討した
  - Release に AAR 単体を追加せずに済む (アーカイブとの二重化を避けられる) 一方、 JitPack のビルドで約 105 MB のダウンロードとアーカイブの内部構造への依存が増える
  - 今回は既存の `shiguredo-webrtc-android` と同じく AAR 単体を Release に追加する方式を採用し、この案は将来の候補として残す