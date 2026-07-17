# Ubuntu 26.04 (armv8 / x86_64) 対応を追加する

- Priority: High
- Created: 2026-07-15
- Completed: 2026-07-15
- Model: Opus 4.7
- Branch: feature/add-ubuntu-26.04-support
- Polished: 2026-07-15

## 目的

Ubuntu 26.04 LTS が 2026 年 4 月にリリースされたことに伴い、既存の Ubuntu 20.04 / 22.04 / 24.04 と同様のビルドターゲットとして `ubuntu-26.04_armv8` と `ubuntu-26.04_x86_64` を追加し、libwebrtc のビルド済みバイナリを提供できるようにする。

## 優先度根拠

High とする。理由:

- Ubuntu 26.04 は 2026 年 4 月リリースの LTS であり、ユーザー側の移行が今後進むタイミングであるため、予防的措置として早期に対応する
- 24.04 系のバイナリは libstdc++ の ABI 互換性により新環境でも動作する可能性が高いが、ネイティブな 26.04 環境向けバイナリを提供することで、将来的なバージョン差異による不具合リスクを排除する

## 調査結果

実装前に以下の項目を調査・確定した:

1. **Ubuntu 26.04 の codename**: `resolute` (Resolute Raccoon)
   - <https://changelogs.ubuntu.com/meta-release> で確認
2. **libstdc++ のパッケージ名**: `libstdc++-15-dev`
   - 26.04 のデフォルト GCC は 15.2.0
   - `http://ports.ubuntu.com/ubuntu-ports/dists/resolute/main/binary-arm64/Packages` で存在確認済み
3. **GitHub Actions runner の `ubuntu-26.04`**: **利用可能** (public preview)
   - デフォルト Python 3.14.4、ninja 1.13.2 プリインストール
   - `apt_install_x86_64.sh` の主要パッケージはすべて runner にプリインストール済み
