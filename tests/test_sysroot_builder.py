from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

import pytest

from sysroot_builder import (
    SysrootBuildError,
    SysrootConfigError,
    _fix_absolute_symlinks,
    _link_pkgconfig_files,
    build_sysroot,
    load_sysroot_config,
    sysroot_config_fingerprint,
)


def write_config(path: Path, *, name: str = "ubuntu-26.04_armv8") -> None:
    # 実際の設定と同じ構造を使い、設定ファイルからの相対パス解決も確認できるようにする。
    config = {
        "name": name,
        "arch": "arm64",
        "triplet": "aarch64-linux-gnu",
        "packages": ["libc6-dev", "libstdc++-15-dev"],
        "repositories": [
            {
                "url": "https://ports.ubuntu.com/ubuntu-ports",
                "suite": "resolute",
                "components": ["main", "universe"],
                "signed_by": "keyrings/ubuntu-archive-keyring.gpg",
            }
        ],
    }
    path.write_text(json.dumps(config), encoding="utf-8")


def test_load_sysroot_config_resolves_relative_keyring(tmp_path: Path) -> None:
    # 署名鍵は設定ファイルの配置場所を基準に解決し、実行時の cwd に依存させない。
    config_path = tmp_path / "ubuntu-26.04_armv8.json"
    keyring_path = tmp_path / "keyrings" / "ubuntu-archive-keyring.gpg"
    keyring_path.parent.mkdir()
    keyring_path.touch()
    write_config(config_path)

    config = load_sysroot_config(config_path)

    assert config.name == "ubuntu-26.04_armv8"
    assert config.arch == "arm64"
    assert config.triplet == "aarch64-linux-gnu"
    assert config.packages == ("libc6-dev", "libstdc++-15-dev")
    assert config.repositories[0].signed_by == keyring_path


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("arch", ""),
        ("triplet", ""),
        ("packages", []),
        ("repositories", []),
    ],
    ids=["empty-name", "empty-arch", "empty-triplet", "empty-packages", "empty-repositories"],
)
def test_load_sysroot_config_rejects_empty_required_values(
    tmp_path: Path, field: str, value: str | list[object]
) -> None:
    # 不完全な設定で APT を実行せず、設定の読み込み時点で明確に失敗させる。
    config_path = tmp_path / "invalid.json"
    write_config(config_path)
    raw_config: object = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw_config, dict):
        raise AssertionError("テスト設定は JSON オブジェクトである必要がある")
    raw_config = cast(dict[str, object], raw_config)
    raw_config[field] = value
    config_path.write_text(json.dumps(raw_config), encoding="utf-8")

    with pytest.raises(SysrootConfigError):
        load_sysroot_config(config_path)


def test_load_sysroot_config_rejects_insecure_repository_url(tmp_path: Path) -> None:
    # 署名検証だけでなく通信経路も保護し、HTTP への意図しない後退を設定読み込み時に拒否する。
    config_path = tmp_path / "invalid.json"
    keyring_path = tmp_path / "keyrings" / "ubuntu-archive-keyring.gpg"
    keyring_path.parent.mkdir()
    keyring_path.touch()
    write_config(config_path)
    raw_config: object = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw_config, dict):
        raise AssertionError("テスト設定は JSON オブジェクトである必要がある")
    raw_config = cast(dict[str, object], raw_config)
    repositories = raw_config.get("repositories")
    if (
        not isinstance(repositories, list)
        or not repositories
        or not isinstance(repositories[0], dict)
    ):
        raise AssertionError("テスト設定の repositories が不正")
    repository = cast(dict[str, object], repositories[0])
    repository["url"] = "http://ports.ubuntu.com/ubuntu-ports"
    config_path.write_text(json.dumps(raw_config), encoding="utf-8")

    with pytest.raises(SysrootConfigError):
        load_sysroot_config(config_path)


def test_sysroot_config_fingerprint_is_independent_of_config_path(tmp_path: Path) -> None:
    # 同一内容なら checkout の場所が異なっても同じ sysroot と判定できるようにする。
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    for config_dir in (first_dir, second_dir):
        (config_dir / "keyrings").mkdir(parents=True)
        (config_dir / "keyrings" / "ubuntu-archive-keyring.gpg").touch()
        write_config(config_dir / "config.json")

    first = load_sysroot_config(first_dir / "config.json")
    second = load_sysroot_config(second_dir / "config.json")

    assert sysroot_config_fingerprint(first) == sysroot_config_fingerprint(second)


