# 変更履歴

- RELEASE
  - タグの追加
- UPDATE
  - 下位互換がある変更
- ADD
  - 下位互換がある追加
- CHANGE
  - 下位互換のない変更
- FIX
  - バグ修正

VERSION ファイルを上げただけの場合は変更履歴記録は不要。
パッチやビルドの変更、リリース時のみ記録すること。

- タイムライン型の変更履歴
- 必ず一番上に書く
- リリース時には [RELEASE] を追加する

## 例

- 2024-03-01 [RELEASE] m127.0.0.1
  - @voluntas
- 2023-02-01 [ADD] h266.patch を追加
  - @melpon
- 2022-01-01 [FIX] h265.patch のバグを修正
  - @melpon

## タイムライン
- 2024-11-25 [RELEASE] m131.6778.3.1
  - @melpon
- 2024-11-25 [FIX] `*.inc` ファイルもリリースに含める
  - @melpon
- 2024-11-25 [RELEASE] m131.6778.3.0
  - @torikizi
- 2024-11-24 [ADD] windows_add_optional.patch を追加
  - @tnoho
- 2024-11-24 [FIX] arm_neon_sve_bridge.patch を修正
  - m131 で libvpx 向けだった arm_neon_sve_bridge.patch と同様の対応が libaom にも必要になったため修正
  - @tnoho
- 2024-10-18 [RELEASE] m129.6668.1.1
  - @melpon
- 2024-10-18 [ADD] fix_moved_function_call.patch を追加
  - @melpon
