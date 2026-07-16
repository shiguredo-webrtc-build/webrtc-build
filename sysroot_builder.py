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


MANIFEST_NAME = ".webrtc-build-sysroot.json"
MANIFEST_VERSION = 1
CONFIG_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._+:/-]+$")


class SysrootConfigError(ValueError):
    pass


class SysrootBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepositoryConfig:
    url: str
    suite: str
    components: tuple[str, ...]
    signed_by: Path


@dataclass(frozen=True)
class SysrootConfig:
    name: str
    arch: str
    triplet: str
    packages: tuple[str, ...]
    repositories: tuple[RepositoryConfig, ...]


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
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise SysrootConfigError(f"{label}.url must be an HTTPS URL: {url}")
    if any(character.isspace() for character in url) or "[" in url or "]" in url:
        raise SysrootConfigError(f"{label}.url contains unsupported characters: {url}")

    suite = _require_token(raw.get("suite"), f"{label}.suite")
    components = tuple(
        _require_token(component, f"{label}.components[]")
        for component in _require_string_array(raw.get("components"), f"{label}.components")
    )
    signed_by_value = _require_string(raw.get("signed_by"), f"{label}.signed_by")
    signed_by = Path(signed_by_value)
    if not signed_by.is_absolute():
        signed_by = config_dir / signed_by
    signed_by = signed_by.resolve()
    if not signed_by.is_file():
        raise SysrootConfigError(f"{label}.signed_by does not exist: {signed_by}")
    if CONFIG_TOKEN_PATTERN.fullmatch(str(signed_by)) is None:
        raise SysrootConfigError(f"{label}.signed_by contains unsupported characters: {signed_by}")

    return RepositoryConfig(
        url=url,
        suite=suite,
        components=components,
        signed_by=signed_by,
    )


def load_sysroot_config(path: Path) -> SysrootConfig:
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
    # checkout の絶対パスではなく、署名鍵の内容を sysroot の識別情報に含める。
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
    if log_command:
        logging.info("Running command: %s", shlex.join(args))
    subprocess.run(args, check=True, env=environment)


def _apt_options(work_dir: Path) -> list[str]:
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
        "Debug::NoLocking=true",
    ]


def _write_apt_files(config: SysrootConfig, work_dir: Path) -> None:
    state_dir = work_dir / "state"
    (state_dir / "lists" / "partial").mkdir(parents=True)
    (state_dir / "cache" / "archives" / "partial").mkdir(parents=True)
    (state_dir / "status").touch()

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
    for legacy, merged in (
        ("bin", "usr/bin"),
        ("sbin", "usr/sbin"),
        ("lib", "usr/lib"),
        ("lib64", "usr/lib64"),
    ):
        legacy_path = root / legacy
        if legacy_path.is_symlink() or legacy_path.exists():
            continue
        if (root / merged).is_dir():
            legacy_path.symlink_to(merged)


def _fix_absolute_symlinks(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        target = Path(os.readlink(path))
        if not target.is_absolute():
            continue
        target_in_sysroot = root / target.relative_to("/")
        if not target_in_sysroot.exists():
            continue
        relative_target = os.path.relpath(target_in_sysroot, start=path.parent)
        path.unlink()
        path.symlink_to(relative_target)


def _link_pkgconfig_files(root: Path, triplet: str) -> None:
    source_dir = root / "usr" / "lib" / triplet / "pkgconfig"
    if not source_dir.is_dir():
        return
    destination_dir = root / "usr" / "share" / "pkgconfig"
    destination_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(source_dir.iterdir()):
        destination = destination_dir / source.name
        if destination.exists() or destination.is_symlink():
            continue
        destination.symlink_to(f"../../lib/{triplet}/pkgconfig/{source.name}")


def _postprocess_sysroot(root: Path, triplet: str) -> None:
    _ensure_usrmerge_symlinks(root)
    _fix_absolute_symlinks(root)
    _link_pkgconfig_files(root, triplet)


def _read_manifest(output_dir: Path) -> dict[str, object] | None:
    manifest_path = output_dir / MANIFEST_NAME
    try:
        raw_value: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw_value, dict) or not all(isinstance(key, str) for key in raw_value):
        return None
    return cast(dict[str, object], raw_value)


def _install_completed_sysroot(new_root: Path, output_dir: Path) -> None:
    backup_dir = new_root.parent / "previous-sysroot"
    had_previous = output_dir.exists() or output_dir.is_symlink()
    if had_previous:
        output_dir.rename(backup_dir)
    try:
        new_root.rename(output_dir)
    except BaseException:
        if had_previous:
            backup_dir.rename(output_dir)
        raise
    if had_previous:
        if backup_dir.is_dir() and not backup_dir.is_symlink():
            shutil.rmtree(backup_dir)
        else:
            backup_dir.unlink()


def build_sysroot(config: SysrootConfig, output_dir: Path, *, force: bool = False) -> bool:
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

    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary_dir_value:
        temporary_dir = Path(temporary_dir_value)
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

        archive_dir = work_dir / "state" / "cache" / "archives"
        deb_files = sorted(archive_dir.glob("*.deb"))
        if not deb_files:
            raise SysrootBuildError(f"No deb packages were downloaded for: {config.name}")
        logging.info("Extracting %d packages", len(deb_files))
        for deb_file in deb_files:
            _run_command([dpkg_deb, "--extract", str(deb_file), str(new_root)], log_command=False)

        _postprocess_sysroot(new_root, config.triplet)
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
