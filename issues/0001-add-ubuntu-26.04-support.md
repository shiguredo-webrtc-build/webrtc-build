# Ubuntu 26.04 (armv8 / x86_64) 対応を追加する

- Priority: High
- Created: 2026-07-15
- Completed: {YYYY-MM-DD}
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
   - `apt_install_x86_64.sh` のパッケージ (git, ninja-build, pkg-config, rsync, python3, binutils, curl, unzip, wget, xz-utils, locales) はすべて runner にプリインストール済み
4. **multistrap の `components` 設定**: `main universe` (24.04 と同様)
   - `resolute` では `main restricted universe multiverse` が利用可能
   - 全 multistrap パッケージが `resolute/main/binary-arm64` に存在確認済み
5. **ubuntu-keyring の署名鍵**: `--no-auth` では不十分
   - `scripts/apt_install_arm.sh` の multistrap sed パッチ (`Acquire::AllowInsecureRepositories=true`) が必須
   - CI (ubuntu-24.04 runner) 上でも同様の対応が必要

## 現状

現在サポートしている Ubuntu 系ターゲット (README.md および run.py `TARGETS` より):

- `ubuntu-20.04_armv8` (Jetson Xavier NX, AGX Xavier, Orin NX, AGX Orin)
- `ubuntu-22.04_armv8` (Jetson AGX Orin, Orin Nano)
- `ubuntu-22.04_x86_64`
- `ubuntu-24.04_armv8`
- `ubuntu-24.04_x86_64`

`ubuntu-26.04_*` は未対応。

24.04 対応時に触られている主なコード箇所:

- `run.py` の `PATCHES` 辞書、`MULTISTRAP_CONFIGS`、`gn_args` 分岐、`TARGETS`、`check_target()`
- `multistrap/ubuntu-24.04_armv8.conf`: `suite=noble`, `packages=... libstdc++-13-dev ...`, `components=main universe`
- `README.md` の「現在提供しているビルド」節: 24.04 系を明記
- `DEVELOPMENT.md` L97-101: x86_64 ターゲットのビルドに必要なホスト OS バージョンがハードコードされている
- `.github/workflows/build.yml` の `build-linux` matrix および `create-release` の download 呼び出し: 24.04 系のエントリあり

## 設計方針

24.04 対応時と同型のパターンを踏襲し、対象を `ubuntu-26.04_armv8` と `ubuntu-26.04_x86_64` の 2 つに絞って追加する。

libwebrtc 側のパッチ (`patches/*.patch`) は既存の全 Ubuntu 系ターゲット (20.04/22.04/24.04) と同一セットを使用する。ビルドエラーが出た場合のみ差分対応を検討する (24.04 対応時と同様のアプローチ)。

### armv8 ターゲットのビルド方針

armv8 ターゲットはクロスコンパイルのためホスト OS バージョンに依存しない。`ubuntu-26.04_armv8` は `ubuntu-24.04` runner 上で multistrap により 26.04 の rootfs を取得してクロスビルドする。

### x86_64 ターゲットのビルド方針

x86_64 ターゲットは `check_target()` (run.py:1449-1455) がホスト OS バージョンの厳密一致を要求する。`ubuntu-26.04` runner が public preview として利用可能であるため、`runs-on: ubuntu-26.04` で直接ビルドする。

## 完了条件

- `python3 run.py build ubuntu-26.04_armv8` が成功し、`webrtc.ubuntu-26.04_armv8.tar.gz` が生成できる
  - これには multistrap による 26.04 armv8 rootfs の正常取得が含まれる
- `python3 run.py build ubuntu-26.04_x86_64` が成功し、`webrtc.ubuntu-26.04_x86_64.tar.gz` が生成できる
- GitHub Actions の `build-linux` ジョブに 26.04 系 2 ターゲットが追加され、CI が緑になる
- `create-release` ジョブでリリースアーティファクトとして 26.04 系 2 ターゲットが配布される
- `README.md` の「現在提供しているビルド」節に `ubuntu-26.04_armv8` および `ubuntu-26.04_x86_64` が記載される
- `DEVELOPMENT.md` L97-101 に `ubuntu-26.04_x86_64` のビルドに必要なホスト OS バージョンが追記される
- `CHANGES.md` に `[ADD] Ubuntu 26.04 (armv8 / x86_64) 対応を追加する` エントリが記録される