4. **multistrap が `resolute` リポジトリに存在しない**
   - 全コンポーネント (`main`, `universe`, `multiverse`, `restricted`) で不在
   - `noble` (24.04) の `universe` には存在
   - この問題を契機に `sysroot_builder.py` による独自実装へ移行 (別 PR #160)
5. **ubuntu-keyring の署名鍵**
   - `signed_by` に `/usr/share/keyrings/ubuntu-archive-keyring.gpg` を指定することで署名検証に対応

## 現状

現在サポートしている Ubuntu 系ターゲット (README.md および run.py `TARGETS` より):

- `ubuntu-20.04_armv8` (Jetson Xavier NX, AGX Xavier, Orin NX, AGX Orin)
- `ubuntu-22.04_armv8` (Jetson AGX Orin, Orin Nano)
- `ubuntu-22.04_x86_64`
- `ubuntu-24.04_armv8`
- `ubuntu-24.04_x86_64`

`ubuntu-26.04_*` は未対応。

24.04 対応時に触られている主なコード箇所:

- `run.py` の `PATCHES` 辞書、`SYSROOT_CONFIGS`、`gn_args` 分岐、`TARGETS`、`check_target()`
- `sysroot/ubuntu-24.04_armv8.json`: `suite=noble`, `libstdc++-13-dev`, `components=main universe`
- `README.md` の「現在提供しているビルド」節: 24.04 系を明記
- `DEVELOPMENT.md` L97-101: x86_64 ターゲットのビルドに必要なホスト OS バージョンがハードコードされている
- `.github/workflows/build.yml` の `build-linux` matrix および `create-release` の download 呼び出し: 24.04 系のエントリあり

## 設計方針

24.04 対応時と同型のパターンを踏襲し、対象を `ubuntu-26.04_armv8` と `ubuntu-26.04_x86_64` の 2 つに絞って追加する。

libwebrtc 側のパッチ (`patches/*.patch`) は既存の全 Ubuntu 系ターゲット (20.04/22.04/24.04) と同一セットを使用する。ビルドエラーが出た場合のみ差分対応を検討する。

### armv8 ターゲットのビルド方針

armv8 ターゲットはクロスコンパイルのためホスト OS バージョンに依存しない。`ubuntu-26.04_armv8` は `ubuntu-24.04` runner 上で `sysroot_builder.py` により `resolute` の rootfs を取得してクロスビルドする。

`sysroot_builder.py` は `debootstrap` 相当の独自実装で、`sysroot/ubuntu-26.04_armv8.json` に定義されたパッケージを取得し、署名検証も行う。multistrap への依存は廃止された。

### x86_64 ターゲットのビルド方針

x86_64 ターゲットは `check_target()` (run.py:1449-1455) がホスト OS バージョンの厳密一致を要求する。`ubuntu-26.04` runner が public preview として利用可能であるため、`runs-on: ubuntu-26.04` でネイティブビルドする。

## 完了条件

- `python3 run.py build ubuntu-26.04_armv8` が成功し、`webrtc.ubuntu-26.04_armv8.tar.gz` が生成できる
  - これには `sysroot_builder.py` による `resolute` arm64 rootfs の正常取得が含まれる
- `python3 run.py build ubuntu-26.04_x86_64` が成功し、`webrtc.ubuntu-26.04_x86_64.tar.gz` が生成できる
- GitHub Actions の `build-linux` ジョブに 26.04 系 2 ターゲットが追加され、CI が緑になる
- `create-release` ジョブでリリースアーティファクトとして 26.04 系 2 ターゲットが配布される
- `README.md` の「現在提供しているビルド」節に `ubuntu-26.04_armv8` および `ubuntu-26.04_x86_64` が記載される
- `DEVELOPMENT.md` に `ubuntu-26.04_x86_64` のビルド制限が追記される
- `CHANGES.md` に `[ADD] Ubuntu 26.04 (armv8 / x86_64) ビルドを追加する` エントリが記録される

## 解決方法

### 新規ファイル

- `sysroot/ubuntu-26.04_armv8.json`
  - `name`: `ubuntu-26.04_armv8`
  - `arch`: `arm64`, `triplet`: `aarch64-linux-gnu`
  - `packages`: `libc6-dev`, `libstdc++-15-dev`, `libasound2-dev`, `libpulse-dev`, `libudev-dev`, `libexpat1-dev`, `libnss3-dev`, `python-dev-is-python3`, `libgtk-3-dev`
  - `repositories`: `url=https://ports.ubuntu.com/ubuntu-ports`, `suite=resolute`, `components=["main", "universe"]`
  - `signed_by`: `/usr/share/keyrings/ubuntu-archive-keyring.gpg`

### `run.py` の修正

- `add_path` 関数のデフォルト値を `is_after=True` に変更 (run.py:87)
  - depot_tools 同梱の ninja ラッパーが CIPD 経由での本体ダウンロードに失敗する問題を回避
  - システム ninja (`/usr/bin/ninja`, apt の `ninja-build` パッケージ) が優先される
  - depot_tools 専用ツール (`gn`, `gclient`, `fetch`) はシステムに存在しないため、PATH 末尾でも `shutil.which` で解決される
- `PATCHES` 辞書に `ubuntu-26.04_armv8` と `ubuntu-26.04_x86_64` を追加 (既存の全 Ubuntu 系ターゲットと同一パッチセット)
- `SYSROOT_CONFIGS` に `ubuntu-26.04_armv8` エントリを追加
- `gn_args` を組み立てる armv8 系分岐の修正 (**2 箇所**):
  - 外側タプル (`elif target in (...)`): `ubuntu-26.04_armv8` を追加
  - 内側 `arm64_set` タプル: `ubuntu-26.04_armv8` を追加 (漏れると `target_cpu` が `"arm"` と誤判定される)
- x86_64 系分岐の外側タプル: `ubuntu-26.04_x86_64` を追加 (**1 箇所**)
- `TARGETS` リストに 2 ターゲットを追加
- `check_target()` の修正:
  - クロスコンパイル対象タプルに `ubuntu-26.04_armv8` を追加
  - x86_64 バージョン判定に `if target == "ubuntu-26.04_x86_64" and osver == "26.04": return True` を追加

### `.github/workflows/build.yml` の修正

- `build-linux` の `matrix.platform` に以下を追加:
  - `- name: ubuntu-26.04_armv8` / `runs-on: ubuntu-24.04` (クロスコンパイルのため)
  - `- name: ubuntu-26.04_x86_64` / `runs-on: ubuntu-26.04`
- `create-release` の `./.github/actions/download` 呼び出しに以下を追加:
  - `platform: ubuntu-26.04_armv8`
  - `platform: ubuntu-26.04_x86_64`

### `scripts/apt_install_arm.sh` の修正

multistrap 廃止に伴い、以下を変更:

- インストールパッケージから `multistrap` と `software-properties-common` を削除
- `ca-certificates`, `debian-archive-keyring`, `ubuntu-keyring` を追加 (パッケージ署名検証用)
- Ubuntu 18.04 向け workaround (`ppa:ubuntu-toolchain-r/test`, multistrap sed パッチ) を削除

### ドキュメント・変更履歴

- `README.md` の「現在提供しているビルド」節に `ubuntu-26.04_armv8` および `ubuntu-26.04_x86_64` を追加
- `DEVELOPMENT.md` の制限節に `ubuntu-26.04_x86_64 の場合は Ubuntu 26.04 が必要` を追加
- `DEVELOPMENT.md` に `sysroot` サブコマンドの説明を追加 (`python3 run.py sysroot <target>`)
- `CHANGES.md` に `[ADD] Ubuntu 26.04 (armv8 / x86_64) ビルドを追加する` と `[UPDATE] ARM 向け sysroot 生成を独自実装へ移行する` を追加

## 動作確認

- `python3 run.py build ubuntu-26.04_x86_64` が成功すること (Ubuntu 26.04 ホスト上)
- `python3 run.py sysroot ubuntu-26.04_armv8` が成功し、`resolute` arm64 rootfs が正常に取得できること
- `python3 run.py build ubuntu-26.04_armv8` が成功すること (クロスコンパイル)
- 生成された `libwebrtc.a` の依存ライブラリを `readelf -d` 等で確認し、26.04 のライブラリにリンクされていることを確認
- CI 上でも `build-linux` が両ターゲットで成功することを確認

## 後方互換性

- 本変更は新規ターゲットの追加のみであり、既存ターゲットには影響しない
- `COMMON_GN_ARGS` (run.py:682-697) は変更しない
- 26.04 系のパッチセットは既存 Ubuntu 系と同一のため、既存パッチへの変更は発生しない
- `add_path(is_after=True)` は全ターゲットに適用されるが、depot_tools 専用ツールは引き続き PATH 末尾から解決されるため安全
