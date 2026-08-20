# add_license_dav1d.patch を削除する

- Created: 2026-08-19
- Completed: 2026-08-20
- Branch: feature/remove-add-license-dav1d-patch
- Polished: {YYYY-MM-DD}

## 目的

`patches/add_license_dav1d.patch` は、upstream に既に存在する dav1d のライセンスエントリを重複して追加する冗長なパッチになっているため、削除する。

## 現状

- `patches/add_license_dav1d.patch` は `tools_webrtc/libs/generate_licenses.py` の `LIB_TO_LICENSES_DICT` に `'dav1d': ['third_party/dav1d/LICENSE']` を追加する。
- このエントリは upstream の webrtc コミット d44badf409 (2022-07-04) で既に追加されている。パッチが追加する内容 (キー・値) は既存エントリと完全に同一のため、適用しても挙動は変わらない。
- パッチは `run.py` の全 15 ターゲットの `PATCHES` リストに登録されており、`patches/README.md` に解説がある。

参照: https://source.chromium.org/chromium/_/webrtc/src/+/d44badf40903097d0e25ea11da33345634c16d76

## 設計方針

- `patches/add_license_dav1d.patch` を削除する。
- `run.py` の全 15 ターゲットの `PATCHES` リストから `add_license_dav1d.patch` を削除する。
- `patches/README.md` の `add_license_dav1d.patch` の解説を削除する。

## 完了条件

- `patches/add_license_dav1d.patch` が削除されていること。
- `run.py` の全 15 ターゲットの `PATCHES` リストに `add_license_dav1d.patch` が存在しないこと。
- `patches/README.md` に `add_license_dav1d.patch` の解説が存在しないこと。
- パッチ削除後も `LIB_TO_LICENSES_DICT` に dav1d のエントリが残っており、ライセンス生成で dav1d が欠落しないこと (upstream のエントリによる)。

## 解決方法

- `git rm` で `patches/add_license_dav1d.patch` を削除した。
- `run.py` の `PATCHES` 辞書の全 15 ターゲットのリストから `add_license_dav1d.patch` を削除した。
- `patches/README.md` から `add_license_dav1d.patch` の解説節を削除した。

dav1d のライセンスエントリは upstream のコミット d44badf409 に既に存在するため、パッチ削除後もライセンス生成で dav1d が欠落しないことは設計方針の通り維持される。
