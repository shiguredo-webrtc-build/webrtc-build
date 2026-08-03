"""tools モジュールのツール関数群のテスト。

LLM の呼び出しには依存せず、実際のファイル操作とコマンド実行のみを検証する。
"""

from __future__ import annotations

from pathlib import Path

from tools import MAX_READ_BYTES, list_files, read_file, run_command, write_file


def test_run_command_success() -> None:
    """成功するコマンドは stdout と終了コード 0 を返す。"""
    result = run_command("echo hello")
    assert result["returncode"] == 0
    assert result["stdout"] == "hello\n"


def test_run_command_failure() -> None:
    """失敗するコマンドは終了コード 1 を返す。"""
    result = run_command("exit 1")
    assert result["returncode"] == 1


def test_run_command_timeout() -> None:
    """タイムアウトしたコマンドは終了コード -1 とエラーメッセージを返す。"""
    result = run_command("sleep 3", timeout=1)
    assert result["returncode"] == -1
    assert "timed out" in result["error"]


def test_read_file_content(tmp_path: Path) -> None:
    """存在するファイルは内容を返す。"""
    p = tmp_path / "test.txt"
    p.write_text("content")
    result = read_file(str(p))
    assert result["content"] == "content"


def test_read_file_not_found(tmp_path: Path) -> None:
    """存在しないファイルはエラーを返す。"""
    result = read_file(str(tmp_path / "not_found.txt"))
    assert "does not exist" in result["error"]


def test_read_file_directory(tmp_path: Path) -> None:
    """ディレクトリを指定するとエラーを返す。"""
    result = read_file(str(tmp_path))
    assert "is a directory" in result["error"]


def test_read_file_truncation(tmp_path: Path) -> None:
    """上限サイズを超えるファイルは切り詰められ、note が付く。"""
    p = tmp_path / "large.txt"
    p.write_bytes(b"a" * (MAX_READ_BYTES + 100))
    result = read_file(str(p))
    assert len(result["content"]) == MAX_READ_BYTES
    assert "truncated" in result["note"]


def test_write_file_overwrite(tmp_path: Path) -> None:
    """書き込みは既存の内容を上書きする。"""
    p = tmp_path / "test.txt"
    write_file(str(p), "first\n")
    write_file(str(p), "second\n")
    assert p.read_text() == "second\n"


def test_write_file_append(tmp_path: Path) -> None:
    """append=True の書き込みは末尾に追記する。"""
    p = tmp_path / "test.txt"
    write_file(str(p), "first\n")
    write_file(str(p), "second\n", append=True)
    assert p.read_text() == "first\nsecond\n"


def test_list_files(tmp_path: Path) -> None:
    """ディレクトリ内のエントリ一覧をソートして返す。"""
    (tmp_path / "b.txt").write_text("")
    (tmp_path / "a.txt").write_text("")
    result = list_files(str(tmp_path))
    assert result["entries"] == ["a.txt", "b.txt"]


def test_list_files_not_found(tmp_path: Path) -> None:
    """存在しないディレクトリはエラーを返す。"""
    result = list_files(str(tmp_path / "not_found"))
    assert "does not exist" in result["error"]
