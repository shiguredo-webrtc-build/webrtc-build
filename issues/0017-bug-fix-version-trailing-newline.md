# VERSION の末尾改行が無いと VERSIONS が壊れて下流のビルドが失敗する

- Created: 2026-09-10
- Completed: {YYYY-MM-DD}
- Branch: feature/fix-version-trailing-newline
- Polished: {YYYY-MM-DD}

## 目的

`VERSION` ファイルに末尾改行が無い場合でも、パッケージ内の `VERSIONS` が壊れないようにする。下流の Sora C++ SDK のビルドが失敗するのを防ぐ。

## 現状

確認対象は `VERSION` の `WEBRTC_BUILD_VERSION=154.8037.1.1` である。

- `run.py` の `generate_version_info` は、`VERSION` を `webrtc_package_dir` の `VERSIONS` にコピーした後、`WEBRTC_SRC_*` の URL とコミットを `writelines` で追記する
- 追記する各要素には `\n` を付与しているが、コピー元の `VERSION` の末尾改行は保証していない
- `VERSION` の末尾に改行が無い場合、コピー後の最終行と最初の追記行が結合し、`WEBRTC_BUILD_VERSION=154.8037.1.1WEBRTC_SRC_URL=...` のように 1 行に複数の `=` を含む壊れた行になる
- 下流の Sora C++ SDK は `buildbase.py` の `read_version_file` で `VERSIONS` を行単位に読み、`[a, b] = line.split("=", 2)` として `KEY=VALUE` を 2 要素に分解する。壊れた行では要素数が 3 以上になり `ValueError: too many values to unpack` でビルドが失敗する
- m107.5304.4.0 のビルドで実際に CI が失敗している。参考: https://github.com/shiguredo/sora-cpp-sdk/actions/runs/3294248600
- 現在の `VERSION` は末尾に改行があるが、生成側で保証していないため再発し得る

## 設計方針

- `generate_version_info` で `VERSION` の内容を読み、末尾が改行で終わっていなければ改行を補ってから `VERSIONS` を書き出す
- コピーと追記を分けず、`VERSION` の内容と追記行を同一の出力へ書き込む形にして、途中で改行が欠落しないようにする
- 下流の `read_version_file` は壊れた行を復元できないため、生成側で `KEY=VALUE` の行が必ず改行で区切られることを保証する

## 不採用とした設計案

- `prek` の `end-of-file-fixer` で `VERSION` の末尾改行を強制する案。webrtc-build に `prek` が導入されておらず、またビルド成果物である `VERSIONS` は追跡対象外のため採用しない

## 完了条件

- `VERSION` の末尾改行の有無に関わらず、生成される `VERSIONS` の各行が `KEY=VALUE` として 2 要素に分解できること
- 下流の Sora C++ SDK の `read_version_file` で `ValueError` にならないこと
- `CHANGES.md` に修正内容を追記していること

## 解決方法

未着手
