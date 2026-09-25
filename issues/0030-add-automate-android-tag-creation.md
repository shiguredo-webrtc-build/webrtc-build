# webrtc-build の Release を検知して Android のタグ作成を自動化する

- Created: 2026-09-25
- Completed: {YYYY-MM-DD}
- Branch: feature/add-automate-android-tag-creation
- Polished: {YYYY-MM-DD}

## 目的

`shiguredo/shiguredo-webrtc-android` のタグ作成、 `CHANGES.md` への追記、 JitPack への反映確認を自動化し、 libwebrtc 更新時の手作業をなくす。

現状は下流 SDK が libwebrtc を更新するたびに、 `prepareAar.sh` の `VERSION` の更新、 `CHANGES.md` への追記、タグの作成と push、 JitPack への反映確認を手作業で行っている。 webrtc-build の Release を契機にこれらを自動化する。

対象リポジトリは `shiguredo/shiguredo-webrtc-android` である。

## 現状

- タグは下流が必要とするバージョンだけ手作業で作られており、 webrtc-build の全 Release には作られていない
  - 2026-09-25 には下流向けに `151.7922.0.0` / `152.7977.0.3` / `153.8010.0.1` がまとめて作られている
- `prepareAar.sh` は `VERSION` をハードコードしており、リリースごとに書き換えている
- `CHANGES.md` はバージョンごとに webrtc-build の Release URL を追記している
- `.github/workflows/release.yml` はタグ push を契機に Release を作成する
- JitPack は登録済みリポジトリの新しいタグを人手を介さず検知してビルドする (タグ push から約 1〜15 分)
- リポジトリをまたぐトークンは設定されていない

## 設計方針

- `prepareAar.sh` の `VERSION` は JitPack がビルド時に設定する環境変数 `VERSION` (タグ名) を使い、リリースごとの書き換えをなくす
- `shiguredo/shiguredo-webrtc-android` に定期実行の workflow を追加する
  - webrtc-build の Release から `webrtc.android_sdk.tar.gz` を持ち、 `m` で始まるタグで、対応する android タグがまだ無いものを探す
  - `CHANGES.md` に追記して master にコミットし、そのコミットに `m` を除いたタグを作成する。複数バージョンをまとめて処理する場合は 1 コミットにまとめる
  - `GITHUB_TOKEN` でのタグ push では `release.yml` が起動しないため、 Release の作成も同じ workflow で行う
  - `release.yml` は削除する。 NOTICE のアップロードも workflow が引き継ぐ
  - `workflow_dispatch` でもバージョンを指定できるようにし、任意のバージョンを後から追加できるようにする
- 導入後の新規 Release のみを対象とし、既存の不足分は遡らない
- リポジトリをまたぐトークンは使わない (webrtc-build の公開 Release を読むだけ)

## 完了条件

- webrtc-build の新しい Release に対して、人手を介さずに android タグ、 Release、 `CHANGES.md` が作成される
- JitPack から対応するバージョンの AAR が取得できる
- 下流 SDK の libwebrtc 更新で `shiguredo-webrtc-android` 側の手作業が発生しない

## 解決方法

未着手