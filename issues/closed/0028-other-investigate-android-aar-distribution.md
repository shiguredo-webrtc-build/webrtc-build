# Android 向け libwebrtc.aar の配布を webrtc-build にまとめられるか検討する

- Created: 2026-09-24
- Completed: 2026-09-25
- Branch: feature/debug-android-aar-distribution
- Polished: 2026-09-24

## 目的

Android 向け libwebrtc の配布を担う `shiguredo/shiguredo-webrtc-android` の役割を webrtc-build にまとめられるか検討する。

`shiguredo/shiguredo-webrtc-android` は webrtc-build がビルドした AAR を再配布しているだけで独自のソースコードを持たず、 下流 SDK が採用する libwebrtc を更新するたびに 2 リポジトリでタグ・リリース・手作業が発生する。配布経路を webrtc-build にまとめられれば、下流 SDK の libwebrtc 更新作業から `shiguredo/shiguredo-webrtc-android` 側の手作業をなくせる。

## 現状

### `shiguredo/shiguredo-webrtc-android` の役割

- リポジトリにあるのは配布用のラッパーだけで、ビルド対象のソースコードは無い
  - `README.md` / `CHANGES.md` / `LICENSE` / `LICENSE_WEBRTC` / `PATENTS_WEBRTC`
  - `prepareAar.sh`: JitPack 用に AAR をローカルの Maven リポジトリへ登録する
  - `jitpack.yml`: `before_install` で `prepareAar.sh` を実行する
  - `.github/workflows/release.yml`: タグ push で GitHub Release を作成する
- `79.5.0` 以降のタグ (50 個) は webrtc-build のタグから `m` を除いた値 (例: webrtc-build `m155.8059.1.0` → `155.8059.1.0`)。 webrtc-build のタグは `m79.5.0` から始まり、 `79.5.0` より前の 24 タグには対応する webrtc-build のタグが無い
- `.github/workflows/release.yml` はタグ push を契機に `https://github.com/shiguredo-webrtc-build/webrtc-build/releases/download/m${TAG}/webrtc.android_sdk.tar.gz` を取得し、 `webrtc/aar/libwebrtc.aar` と `webrtc/NOTICE` を Release の成果物としてアップロードする
- JitPack は `jitpack.yml` の `before_install` で `prepareAar.sh` を実行する。 `prepareAar.sh` は自分の Release から AAR を取得して `mvn install:install-file` でローカルの Maven リポジトリへ登録し、 JitPack が `com.github.shiguredo:shiguredo-webrtc-android:<version>` として公開する
- libwebrtc を更新するときの手作業
  - `prepareAar.sh` の `VERSION` を更新する
  - `CHANGES.md` に追記する
  - タグを作成して push する (Release 作成と JitPack への反映は push 後に自動で進む)
  - JitPack に反映されたことを確認する
- 下流は JitPack 経由で `com.github.shiguredo:shiguredo-webrtc-android` を参照している
  - Sora Android SDK の `gradle/libs.versions.toml` は `libwebrtc` の値をそのまま JitPack のバージョンに使う
  - 他にも JitPack 経由で参照する公開リポジトリがある (例: zztkm/ayame-android-sdk)

### webrtc-build の現状

- `run.py` の `android_sdk` ターゲットが `tools_webrtc/android/build_aar.py` で AAR を生成し、 `webrtc.android_sdk.tar.gz` に `webrtc/aar/libwebrtc.aar` と `webrtc/NOTICE` を含めてパッケージしている
- `.github/workflows/build.yml` の `create-release` ジョブは `tags/m` のときだけ Release を作成し、各プラットフォームのアーカイブだけをアップロードする。 AAR 単体は Release の成果物に含まれない
- JitPack 用の設定ファイルは無い
- `VERSION` は `WEBRTC_BUILD_VERSION=155.8059.1.0` のように `m` を含まず、 `m` が付くのはタグ名だけである

### 調査で確認した事実

