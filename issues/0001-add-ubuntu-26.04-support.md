# Ubuntu 26.04 (armv8 / x86_64) 対応を追加する

- Priority: High
- Created: 2026-07-15
- Completed: {YYYY-MM-DD}
- Model: Opus 4.7
- Branch: feature/add-ubuntu-26.04-support
- Polished: {YYYY-MM-DD}

## 目的

Ubuntu 26.04 LTS が 2026 年 4 月にリリースされたことに伴い、既存の Ubuntu 20.04 / 22.04 / 24.04 と同様のビルドターゲットとして `ubuntu-26.04_armv8` と `ubuntu-26.04_x86_64` を追加し、libwebrtc のビルド済みバイナリを提供できるようにする。

## 優先度根拠

High とする。理由:

- Ubuntu 26.04 は 2026 年 4 月リリースの LTS であり、ユーザー側の移行が今後進むタイミングである
- 24.04 系のバイナリは新環境でも動作する可能性が高いが、ネイティブな 26.04 環境向けバイナリを早期に提供することで、依存ライブラリ (libstdc++ 等) のバージョン差異による不具合を回避したい
- Jetson 系のサポート (armv8 側) は組み込み案件で LTS 追従が求められることが多い

## 現状

現在サポートしている Ubuntu 系ターゲットは以下の通り (README.md および run.py の `TARGETS` より):

- `ubuntu-20.04_armv8` (Jetson 系。armv8 のみ)
- `ubuntu-22.04_armv8`
- `ubuntu-22.04_x86_64`
- `ubuntu-24.04_armv8`
- `ubuntu-24.04_x86_64`

`ubuntu-26.04_*` は未対応。

24.04 対応時に触られている主なコード箇所を確認済み:

- `run.py`
  - `PATCHES` 辞書 (run.py:353, run.py:377): 24.04 用エントリあり
  - `MULTISTRAP_CONFIGS` (run.py:625): 24.04 armv8 用エントリあり
  - `gn_args` を組み立てる分岐 (run.py:1075-1094): armv8 系と x86_64 系に 24.04 が含まれている
  - `TARGETS` (run.py:1403-1407): 24.04 armv8 / x86_64 が並んでいる
  - `check_target()` (run.py:1439-1455): armv8 リストと x86_64 バージョン判定に 24.04 が含まれている
- `multistrap/ubuntu-24.04_armv8.conf`: `suite=noble`、`packages=... libstdc++-13-dev ...` を指定
- `README.md` の「現在提供しているビルド」節: 24.04 系を明記
- `.github/workflows/build.yml`
  - `build-linux` matrix (build.yml:117-133): 24.04 系のエントリと runner 指定あり (`ubuntu-24.04`)
  - `create-release` の download 呼び出し (build.yml:215-229): 24.04 系のダウンロード指定あり

## 設計方針

24.04 対応時と同型のパターンを踏襲し、対象を `ubuntu-26.04_armv8` (Jetson 系および ARM64 向け) と `ubuntu-26.04_x86_64` の 2 つに絞って追加する。

以下の点を事前調査で確定させたうえで実装する:

1. **Ubuntu 26.04 の codename** (multistrap の `suite=` に指定する値。24.04 は `noble`、22.04 は `jammy`)
2. **libstdc++ の major バージョン** (`multistrap/ubuntu-26.04_armv8.conf` の `packages=` に指定する値。24.04 は `libstdc++-13-dev` を使用しているため、26.04 では GCC のデフォルトバージョンに合わせて `libstdc++-14-dev` あるいは `libstdc++-15-dev` になる想定)
3. **GitHub Actions runner の `ubuntu-26.04` 提供状況** (build.yml で `runs-on: ubuntu-26.04` が使えるかどうか。未提供なら暫定的に `ubuntu-24.04` runner でクロスビルドする)
4. **`scripts/apt_install_x86_64.sh` および `scripts/apt_install_arm.sh` の依存パッケージ** が 26.04 でも変わらず取得できるか

上記の調査結果を issue にコメント追記したうえでコード変更に着手する。

