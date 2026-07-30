"""クロスコンパイル用 sysroot を APT リポジトリから直接生成するモジュール。

multistrap や debootstrap に依存せず、apt-get の --download-only と
dpkg-deb --extract だけで sysroot を組み立てる。この構成には次の制約がある。

- root 権限を要求しない（chroot もパッケージの maintainer script も実行しない）
- ホストの APT 状態（/var/lib/apt など）を一切読み書きしない
- 設定ファイル (sysroot/*.json) と署名鍵だけから決定的に同じ sysroot を再現できる

maintainer script を実行しないため、通常はスクリプトが行う後処理
（usrmerge のシンボリックリンク作成など）は _postprocess_sysroot で自前で補う。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

__all__ = [
    "RepositoryConfig",
    "SysrootConfig",
    "SysrootBuildError",
    "SysrootConfigError",
    "build_sysroot",
    "load_sysroot_config",
    "sysroot_config_fingerprint",
]


# sysroot 直下に置く生成記録ファイル。設定のフィンガープリントを保存し、
# 次回のビルドで同一設定なら再生成をスキップする判定に使う。
MANIFEST_NAME = ".webrtc-build-sysroot.json"

# sysroot の生成形式（後処理の内容など）を変えたらインクリメントする。
# 古い形式の sysroot は fingerprint が一致しても再利用しない。
MANIFEST_VERSION = 1

# 設定値のうち APT の設定ファイルやコマンドラインへ埋め込むものに許可する文字。
# sources.list の [] オプションや空白による区切りを壊す文字を弾き、
# 設定ファイル経由のインジェクションを構文レベルで防ぐ。
CONFIG_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._+:/-]+$")


class SysrootConfigError(ValueError):
    """設定ファイル (sysroot/*.json) の内容が不正なときに送出するエラー。"""

    pass


class SysrootBuildError(RuntimeError):
    """設定は正しいが sysroot の生成処理が継続できないときに送出するエラー。"""

    pass


@dataclass(frozen=True)
class RepositoryConfig:
    """APT リポジトリ 1 つ分の設定。sources.list の 1 行に対応する。"""

    url: str
    suite: str
    components: tuple[str, ...]
    # Release ファイルの署名検証に使う鍵。設定読み込み時に絶対パスへ解決済み。
    signed_by: Path


@dataclass(frozen=True)
class SysrootConfig:
    """sysroot 1 つ分の設定。sysroot/*.json を検証済みの形で保持する。"""

    name: str
    # dpkg アーキテクチャ名 (arm64 など)
    arch: str
    # GNU トリプレット (aarch64-linux-gnu など)。ライブラリパスの解決に使う。
    triplet: str
    packages: tuple[str, ...]
    repositories: tuple[RepositoryConfig, ...]


# 以下の _require_* は JSON から読んだ値の検証ヘルパー。
# 不正な設定は APT 実行前の読み込み時点で SysrootConfigError として失敗させる。


def _require_object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SysrootConfigError(f"{label} must be a JSON object")
    if not all(isinstance(key, str) for key in value):
        raise SysrootConfigError(f"{label} must contain only string keys")
    return cast(dict[str, object], value)


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SysrootConfigError(f"{label} must be a non-empty string")
    return value


def _require_token(value: object, label: str) -> str:
    token = _require_string(value, label)
    if CONFIG_TOKEN_PATTERN.fullmatch(token) is None:
        raise SysrootConfigError(f"{label} contains unsupported characters: {token}")
    return token


def _require_string_array(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise SysrootConfigError(f"{label} must be a non-empty array")
    result = tuple(_require_string(item, f"{label}[]") for item in value)
    if len(set(result)) != len(result):
        raise SysrootConfigError(f"{label} must not contain duplicate values")
    return result


def _load_repository(value: object, config_dir: Path, index: int) -> RepositoryConfig:
    label = f"repositories[{index}]"
    raw = _require_object(value, label)
    url = _require_string(raw.get("url"), f"{label}.url")
    # 署名検証だけでなく通信経路も保護するため、HTTP への後退をここで拒否する。
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise SysrootConfigError(f"{label}.url must be an HTTPS URL: {url}")
    # URL は sources.list の "deb [options] url suite components" 行へ埋め込むため、
    # 行の構文を壊す空白と、オプション区切りの角括弧を含む URL は受け付けない。
    if any(character.isspace() for character in url) or "[" in url or "]" in url:
        raise SysrootConfigError(f"{label}.url contains unsupported characters: {url}")

    suite = _require_token(raw.get("suite"), f"{label}.suite")
    components = tuple(
        _require_token(component, f"{label}.components[]")
        for component in _require_string_array(raw.get("components"), f"{label}.components")
    )
    # 署名鍵の相対パスは設定ファイルの配置場所を基準に解決し、
    # 実行時のカレントディレクトリに依存させない。
    signed_by_value = _require_string(raw.get("signed_by"), f"{label}.signed_by")
    signed_by = Path(signed_by_value)
    if not signed_by.is_absolute():
        signed_by = config_dir / signed_by
    signed_by = signed_by.resolve()
    if not signed_by.is_file():
        raise SysrootConfigError(f"{label}.signed_by does not exist: {signed_by}")
    # 解決後の絶対パスも sources.list の signed-by= オプションへ埋め込むため、
    # checkout の置き場所に構文を壊す文字が含まれていないかまで確認する。
    if CONFIG_TOKEN_PATTERN.fullmatch(str(signed_by)) is None:
        raise SysrootConfigError(f"{label}.signed_by contains unsupported characters: {signed_by}")

    return RepositoryConfig(
        url=url,
        suite=suite,
        components=components,
        signed_by=signed_by,
    )


def load_sysroot_config(path: Path) -> SysrootConfig:
    """sysroot 設定 JSON を読み込み、検証済みの SysrootConfig を返す。"""
    try:
        raw_value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SysrootConfigError(f"Failed to read sysroot config: {path}: {error}") from error

    raw = _require_object(raw_value, "config")
    name = _require_token(raw.get("name"), "name")
    arch = _require_token(raw.get("arch"), "arch")
    triplet = _require_token(raw.get("triplet"), "triplet")
    packages = tuple(
        _require_token(package, "packages[]")
        for package in _require_string_array(raw.get("packages"), "packages")
    )

    repositories_value = raw.get("repositories")
    if not isinstance(repositories_value, list) or not repositories_value:
        raise SysrootConfigError("repositories must be a non-empty array")
    repositories = tuple(
        _load_repository(repository, path.parent, index)
        for index, repository in enumerate(repositories_value)
    )

    return SysrootConfig(
        name=name,
        arch=arch,
        triplet=triplet,
        packages=packages,
        repositories=repositories,
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sysroot_config_fingerprint(config: SysrootConfig) -> str:
    """設定内容から sysroot の同一性を判定するためのハッシュを計算する。

    manifest に保存したこの値と比較して、設定が変わっていなければ
    既存 sysroot を再利用する。署名鍵は checkout の絶対パスではなく
    ファイル内容のハッシュで表現し、checkout の場所が違っても
    同一内容なら同じ fingerprint になるようにする。
    """
    payload = {
        "name": config.name,
        "arch": config.arch,
        "triplet": config.triplet,
        "packages": config.packages,
        "repositories": [
            {
                "url": repository.url,
                "suite": repository.suite,
                "components": repository.components,
                "signed_by_sha256": _file_sha256(repository.signed_by),
            }
            for repository in config.repositories
        ],
    }
    # キー順序と区切り文字を固定した正規化 JSON をハッシュ対象にする。
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_command(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise SysrootBuildError(f"Required command was not found: {name}")
    return path


def _run_command(
    args: list[str], *, environment: dict[str, str] | None = None, log_command: bool = True
) -> None:
    # log_command=False はパッケージごとの展開のようにログが冗長になる場合に使う。
    if log_command:
        logging.info("Running command: %s", shlex.join(args))
    subprocess.run(args, check=True, env=environment)


def _apt_options(work_dir: Path) -> list[str]:
    # APT の状態ディレクトリ・キャッシュ・ソース定義をすべて work_dir 配下へ隔離し、
    # ホストの /var/lib/apt や /etc/apt を読み書きしないようにする。
    # これにより root 権限なしで、ホスト環境を汚さずに apt-get を実行できる。
    state_dir = work_dir / "state"
    return [
        "-o",
        f"Dir::State={state_dir}",
        "-o",
        f"Dir::State::status={state_dir / 'status'}",
        "-o",
        f"Dir::Cache={state_dir / 'cache'}",
        "-o",
        f"Dir::Etc::sourcelist={work_dir / 'sources.list'}",
        "-o",
        "Dir::Etc::sourceparts=/dev/null",
        "-o",
        "Dir::Etc::preferences=/dev/null",
        "-o",
        "Dir::Etc::preferencesparts=/dev/null",
        "-o",
        # 隔離した状態ディレクトリではロックファイルの所有権チェックが
        # 失敗することがあるため、ロックを無効化する。
        "Debug::NoLocking=true",
    ]


def _write_apt_files(config: SysrootConfig, work_dir: Path) -> None:
    # apt-get が期待するディレクトリ構造を用意する。
    # 空の status ファイルは「何もインストールされていないシステム」を意味し、
    # install が依存パッケージを漏れなく解決・ダウンロードする前提になる。
    state_dir = work_dir / "state"
    (state_dir / "lists" / "partial").mkdir(parents=True)
    (state_dir / "cache" / "archives" / "partial").mkdir(parents=True)
    (state_dir / "status").touch()

    # ホストの /etc/apt を読ませず、対象アーキテクチャだけを見る apt.conf を生成する。
    # APT::Architecture を設定ファイル側で固定することで、
    # x86_64 ホスト上でも arm64 などのパッケージを解決できる。
    apt_config = "\n".join(
        [
            'Dir::Etc::main "/dev/null";',
            'Dir::Etc::parts "/dev/null";',
            f'APT::Architecture "{config.arch}";',
            f'APT::Architectures {{ "{config.arch}"; }};',
            'Acquire::Languages "none";',
            'APT::Install-Recommends "false";',
            'APT::Install-Suggests "false";',
            "",
        ]
    )
    (work_dir / "apt.conf").write_text(apt_config, encoding="utf-8")

    source_lines = []
    for repository in config.repositories:
        components = " ".join(repository.components)
        source_lines.append(
            "deb "
            f"[arch={config.arch} signed-by={repository.signed_by}] "
            f"{repository.url} {repository.suite} {components}"
        )
    (work_dir / "sources.list").write_text("\n".join(source_lines) + "\n", encoding="utf-8")


def _ensure_usrmerge_symlinks(root: Path) -> None:
    # dpkg-deb --extract は maintainer script を実行しないため、
    # 通常は usrmerge パッケージが作成する /lib -> usr/lib などのリンクが存在しない。
    # このリンクがないと、パッケージが /lib/... を参照するパスで配置したファイルと
    # /usr/lib/... を参照するリンカがすれ違って解決に失敗するため、ここで補う。
    for legacy, merged in (
        ("bin", "usr/bin"),
        ("sbin", "usr/sbin"),
        ("lib", "usr/lib"),
        ("lib64", "usr/lib64"),
    ):
        legacy_path = root / legacy
        # パッケージが実体のディレクトリやリンクを配置済みの場合はそれを尊重する。
        if legacy_path.is_symlink() or legacy_path.exists():
            continue
        if (root / merged).is_dir():
            legacy_path.symlink_to(merged)


def _fix_absolute_symlinks(root: Path) -> None:
    # パッケージ内の絶対パスリンク (例: libfoo.so -> /usr/lib/.../libfoo.so.1) は
    # sysroot の外、つまりホスト側のファイルを指してしまう。
    # クロスコンパイル時にリンカが正しいライブラリを解決できるよう、
    # sysroot 内で完結する相対リンクへ張り替える。
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        target = Path(os.readlink(path))
        if not target.is_absolute():
            continue
        # /etc/alternatives 経由のリンクなど、展開だけでは実体が存在しない
        # リンク先は張り替えの根拠がないためそのまま残す。
        target_in_sysroot = root / target.relative_to("/")
        if not target_in_sysroot.exists():
            continue
        relative_target = os.path.relpath(target_in_sysroot, start=path.parent)
        path.unlink()
        path.symlink_to(relative_target)


def _link_pkgconfig_files(root: Path, triplet: str) -> None:
    # WebRTC のビルドは usr/share/pkgconfig から .pc ファイルを探すため、
    # トリプレット固有ディレクトリにしかない定義へ互換リンクを張る。
    source_dir = root / "usr" / "lib" / triplet / "pkgconfig"
    if not source_dir.is_dir():
        return
    destination_dir = root / "usr" / "share" / "pkgconfig"
    destination_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_dir.iterdir()):
        destination = destination_dir / source.name
        # パッケージが usr/share/pkgconfig へ直接配置した定義を上書きしない。
        if destination.exists() or destination.is_symlink():
            continue
        # sysroot を移動しても壊れないよう相対パスでリンクする。
        destination.symlink_to(f"../../lib/{triplet}/pkgconfig/{source.name}")


def _postprocess_sysroot(root: Path, triplet: str) -> None:
    # maintainer script を実行しない展開方式の穴を埋める後処理をまとめて行う。
    # 後処理の内容を変えたら MANIFEST_VERSION をインクリメントすること。
    _ensure_usrmerge_symlinks(root)
    _fix_absolute_symlinks(root)
    _link_pkgconfig_files(root, triplet)


def _read_manifest(output_dir: Path) -> dict[str, object] | None:
    # manifest が読めない・形式が不正な場合は None を返し、
    # 呼び出し側で「由来不明の既存ディレクトリ」として扱う。
    manifest_path = output_dir / MANIFEST_NAME
    try:
        raw_value: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw_value, dict) or not all(isinstance(key, str) for key in raw_value):
        return None
    return cast(dict[str, object], raw_value)


def _install_completed_sysroot(new_root: Path, output_dir: Path) -> None:
    # 完成した sysroot を出力先へ rename で切り替える。
    # 展開途中の状態が output_dir に見える瞬間を作らないため、
    # 既存の出力は退避 -> 新規を配置 -> 退避を削除、の順で入れ替える。
    backup_dir = new_root.parent / "previous-sysroot"
    had_previous = output_dir.exists() or output_dir.is_symlink()
    if had_previous:
        output_dir.rename(backup_dir)
    try:
        new_root.rename(output_dir)
    except BaseException:
        # 新規の配置に失敗した場合は退避した既存の出力を元へ戻す。
        if had_previous:
            backup_dir.rename(output_dir)
        raise
    if had_previous:
        if backup_dir.is_dir() and not backup_dir.is_symlink():
            shutil.rmtree(backup_dir)
        else:
            # 既存の出力が symlink や通常ファイルだった場合は unlink で消す。
            backup_dir.unlink()


def build_sysroot(config: SysrootConfig, output_dir: Path, *, force: bool = False) -> bool:
    """設定に従って sysroot を output_dir へ生成する。

    一致する manifest を持つ sysroot が既にあれば再生成せず False を返す。
    実際に生成した場合は True を返す。設定と一致しない既存の出力は、
    force が指定されない限り黙って削除も再利用もせずエラーにする。
    """
    fingerprint = sysroot_config_fingerprint(config)
    manifest = _read_manifest(output_dir)
    if (
        not force
        and manifest is not None
        and manifest.get("format_version") == MANIFEST_VERSION
        and manifest.get("fingerprint") == fingerprint
    ):
        logging.info("Reusing sysroot: %s", output_dir)
        return False
    if not force and (output_dir.exists() or output_dir.is_symlink()):
        raise SysrootBuildError(
            f"Existing sysroot does not match the current config: {output_dir}; use --force"
        )

    apt_get = _require_command("apt-get")
    dpkg_deb = _require_command("dpkg-deb")
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    # 作業ディレクトリは output_dir と同じ親に作り、
    # 完成後の rename による入れ替えが同一ファイルシステム内で完結するようにする。
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary_dir_value:
        temporary_dir = Path(temporary_dir_value)
        # TemporaryDirectory は 0700 で作られるため、
        # sysroot をそのまま参照しても支障がないよう権限を緩める。
        temporary_dir.chmod(0o755)
        work_dir = temporary_dir / "apt"
        new_root = temporary_dir / "rootfs"
        work_dir.mkdir()
        new_root.mkdir()
        _write_apt_files(config, work_dir)

        environment = os.environ.copy()
        environment["APT_CONFIG"] = str(work_dir / "apt.conf")
        apt_options = _apt_options(work_dir)
        _run_command([apt_get, *apt_options, "update"], environment=environment)
        # --download-only により、依存解決とダウンロードだけを apt-get に任せる。
        # インストール（＝maintainer script の実行）はしないので root 権限が要らない。
        _run_command(
            [
                apt_get,
                *apt_options,
                "--download-only",
                "--yes",
                "--no-install-recommends",
                "--no-install-suggests",
                "install",
                *config.packages,
            ],
            environment=environment,
        )

        # ダウンロード済みの deb をすべて sysroot へ展開する。
        # dpkg-deb --extract はファイルを取り出すだけで maintainer script を実行しない。
        archive_dir = work_dir / "state" / "cache" / "archives"
        deb_files = sorted(archive_dir.glob("*.deb"))
        if not deb_files:
            raise SysrootBuildError(f"No deb packages were downloaded for: {config.name}")
        logging.info("Extracting %d packages", len(deb_files))
        for deb_file in deb_files:
            _run_command([dpkg_deb, "--extract", str(deb_file), str(new_root)], log_command=False)

        _postprocess_sysroot(new_root, config.triplet)
        # 生成が最後まで完了した sysroot にだけ manifest を書き込む。
        # 途中で失敗した出力には manifest がないため、誤って再利用されることはない。
        manifest_value = {
            "format_version": MANIFEST_VERSION,
            "fingerprint": fingerprint,
            "name": config.name,
            "arch": config.arch,
            "triplet": config.triplet,
            "deb_files": [deb_file.name for deb_file in deb_files],
        }
        (new_root / MANIFEST_NAME).write_text(
            json.dumps(manifest_value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        _install_completed_sysroot(new_root, output_dir)

    logging.info("Built sysroot: %s", output_dir)
    return True