- `shiguredo/shiguredo-webrtc-android` の `79.5.0` 以降のタグは 50 個で、すべて webrtc-build の `m` 付きタグに対応する。逆に webrtc-build の全 399 タグのうち `shiguredo/shiguredo-webrtc-android` にタグがあるのは 50 個だけで、残り 349 タグには android 側のタグが無い。 android 側のタグと Release はすべての webrtc-build リリースには作られていない
- `shiguredo/shiguredo-webrtc-android` には同一 AAR に別バージョンを付けるサフィックス付きのタグ (例: 68.10.1.1) があるが、いずれも `79.5.0` より前のタグで、 `79.5.0` 以降は使われていない
- JitPack は `jitpack.yml` のカスタムコマンドで既存の AAR を公開できる。 JitPack がビルドするバージョンはタグ名そのものである
- JitPack はリポジトリを削除しても公開済みの成果物をホストし続ける
- 公開リポジトリを対象にしたコード検索では、 JitPack 経由以外に `shiguredo/shiguredo-webrtc-android` の Release 成果物を直接参照している例は見つかっていない

## 設計方針

次の案を比較して、統合の可否と方式を決める。案 2 と案 3 は排他ではなく、組み合わせられる。

- 案 1: JitPack を webrtc-build へ移して完全に統合する
  - webrtc-build 直下に `jitpack.yml` と AAR を用意するスクリプトを置き、 `m` 付きタグで JitPack をビルドする
  - 座標は `com.github.shiguredo-webrtc-build:webrtc-build:m<version>` になり、下流は依存座標とバージョン表記 (先頭の `m`) の両方を変更する必要がある
  - `shiguredo/shiguredo-webrtc-android` を廃止できる
  - 同一 AAR にサフィックス付きの別バージョンを付ける運用はできなくなる。 webrtc-build のリリース番号を進めた新しいタグを切ることはできるが、その場合は全プラットフォームの再リリースになる (サフィックス付きのタグは `79.5.0` 以降は使われていない)
- 案 2: AAR を webrtc-build の Release 成果物にして、 JitPack の座標を維持するために `shiguredo/shiguredo-webrtc-android` を残す
  - `create-release` ジョブで AAR と NOTICE を Release にアップロードし、 `prepareAar.sh` の取得元を webrtc-build の Release に変更する。あわせて `shiguredo/shiguredo-webrtc-android` の `release.yml` は AAR と NOTICE のアップロードをやめる
  - android 側の Release 作成はタグ push で既に自動化されているため手作業の削減は限定的だが、同じ AAR を 2 リポジトリで保存する状態を解消でき、 AAR の取得元を webrtc-build に一本化できる
  - `prepareAar.sh` の `VERSION` の更新と `CHANGES.md` への追記は手作業として残る。案 3 の自動化を組み合わせれば削減できる
  - 下流の依存座標とバージョンは変わらない
- 案 3: 統合せず、 `shiguredo/shiguredo-webrtc-android` を自動化する
  - `prepareAar.sh` の `VERSION` をタグから導出し、 `CHANGES.md` への追記を自動化し、 webrtc-build の Release 完了時に `shiguredo/shiguredo-webrtc-android` のタグ作成を自動化する (android 側のタグはすべての webrtc-build リリースには作られていないため、対象の絞り方も決める)
  - リポジトリは残るが、下流の依存座標とバージョンは変わらず、人手もゼロにできる見込み

いずれの案も、 JitPack が `m` 付きタグやカスタムコマンドを受け付けるかを実ビルドで確認する。下流 SDK の座標変更は本 issue では行わない。

## 完了条件

- どの案を採用するかを決め、判断根拠 (下流への影響、手作業の削減量、JitPack の制約) を本 issue に記載すること
- 採用する案に実装が必要な場合、実装 issue を別途起票すること
- 下流 SDK の依存座標の変更と `shiguredo/shiguredo-webrtc-android` の廃止判断は、本 issue の結論を前提に別 issue で扱うこと

## 解決方法

案 1 を採用する。 `shiguredo/shiguredo-webrtc-android` をアーカイブし、 Android 向け AAR の配布を webrtc-build に完全に統合する。

### 採用する方式

- webrtc-build 直下に `jitpack.yml` と AAR をローカルの Maven リポジトリに登録するスクリプトを追加し、 `m` 付きタグで JitPack がビルドする
  - 座標は `com.github.shiguredo-webrtc-build:webrtc-build:m<version>` になる
  - `jitpack.yml` はタグのコミットに含まれる必要があるため、新しい座標で公開できるのはマージ後に作られるタグからである
- webrtc-build の Release に `libwebrtc.aar` と `NOTICE` を単体の成果物として追加し、 JitPack はこれを取得する
  - `webrtc.android_sdk.tar.gz` から取り出す。 AAR 単体の追加により取得が単純になり、ダウンロードも約 105 MB から約 14 MB に減る
