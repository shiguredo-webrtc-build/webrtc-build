"""libwebrtc-update-check エージェントが LLM に提供するツール関数群。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from openai.types.chat import ChatCompletionFunctionToolParam

# リポジトリルート (run.py が存在するディレクトリ)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# 一度に読み込むファイルの最大バイト数 (LLM のコンテキスト肥大化を防ぐ)
MAX_READ_BYTES = 200 * 1024

# ツール実行のデフォルトタイムアウト (秒)。WebRTC のソース取得やビルドは長いため大きめに設定する
DEFAULT_COMMAND_TIMEOUT = 3600


def _resolve_path(path: str) -> Path:
    """相対パスをリポジトリルートからの相対パスとして解決する。"""
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p


def run_command(command: str, timeout: int = DEFAULT_COMMAND_TIMEOUT) -> dict[str, Any]:
    """リポジトリルートでシェルコマンドを実行し、標準出力・標準エラー出力・終了コードを返す。"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired as e:
        # タイムアウト時も途中までの出力を返し、LLM が状況を判断できるようにする
        return {
            "stdout": e.stdout or "",
            "stderr": e.stderr or "",
            "returncode": -1,
            "error": f"Command timed out after {timeout} seconds",
        }


def read_file(path: str) -> dict[str, Any]:
    """指定されたファイルの内容を読み込む。上限を超える場合は切り詰めて返す。"""
    p = _resolve_path(path)
    if p.is_dir():
        return {"error": f"{path} is a directory"}
    if not p.exists():
        return {"error": f"{path} does not exist"}
    data = p.read_bytes()
    truncated = len(data) > MAX_READ_BYTES
    text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
    result: dict[str, Any] = {"content": text}
    if truncated:
        result["note"] = f"File is truncated to {MAX_READ_BYTES} bytes"
    return result


def write_file(path: str, content: str, append: bool = False) -> dict[str, Any]:
    """ファイルを書き込む。append が True の場合は末尾に追記する。"""
    p = _resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with p.open(mode) as f:
        f.write(content)
    return {"path": str(p), "append": append}


def list_files(path: str = ".") -> dict[str, Any]:
    """指定されたディレクトリ内のエントリ名一覧を返す。"""
    p = _resolve_path(path)
    if not p.exists():
        return {"error": f"{path} does not exist"}
    if not p.is_dir():
        return {"error": f"{path} is not a directory"}
    entries = sorted(entry.name for entry in p.iterdir())
    return {"path": str(p), "entries": entries}


# Chat Completions API に渡すツール定義 (function calling)
TOOL_DEFINITIONS: list[ChatCompletionFunctionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "リポジトリルートでシェルコマンドを実行します。"
                "WebRTC のソース取得・パッチ適用・ビルドは run.py を経由して実行します。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "実行するコマンド"},
                    "timeout": {
                        "type": "integer",
                        "description": f"タイムアウト秒数 (デフォルト {DEFAULT_COMMAND_TIMEOUT})",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "ファイルの内容を読み込みます。パッチやソースコードの確認に利用します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "ファイルパス (リポジトリルートからの相対パス)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "ファイルを書き込みます。append に True を指定すると末尾に追記します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "ファイルパス (リポジトリルートからの相対パス)",
                    },
                    "content": {"type": "string", "description": "書き込む内容"},
                    "append": {
                        "type": "boolean",
                        "description": "True の場合は追記 (デフォルト False)",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "ディレクトリ内のエントリ名一覧を返します。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "ディレクトリパス (デフォルトはリポジトリルート)",
                    },
                },
            },
        },
    },
]


def execute_tool(name: str, arguments: str) -> dict[str, Any]:
    """ツール名と JSON 文字列の引数を受け取り、対応するツール関数を実行する。"""
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON arguments: {arguments}"}
    try:
        if name == "run_command":
            return run_command(**args)
        if name == "read_file":
            return read_file(**args)
        if name == "write_file":
            return write_file(**args)
        if name == "list_files":
            return list_files(**args)
        return {"error": f"Unknown tool: {name}"}
    except TypeError as e:
        return {"error": f"Invalid arguments for tool {name}: {e}"}
