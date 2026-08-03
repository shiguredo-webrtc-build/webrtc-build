# libwebrtc-update-check

libwebrtc のアップデートを検知し、ビルドが壊れていないか、パッチが当たるかを
LLM (openai Python SDK) を利用して確認するエージェント。

## 前提

- uv がインストールされていること
- 環境変数の設定 (下記参照)

## 環境変数

| 変数名 | 必須 | 説明 |
|---|---|---|
| `OPENAI_API_KEY` | 必須 | OpenAI 互換 API の API キー |
| `OPENAI_BASE_URL` | 必須 | OpenAI 互換 API のエンドポイント |
| `OPENAI_MODEL` | 必須 | 利用するモデル名 |

## 使い方

```bash
# パッチ適用確認 (パッチ適用と gn gen まで。ビルドはしない)
uv --directory agents/libwebrtc-update-check run python libwebrtc_update_check.py --target macos_arm64

# フルビルドまで実行
uv --directory agents/libwebrtc-update-check run python libwebrtc_update_check.py --target macos_arm64 --build
```

## 終了コード

| 終了コード | 意味 |
|---|---|
| `0` | パッチ適用とビルドが成功 |
| `1` | 失敗パッチがあり、修正方針を `libwebrtc-follow/` に記録した |
| `2` | 最新バージョンへの更新が不要だった |

## 出力

- レポートはマークダウンで標準出力に出力される
- 追従記録は `libwebrtc-follow/` に月ごとのファイルで時系列に追記される

## 開発

```bash
# 依存の同期
uv --directory agents/libwebrtc-update-check sync

# lint / 型チェック / テスト
uv --directory agents/libwebrtc-update-check run ruff check
uv --directory agents/libwebrtc-update-check run ty check
uv --directory agents/libwebrtc-update-check run pytest
```
