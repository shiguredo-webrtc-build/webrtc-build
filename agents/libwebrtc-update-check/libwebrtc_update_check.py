"""libwebrtc-update-check エージェント本体。

libwebrtc のアップデートを検知し、ビルドが壊れていないか、パッチが当たるかを
LLM (openai Python SDK) を利用して確認する。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from typing import Any

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageParam,
)

from tools import TOOL_DEFINITIONS, execute_tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SYSTEM_PROMPT = """\
あなたは libwebrtc の追従確認エージェントです。

libwebrtc のアップデートを検知し、ビルドが壊れていないか、パッチが当たるかを確認して、
結果を libwebrtc-follow/ に記録し、レポートを出力します。

## 前提

- VERSION ファイルが libwebrtc のバージョンを管理している (例: WEBRTC_BUILD_VERSION=151.7922.0.0)
- run.py がソース取得・パッチ適用・ビルドを一括で行う
- パッチは patches/ にあり、ターゲットごとに run.py の PATCHES の順番で適用される
- パッチ適用は run.py が行う。patch コマンドを直接実行してはならない
- パッチの修正手順は DEVELOPMENT.md の「エラーになったパッチを修正する」に従う
- ブランチ運用は scripts/version_update.sh の流儀に従う (feature/<milestone>.<branch>)

## 作業手順

### 1. 最新バージョンの確認

1. `python3 run.py version_list` を実行して最新の milestone を確認する
2. VERSION ファイルの WEBRTC_BUILD_VERSION と比較する
3. 最新 milestone が現在のバージョンと同じか古い場合は、レポートに `STATUS: no_update`
   を出力して終了する

### 2. ブランチの準備

1. 最新 milestone に対応する feature/<milestone>.<branch> ブランチを確認する
   - `git fetch origin` を実行してから確認する
   - origin に存在する場合は `git checkout feature/<milestone>.<branch>` で切り替える
   - 存在しない場合は master から `git checkout -b feature/<milestone>.<branch> master` で作成する
2. `python3 run.py version_update m<milestone>` で VERSION を更新する

### 3. 過去の記録の参照

libwebrtc-follow/ ディレクトリの markdown から対象ブランチの過去の記録を確認し、
同じ問題が再発していないか、過去の修正方針を踏襲できるかを確認する。
現在の日時は `date +%Y-%m-%d` で確認すること。

### 4. パッチ適用の確認

`python3 run.py build <target> --no-history --webrtc-nobuild` を実行する。
フルビルドを指示された場合は --webrtc-nobuild を付けずに実行する。

### 5. 結果の判定

以下の項目を必ず確認する。

- パッチ適用の成否: 終了コードが 0 でない場合、ログの `patch -p1 <` の行から
  どのパッチで失敗したかを特定する。失敗パッチは `FAILED` や `saving rejects` の行でも特定できる
- fuzz 警告: ログに `with fuzz` の行がないか確認する。ある場合は適用位置がズレている
  可能性があるため警告として記録する
- コミット検証: `git log --format=%s -n 30` で [shiguredo-patch] Apply <パッチ名> コミットが
  適用予定のパッチ数と一致するかを確認する
- gn gen の成否: gn gen でエラーが出た場合はビルド設定の破壊を示すため記録する

### 6. 失敗パッチの調査

パッチ適用に失敗した場合、以下の手順で調査して「どう修正すればいいか」と「理由」を特定する。

1. 失敗したパッチを特定する (適用は PATCHES の順番で行われ、最初に失敗したパッチで止まる)
2. パッチの中身を read_file で読み、何を変更しようとしているかを把握する
3. `python3 run.py revert <target> --patch <パッチ名>` を実行して該当パッチまでの状態にする
   - このコマンドは失敗パッチの適用でエラーになるが、気にせず次に進む (DEVELOPMENT.md に従う)
4. 失敗パッチが触るファイルを _source/<target>/webrtc/src で確認し、libwebrtc 側の変更内容と照合する
5. `python3 run.py diff <target>` で現在の差分を確認する
6. 修正方針と理由をまとめる。修正が難しい場合は README.md の「パッチ運用について」に従い、
   パッチ削除の判断理由も記録する