libwebrtc 側のパッチ (`patches/*.patch`) は 24.04 と同一セットで開始し、ビルドエラーが出た場合のみ差分対応を検討する (24.04 対応時と同様のアプローチ)。

## 完了条件

以下すべてが満たされること:

- `python3 run.py build ubuntu-26.04_armv8` が成功し、`libwebrtc.a` およびヘッダを含む `webrtc.ubuntu-26.04_armv8.tar.gz` が生成できる
- `python3 run.py build ubuntu-26.04_x86_64` が成功し、`libwebrtc.a` およびヘッダを含む `webrtc.ubuntu-26.04_x86_64.tar.gz` が生成できる
- GitHub Actions の `build-linux` ジョブに ubuntu-26.04 系 2 ターゲットが追加され、CI が緑になる
- `create-release` ジョブでリリースアーティファクトとして 26.04 系 2 ターゲットが配布される
- `README.md` の「現在提供しているビルド」節に `ubuntu-26.04_armv8` および `ubuntu-26.04_x86_64` が記載される
- `CHANGES.md` に `[ADD] Ubuntu 26.04 (armv8 / x86_64) 対応を追加する` エントリが記録される

## 解決方法

24.04 対応時と同型の差分を、以下の箇所に追加する。

### 新規ファイル

- `multistrap/ubuntu-26.04_armv8.conf`
  - `multistrap/ubuntu-24.04_armv8.conf` をベースにコピー
  - `suite=` を 26.04 の codename に差し替え
  - `packages=` の `libstdc++-13-dev` を 26.04 のデフォルト GCC メジャーバージョンに差し替え
  - その他のパッケージ (`libc6-dev libasound2-dev libpulse-dev libudev-dev libexpat1-dev libnss3-dev python-dev-is-python3 libgtk-3-dev`) は 26.04 でも同名で存在するか確認したうえで維持する

### `run.py` の修正

- `PATCHES` 辞書に `ubuntu-26.04_armv8` と `ubuntu-26.04_x86_64` を追加 (24.04 と同一パッチセットで開始)
- `MULTISTRAP_CONFIGS` に `ubuntu-26.04_armv8` を追加 (`arch="arm64"`, `triplet="aarch64-linux-gnu"`)
- `gn_args` を組み立てる armv8 系分岐 (run.py:1075-1093) の対象タプルに `ubuntu-26.04_armv8` を追加
- x86_64 系分岐 (run.py:1094) の対象タプルに `ubuntu-26.04_x86_64` を追加
- `TARGETS` リストに 2 ターゲットを追加
- `check_target()` の armv8 タプルに `ubuntu-26.04_armv8` を追加、x86_64 バージョン判定に `if target == "ubuntu-26.04_x86_64" and osver == "26.04": return True` を追加

### `.github/workflows/build.yml` の修正

- `build-linux` の `matrix.platform` に以下を追加
  - `- name: ubuntu-26.04_armv8` / `runs-on: ubuntu-26.04` (GitHub Actions runner が未対応なら暫定 `ubuntu-24.04`)
  - `- name: ubuntu-26.04_x86_64` / `runs-on: ubuntu-26.04` (同上)
- `create-release` の `./.github/actions/download` 呼び出しに以下を追加
  - `platform: ubuntu-26.04_armv8`
  - `platform: ubuntu-26.04_x86_64`

### ドキュメント・変更履歴

- `README.md` の「現在提供しているビルド」節に以下を追加
  - `- ubuntu-26.04_armv8`
  - `- ubuntu-26.04_x86_64`
- `CHANGES.md` の先頭に `- YYYY-MM-DD [ADD] Ubuntu 26.04 (armv8 / x86_64) 対応を追加する` を追加

### 動作確認

- ローカル (Ubuntu 24.04 x86_64) で `run.py build ubuntu-26.04_armv8` を実行し、multistrap による rootfs 取得と libwebrtc のクロスビルドが成功することを確認
- ローカル (Ubuntu 26.04 x86_64) で `run.py build ubuntu-26.04_x86_64` を実行し、ネイティブビルドが成功することを確認 (Ubuntu 26.04 環境が用意できない場合は Docker あるいは CI 実行で代替)
- CI 上でも `build-linux` が両ターゲットで成功することを確認