- JitPack のビルドが成果物のアップロード完了前に始まらないよう、 Release は draft として作成し、全成果物をアップロードしてから publish する
- publish 後に JitPack のビルドを起動して artifact の公開を確認する。 JitPack の自動検知の有無やタイミングに依存しないようにする
- `shiguredo/shiguredo-webrtc-android` は下流の移行完了後にアーカイブする。 JitPack は公開済みの成果物を配布し続けるため、既存バージョンのビルドは壊れない

### 判断根拠

#### リポジトリの集約

- 配布専用リポジトリ (タグ、 Release、 `CHANGES.md`、 JitPack 設定) が不要になり、 webrtc-build の 1 リポジトリで完結する
- 下流が採用する libwebrtc を更新するときの作業が webrtc-build のリリースだけになる

#### 下流への影響

- 依存座標が `com.github.shiguredo:shiguredo-webrtc-android` から `com.github.shiguredo-webrtc-build:webrtc-build` に変わり、バージョンに `m` が付く
  - Sora Android SDK の `gradle/libs.versions.toml` と `skills/sora-android-sdk/SKILL.md` などの追随が必要になる
  - Sora Android SDK の利用者は SDK のバージョンを上げるだけで、依存座標を直接意識する必要はない
- JitPack はリポジトリをアーカイブ・削除しても公開済みの成果物を配布し続けるため、既存バージョンを使うビルドは壊れない。新バージョンに追従するには座標の変更が必要になる
- 外部利用者 (例: zztkm/ayame-android-sdk) はそれぞれの判断で追随する

#### 手作業の削減量

- 現行の手作業は 4 つある
  - `prepareAar.sh` の `VERSION` の更新
  - `CHANGES.md` への追記
  - タグの作成と push
  - JitPack への反映確認
- 案 1 で 4 つとも不要になる。 webrtc-build のリリース作業は従来どおりで、 AAR の成果物追加と Release の公開手順は実装時に 1 回だけ対応する

#### JitPack の制約

- JitPack は登録済みリポジトリの新しいバージョンを検知して自動ビルドする。 `shiguredo-webrtc-android` ではタグ push から約 1〜15 分でビルドが始まることを確認した
  - 例: `155.8059.1.0` は 1 分 41 秒後、 `153.8010.0.1` は 14 分 1 秒後。 webhook は設定されておらず、 JitPack の定期チェックによるものとみられる
- webrtc-build の Release 成果物は全プラットフォームのビルド完了後に作られるため、タグ push から約 1 時間かかる
  - 実測: `m155.8059.1.0` は 1 時間 7 分、 `m154.8037.1.2` は 1 時間 18 分
- このため、 Release を draft として作成して全成果物のアップロード後に publish し、 JitPack に完全な Release だけを検知させる
- 同一 AAR にサフィックス付きの別バージョンを付ける運用はできなくなる。 webrtc-build のリリース番号を進めた新しいタグを切ることはできるが、その場合は全プラットフォームの再リリースになる (サフィックス付きのタグは `79.5.0` 以降は使われていない)

### 未検証の点

- 実ビルドでの確認が必要な項目は 0031 で対応する
  - `m` 付きタグが JitPack のバージョンとして通ること
  - org 名にハイフンを含む groupId (`com.github.shiguredo-webrtc-build`) が通ること
  - JitPack が新しいタグと Release のどちらを契機にビルドを検知するか
  - JitPack のビルドをリクエストで起動できるか。起動できない場合は publish 後の手動リクエストを手順化する

### 実装 issue

- 0031 JitPack を webrtc-build に追加して Android の AAR を公開する (対象: webrtc-build)
- 0032 Sora Android SDK の libwebrtc の依存座標を webrtc-build に移行する (対象: shiguredo/sora-android-sdk)
- 0033 shiguredo-webrtc-android をアーカイブする (対象: shiguredo/shiguredo-webrtc-android)
- 0032 と 0033 は 0031 の完了後に実施する。 0032 の移行先バージョンは 0031 の完了後に作られる webrtc-build の Release になる
- 対象リポジトリが webrtc-build 以外の issue は、実装着手時にそれぞれのリポジトリの issue 管理へ移すことを検討する

### 補足

- sora-android-sdk の 0047 は pending 理由 (配布まわりの方針が未決) が本 issue の結論で解消するため、必要なら更新する