### 7. 記録の追記

libwebrtc-follow/<現在の年月>.md に以下の形式で追記する。ファイルがなければ新規作成する。

```
# <YYYY-MM>

## <YYYY-MM-DD> <milestone>.<branch> <commit hash>

- パッチ適用: 成功 / 失敗
- 失敗パッチ: <パッチ名>
- 修正方針: <どう修正すればいいか>
- 理由: <なぜその修正が必要か>
- fuzz 警告: あり (<パッチ名>) / なし
- ビルド: 成功 / 失敗 / 未実施
- 残課題: <次の作業への引き継ぎ事項>
```

### 8. レポートの出力

最終レポートをマークダウンで出力する。1 行目は必ず以下の STATUS を出力する。

- STATUS: success (パッチ適用とビルドがすべて成功)
- STATUS: patch_failed (失敗パッチがあり、修正方針を記録した)
- STATUS: no_update (最新バージョンへの更新が不要だった)

STATUS の次の行から日本語でレポート本文を出力する。レポートには以下を含めること。

- 確認した libwebrtc のバージョン (milestone, branch, commit hash)
- パッチ適用の成否 (失敗したパッチと理由)
- fuzz 警告の有無
- ビルドの成否
- 記録した修正方針と理由
- 残課題と次のアクション

## 禁止事項

- git push を実行しない (記録のコミットと push はワークフローが行う)
- パッチの実修正をしない (修正方針を記録するだけ)
- パッチの適用を patch コマンドで直接行わない (run.py を経由する)
"""

# レポートの 1 行目に出力する STATUS のパース用パターン
STATUS_RE = re.compile(r"^STATUS:\s*(success|patch_failed|no_update)", re.MULTILINE)


def get_env(name: str) -> str:
    """必須の環境変数を取得し、未設定ならエラーで終了する。"""
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Environment variable {name} is not set")
    return value


def run_agent(
    client: OpenAI,
    model: str,
    user_prompt: str,
    max_iterations: int,
) -> str:
    """Chat Completions とツール呼び出しのループでエージェントを実行し、最終レポートを返す。"""
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
        )
        message = response.choices[0].message
        tool_calls = message.tool_calls
        if tool_calls is None:
            return message.content or ""
        # ツール定義は function タイプのみなので、function 以外のツール呼び出しは無視する
        function_tool_calls = [
            tool_call
            for tool_call in tool_calls
            if isinstance(tool_call, ChatCompletionMessageFunctionToolCall)
        ]
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in function_tool_calls
                ],
            }
        )
        for tool_call in function_tool_calls:
            result: dict[str, Any] = execute_tool(
                tool_call.function.name, tool_call.function.arguments
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    return "STATUS: patch_failed\n\nイテレーション上限に達したためエージェントを中断しました"


def parse_status(report: str) -> str:
    """レポートから STATUS を抽出する。見つからない場合は patch_failed とする。"""
    match = STATUS_RE.search(report)
    if match is None:
        return "patch_failed"
    return match.group(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="libwebrtc の更新確認エージェント")
    parser.add_argument(
        "--target", default="macos_arm64", help="ビルドターゲット (デフォルト: macos_arm64)"
    )
    parser.add_argument("--build", action="store_true", help="フルビルドまで実行する")
    parser.add_argument(
        "--max-iterations", type=int, default=100, help="エージェントの最大イテレーション数"
    )
    args = parser.parse_args()

    api_key = get_env("OPENAI_API_KEY")
    base_url = get_env("OPENAI_BASE_URL")
    model = get_env("OPENAI_MODEL")

    client = OpenAI(api_key=api_key, base_url=base_url)

    user_prompt = (
        f"ターゲット: {args.target}\n"
        f"フルビルド: {'あり' if args.build else 'なし (パッチ適用確認のみ)'}\n"
        "上記の設定で作業を開始してください。\n"
    )

    logging.info("agent started (target=%s, build=%s)", args.target, args.build)
    report = run_agent(client, model, user_prompt, args.max_iterations)
    print(report)

    status = parse_status(report)
    logging.info("agent finished (status=%s)", status)
    if status == "no_update":
        return 2
    if status == "success":
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
