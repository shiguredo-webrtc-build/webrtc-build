# shiguredo-webrtc-android をアーカイブする

- Created: 2026-09-25
- Completed: {YYYY-MM-DD}
- Branch: feature/remove-archive-shiguredo-webrtc-android
- Polished: {YYYY-MM-DD}

## 目的

AAR の配布を webrtc-build に統合した後、 `shiguredo/shiguredo-webrtc-android` をアーカイブして読み取り専用にする。

配布元が 2 つある状態を解消し、以後の libwebrtc 更新で `shiguredo-webrtc-android` 側の作業が発生しないことを明確にする。

対象リポジトリは `shiguredo/shiguredo-webrtc-android` である。

## 現状

- リポジトリには `prepareAar.sh` / `jitpack.yml` / `CHANGES.md` / `.github/workflows/release.yml` が残っている
- JitPack は `com.github.shiguredo:shiguredo-webrtc-android` として既存バージョンの AAR を配布し続けている
- JitPack はリポジトリをアーカイブ・削除しても公開済みの成果物を配布し続ける

## 設計方針

- 0031 (webrtc-build への JitPack 追加) と 0032 (Sora Android SDK の座標移行) の完了後にアーカイブする
- README に移行先の座標 (`com.github.shiguredo-webrtc-build:webrtc-build`) と移行の案内を記載してから、 GitHub の archive 機能で読み取り専用にする
- タグと Release は削除しない。既存バージョンのビルドは JitPack が配布し続けるため壊れないが、参照用に残す
- `shiguredo-webrtc-android` の既存バージョンを使い続ける下流はそのまま動作する。新バージョンに追従する場合は座標の変更が必要である

## 完了条件

- `shiguredo/shiguredo-webrtc-android` が archived になっている
- README に移行先の座標と移行の案内が記載されている
- 既存バージョン (`com.github.shiguredo:shiguredo-webrtc-android:<version>`) が JitPack から引き続き取得できる

## 解決方法

未着手