## 解決方法

### 新規ファイル

- `multistrap/ubuntu-26.04_armv8.conf`
  - `multistrap/ubuntu-24.04_armv8.conf` をベースにコピー
  - `suite=resolute`
  - `packages=libc6-dev libstdc++-15-dev libasound2-dev libpulse-dev libudev-dev libexpat1-dev libnss3-dev python-dev-is-python3 libgtk-3-dev`
  - `components=main universe`
  - `source=http://ports.ubuntu.com`

### `run.py` の修正

- `PATCHES` 辞書に `ubuntu-26.04_armv8` と `ubuntu-26.04_x86_64` を追加 (既存の全 Ubuntu 系ターゲットと同一パッチセット)
- `MULTISTRAP_CONFIGS` に `ubuntu-26.04_armv8` を追加 (`arch="arm64"`, `triplet="aarch64-linux-gnu"`)
- `gn_args` を組み立てる armv8 系分岐 (run.py:1075-1093) の修正 (**2 箇所**):
  - 外側タプル (`elif target in (...)`): `ubuntu-26.04_armv8` を追加
  - 内側 `arm64_set` タプル: `ubuntu-26.04_armv8` を追加 (漏れると `target_cpu` が `"arm"` と誤判定される)
- x86_64 系分岐の外側タプル (run.py:1094-1097): `ubuntu-26.04_x86_64` を追加 (**1 箇所**)
- `TARGETS` リストに 2 ターゲットを追加
- `check_target()` の修正:
  - クロスコンパイル対象タプル (run.py:1439-1446) に `ubuntu-26.04_armv8` を追加
  - x86_64 バージョン判定 (run.py:1449-1455) に `if target == "ubuntu-26.04_x86_64" and osver == "26.04": return True` を追加
- `add_path(dir)` を `add_path(dir, is_after=True)` に変更 (5 箇所)
  - depot_tools 同梱の ninja ラッパーよりシステム ninja を優先させるため

### `.github/workflows/build.yml` の修正

- `build-linux` の `matrix.platform` に以下を追加:
  - `- name: ubuntu-26.04_armv8` / `runs-on: ubuntu-24.04`
  - `- name: ubuntu-26.04_x86_64` / `runs-on: ubuntu-26.04`
- `create-release` の `./.github/actions/download` 呼び出しに以下を追加:
  - `platform: ubuntu-26.04_armv8`
  - `platform: ubuntu-26.04_x86_64`

### ドキュメント・変更履歴

- `README.md` の「現在提供しているビルド」節に `ubuntu-26.04_armv8` および `ubuntu-26.04_x86_64` を追加
- `DEVELOPMENT.md` の制限節に `ubuntu-26.04_x86_64 の場合は Ubuntu 26.04 が必要` を追加
- `CHANGES.md` の先頭に `[ADD] Ubuntu 26.04 (armv8 / x86_64) 対応を追加する` を追加

## 動作確認

- `python3 run.py build ubuntu-26.04_x86_64` が成功すること (Ubuntu 26.04 ホスト上)
- `python3 run.py build ubuntu-26.04_armv8` が成功すること
  - multistrap による `resolute` rootfs の正常取得を含む
  - 26.04 ホストでは `multistrap` がリポジトリに存在しないため、22.04 の .deb から手動インストールが必要 (`sudo scripts/apt_install_arm.sh` 相当 + sed パッチ)
- 生成された `libwebrtc.a` の依存ライブラリを `readelf -d` 等で確認し、26.04 のライブラリにリンクされていることを確認
- CI 上でも `build-linux` が両ターゲットで成功することを確認

## 後方互換性

- 本変更は新規ターゲットの追加のみであり、既存ターゲットには影響しない
- `COMMON_GN_ARGS` (run.py:682-697) は変更しない
- 26.04 系のパッチセットは既存 Ubuntu 系と同一のため、既存パッチへの変更は発生しない