def test_fix_absolute_symlinks_makes_existing_target_relative(tmp_path: Path) -> None:
    # sysroot の移動後もリンクがホスト側の /usr/lib を参照しないことを確認する。
    target = tmp_path / "usr" / "lib" / "aarch64-linux-gnu" / "libexample.so.1"
    target.parent.mkdir(parents=True)
    target.touch()
    link = target.parent / "libexample.so"
    link.symlink_to("/usr/lib/aarch64-linux-gnu/libexample.so.1")

    _fix_absolute_symlinks(tmp_path)

    assert link.is_symlink()
    assert not os.readlink(link).startswith("/")
    assert link.resolve() == target


def test_fix_absolute_symlinks_keeps_unresolved_target(tmp_path: Path) -> None:
    # alternatives など展開だけでは解決しないリンクを誤った相対リンクへ変更しない。
    link = tmp_path / "usr" / "bin" / "example"
    link.parent.mkdir(parents=True)
    link.symlink_to("/etc/alternatives/example")

    _fix_absolute_symlinks(tmp_path)

    assert os.readlink(link) == "/etc/alternatives/example"


def test_link_pkgconfig_files_creates_compatibility_links(tmp_path: Path) -> None:
    # WebRTC の pkg-config 探索が従来と同じ場所からターゲット用定義を発見できるようにする。
    source_dir = tmp_path / "usr" / "lib" / "aarch64-linux-gnu" / "pkgconfig"
    source_dir.mkdir(parents=True)
    (source_dir / "example.pc").touch()

    _link_pkgconfig_files(tmp_path, "aarch64-linux-gnu")

    link = tmp_path / "usr" / "share" / "pkgconfig" / "example.pc"
    assert link.is_symlink()
    assert os.readlink(link) == "../../lib/aarch64-linux-gnu/pkgconfig/example.pc"


def test_build_sysroot_reuses_matching_manifest(tmp_path: Path) -> None:
    # 一致する manifest があれば APT を再実行せず、安全に既存 sysroot を再利用する。
    config_path = tmp_path / "config" / "config.json"
    keyring_path = config_path.parent / "keyrings" / "ubuntu-archive-keyring.gpg"
    keyring_path.parent.mkdir(parents=True)
    keyring_path.touch()
    write_config(config_path)
    config = load_sysroot_config(config_path)
    output_dir = tmp_path / "rootfs"
    output_dir.mkdir()
    manifest = {
        "format_version": 1,
        "fingerprint": sysroot_config_fingerprint(config),
    }
    (output_dir / ".webrtc-build-sysroot.json").write_text(json.dumps(manifest), encoding="utf-8")

    built = build_sysroot(config, output_dir)

    assert built is False


def test_build_sysroot_rejects_old_manifest_without_force(tmp_path: Path) -> None:
    # 生成形式が変わった sysroot を再利用せず、明示的な再生成を要求する。
    config_path = tmp_path / "config" / "config.json"
    keyring_path = config_path.parent / "keyrings" / "ubuntu-archive-keyring.gpg"
    keyring_path.parent.mkdir(parents=True)
    keyring_path.touch()
    write_config(config_path)
    config = load_sysroot_config(config_path)
    output_dir = tmp_path / "rootfs"
    output_dir.mkdir()
    manifest = {
        "format_version": 0,
        "fingerprint": sysroot_config_fingerprint(config),
    }
    (output_dir / ".webrtc-build-sysroot.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(SysrootBuildError):
        build_sysroot(config, output_dir)


def test_build_sysroot_rejects_stale_directory_without_force(tmp_path: Path) -> None:
    # 設定由来か不明な既存ディレクトリを黙って削除または再利用しない。
    config_path = tmp_path / "config" / "config.json"
    keyring_path = config_path.parent / "keyrings" / "ubuntu-archive-keyring.gpg"
    keyring_path.parent.mkdir(parents=True)
    keyring_path.touch()
    write_config(config_path)
    config = load_sysroot_config(config_path)
    output_dir = tmp_path / "rootfs"
    output_dir.mkdir()

    with pytest.raises(SysrootBuildError):
        build_sysroot(config, output_dir)


def test_build_sysroot_rejects_stale_symlink_without_force(tmp_path: Path) -> None:
    # 壊れたリンクも既存出力として扱い、利用者の明示なしに置き換えない。
    config_path = tmp_path / "config" / "config.json"
    keyring_path = config_path.parent / "keyrings" / "ubuntu-archive-keyring.gpg"
    keyring_path.parent.mkdir(parents=True)
    keyring_path.touch()
    write_config(config_path)
    config = load_sysroot_config(config_path)
    output_dir = tmp_path / "rootfs"
    output_dir.symlink_to(tmp_path / "missing")

    with pytest.raises(SysrootBuildError):
        build_sysroot(config, output_dir)
