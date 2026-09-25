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

案 2 と案 3 を組み合わせて採用する。案 1 は採用しない。

### 採用する方式

- 案 2: AAR の取得元を webrtc-build の Release に一本化する
  - `shiguredo/shiguredo-webrtc-android` の `prepareAar.sh` は `https://github.com/shiguredo-webrtc-build/webrtc-build/releases/download/m${VERSION}/webrtc.android_sdk.tar.gz` を取得し、 展開して `webrtc/aar/libwebrtc.aar` を取り出す
  - `.github/workflows/release.yml` は AAR のアップロードをやめる。 NOTICE はライセンス通知を配布点に残すためアップロードを続ける
  - webrtc-build 側の変更は不要である。 `webrtc.android_sdk.tar.gz` の中に `webrtc/aar/libwebrtc.aar` が含まれており、 AAR 単体を Release に追加しなくても取得元を一本化できる
  - 同じ AAR を 2 リポジトリの Release に保存する状態が解消され、下流の依存座標とバージョンは変わらない
- 案 3: タグ作成と JitPack への反映を自動化する
  - `prepareAar.sh` は JitPack がビルド時に設定する環境変数 `VERSION` (タグ名) を使い、リリースごとの `VERSION` の書き換えをなくす
  - `shiguredo/shiguredo-webrtc-android` に定期実行の workflow を追加し、 webrtc-build の新しい Release (対応する android タグが無く `webrtc.android_sdk.tar.gz` を持つもの) を検知して `m` を除いたタグを作成する。 `CHANGES.md` への追記と Release の作成も同じ workflow で行う
  - タグ作成後に JitPack が自動ビルドするため、反映確認を人手で行う必要がなくなる
  - リポジトリをまたぐトークンは不要である (webrtc-build の公開 Release を読むだけ)

### 判断根拠

#### 下流への影響

- 案 1 は依存座標を `com.github.shiguredo:shiguredo-webrtc-android` から `com.github.shiguredo-webrtc-build:webrtc-build` へ、 バージョン表記を `155.8059.1.0` から `m155.8059.1.0` へ変更する
  - Sora Android SDK の `gradle/libs.versions.toml` と `skills/sora-android-sdk/SKILL.md`、 外部利用者 (`zztkm/ayame-android-sdk` など) の追随が必要になる
  - JitPack はリポジトリを削除しても公開済みの成果物を配布し続けるため既存バージョンは壊れないが、新バージョンに追従する利用者全員に変更を強いる
- 案 2 と案 3 は座標もバージョンも変えないため、下流の変更は不要である

#### 手作業の削減量

- 現行の手作業は 4 つある
  - `prepareAar.sh` の `VERSION` の更新
  - `CHANGES.md` への追記
  - タグの作成と push
  - JitPack への反映確認
- 案 2 と案 3 の組み合わせで 4 つとも不要にできる
- 案 1 は下流の座標変更に加えて、下記の JitPack ビルドの競合によりリリースごとの手動リビルドが必要になり、手作業が残る

#### JitPack の制約

- JitPack は登録済みリポジトリの新しいタグを人手を介さず検知してビルドする。 `shiguredo-webrtc-android` ではタグ push から約 1〜15 分でビルドが始まることを確認した
  - 例: `155.8059.1.0` は 1 分 41 秒後、 `153.8010.0.1` は 14 分 1 秒後。 webhook は設定されておらず、 JitPack の定期チェックによるものとみられる
- webrtc-build の Release 成果物は全プラットフォームのビルド完了後に作られるため、タグ push から約 1 時間かかる
  - 実測: `m155.8059.1.0` は 1 時間 7 分、 `m154.8037.1.2` は 1 時間 18 分
- このため案 1 では、 JitPack がビルドを始める時点で `webrtc.android_sdk.tar.gz` がまだ存在せず、初回ビルドが失敗するおそれがある
  - JitPack のビルドを起動する公開 API はドキュメント化されておらず、 7 日以内の手動リビルド (jitpack.io での再リクエスト) が必要になる
  - リリース完了後に別のタグを作って JitPack にビルドさせる回避策もあるが、タグが 2 本になりバージョン表記も複雑になる
- JitPack は 1 リポジトリ 1 パッケージのため、将来 AAR 以外の配布物を増やしたい場合の拡張性が無い

### 未検証の点

- 案 1 で必要になる `m` 付きタグが JitPack のバージョンとして通ることと、 org 名にハイフンを含む groupId (`com.github.shiguredo-webrtc-build`) が通ることは、実ビルドでの確認を行っていない
- JitPack が新しいタグと Release のどちらを契機にビルドを検知するかは未検証である。どちらの場合も、 webrtc-build では成果物のアップロード完了前にビルドが始まる可能性がある
- どちらも案 1 固有の論点である。採用する案 2 と案 3 は、現行の JitPack の使い方 (タグ名をバージョンとしてカスタムコマンドで AAR を登録する) の範囲内で成立する

### 実装 issue

- 0029 AAR の取得元を webrtc-build の Release に変更する (対象: shiguredo/shiguredo-webrtc-android)
- 0030 webrtc-build の Release を検知して Android のタグ作成を自動化する (対象: shiguredo/shiguredo-webrtc-android)
- `shiguredo/shiguredo-webrtc-android` は GitHub Issues を無効にしているため、実装 issue は本リポジトリの issues/ に起票する

### 補足

- 下流 SDK の依存座標の変更と `shiguredo/shiguredo-webrtc-android` の廃止は、案 2 と案 3 では不要になるため別 issue は起票しない
- Sora Android SDK 側の libwebrtc 更新作業の自動化は sora-android-sdk の 0047 で扱う