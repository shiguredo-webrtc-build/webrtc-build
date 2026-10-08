import argparse
import collections
import ctypes
import filecmp
import fnmatch
import json
import logging
import os
import platform
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sysroot_builder import build_sysroot, load_sysroot_config

logging.basicConfig(level=logging.INFO)


class ChangeDirectory(object):
    def __init__(self, cwd):
        self._cwd = cwd

    def __enter__(self):
        self._old_cwd = os.getcwd()
        logging.debug(f"pushd {self._old_cwd} --> {self._cwd}")
        os.chdir(self._cwd)

    def __exit__(self, exctype, excvalue, trace):
        logging.debug(f"popd {self._old_cwd} <-- {self._cwd}")
        os.chdir(self._old_cwd)
        return False


def cd(cwd):
    return ChangeDirectory(cwd)


def cmd(args, **kwargs):
    logging.debug(f"+{args} {kwargs}")
    if "check" not in kwargs:
        kwargs["check"] = True
    if "resolve" in kwargs:
        resolve = kwargs["resolve"]
        del kwargs["resolve"]
    else:
        resolve = True
    if resolve:
        args = [shutil.which(args[0]), *args[1:]]
    return subprocess.run(args, **kwargs)


# 標準出力をキャプチャするコマンド実行。シェルの `cmd ...` や $(cmd ...) と同じ
def cmdcap(args, **kwargs):
    # 3.7 でしか使えない
    # kwargs['capture_output'] = True
    kwargs["stdout"] = subprocess.PIPE
    kwargs["stderr"] = subprocess.PIPE
    kwargs["encoding"] = "utf-8"
    return cmd(args, **kwargs).stdout.strip()


def rm_rf(path: str):
    if not os.path.exists(path):
        logging.debug(f"rm -rf {path} => path not found")
        return
    if os.path.isfile(path) or os.path.islink(path):
        os.remove(path)
        logging.debug(f"rm -rf {path} => file removed")
    if os.path.isdir(path):
        shutil.rmtree(path)
        logging.debug(f"rm -rf {path} => directory removed")


def mkdir_p(path: str):
    if os.path.exists(path):
        logging.debug(f"mkdir -p {path} => already exists")
        return
    os.makedirs(path, exist_ok=True)
    logging.debug(f"mkdir -p {path} => directory created")


if platform.system() == "Windows":
    PATH_SEPARATOR = ";"
else:
    PATH_SEPARATOR = ":"


def add_path(path: str, is_after=False):
    logging.debug(f"add_path: {path}")
    if "PATH" not in os.environ:
        os.environ["PATH"] = path
        return

    if is_after:
        os.environ["PATH"] = os.environ["PATH"] + PATH_SEPARATOR + path
    else:
        os.environ["PATH"] = path + PATH_SEPARATOR + os.environ["PATH"]


def download(url: str, output_dir: Optional[str] = None, filename: Optional[str] = None) -> str:
    if filename is None:
        output_path = urllib.parse.urlparse(url).path.split("/")[-1]
    else:
        output_path = filename

    if output_dir is not None:
        output_path = os.path.join(output_dir, output_path)

    if os.path.exists(output_path):
        return output_path

    try:
        if shutil.which("curl") is not None:
            cmd(["curl", "-fLo", output_path, url])
        else:
            cmd(["wget", "-cO", output_path, url])
    except Exception:
        # ゴミを残さないようにする
        if os.path.exists(output_path):
            os.remove(output_path)
        raise

    return output_path


def downloadcap(url) -> str:
    if shutil.which("curl") is not None:
        return cmdcap(["curl", "-L", url])
    else:
        return cmdcap(["wget", "-O", "-", url])


def read_version_file(path: str) -> Dict[str, str]:
    versions = {}

    lines = open(path).readlines()
    for line in lines:
        line = line.strip()

        # コメント行
        if line[:1] == "#":
            continue

        # 空行
        if len(line) == 0:
            continue

        [a, b] = map(lambda x: x.strip(), line.split("=", 2))
        versions[a] = b.strip('"')

    return versions


# dir 以下にある全てのファイルパスを、dir2 からの相対パスで返す
def enum_all_files(dir, dir2):
    for root, _, files in os.walk(dir):
        for file in files:
            yield os.path.relpath(os.path.join(root, file), dir2)


def get_depot_tools(source_dir, fetch=False):
    dir = os.path.join(source_dir, "depot_tools")
    if os.path.exists(dir):
        if fetch:
            cmd(["git", "fetch"])
            cmd(["git", "checkout", "-f", "origin/HEAD"])
    else:
        cmd(
            [
                "git",
                "clone",
                "https://chromium.googlesource.com/chromium/tools/depot_tools.git",
                dir,
            ]
        )
    return dir


PATCHES = {
    "windows_x86_64": [
        "4k.patch",
        "revive_proxy.patch",
        "windows_add_deps.patch",
        "windows_silence_warnings.patch",
        "windows_fix_audio_device.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "windows_fix_adm_device_count.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    "windows_arm64": [
        "4k.patch",
        "revive_proxy.patch",
        "windows_add_deps.patch",
        "windows_silence_warnings.patch",
        "windows_fix_audio_device.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    "macos_arm64": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "macos_screen_capture.patch",
        "ios_simulcast.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "h265_ios.patch",
        "arm_neon_sve_bridge.patch",
        "dav1d_config_change.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    # ios と ios_sdk の共通パッチを先に、ターゲット固有のパッチを後に並べる。
    # ios_sdk 専用パッチは末尾 (ios の一覧に無いもの) にまとめる。
    "ios": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "macos_screen_capture.patch",
        "ios_simulcast.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "ios_proxy.patch",
        "h265.patch",
        "h265_ios.patch",
        "arm_neon_sve_bridge.patch",
        "dav1d_config_change.patch",
        "ios_add_scale_resolution_down_to.patch",
        "remove_crel.patch",
        "revert_siso.patch",
        # stereo は ios_manual_audio_input より先に適用する。
        # 編集領域が重なるため、ios_manual_audio_input は stereo 適用後の内容に依存させる。
        "ios_stereo_audio_output.patch",
        "ios_manual_audio_input.patch",
        "unsafe_buffers_optout_list.patch",
        "ios_ssl_certificate_verifier_chain.patch",
        "turn_tls_client_certificate.patch",
    ],
    "ios_sdk": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "macos_screen_capture.patch",
        "ios_simulcast.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "ios_proxy.patch",
        "h265.patch",
        "h265_ios.patch",
        "arm_neon_sve_bridge.patch",
        "dav1d_config_change.patch",
        "ios_add_scale_resolution_down_to.patch",
        "remove_crel.patch",
        "revert_siso.patch",
        "ios_stereo_audio_output.patch",
        "ios_manual_audio_input.patch",
        "unsafe_buffers_optout_list.patch",
        "ios_ssl_certificate_verifier_chain.patch",
        "turn_tls_client_certificate.patch",
        # ios_sdk 専用パッチ
        "ios_audio_track_sink.patch",
        "ios_audio_pause_resume.patch",
    ],
    "android": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "android_webrtc_version.patch",
        "android_fixsegv.patch",
        "android_simulcast.patch",
        "android_hardware_video_encoder.patch",
        "android_proxy.patch",
        "h265.patch",
        "h265_android.patch",
        "remove_crel.patch",
        "revert_siso.patch",
        "android_audio_pause_resume.patch",
        "android_audio_track_sink.patch",
        "unsafe_buffers_optout_list.patch",
        "android_ssl_certificate_verifier_chain.patch",
        "turn_tls_client_certificate.patch",
        "android_turn_tls_client_certificate.patch",
        "android_jni_zero_generated_java.patch",
    ],
    "android_sdk": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "android_webrtc_version.patch",
        "android_fixsegv.patch",
        "android_simulcast.patch",
        "android_hardware_video_encoder.patch",
        "android_proxy.patch",
        "h265.patch",
        "h265_android.patch",
        "remove_crel.patch",
        "revert_siso.patch",
        "android_audio_pause_resume.patch",
        "android_audio_track_sink.patch",
        "unsafe_buffers_optout_list.patch",
        "android_ssl_certificate_verifier_chain.patch",
        "turn_tls_client_certificate.patch",
        "android_turn_tls_client_certificate.patch",
        "android_jni_zero_generated_java.patch",
    ],
    "raspberry-pi-os_armv8": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    "ubuntu-20.04_armv8": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    "ubuntu-22.04_armv8": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    "ubuntu-24.04_armv8": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    "ubuntu-26.04_armv8": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    "ubuntu-22.04_x86_64": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    "ubuntu-24.04_x86_64": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
    "ubuntu-26.04_x86_64": [
        "add_deps.patch",
        "4k.patch",
        "revive_proxy.patch",
        "ssl_verify_callback_with_native_handle.patch",
        "h265.patch",
        "remove_crel.patch",
        "unsafe_buffers_optout_list.patch",
        "turn_tls_client_certificate.patch",
    ],
}

# パッチ適用および差分表示で無視したいファイルは以下に追加する
GIT_ADD_EXCLUDES = [
    ":!*.orig",
    ":!*.rej",
    ":!:__config_site",
    ":!:__assertion_handler",
    ":!sdk/android/api/org/webrtc/WebrtcBuildVersion.java",
    ":!*.pyc",
]


def apply_patch(patch, dir, depth):
    with cd(dir):
        logging.info(f"patch -p{depth} < {patch}")
        if platform.system() in ["Windows"]:
            cmd(
                [
                    "git",
                    "apply",
                    f"-p{depth}",
                    "--ignore-space-change",
                    "--ignore-whitespace",
                    "--whitespace=nowarn",
                    "--reject",
                    patch,
                ]
            )
        else:
            with open(patch) as stdin:
                cmd(["patch", f"-p{depth}"], stdin=stdin)


def _deps_dirs(src_dir):
    if platform.system() == "Windows":
        cap = cmdcap(["gclient", "recurse", "-j1", "cd"])
    else:
        cap = cmdcap(["gclient", "recurse", "-j1", "pwd"])
    abs_dirs = cap.split("\n")
    # Windows だと Updating depot_tools という行があったりするので、
    # # 存在してるディレクトリのみを取り出して相対パスにする
    rel_dirs = [
        os.path.relpath(abs_dir, src_dir) for abs_dir in abs_dirs if os.path.exists(abs_dir)
    ]
    return rel_dirs


def apply_patches(target, patch_dir, src_dir, patch_until, commit_patch):
    # patch_until が指定されている場合、そのパッチファイルまで適用とコミットして、
    # patch_until のパッチに関しては適用だけ行う
    if patch_until is not None:
        if patch_until not in PATCHES[target]:
            raise Exception(f"{patch_until} file is not in PATCHES")

    with cd(src_dir):
        for patch in PATCHES[target]:
            apply_patch(os.path.join(patch_dir, patch), src_dir, 1)
            if patch == patch_until and not commit_patch:
                break
            cmd(["gclient", "recurse", "git", "add", "--", *GIT_ADD_EXCLUDES])
            cmd(
                [
                    "gclient",
                    "recurse",
                    "git",
                    "commit",
                    "--allow-empty",
                    "-am",
                    f"[shiguredo-patch] Apply {patch}",
                ]
            )
            if patch == patch_until and commit_patch:
                break


# 時雨堂パッチが当たっていない最新のコミットを取得する
def get_base_commit(n=30):
    lines = cmdcap(["git", "log", "--format=%H %s", f"-n{n}"]).split("\n")
    for line in lines:
        if "[shiguredo-patch]" in line:
            continue
        return line.split(" ")[0]
    raise Exception("base commit not found")


def get_webrtc(source_dir, patch_dir, version, target, webrtc_source_dir, no_history=False):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")

    mkdir_p(webrtc_source_dir)

    no_history_flag = ["--no-history"] if no_history else []

    src_dir = os.path.join(webrtc_source_dir, "src")
    if not os.path.exists(src_dir):
        with cd(webrtc_source_dir):
            cmd(["gclient"])
            cmd(["fetch", *no_history_flag, "webrtc"])
            if target in ("android", "android_sdk"):
                with open(".gclient", "a") as f:
                    f.write("target_os = [ 'android' ]\n")
            if target in ("ios", "ios_sdk"):
                with open(".gclient", "a") as f:
                    f.write("target_os = [ 'ios' ]\n")

        with cd(src_dir):
            if no_history:
                cmd(["git", "fetch", "--depth=1", "origin", version])
            else:
                cmd(["git", "fetch"])
            cmd(["git", "checkout", "-f", version])
            cmd(["git", "clean", "-df"])
            cmd(
                [
                    "gclient",
                    "sync",
                    "-D",
                    "--force",
                    "--reset",
                    "--with_branch_heads",
                    *no_history_flag,
                ]
            )
            apply_patches(target, patch_dir, src_dir, None, False)


def fetch_webrtc(source_dir, patch_dir, version, target, webrtc_source_dir):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")

    src_dir = os.path.join(webrtc_source_dir, "src")
    with cd(src_dir):
        cmd(["git", "fetch"])
        cmd(["git", "checkout", "-f", version])
        cmd(["git", "clean", "-df"])
        cmd(["gclient", "sync", "-D", "--force", "--reset", "--with_branch_heads"])
        apply_patches(target, patch_dir, src_dir, None, False)


def revert_webrtc(source_dir, patch_dir, target, webrtc_source_dir, patch, commit):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")

    src_dir = os.path.join(webrtc_source_dir, "src")
    with cd(src_dir):
        dirs = _deps_dirs(src_dir)
        for dir in dirs:
            with cd(dir):
                commit_hash = get_base_commit()
                # どうせこの後全部 reset --hard するので、ここでは reset --soft でいい
                cmd(["git", "reset", "--soft", commit_hash])
        cmd(["gclient", "recurse", "git", "reset", "--hard"])
        cmd(["gclient", "recurse", "git", "clean", "-df"])
        apply_patches(target, patch_dir, src_dir, patch, commit)


def diff_webrtc(source_dir, webrtc_source_dir):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")

    src_dir = os.path.join(webrtc_source_dir, "src")
    with cd(src_dir):
        cmd(["gclient", "recurse", "git", "add", "-N", "--", *GIT_ADD_EXCLUDES])

        dirs = _deps_dirs(src_dir)
        for dir in dirs:
            with cd(dir):
                dir = os.path.normpath(dir)
                if dir == ".":
                    src_prefix = "a/"
                    dst_prefix = "b/"
                else:
                    src_prefix = f"a/{dir}/".replace("\\", "/")
                    dst_prefix = f"b/{dir}/".replace("\\", "/")
                cmd(
                    [
                        "git",
                        "--no-pager",
                        "diff",
                        "--ignore-submodules",
                        "--src-prefix",
                        src_prefix,
                        "--dst-prefix",
                        dst_prefix,
                    ]
                )


def git_get_url_and_revision(dir):
    with cd(dir):
        rev = get_base_commit()
        url = cmdcap(["git", "remote", "get-url", "origin"])
        return url, rev


VersionInfo = collections.namedtuple(
    "VersionInfo",
    [
        "webrtc_version",
        "webrtc_commit",
        "webrtc_build_version",
    ],
)
DepsInfo = collections.namedtuple(
    "DepsInfo",
    [
        "macos_deployment_target",
    ],
)


def find_files(dir: str, pattern: str) -> List[str]:
    # dir 配下の pattern に一致するファイルを列挙する。
    # プラットフォームに依存しないよう Python で辿り、アーカイブのメンバーの並び順が
    # 実行ごとに変わらないようソートして返す。
    files: List[str] = []
    for root, _, names in os.walk(dir):
        for name in names:
            if fnmatch.fnmatch(name, pattern):
                files.append(os.path.join(root, name))
    return sorted(files)


def find_ninja_inputs(webrtc_build_dir: str, target: str) -> List[str]:
    # ninja -t query の出力からターゲットの入力ファイルを集める。
    #   明示入力は "    <path>"、暗黙入力は "    | <path>"、順序のみの依存は
    #   "    || <path>" として出力される。順序のみの依存はリンクに渡らないため含めない。
    inputs: List[str] = []
    root = os.path.abspath(webrtc_build_dir)
    for line in cmdcap(["ninja", "-C", webrtc_build_dir, "-t", "query", target]).splitlines():
        text = line.strip()
        # 先頭は "<ターゲット名>:"、以降は "  input: <ルール名>" と入力ファイルが並ぶ
        if text == "" or text.endswith(":") or text.startswith("input:"):
            continue
        if text == "outputs:":
            break
        if text.startswith("||"):
            continue
        if text.startswith("|"):
            text = text[1:].strip()
        if text != "":
            inputs.append(os.path.normpath(os.path.join(root, text)))
    return inputs


def find_build_rlibs(webrtc_build_dir: str, archive: str) -> List[str]:
    # GN が alink の入力として宣言している rlib を ninja から取る
    return [path for path in find_ninja_inputs(webrtc_build_dir, archive) if path.endswith(".rlib")]


def find_cxx_runtime_archives(webrtc_build_dir: str) -> List[str]:
    # GN が実行ファイルと共有ライブラリのリンクに渡す C++ のランタイム (libc++.a と
    # libc++abi.a) を obj の下から探す。obj の下にあるのがターゲットのツールチェーンの
    # 出力で、clang_x64 の下にあるのがホストのツールチェーンの出力である
    archives: List[str] = []
    for name in ("libc++.a", "libc++abi.a"):
        for path in find_files(os.path.join(webrtc_build_dir, "obj"), name):
            archives.append(path)
    return sorted(archives)


def is_thin_archive(archive: str) -> bool:
    # thin アーカイブはメンバーを展開できず、実体のファイルを指しているだけなので見分ける
    with open(archive, "rb") as f:
        return f.read(8) == b"!<thin>\n"


def collect_archive_objects(ar: str, archives: List[str], dest_dir: str) -> List[str]:
    # アーカイブが持つオブジェクトファイルを集める。
    # リンカは入れ子になったアーカイブの中身を見ないため、アーカイブではなく
    # メンバーのオブジェクトファイルを加える。
    objects: List[str] = []
    for archive in archives:
        archive = os.path.abspath(archive)
        if is_thin_archive(archive):
            # GN が作る libc++.a などは thin アーカイブで、llvm-ar は展開に対応していない。
            # メンバーは実体のファイルを指しているので、そのファイルをそのまま加える
            for name in cmdcap([ar, "t", archive]).splitlines():
                path = name if os.path.isabs(name) else os.path.join(os.path.dirname(archive), name)
                path = os.path.normpath(path)
                if path.endswith(".o"):
                    if not os.path.isfile(path):
                        raise Exception(f"object file not found: {path} in {archive}")
                    objects.append(path)
            continue
        # 展開先はアーカイブごとに分ける。lib.rmeta のように複数のアーカイブで名前が
        # 重複するメンバーがあるため、同じディレクトリに展開しない
        # lib.rmeta と lib.rmeta-link はコードを含まないメタデータなので加えない
        names = [name for name in cmdcap([ar, "t", archive]).splitlines() if name.endswith(".o")]
        # アーカイブのメンバーに重複が無い場合は一括で同じディレクトリに展開する
        if len(set(names)) == len(names):
            dest = tempfile.mkdtemp(dir=dest_dir)
            with cd(dest):
                cmd([ar, "x", archive])
            objects += find_files(dest, "*.o")
            continue
        # アーカイブのメンバーに重複がある場合は個別に別ディレクトリに展開する。
        # ar xN で同じ名前のメンバーの何番目かを指定して 1 つずつ展開する
        counts: Dict[str, int] = {}
        for name in names:
            counts[name] = counts.get(name, 0) + 1
            dest = tempfile.mkdtemp(dir=dest_dir)
            with cd(dest):
                cmd([ar, "xN", str(counts[name]), archive, name])
            objects += find_files(dest, "*.o")
    return objects


def same_archive_member(ar: str, archive: str, name: str, path: str, dest_dir: str) -> bool:
    # アーカイブの中のメンバーとファイルの中身が同じかを調べる
    # cd してからでは相対パスが解決できなくなるため、先に絶対パスに直す
    archive = os.path.abspath(archive)
    path = os.path.abspath(path)
    dest = os.path.join(dest_dir, name)
    mkdir_p(dest_dir)
    with cd(dest_dir):
        cmd([ar, "x", archive, name])
    return filecmp.cmp(dest, path, shallow=False)


def append_objects(ar: str, output: str, objects: List[str]) -> None:
    # アーカイブにオブジェクトを追加する。ar は同名のメンバーを置き換えてしまうため、
    # 名前が衝突した場合は別名にして追加する。中身が同じメンバーは追加しない
    # (二重に入れると --whole-archive で重複定義になる)。
    if len(objects) == 0:
        return
    # 既にあるメンバーと、この後追加するメンバーの名前を分けて持つ。
    # 追加予定のものはアーカイブに入っていないので中身を比べられない。
    existing = set(cmdcap([ar, "t", output]).splitlines())
    planned = set(existing)
    with tempfile.TemporaryDirectory() as tmp_dir:
        paths: List[str] = []
        for i, obj in enumerate(objects):
            name = os.path.basename(obj)
            if name in planned:
                if name in existing and same_archive_member(
                    ar, output, name, obj, os.path.join(tmp_dir, "compare")
                ):
                    continue
                name = f"{i}_{name}"
                while name in planned:
                    name = f"_{name}"
                dst = os.path.join(tmp_dir, name)
                shutil.copyfile(obj, dst)
                obj = dst
            planned.add(name)
            paths.append(obj)
        if len(paths) > 0:
            cmd([ar, "-rc", output, *paths])


def find_llvm_tool(webrtc_src_dir: str, name: str) -> str:
    # llvm-build に含まれるツール (llvm-objcopy など) のパスを返す
    root = os.path.join(webrtc_src_dir, "third_party/llvm-build/Release+Asserts/bin")
    for path in [os.path.join(root, name), os.path.join(root, name + ".exe")]:
        if os.path.isfile(path):
            return path
    raise Exception(f"{name} is not found in {root}")


# Rust の std が固定名で定義するシンボルと、アーカイブに入れるときに付ける名前。
# 固定名のままだと、アーカイブをリンクする側の Rust の std と同じ名前になり
# 重複定義のエラーになる。
RUST_RENAMED_SYMBOLS: List[Tuple[str, str]] = [
    ("rust_eh_personality", "webrtc_rust_eh_personality"),
    ("DW.ref.rust_eh_personality", "DW.ref.webrtc_rust_eh_personality"),
]


def rename_rust_symbols(objcopy: str, objects: List[str]) -> None:
    # Rust の std が定義する固定名のシンボルを、アーカイブの中だけで使う名前に変える。
    # 固定名のままだと、アーカイブをリンクする側の Rust の std と同じ名前になり
    # 重複定義のエラーになる。--redefine-sym は参照とリロケーションも一緒に張り替えるので、
    # personality を参照する構成 (ARM の EHABI や extern "C-unwind") でも壊れない。
    args = [f"--redefine-sym={old}={new}" for old, new in RUST_RENAMED_SYMBOLS]
    for obj in objects:
        cmd([objcopy, *args, obj])


def merge_rust_objects(ar: str, webrtc_src_dir: str, webrtc_build_dir: str, output: str):
    # GN が作った libwebrtc.a に、C++ のランタイムライブラリ (libc++.a と
    # libc++abi.a) と Rust の静的ライブラリ (*.rlib) の中身を足して配布用のアーカイブを作る。
    # unwind のライブラリは足さない。Android の NDK の clang や Rust のように利用者が
    # 自分でリンクするもので、足すと _Unwind_* が重複する
    rlibs = find_build_rlibs(webrtc_build_dir, os.path.join("obj", "libwebrtc.a"))
    archives = find_cxx_runtime_archives(webrtc_build_dir)
    logging.info(f"create {output} with {len(rlibs)} rlibs and {len(archives)} archives")
    shutil.copyfile(os.path.join(webrtc_build_dir, "obj", "libwebrtc.a"), output)
    with tempfile.TemporaryDirectory() as tmp_dir:
        extracted = collect_archive_objects(ar, archives, tmp_dir)
        rust_objects = collect_archive_objects(ar, rlibs, tmp_dir)
        rename_rust_symbols(find_llvm_tool(webrtc_src_dir, "llvm-objcopy"), rust_objects)
        append_objects(ar, output, [*extracted, *rust_objects])


def find_compiler_rt_builtins(webrtc_src_dir: str, arch: str) -> Optional[str]:
    # compiler-rt の builtins を探す。Rust の std が f16 の変換関数 (__truncsfhf2 と
    # __extendhfsf2) を参照するため、MSVC でリンクする利用者向けにアーカイブへ同梱する。
    # builtins は llvm-build の中のバージョンごとのディレクトリ (clang/24 など) にある。
    root = os.path.join(webrtc_src_dir, "third_party/llvm-build/Release+Asserts/lib/clang")
    if not os.path.isdir(root):
        return None
    for version in sorted(os.listdir(root)):
        path = os.path.join(root, version, "lib", "windows", f"clang_rt.builtins-{arch}.lib")
        if os.path.isfile(path):
            return path
    return None


def merge_rust_objects_windows(
    webrtc_src_dir: str, webrtc_build_dir: str, target: str, output: str
):
    # Windows は lld-link の /lib でアーカイブを作る。lld-link はアーカイブの入力を展開して
    # 取り込むため、rlib をそのまま渡せば Rust のオブジェクトがメンバーになる。lib.rmeta と
    # lib.rmeta-link も一緒に入るがリンクには影響しない。/machine を明示して、ターゲットと
    # 違うアーキテクチャのオブジェクトが混ざったら失敗させる。
    lld_link = os.path.join(
        webrtc_src_dir, "third_party/llvm-build/Release+Asserts/bin/lld-link.exe"
    )
    if target == "windows_x86_64":
        machine = "x64"
        arch = "x86_64"
    else:
        machine = "arm64"
        arch = "aarch64"
    rlibs = find_build_rlibs(webrtc_build_dir, os.path.join("obj", "webrtc.lib"))
    libs = [os.path.join(webrtc_build_dir, "obj", "webrtc.lib"), *rlibs]
    compiler_rt = find_compiler_rt_builtins(webrtc_src_dir, arch)
    if compiler_rt is not None:
        libs.append(compiler_rt)
    logging.info(f"create {output} with {len(rlibs)} rlibs")
    rm_rf(output)
    cmd([lld_link, "/lib", f"/machine:{machine}", f"/out:{output}", *libs])


def split_command_line(command_line: str) -> List[str]:
    # コマンドラインを引数に分割する。Windows のコマンドラインはバックスラッシュで
    # 引用符をエスケープするため shlex では再現できない。OS の CommandLineToArgvW を
    # 使って、コンパイラが実際に受け取るのと同じ引数に分割する
    if platform.system() != "Windows":
        return shlex.split(command_line)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
    shell32.CommandLineToArgvW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    argc = ctypes.c_int(0)
    argv = shell32.CommandLineToArgvW(command_line, ctypes.byref(argc))
    if not argv:
        raise Exception(f"CommandLineToArgvW failed to split {command_line}")
    try:
        return [argv[i] for i in range(argc.value)]
    finally:
        # CommandLineToArgvW が確保したメモリは LocalFree で解放する
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree(argv)


def find_cxx_compile_command(webrtc_build_dir: str) -> List[str]:
    # アーカイブに入っている C++ のオブジェクトのコンパイルコマンドを GN から取り出す。
    # テストプログラムは WebRTC と同じコンパイラと同じフラグ (libc++ や sysroot、--target)
    # と、同じ定義マクロでコンパイルする必要があるため、GN が生成したコマンドをそのまま
    # 利用する。ninja -t commands は依存も含めたコマンドを一度に出力するので、その中から
    # WebRTC の実装をコンパイルするものを選ぶ。
    # Windows のテストは MSVC でコンパイルするため、定義マクロとインクルードパスだけを
    # ここから取り出して cl.exe に渡す
    if platform.system() == "Windows":
        # Windows のアーカイブは webrtc.lib で、C++ の標準の指定も MSVC と同じ /std: になる
        archive = os.path.join("obj", "webrtc.lib")
        std_flag = "/std:c++"
    else:
        archive = os.path.join("obj", "libwebrtc.a")
        std_flag = "-std=c++"
    # 出力に UTF-8 として不正なバイトが混ざることがあるため surrogateescape でデコードする
    stdout = subprocess.run(
        ["ninja", "-C", webrtc_build_dir, "-t", "commands", archive],
        capture_output=True,
    ).stdout
    for line in stdout.decode("utf-8", errors="surrogateescape").splitlines():
        command = split_command_line(line)
        if not any(token.startswith(std_flag) for token in command):
            continue
        # WebRTC の実装をコンパイルするコマンドを選ぶ。アーカイブの C++ のオブジェクトは
        # どれも WEBRTC_LIBRARY_IMPL を付けてコンパイルされている
        if "-DWEBRTC_LIBRARY_IMPL" in command:
            return command
    raise Exception(f"C++ compile command of webrtc is not found in {webrtc_build_dir}")


def get_test_link_libraries(target: str, work_dir: str) -> List[str]:
    # 配布する libwebrtc.a を使う側がリンクする必要があるプラットフォームのライブラリ。
    # GN のリンクでは GN がこれらを直接リンカに渡すため、アーカイブには入っていない。
    # この指定だけでアーカイブの中の未定義シンボルを解決できることを確認する
    if target in ("android", "android_sdk"):
        # Android は unwind のライブラリを利用者が用意する。NDK の clang は
        # -l:libunwind.a を自動でリンクし、Rust も -lunwind を付ける。GN の ldflags は
        # 共有ライブラリ向けに --unwindlib=none を付けるので、テストでは GN がビルドした
        # libunwind のオブジェクトを渡して C++ のランタイムが参照する _Unwind_* を解決する
        unwinds = find_files(
            os.path.join(work_dir, "obj", "buildtools", "third_party", "libunwind"), "*.o"
        )
        if not unwinds:
            raise Exception(f"libunwind objects are not found in {work_dir}")
        return ["-llog", "-lOpenSLES", *unwinds]
    if target == "macos_arm64":
        return [
            "-framework",
            "AVFoundation",
            "-framework",
            "AudioToolbox",
            "-framework",
            "CoreAudio",
            "-framework",
            "QuartzCore",
            "-framework",
            "CoreMedia",
            "-framework",
            "VideoToolbox",
            "-framework",
            "AppKit",
            "-framework",
            "Metal",
            "-framework",
            "MetalKit",
            "-framework",
            "OpenGL",
            "-framework",
            "IOSurface",
            "-framework",
            "ScreenCaptureKit",
        ]
    if target in ("ios", "ios_sdk"):
        return [
            "-framework",
            "CoreFoundation",
            "-framework",
            "AVFoundation",
            "-framework",
            "AudioToolbox",
            "-framework",
            "CoreAudio",
            "-framework",
            "CoreMedia",
            "-framework",
            "CoreVideo",
            "-framework",
            "VideoToolbox",
            "-framework",
            "Metal",
            "-framework",
            "IOSurface",
            "-framework",
            "QuartzCore",
            "-framework",
            "UIKit",
        ]
    # Linux と Raspberry Pi OS
    return ["-lX11", "-ldl", "-lrt", "-lpthread"]


def gn_desc(webrtc_src_dir: str, webrtc_build_dir: str, name: str) -> List[str]:
    # GN からリンクの指定を取り出す。テストのリンクは GN と同じ指定で行う必要がある
    with cd(webrtc_src_dir):
        return cmdcap(["gn", "desc", webrtc_build_dir, "//:webrtc", "--all", name]).split()


def get_test_include_dirs(webrtc_src_dir: str) -> List[str]:
    # テストプログラムから WebRTC の公開ヘッダーを include するために必要なディレクトリ。
    # コンパイルコマンドの include はそのソースファイルが使うものだけなので、テスト自身が
    # include するヘッダーが必要とするディレクトリはここで足す。公開ヘッダーが include
    # している third_party のヘッダーも含める
    return [
        "-I" + webrtc_src_dir,
        "-I" + os.path.join(webrtc_src_dir, "third_party/abseil-cpp"),
        "-I" + os.path.join(webrtc_src_dir, "third_party/boringssl/src/include"),
        "-I" + os.path.join(webrtc_src_dir, "third_party/libyuv/include"),
        "-I" + os.path.join(webrtc_src_dir, "third_party/zlib"),
        "-I" + os.path.join(webrtc_src_dir, "sdk/objc"),
    ]


def get_test_compile_flags(command: List[str]) -> List[str]:
    # コンパイルコマンドから、テストプログラムのコンパイルとリンクに使うフラグを作る。
    # コンパイルとリンクの指定 (-c と -o)、依存ファイルの出力先 (-MMD と -MF)、
    # テストに不要な Chromium 内部のチェック (-Xclang) と警告のエラー化 (-Werror) を外す。
    # テストプログラムは WebRTC の一部ではないので、テスト側の警告でビルドを止めない
    flags: List[str] = [command[0]]
    i = 1
    while i < len(command):
        token = command[i]
        if token in ("-c", "-o", "-MF", "-fmodule-name", "/c", "/Fo"):
            i += 2
            continue
        if token in ("-MMD", "-fmodule-name") or token.startswith("-Werror") or token == "-Xclang":
            i += 2 if token == "-Xclang" else 1
            continue
        flags.append(token)
        i += 1
    return flags


# MSVC の cl.exe にそのまま渡せる GN のコンパイルフラグ。GN は clang-cl 向けの
# フラグを生成するため、MSVC が解釈できないもの (-imsvc や -f... や -W... など) は
# 渡さない。定義マクロとインクルードパス、ABI に関わる /MT と /std: はそのまま渡す
MSVC_COMPILE_FLAGS: Tuple[str, ...] = (
    "-D",
    "-I",
    "/bigobj",
    "/Brepro",
    "/D",
    "/FS",
    "/guard:cf",
    "/Gw",
    "/Gy",
    "/I",
    "/MT",
    "/O2",
    "/Oy-",
    "/std:",
    "/TP",
    "/utf-8",
    "/Z7",
    "/Zc:",
)


def get_msvc_env(arch: str) -> Dict[str, str]:
    # テストプログラムのコンパイルとリンクに使う MSVC の環境変数を組み立てる。
    # main() が取り込む VsDevCmd.bat はアーキテクチャを指定しないため x86 の環境に
    # なる。ビルドしたアーキテクチャでテストするために、ここで指定し直す
    vs_install_dir = os.environ.get("VSINSTALLDIR")
    if vs_install_dir is None:
        raise Exception("VSINSTALLDIR is not set")
    vs_dev_cmd = os.path.join(vs_install_dir, "Common7", "Tools", "VsDevCmd.bat")
    stdout = cmdcap(["cmd", "/c", f"{vs_dev_cmd}", f"-arch={arch}", "&&", "set"])
    env = dict(os.environ)
    for m in re.finditer(r"(\w+)=(.*)", stdout):
        key = m.group(1)
        # Windows の環境変数は大文字小文字を区別しない。VsDevCmd.bat は Path のように
        # 一部を大文字小文字違いで設定するので、名前を大文字に揃えて上書きする
        for name in [name for name in env if name.upper() == key.upper()]:
            del env[name]
        env[key.upper()] = m.group(2)
    return env


def get_msvc_tools(env: Dict[str, str], target: str) -> Tuple[str, str]:
    # MSVC のコンパイラとリンカをパスで直接選ぶ。VsDevCmd.bat が設定する PATH には
    # main() が先に取り込んだ別のアーキテクチャのツールが残っているため、PATH から
    # 探すとビルドしたアーキテクチャと違うツールを選ぶことがある
    vc_tools_dir = env.get("VCTOOLSINSTALLDIR")
    if vc_tools_dir is None:
        raise Exception("VCToolsInstallDir is not set")
    host = platform.machine().lower()
    if host in ("x86_64", "amd64"):
        host = "x64"
    elif host in ("aarch64", "arm64"):
        host = "arm64"
    else:
        raise Exception(f"unknown host architecture {platform.machine()}")
    bin_dir = os.path.join(vc_tools_dir, "bin", f"Host{host}", target)
    compiler = os.path.join(bin_dir, "cl.exe")
    linker = os.path.join(bin_dir, "link.exe")
    for path in (compiler, linker):
        if not os.path.isfile(path):
            raise Exception(f"{path} is not found")
    return (compiler, linker)


def can_run_on_host(target: str, arch: str) -> bool:
    # ビルドした実行ファイルをこのホストで実行できるかどうか。
    # iOS と Android の実行ファイルはホストの OS では動かせない。
    if target in ("ios", "ios_sdk", "android", "android_sdk"):
        return False
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return arch.endswith("x86_64")
    if machine in ("aarch64", "arm64"):
        return arch.endswith("arm64") or arch.endswith("armv8")
    return False


def test_link_in(webrtc_src_dir: str, work_dir: str, target: str, arch: str) -> None:
    # 配布するアーカイブだけをリンクした実行ファイルを作る。
    # GN のリンクでは rlib や libc++ がリンカに直接渡されるため、アーカイブが
    # 自己完結していなくてもリンクできてしまう。ここではアーカイブだけを渡す。
    archive = os.path.join(work_dir, "webrtc.lib")
    if not os.path.isfile(archive):
        archive = os.path.join(work_dir, "libwebrtc.a")
    if not os.path.isfile(archive):
        raise Exception(f"archive is not found in {work_dir}")
    source = os.path.join(BASE_DIR, "tests", "link_test.cc")
    object_file = os.path.join(work_dir, "link_test.o")
    binary = os.path.join(work_dir, "link_test")
    if platform.system() == "Windows":
        binary += ".exe"

    logging.info(f"test link {archive} in {work_dir}")
    if platform.system() == "Windows":
        # 配布したアーカイブをリンクするのは利用者 (sora-cpp-sdk や webrtc-rs) と同じ
        # MSVC である。テストプログラムも MSVC でコンパイルして link.exe でリンクする
        if target == "windows_x86_64":
            machine = "x64"
        elif target == "windows_arm64":
            machine = "arm64"
        else:
            raise Exception(f"unknown Windows target {target}")
        env = get_msvc_env(machine)
        compiler, linker = get_msvc_tools(env, machine)
        # コンパイルコマンドの中のパスはビルドディレクトリからの相対パスなので、ビルド
        # ディレクトリを作業ディレクトリにして実行する。定義マクロとインクルードパスは
        # GN が生成したものから MSVC でも通用するものだけを渡す
        flags = [
            *[
                token
                for token in find_cxx_compile_command(work_dir)[1:]
                if token.startswith(MSVC_COMPILE_FLAGS)
            ],
            *get_test_include_dirs(webrtc_src_dir),
        ]
        cmd(
            [compiler, "/nologo", "/c", *flags, f"/Fo{object_file}", source],
            cwd=work_dir,
            env=env,
        )

        # リンクするライブラリは GN のリンク行と同じものにする。gn desc の libs に加えて
        # GN の ldflags に入っている toolchain 既定のライブラリ (ntdll や userenv など) も
        # 渡す。Rust の std が Windows の API を参照するため、これらが無いと未定義シンボル
        # になる。ビルドディレクトリの中のパス (compiler-rt の builtins など) はアーカイブに
        # 同梱されているので渡さない
        link_libraries = [
            token
            for token in [
                *gn_desc(webrtc_src_dir, work_dir, "libs"),
                *gn_desc(webrtc_src_dir, work_dir, "ldflags"),
            ]
            if token.lower().endswith(".lib") and "/" not in token
        ]
        # 渡すのはテストプログラムのオブジェクトとアーカイブだけである。GN がリンク行に
        # 並べる rlib や C++ のランタイムは渡さない。これらがアーカイブに入っていなければ
        # 未定義シンボルになる
        cmd(
            [
                linker,
                "/nologo",
                f"/machine:{machine}",
                f"/out:{binary}",
                object_file,
                archive,
                *link_libraries,
            ],
            cwd=work_dir,
            env=env,
        )
    else:
        flags = [
            *get_test_compile_flags(find_cxx_compile_command(work_dir)),
            *get_test_include_dirs(webrtc_src_dir),
        ]
        # コンパイルコマンドの中のパスはビルドディレクトリからの相対パスなので、ビルド
        # ディレクトリを作業ディレクトリにして実行する。コンパイラだけは絶対パスにする
        flags[0] = os.path.abspath(os.path.join(work_dir, flags[0]))
        compiler = flags[0]
        cmd([*flags, "-c", source, "-o", object_file], cwd=work_dir)

        # リンクは GN が使うフラグで行う (GC の設定や sysroot、スレッドのライブラリなどが
        # 含まれる)。渡すのはテストプログラムのオブジェクトとアーカイブだけで、GN がリンク行に
        # 並べる rlib や C++ のランタイムは渡さない。これらがアーカイブに入っていなければ
        # 未定義シンボルになる
        # GN はリンカに lld を使う。gn desc で取れる ldflags には含まれないので足す
        link_flags = [
            "-fuse-ld=lld",
            # テストのリンクでは警告をエラーにしない。GN の ldflags にも -Werror が入っており、
            # テストプログラムは WebRTC の一部ではないので、テスト側の警告でリンクを止めない
            *[
                token
                for token in gn_desc(webrtc_src_dir, work_dir, "ldflags")
                if not token.startswith("-Werror")
            ],
        ]
        # ライブラリのうち、ビルドディレクトリの中のファイルのパス (compiler-rt の builtins
        # など) はリンクする側が用意できないので渡さず、名前で指定できるプラットフォームの
        # ライブラリだけを渡す
        link_libraries = []
        for token in gn_desc(webrtc_src_dir, work_dir, "libs"):
            if token.startswith("-"):
                link_libraries.append(token)
            elif "/" not in token:
                link_libraries.append(f"-l{token}")
        cmd(
            [
                compiler,
                *link_flags,
                "-o",
                binary,
                object_file,
                archive,
                *link_libraries,
                *get_test_link_libraries(target, work_dir),
            ],
            cwd=work_dir,
        )
    if not can_run_on_host(target, arch):
        # 実行できないホストでは、リンクできたことだけをテストの結果として報告する
        logging.info(f"skip running {binary} because it cannot run on this host")
        print(f"link_test: リンクに成功しました ({arch} の実行はこのホストでは行いません)")
        return
    cmd([binary])


def test_link(target: str, webrtc_src_dir: str, webrtc_build_dir: str) -> None:
    # 配布する libwebrtc.a (Windows は webrtc.lib) がリンクできるか確認する。
    # アーカイブに Rust の実装や C++ のランタイムが入っていなければ未定義シンボルでリンクエラーになる。
    if target == "android":
        work_dirs = [(arch, os.path.join(webrtc_build_dir, arch)) for arch in ANDROID_ARCHS]
    elif target == "ios":
        work_dirs = [
            (
                device_arch.split(":")[1],
                os.path.join(webrtc_build_dir, *device_arch.split(":")),
            )
            for device_arch in IOS_ARCHS
        ]
    elif target in ("android_sdk", "ios_sdk"):
        # SDK が配布するのは GN がリンクしたバイナリ (aar の中の .so と xcframework の
        # 中の dylib) だけである。GN のリンクには rlib が渡されるため Rust の実装は
        # 入っており、配布物に静的ライブラリは含まれないのでリンクテストは要らない
        raise Exception(f"test-link is not needed for {target}")
    else:
        work_dirs = [(target, webrtc_build_dir)]
    for arch, work_dir in work_dirs:
        test_link_in(webrtc_src_dir, work_dir, target, arch)


SYSROOT_CONFIGS = {
    "raspberry-pi-os_armv8": "raspberry-pi-os_armv8.json",
    "ubuntu-20.04_armv8": "ubuntu-20.04_armv8.json",
    "ubuntu-22.04_armv8": "ubuntu-22.04_armv8.json",
    "ubuntu-24.04_armv8": "ubuntu-24.04_armv8.json",
    "ubuntu-26.04_armv8": "ubuntu-26.04_armv8.json",
}


def init_sysroot(target: str, output_dir: str, force: bool) -> None:
    config_path = Path(BASE_DIR) / "sysroot" / SYSROOT_CONFIGS[target]
    config = load_sysroot_config(config_path)
    if config.name != target:
        raise RuntimeError(
            f"Sysroot config name does not match target: expected={target}, actual={config.name}"
        )
    build_sysroot(config, Path(output_dir), force=force)


COMMON_GN_ARGS = [
    "rtc_include_tests=false",
    "rtc_use_h264=false",
    "is_component_build=false",
    "rtc_build_examples=false",
    "use_rtti=true",
    "rtc_build_tools=false",
    "rtc_use_perfetto=false",
    "libyuv_include_tests=false",
    "libyuv_use_sme=false",
    "use_debug_fission=false",
]
# - https://webrtc-review.googlesource.com/c/src/+/232600 が影響している可能性があるため use_lld=false を追加
IOS_COMMON_GN_ARGS = [
    "rtc_libvpx_build_vp9=true",
    "enable_dsyms=true",
    "use_lld=false",
    "rtc_enable_objc_symbol_export=true",
    "treat_warnings_as_errors=false",
]
ANDROID_COMMON_GN_ARGS: list[str] = []

WEBRTC_BUILD_TARGETS_MACOS_COMMON = [
    "api/audio_codecs:builtin_audio_decoder_factory",
    "api/task_queue:default_task_queue_factory",
    "sdk:native_api",
    "sdk:default_codec_factory_objc",
    "pc:peer_connection",
    "sdk:videocapture_objc",
]
WEBRTC_BUILD_TARGETS = {
    "macos_arm64": [*WEBRTC_BUILD_TARGETS_MACOS_COMMON, "sdk:mac_framework_objc"],
    "ios": [*WEBRTC_BUILD_TARGETS_MACOS_COMMON, "sdk:framework_objc"],
    "ios_sdk": [*WEBRTC_BUILD_TARGETS_MACOS_COMMON, "sdk:framework_objc"],
    "android": [
        "sdk/android:libwebrtc",
        "sdk/android:libjingle_peerconnection_so",
        "sdk/android:native_api",
    ],
    "android_sdk": [
        "sdk/android:libwebrtc",
        "sdk/android:libjingle_peerconnection_so",
        "sdk/android:native_api",
    ],
}


def get_build_targets(target):
    ts = [":default"]
    if target not in ("windows_x86_64", "windows_arm64"):
        ts += ["buildtools/third_party/libc++"]
    ts += WEBRTC_BUILD_TARGETS.get(target, [])
    return ts


IOS_ARCHS = ["device:arm64"]
IOS_FRAMEWORK_ARCHS = ["simulator:arm64", "device:arm64"]


def to_gn_args(gn_args: List[str], extra_gn_args: str) -> str:
    s = " ".join(gn_args)
    if len(extra_gn_args) == 0:
        return s
    return s + " " + extra_gn_args


def gn_gen(webrtc_src_dir: str, webrtc_build_dir: str, gn_args: List[str], extra_gn_args: str):
    with cd(webrtc_src_dir):
        args = ["gn", "gen", webrtc_build_dir, "--args=" + to_gn_args(gn_args, extra_gn_args)]
        logging.info(" ".join(args))
        return cmd(args)


def get_webrtc_version_info(version_info: VersionInfo):
    xs = version_info.webrtc_version.split(".")
    ys = version_info.webrtc_build_version.split(".")
    if len(xs) >= 3 and len(ys) >= 4:
        branch = "M" + version_info.webrtc_version.split(".")[0]
        commit = version_info.webrtc_version.split(".")[2]
        revision = version_info.webrtc_commit
        maint = version_info.webrtc_build_version.split(".")[3]
    else:
        # HEAD ビルドだと正しくバージョンが取れないので、その場合は適当に空文字を入れておく
        branch = ""
        commit = ""
        revision = ""
        maint = ""
    return [branch, commit, revision, maint]


def build_webrtc_ios(
    source_dir,
    build_dir,
    version_info: VersionInfo,
    deps_info: DepsInfo,
    extra_gn_args,
    webrtc_source_dir=None,
    webrtc_build_dir=None,
    debug=False,
    gen=False,
    gen_force=False,
    nobuild=False,
):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")
    if webrtc_build_dir is None:
        webrtc_build_dir = os.path.join(build_dir, "webrtc")

    webrtc_src_dir = os.path.join(webrtc_source_dir, "src")

    mkdir_p(webrtc_build_dir)

    libs = []
    for device_arch in IOS_ARCHS:
        [device, arch] = device_arch.split(":")
        work_dir = os.path.join(webrtc_build_dir, device, arch)
        if gen_force:
            rm_rf(work_dir)

        with cd(os.path.join(webrtc_src_dir, "tools_webrtc", "ios")):
            ios_deployment_target = cmdcap(
                [
                    "python3",
                    "-c",
                    "from build_ios_libs import IOS_MINIMUM_DEPLOYMENT_TARGET;"
                    f'print(IOS_MINIMUM_DEPLOYMENT_TARGET["{device}"])',
                ]
            )

        if not os.path.exists(os.path.join(work_dir, "args.gn")) or gen:
            gn_args = [
                f"is_debug={'true' if debug else 'false'}",
                'target_os="ios"',
                f'target_cpu="{arch}"',
                f'target_environment="{device}"',
                "ios_enable_code_signing=false",
                f'ios_deployment_target="{ios_deployment_target}"',
                f"enable_stripping={'false' if debug else 'true'}",
                *IOS_COMMON_GN_ARGS,
                *COMMON_GN_ARGS,
            ]
            gn_gen(webrtc_src_dir, work_dir, gn_args, extra_gn_args)
        if not nobuild:
            cmd(["ninja", "-C", work_dir, *get_build_targets("ios")])
            merge_rust_objects(
                "/usr/bin/ar", webrtc_src_dir, work_dir, os.path.join(work_dir, "libwebrtc.a")
            )
        libs.append(os.path.join(work_dir, "libwebrtc.a"))

    cmd(["lipo", *libs, "-create", "-output", os.path.join(webrtc_build_dir, "libwebrtc.a")])


def build_webrtc_ios_sdk(
    source_dir,
    build_dir,
    version_info: VersionInfo,
    deps_info: DepsInfo,
    extra_gn_args,
    webrtc_source_dir=None,
    webrtc_build_dir=None,
    debug=False,
):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")

    webrtc_src_dir = os.path.join(webrtc_source_dir, "src")

    # WebRTC.xcframework のビルド
    gn_args = [
        *COMMON_GN_ARGS,
        *IOS_COMMON_GN_ARGS,
    ]
    cmd(
        [
            os.path.join(webrtc_src_dir, "tools_webrtc", "ios", "build_ios_libs.sh"),
            "-o",
            # M140 あたりからソースディレクトリ以下でないとエラーになるようになっているので
            # webrtc_src_dir を利用する
            # os.path.join(webrtc_build_dir, "framework"),
            os.path.join(webrtc_src_dir, "out"),
            "--build_config",
            "debug" if debug else "release",
            "--arch",
            *IOS_FRAMEWORK_ARCHS,
            "--extra-gn-args",
            to_gn_args(gn_args, extra_gn_args),
        ]
    )
    info = {}
    branch, commit, revision, maint = get_webrtc_version_info(version_info)
    info["branch"] = branch
    info["commit"] = commit
    info["revision"] = revision
    info["maint"] = maint
    with open(
        os.path.join(webrtc_src_dir, "out", "WebRTC.xcframework", "build_info.json"),
        "w",
    ) as f:
        f.write(json.dumps(info, indent=4))


ANDROID_ARCHS = ["arm64-v8a"]
ANDROID_SDK_ARCHS = ["arm64-v8a"]
ANDROID_TARGET_CPU = {
    "armeabi-v7a": "arm",
    "arm64-v8a": "arm64",
}


def build_webrtc_android(
    source_dir,
    build_dir,
    version_info: VersionInfo,
    deps_info: DepsInfo,
    extra_gn_args,
    webrtc_source_dir=None,
    webrtc_build_dir=None,
    debug=False,
    gen=False,
    gen_force=False,
    nobuild=False,
):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")
    if webrtc_build_dir is None:
        webrtc_build_dir = os.path.join(build_dir, "webrtc")

    webrtc_src_dir = os.path.join(webrtc_source_dir, "src")

    mkdir_p(webrtc_build_dir)

    # Java ファイル作成
    branch, commit, revision, maint = get_webrtc_version_info(version_info)
    name = "WebrtcBuildVersion"
    lines = []
    lines.append("package org.webrtc;")
    lines.append(f"public interface {name} {{")
    lines.append(f'    public static final String webrtc_branch = "{branch}";')
    lines.append(f'    public static final String webrtc_commit = "{commit}";')
    lines.append(f'    public static final String webrtc_revision = "{revision}";')
    lines.append(f'    public static final String maint_version = "{maint}";')
    lines.append("}")
    with open(
        os.path.join(webrtc_src_dir, "sdk", "android", "api", "org", "webrtc", f"{name}.java"), "wb"
    ) as f:
        f.writelines(map(lambda x: (x + "\n").encode("utf-8"), lines))

    for arch in ANDROID_ARCHS:
        work_dir = os.path.join(webrtc_build_dir, arch)
        if gen_force:
            rm_rf(work_dir)
        if not os.path.exists(os.path.join(work_dir, "args.gn")) or gen:
            gn_args = [
                f"is_debug={'true' if debug else 'false'}",
                f"is_java_debug={'true' if debug else 'false'}",
                'target_os="android"',
                f'target_cpu="{ANDROID_TARGET_CPU[arch]}"',
                'android_static_analysis="off"',
                *ANDROID_COMMON_GN_ARGS,
                *COMMON_GN_ARGS,
            ]
            gn_gen(webrtc_src_dir, work_dir, gn_args, extra_gn_args)
        if not nobuild:
            cmd(["ninja", "-C", work_dir, *get_build_targets("android")])
            ar = os.path.join(webrtc_src_dir, "third_party/llvm-build/Release+Asserts/bin/llvm-ar")
            merge_rust_objects(ar, webrtc_src_dir, work_dir, os.path.join(work_dir, "libwebrtc.a"))


def build_webrtc_android_sdk(
    source_dir,
    build_dir,
    version_info: VersionInfo,
    deps_info: DepsInfo,
    extra_gn_args,
    webrtc_source_dir=None,
    webrtc_build_dir=None,
    debug=False,
):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")
    if webrtc_build_dir is None:
        webrtc_build_dir = os.path.join(build_dir, "webrtc")

    webrtc_src_dir = os.path.join(webrtc_source_dir, "src")

    mkdir_p(webrtc_build_dir)

    # Java ファイル作成
    branch, commit, revision, maint = get_webrtc_version_info(version_info)
    name = "WebrtcBuildVersion"
    lines = []
    lines.append("package org.webrtc;")
    lines.append(f"public interface {name} {{")
    lines.append(f'    public static final String webrtc_branch = "{branch}";')
    lines.append(f'    public static final String webrtc_commit = "{commit}";')
    lines.append(f'    public static final String webrtc_revision = "{revision}";')
    lines.append(f'    public static final String maint_version = "{maint}";')
    lines.append("}")
    with open(
        os.path.join(webrtc_src_dir, "sdk", "android", "api", "org", "webrtc", f"{name}.java"), "wb"
    ) as f:
        f.writelines(map(lambda x: (x + "\n").encode("utf-8"), lines))

    gn_args_base = [
        f"is_debug={'true' if debug else 'false'}",
        f"is_java_debug={'true' if debug else 'false'}",
        *COMMON_GN_ARGS,
        *ANDROID_COMMON_GN_ARGS,
    ]

    # aar 生成
    # M140 あたりからソースディレクトリ以下でないとエラーになるようになっているので
    # webrtc_src_dir を利用する
    work_dir = os.path.join(webrtc_src_dir, "out")
    mkdir_p(work_dir)
    gn_args = [*gn_args_base]
    with cd(webrtc_src_dir):
        cmd(
            [
                "python3",
                os.path.join(webrtc_src_dir, "tools_webrtc", "android", "build_aar.py"),
                "--build-dir",
                work_dir,
                "--output",
                os.path.join(work_dir, "libwebrtc.aar"),
                "--arch",
                *ANDROID_SDK_ARCHS,
                "--extra-gn-args",
                to_gn_args(gn_args, extra_gn_args),
            ]
        )


def build_webrtc(
    source_dir,
    build_dir,
    target: str,
    version_info: VersionInfo,
    deps_info: DepsInfo,
    extra_gn_args,
    webrtc_source_dir=None,
    webrtc_build_dir=None,
    debug=False,
    gen=False,
    gen_force=False,
    nobuild=False,
    nobuild_macos_framework=False,
):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")
    if webrtc_build_dir is None:
        webrtc_build_dir = os.path.join(build_dir, "webrtc")

    webrtc_src_dir = os.path.join(webrtc_source_dir, "src")

    mkdir_p(webrtc_build_dir)

    # ビルド
    if gen_force:
        rm_rf(webrtc_build_dir)
    if not os.path.exists(os.path.join(webrtc_build_dir, "args.gn")) or gen:
        gn_args = [
            f"is_debug={'true' if debug else 'false'}",
            *COMMON_GN_ARGS,
        ]
        if target in ["windows_x86_64", "windows_arm64"]:
            gn_args += [
                'target_os="win"',
                f'target_cpu="{"x64" if target == "windows_x86_64" else "arm64"}"',
                "use_custom_libcxx=false",
                "use_custom_libcxx_for_host=false",
            ]
        elif target in ("macos_arm64",):
            gn_args += [
                'target_os="mac"',
                'target_cpu="arm64"',
                f'mac_deployment_target="{deps_info.macos_deployment_target}"',
                "enable_stripping=true",
                "enable_dsyms=true",
                "rtc_libvpx_build_vp9=true",
                "rtc_enable_symbol_export=true",
                "rtc_enable_objc_symbol_export=false",
                "treat_warnings_as_errors=false",
                "clang_use_chrome_plugins=false",
                "use_lld=false",
            ]
        elif target in (
            "raspberry-pi-os_armv8",
            "ubuntu-20.04_armv8",
            "ubuntu-22.04_armv8",
            "ubuntu-24.04_armv8",
            "ubuntu-26.04_armv8",
        ):
            sysroot = os.path.join(source_dir, "rootfs")
            arm64_set = (
                "raspberry-pi-os_armv8",
                "ubuntu-20.04_armv8",
                "ubuntu-22.04_armv8",
                "ubuntu-24.04_armv8",
                "ubuntu-26.04_armv8",
            )
            gn_args += [
                'target_os="linux"',
                f'target_cpu="{"arm64" if target in arm64_set else "arm"}"',
                f'target_sysroot="{sysroot}"',
                "rtc_use_pipewire=false",
            ]
        elif target in ("ubuntu-22.04_x86_64", "ubuntu-24.04_x86_64", "ubuntu-26.04_x86_64"):
            gn_args += [
                'target_os="linux"',
                "rtc_use_pipewire=false",
            ]
        else:
            raise Exception(f"Target {target} is not supported")

        gn_gen(webrtc_src_dir, webrtc_build_dir, gn_args, extra_gn_args)

    if nobuild:
        return

    cmd(["ninja", "-C", webrtc_build_dir, *get_build_targets(target)])

    if target in ["windows_x86_64", "windows_arm64"]:
        merge_rust_objects_windows(
            webrtc_src_dir, webrtc_build_dir, target, os.path.join(webrtc_build_dir, "webrtc.lib")
        )
    else:
        if target in ("macos_arm64",):
            ar = "/usr/bin/ar"
        else:
            ar = os.path.join(webrtc_src_dir, "third_party/llvm-build/Release+Asserts/bin/llvm-ar")
        merge_rust_objects(
            ar, webrtc_src_dir, webrtc_build_dir, os.path.join(webrtc_build_dir, "libwebrtc.a")
        )

    # macOS の場合は WebRTC.framework に追加情報を入れる
    if (target in ("macos_arm64",)) and not nobuild_macos_framework:
        branch, commit, revision, maint = get_webrtc_version_info(version_info)
        info = {}
        info["branch"] = branch
        info["commit"] = commit
        info["revision"] = revision
        info["maint"] = maint
        with open(
            os.path.join(webrtc_build_dir, "WebRTC.framework", "Resources", "build_info.json"), "w"
        ) as f:
            f.write(json.dumps(info, indent=4))

        # Info.plistの編集(tools_wertc/ios/build_ios_libs.py内の処理を踏襲)
        info_plist_path = os.path.join(
            webrtc_build_dir, "WebRTC.framework", "Resources", "Info.plist"
        )
        ver = cmdcap(
            ["/usr/libexec/PlistBuddy", "-c", "Print :CFBundleShortVersionString", info_plist_path],
            resolve=False,
        )
        cmd(
            ["/usr/libexec/PlistBuddy", "-c", f"Set :CFBundleVersion {ver}.0", info_plist_path],
            resolve=False,
            encoding="utf-8",
        )
        cmd(["plutil", "-convert", "binary1", info_plist_path])

        # xcframeworkの作成
        rm_rf(os.path.join(webrtc_build_dir, "WebRTC.xcframework"))
        cmd(
            [
                "xcodebuild",
                "-create-xcframework",
                "-framework",
                os.path.join(webrtc_build_dir, "WebRTC.framework"),
                "-debug-symbols",
                os.path.join(webrtc_build_dir, "WebRTC.dSYM"),
                "-output",
                os.path.join(webrtc_build_dir, "WebRTC.xcframework"),
            ]
        )


def copy_headers(webrtc_src_dir, webrtc_package_dir, target):
    if target in ["windows_x86_64", "windows_arm64"]:
        # robocopy の戻り値は特殊なので、check=False にしてうまくエラーハンドリングする
        # https://docs.microsoft.com/ja-jp/troubleshoot/windows-server/backup-and-storage/return-codes-used-robocopy-utility
        r = cmd(
            [
                "robocopy",
                webrtc_src_dir,
                os.path.join(webrtc_package_dir, "include"),
                "*.h",
                "*.hpp",
                "*.inc",
                "/S",
                "/NP",
                "/NFL",
                "/NDL",
            ],
            check=False,
        )
        if r.returncode >= 4:
            raise Exception("robocopy failed")
    else:
        mkdir_p(os.path.join(webrtc_package_dir, "include"))
        cmd(
            [
                "rsync",
                "-amv",
                "--exclude=out/",
                "--include=*/",
                "--include=*.h",
                "--include=*.hpp",
                "--include=*.inc",
                "--exclude=*",
                os.path.join(webrtc_src_dir, "."),
                os.path.join(webrtc_package_dir, "include", "."),
            ]
        )


def generate_version_info(webrtc_src_dir, webrtc_package_dir):
    lines = []
    GIT_INFOS = [
        (["."], ""),
        (["build"], "BUILD"),
        (["buildtools"], "BUILDTOOLS"),
        (["third_party", "libc++", "src"], "THIRD_PARTY_LIBCXX_SRC"),
        (["third_party", "libc++abi", "src"], "THIRD_PARTY_LIBCXXABI_SRC"),
        (["third_party", "libunwind", "src"], "THIRD_PARTY_LIBUNWIND_SRC"),
        (["third_party"], "THIRD_PARTY"),
        (["tools"], "TOOLS"),
    ]
    for dirs, name in GIT_INFOS:
        url, rev = git_get_url_and_revision(os.path.join(webrtc_src_dir, *dirs))
        prefix = "WEBRTC_SRC_" + (f"{name}_" if len(name) != 0 else "")
        lines += [
            f"{prefix}URL={url}",
            f"{prefix}COMMIT={rev}",
        ]
    shutil.copyfile("VERSION", os.path.join(webrtc_package_dir, "VERSIONS"))
    with open(os.path.join(webrtc_package_dir, "VERSIONS"), "ab") as f:
        f.writelines(map(lambda x: (x + "\n").encode("utf-8"), lines))


def generate_deps_info(webrtc_src_dir, webrtc_package_dir):
    shutil.copyfile("DEPS", os.path.join(webrtc_package_dir, "DEPS"))
    with cd(os.path.join(webrtc_src_dir, "tools_webrtc", "ios")):
        ios_deployment_target = cmdcap(
            [
                "python3",
                "-c",
                "from build_ios_libs import IOS_MINIMUM_DEPLOYMENT_TARGET;"
                'print(IOS_MINIMUM_DEPLOYMENT_TARGET["device"])',
            ]
        )
    with open(os.path.join(webrtc_package_dir, "DEPS"), "ab") as f:
        f.write(f"IOS_DEPLOYMENT_TARGET={ios_deployment_target}\n".encode("utf-8"))


def package_webrtc(
    source_dir,
    build_dir,
    package_dir,
    target,
    webrtc_source_dir=None,
    webrtc_build_dir=None,
    webrtc_package_dir=None,
):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, "webrtc")
    if webrtc_build_dir is None:
        webrtc_build_dir = os.path.join(build_dir, "webrtc")
    if webrtc_package_dir is None:
        webrtc_package_dir = os.path.join(package_dir, "webrtc")

    webrtc_src_dir = os.path.join(webrtc_source_dir, "src")

    rm_rf(webrtc_package_dir)
    mkdir_p(webrtc_package_dir)

    # ライセンス生成
    if target == "android":
        dirs = []
        for arch in ANDROID_ARCHS:
            dirs += [
                os.path.join(webrtc_build_dir, arch),
            ]
    elif target == "android_sdk":
        dirs = []
        for arch in ANDROID_SDK_ARCHS:
            dirs += [
                os.path.join(webrtc_src_dir, "out", arch),
            ]
    elif target == "ios":
        dirs = []
        for device_arch in IOS_ARCHS:
            [device, arch] = device_arch.split(":")
            dirs.append(os.path.join(webrtc_build_dir, device, arch))
    elif target == "ios_sdk":
        dirs = []
        for device_arch in IOS_FRAMEWORK_ARCHS:
            [device, arch] = device_arch.split(":")
            dirs.append(os.path.join(webrtc_src_dir, "out", f"{device}_{arch}_libs"))
    else:
        dirs = [webrtc_build_dir]
    ts = []
    for t in get_build_targets(target):
        ts += ["--target", t]
    cmd(
        [
            "python3",
            os.path.join(webrtc_src_dir, "tools_webrtc", "libs", "generate_licenses.py"),
            *ts,
            webrtc_package_dir,
            *dirs,
        ]
    )
    os.rename(
        os.path.join(webrtc_package_dir, "LICENSE.md"), os.path.join(webrtc_package_dir, "NOTICE")
    )

    # ヘッダーファイルをコピー
    copy_headers(webrtc_src_dir, webrtc_package_dir, target)

    # バージョン情報
    generate_version_info(webrtc_src_dir, webrtc_package_dir)

    # 依存情報
    generate_deps_info(webrtc_src_dir, webrtc_package_dir)

    # ライブラリ
    src_root_dir = webrtc_build_dir
    if target in ["windows_x86_64", "windows_arm64"]:
        files = [
            (["webrtc.lib"], ["lib", "webrtc.lib"]),
        ]
    elif target in ("macos_arm64",):
        files = [
            (["libwebrtc.a"], ["lib", "libwebrtc.a"]),
            (["WebRTC.xcframework"], ["Frameworks", "WebRTC.xcframework"]),
        ]
    elif target == "ios":
        files = [
            (["libwebrtc.a"], ["lib", "libwebrtc.a"]),
        ]
    elif target == "ios_sdk":
        # M140 あたりからソースディレクトリ以下でないとエラーになるようになっているので
        # webrtc_src_dir にビルド済みバイナリが配置されている
        src_root_dir = webrtc_src_dir
        files = [
            (["out", "WebRTC.xcframework"], ["Frameworks", "WebRTC.xcframework"]),
        ]
    elif target == "android":
        # どの arch でも jar は同じなので適当に最初のアーキテクチャを選ぶ
        jar_arch = ANDROID_ARCHS[0]
        files = [
            (
                [jar_arch, "lib.java", "sdk", "android", "libwebrtc.jar"],
                ["jar", "webrtc.jar"],
            ),
        ]
        for arch in ANDROID_ARCHS:
            files.append(([arch, "libwebrtc.a"], ["lib", arch, "libwebrtc.a"]))
    elif target == "android_sdk":
        # M140 あたりからソースディレクトリ以下でないとエラーになるようになっているので
        # webrtc_src_dir にビルド済みバイナリが配置されている
        src_root_dir = webrtc_src_dir

        files = [
            (["out", "libwebrtc.aar"], ["aar", "libwebrtc.aar"]),
        ]
    else:
        files = [
            (["libwebrtc.a"], ["lib", "libwebrtc.a"]),
        ]
    for src, dst in files:
        dstpath = os.path.join(webrtc_package_dir, *dst)
        mkdir_p(os.path.dirname(dstpath))
        srcpath = os.path.join(src_root_dir, *src)
        if os.path.isdir(srcpath):
            shutil.copytree(srcpath, dstpath)
        else:
            shutil.copy2(srcpath, dstpath)

    # Android 向け AAR にライセンス通知 (NOTICE) を同梱する
    #
    # JitPack などの Maven リポジトリでは AAR 単体が配布されるため、 AAR の中に
    # NOTICE を入れておく。 META-INF/NOTICE は Android Gradle Plugin が既定で
    # APK から除外するため、 利用者のパッケージングには影響しない。
    if target == "android_sdk":
        aar_path = os.path.join(webrtc_package_dir, "aar", "libwebrtc.aar")
        with zipfile.ZipFile(aar_path, "a") as f:
            f.write(os.path.join(webrtc_package_dir, "NOTICE"), "META-INF/NOTICE")

    # 圧縮
    with cd(package_dir):
        if target in ["windows_x86_64", "windows_arm64"]:
            with zipfile.ZipFile(f"webrtc.{target}.zip", "w") as f:
                for file in enum_all_files("webrtc", "."):
                    f.write(filename=file, arcname=file)
        else:
            with tarfile.open(f"webrtc.{target}.tar.gz", "w:gz") as f:
                for file in enum_all_files("webrtc", "."):
                    f.add(name=file, arcname=file)

    # target が ios_sdk のときに WebRTC.xcframework を zip 化
    if target == "ios_sdk":
        frameworks_dir = os.path.join(package_dir, "webrtc", "Frameworks")
        with cd(frameworks_dir):
            with zipfile.ZipFile("WebRTC.xcframework.zip", "w") as f:
                for file in enum_all_files("WebRTC.xcframework", "."):
                    f.write(filename=file, arcname=file)
        # WebRTC.xcframework.zip を package_dir に移動
        src_xcframework_zip_path = os.path.join(frameworks_dir, "WebRTC.xcframework.zip")
        dst_xcframework_zip_path = os.path.join(package_dir, "WebRTC.xcframework.zip")
        shutil.move(src_xcframework_zip_path, dst_xcframework_zip_path)


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TARGETS = [
    "windows_x86_64",
    "windows_arm64",
    "macos_arm64",
    "ubuntu-22.04_x86_64",
    "ubuntu-24.04_x86_64",
    "ubuntu-26.04_x86_64",
    "ubuntu-20.04_armv8",
    "ubuntu-22.04_armv8",
    "ubuntu-24.04_armv8",
    "ubuntu-26.04_armv8",
    "raspberry-pi-os_armv8",
    "android",
    "android_sdk",
    "ios",
    "ios_sdk",
]


def check_target(target):
    logging.debug(f"uname: {platform.uname()}")

    if platform.system() == "Windows":
        logging.info(f"OS: {platform.system()}")
        return target in ["windows_x86_64", "windows_arm64"]
    elif platform.system() == "Darwin":
        logging.info(f"OS: {platform.system()}")
        return target in ("macos_arm64", "ios", "ios_sdk")
    elif platform.system() == "Linux":
        release = read_version_file("/etc/os-release")
        os = release["NAME"]
        logging.info(f"OS: {os}")
        if os != "Ubuntu":
            return False

        # x86_64 環境以外ではビルド不可
        arch = platform.machine()
        logging.info(f"Arch: {arch}")
        if arch not in ("AMD64", "x86_64"):
            return False

        # クロスコンパイルなので Ubuntu だったら任意のバージョンでビルド可能（なはず）
        if target in (
            "ubuntu-20.04_armv8",
            "ubuntu-22.04_armv8",
            "ubuntu-24.04_armv8",
            "ubuntu-26.04_armv8",
            "raspberry-pi-os_armv8",
            "android",
            "android_sdk",
        ):
            return True

        # x86_64 用ビルドはバージョンが合っている必要がある
        osver = release["VERSION_ID"]
        logging.info(f"OS Version: {osver}")
        if target == "ubuntu-22.04_x86_64" and osver == "22.04":
            return True
        if target == "ubuntu-24.04_x86_64" and osver == "24.04":
            return True
        if target == "ubuntu-26.04_x86_64" and osver == "26.04":
            return True

        return False
    else:
        return False


def get_webrtc_branch_info(branch: str) -> Tuple[str, str]:
    # 指定されたブランチのコミットハッシュとコミットポジションを取得する
    src_commits = downloadcap(
        f"https://webrtc.googlesource.com/src.git/+log/refs/branch-heads/{branch}"
    )
    r = re.search(r'\<a href="(.*?)"\>', src_commits)
    if r is None:
        raise Exception("Could not find commit hash")
    url = r.group(1)
    commit = url.split("/")[-1]
    src_commit = downloadcap(f"https://webrtc.googlesource.com{url}")
    r = re.search(
        r"^Cr-Commit-Position: refs/branch-heads/([0-9]+)@\{#([0-9]+)\}", src_commit, re.MULTILINE
    )
    r2 = re.search(r"^Cr-Commit-Position: refs/heads/main@{#[0-9]+}", src_commit, re.MULTILINE)
    if r is None and r2 is None:
        raise Exception("Could not find commit position")
    if r is not None:
        if branch != r.group(1):
            raise Exception("Branch mismatch")
        position = r.group(2)
    else:
        # 最初のコミットの場合は refs/heads/main になって、コミットポジションは存在しない
        position = "0"
    return commit, position


def version_list(args):
    milestones = json.loads(downloadcap("https://chromiumdash.appspot.com/fetch_milestones"))
    for m in milestones[:5]:
        milestone = m["milestone"]
        branch = m["webrtc_branch"]
        commit, position = get_webrtc_branch_info(branch)
        print(f"m{milestone} {branch} {position} {commit}")


def version_update(args):
    milestones = json.loads(downloadcap("https://chromiumdash.appspot.com/fetch_milestones"))
    # milestones は以下のようなデータになっている
    # [
    #   {
    #     "angle_branch": "6422",
    #     "bling_ldap": "govind",
    #     "bling_owner": "Krishna Govind",
    #     "chromium_branch": "6422",
    #     "chromium_main_branch_hash": "9012208d0ce02e0cf0adb9b62558627c356f3278",
    #     "chromium_main_branch_position": 1287751,
    #     "clank_ldap": "govind",
    #     "clank_owner": "Krishna Govind",
    #     "cros_ldap": "matthewjoseph",
    #     "cros_owner": "Matt Nelson",
    #     "dawn_branch": "6422",
    #     "desktop_ldap": "pbommana",
    #     "desktop_owner": "Prudhvi Bommana",
    #     "devtools_branch": "6422",
    #     "merge_phase": "medium_priority",
    #     "milestone": 125,
    #     "pdfium_branch": "6422",
    #     "schedule_active": true,
    #     "schedule_phase": "beta",
    #     "skia_branch": "m125",
    #     "v8_branch": "12.5",
    #     "webrtc_branch": "6422"
    #   },
    #   ...
    # ]
    version_path = os.path.join(BASE_DIR, "VERSION")
    for m in milestones:
        milestone = m["milestone"]
        branch = m["webrtc_branch"]
        if args.target == f"m{milestone}":
            version_file = read_version_file(version_path)
            rmilestone, rbranch, rposition, rbuild = version_file["WEBRTC_BUILD_VERSION"].split(".")

            commit, position = get_webrtc_branch_info(branch)

            # 同じバージョンなら元のビルド番号を利用する
            if rmilestone == str(milestone) and rbranch == branch and rposition == position:
                build = rbuild
            else:
                build = 0

            with open(version_path, "w") as f:
                f.write(f"WEBRTC_BUILD_VERSION={milestone}.{branch}.{position}.{build}\n")
                f.write(f"WEBRTC_VERSION={milestone}.{branch}.{position}\n")
                f.write(f"WEBRTC_READABLE_VERSION=M{milestone}.{branch}@{{#{position}}}\n")
                f.write(f"WEBRTC_COMMIT={commit}\n")
            return
    else:
        raise Exception(f"Could not find milestone {args.target}")


def main():
    """
    メモ

    ビルド方針:
        - 引数無しで実行した場合、ビルドのみ行う
            - もし必要とするファイルが存在しなければ取得や生成を行うが、新しい更新があるかどうかは確認しない。
        - 各種引数を渡すと、更新や生成を行う。
            - fetch 系: 各種ソースを更新する
            - fetch-force 系: 一旦全て削除してから取得し直す
            - gen 系: 既存のビルドディレクトリの上に gn gen を行う
            - gen-force 系: 既存のビルドディレクトリは完全に削除してから gn gen をやり直す
            - nobuild 系: ビルドを行わない
    """
    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers()
    bp = sp.add_parser("build")
    bp.set_defaults(op="build")
    bp.add_argument("target", choices=TARGETS)
    bp.add_argument("--debug", action="store_true")
    bp.add_argument("--source-dir")
    bp.add_argument("--build-dir")
    bp.add_argument("--rootfs-fetch-force", action="store_true")
    bp.add_argument("--depottools-fetch", action="store_true")
    bp.add_argument("--webrtc-gen", action="store_true")
    bp.add_argument("--webrtc-gen-force", action="store_true")
    bp.add_argument("--webrtc-extra-gn-args", default="")
    bp.add_argument("--webrtc-nobuild", action="store_true")
    bp.add_argument("--webrtc-build-dir")
    bp.add_argument("--webrtc-source-dir")
    bp.add_argument("--no-history", action="store_true")
    # WebRTC の取得やビルドを行わず、クロスコンパイル用 sysroot だけを生成する
    sp_sysroot = sp.add_parser("sysroot")
    sp_sysroot.set_defaults(op="sysroot")
    sp_sysroot.add_argument("target", choices=SYSROOT_CONFIGS)
    sp_sysroot.add_argument("--source-dir")
    sp_sysroot.add_argument("--force", action="store_true")
    # VERSION で指定されたバージョンのソースを取得する
    fp = sp.add_parser("fetch")
    fp.set_defaults(op="fetch")
    fp.add_argument("target", choices=TARGETS)
    fp.add_argument("--debug", action="store_true")
    fp.add_argument("--source-dir")
    fp.add_argument("--build-dir")
    fp.add_argument("--webrtc-source-dir")
    fp.add_argument("--webrtc-build-dir")
    # ソースコードの状態を現在のバージョンに戻す
    rp = sp.add_parser("revert")
    rp.set_defaults(op="revert")
    rp.add_argument("target", choices=TARGETS)
    rp.add_argument("--debug", action="store_true")
    rp.add_argument("--source-dir")
    rp.add_argument("--build-dir")
    rp.add_argument("--webrtc-source-dir")
    rp.add_argument("--webrtc-build-dir")
    rp.add_argument("--patch")
    rp.add_argument("--commit", action="store_true")
    # ソースコードの差分を出力する
    dp = sp.add_parser("diff")
    dp.set_defaults(op="diff")
    dp.add_argument("target", choices=TARGETS)
    dp.add_argument("--debug", action="store_true")
    dp.add_argument("--source-dir")
    dp.add_argument("--build-dir")
    dp.add_argument("--webrtc-source-dir")
    dp.add_argument("--webrtc-build-dir")
    # 現在 build と package を分ける意味は無いのだけど、
    # 今後複数のビルドを纏めてパッケージングする時に備えて別コマンドにしておく
    pp = sp.add_parser("package")
    pp.set_defaults(op="package")
    pp.add_argument("target", choices=TARGETS)
    pp.add_argument("--debug", action="store_true")
    pp.add_argument("--source-dir")
    pp.add_argument("--build-dir")
    pp.add_argument("--package-dir")
    pp.add_argument("--depottools-fetch", action="store_true")
    pp.add_argument("--webrtc-build-dir")
    pp.add_argument("--webrtc-source-dir")
    pp.add_argument("--webrtc-package-dir")
    tp = sp.add_parser("test-link")
    tp.set_defaults(op="test-link")
    tp.add_argument("target", choices=TARGETS)
    tp.add_argument("--debug", action="store_true")
    tp.add_argument("--source-dir")
    tp.add_argument("--build-dir")
    tp.add_argument("--webrtc-build-dir")
    tp.add_argument("--webrtc-source-dir")
    # バージョン操作系
    vup = sp.add_parser("version_update")
    vup.set_defaults(op="version_update")
    vup.add_argument("target")
    vlp = sp.add_parser("version_list")
    vlp.set_defaults(op="version_list")

    args = parser.parse_args()

    if not hasattr(args, "op"):
        parser.error("Required subcommand")

    if args.op == "version_list":
        version_list(args)
        return

    if args.op == "version_update":
        version_update(args)
        return

    if args.op == "sysroot":
        source_dir = os.path.join(BASE_DIR, "_source", args.target)
        if args.source_dir is not None:
            source_dir = os.path.abspath(args.source_dir)
        mkdir_p(source_dir)
        init_sysroot(args.target, os.path.join(source_dir, "rootfs"), args.force)
        return

    if not check_target(args.target):
        raise Exception(f"Target {args.target} is not supported on your platform")

    configuration = "debug" if args.debug else "release"

    source_dir = os.path.join(BASE_DIR, "_source", args.target)
    build_dir = os.path.join(BASE_DIR, "_build", args.target, configuration)
    package_dir = os.path.join(BASE_DIR, "_package", args.target)
    patch_dir = os.path.join(BASE_DIR, "patches")

    if args.source_dir is not None:
        source_dir = os.path.abspath(args.source_dir)
    if args.build_dir is not None:
        build_dir = os.path.abspath(args.build_dir)

    webrtc_source_dir = (
        os.path.abspath(args.webrtc_source_dir) if args.webrtc_source_dir is not None else None
    )
    webrtc_build_dir = (
        os.path.abspath(args.webrtc_build_dir) if args.webrtc_build_dir is not None else None
    )

    if args.op == "package":
        if args.package_dir is not None:
            package_dir = args.package_dir
        webrtc_package_dir = (
            os.path.abspath(args.webrtc_package_dir)
            if args.webrtc_package_dir is not None
            else None
        )

    if args.target in ["windows_x86_64", "windows_arm64"]:
        # Windows の WebRTC ビルドに必要な環境変数の設定
        mkdir_p(build_dir)
        download(
            "https://github.com/microsoft/vswhere/releases/download/2.8.4/vswhere.exe", build_dir
        )
        path = cmdcap(
            [
                os.path.join(build_dir, "vswhere.exe"),
                "-latest",
                "-products",
                "*",
                "-requires",
                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                "-property",
                "installationPath",
            ]
        )
        if len(path) == 0:
            raise Exception("Visual Studio not installed")
        path = os.path.join(path, "Common7", "Tools", "VsDevCmd.bat")
        stdout = cmdcap(["cmd", "/c", f"{path}", "&&", "set"])
        for m in re.finditer(r"(\w+)=(.*)", stdout):
            os.environ[m.group(1)] = m.group(2)

        os.environ["GYP_MSVS_VERSION"] = "2019"
        os.environ["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"
        os.environ["PYTHONIOENCODING"] = "utf-8"

    version_file = read_version_file("VERSION")
    version_info = VersionInfo(
        webrtc_version=version_file["WEBRTC_VERSION"],
        webrtc_commit=version_file["WEBRTC_COMMIT"],
        webrtc_build_version=version_file["WEBRTC_BUILD_VERSION"],
    )
    deps_file = read_version_file("DEPS")
    deps_info = DepsInfo(macos_deployment_target=deps_file["MACOS_DEPLOYMENT_TARGET"])

    if args.op == "build":
        mkdir_p(source_dir)
        mkdir_p(build_dir)

        with cd(BASE_DIR):
            if args.target in SYSROOT_CONFIGS:
                sysroot = os.path.join(source_dir, "rootfs")
                init_sysroot(args.target, sysroot, args.rootfs_fetch_force)

            dir = get_depot_tools(source_dir, fetch=args.depottools_fetch)
            add_path(dir, is_after=True)
            if args.target in ["windows_x86_64", "windows_arm64"]:
                cmd(["git", "config", "--global", "core.longpaths", "true"])

            # ソース取得
            get_webrtc(
                source_dir,
                patch_dir,
                version_info.webrtc_commit,
                args.target,
                webrtc_source_dir=webrtc_source_dir,
                no_history=args.no_history,
            )

            # ビルド
            build_webrtc_args = {
                "source_dir": source_dir,
                "build_dir": build_dir,
                "version_info": version_info,
                "deps_info": deps_info,
                "extra_gn_args": args.webrtc_extra_gn_args,
                "webrtc_source_dir": webrtc_source_dir,
                "webrtc_build_dir": webrtc_build_dir,
                "debug": args.debug,
            }
            # iOS と Android は特殊すぎるので別枠行き
            if args.target == "ios":
                build_webrtc_ios(
                    **build_webrtc_args,
                    gen=args.webrtc_gen,
                    gen_force=args.webrtc_gen_force,
                    nobuild=args.webrtc_nobuild,
                )
            elif args.target == "ios_sdk":
                build_webrtc_ios_sdk(
                    **build_webrtc_args,
                )
            elif args.target == "android":
                build_webrtc_android(
                    **build_webrtc_args,
                    gen=args.webrtc_gen,
                    gen_force=args.webrtc_gen_force,
                    nobuild=args.webrtc_nobuild,
                )
            elif args.target == "android_sdk":
                build_webrtc_android_sdk(
                    **build_webrtc_args,
                )
            else:
                build_webrtc(
                    **build_webrtc_args,
                    target=args.target,
                    gen=args.webrtc_gen,
                    gen_force=args.webrtc_gen_force,
                    nobuild=args.webrtc_nobuild,
                )

    if args.op == "fetch":
        mkdir_p(source_dir)

        with cd(BASE_DIR):
            dir = get_depot_tools(source_dir, fetch=False)
            add_path(dir, is_after=True)
            fetch_webrtc(
                source_dir=source_dir,
                patch_dir=patch_dir,
                version=version_info.webrtc_commit,
                target=args.target,
                webrtc_source_dir=webrtc_source_dir,
            )

    if args.op == "revert":
        mkdir_p(source_dir)

        with cd(BASE_DIR):
            dir = get_depot_tools(source_dir, fetch=False)
            add_path(dir, is_after=True)
            revert_webrtc(
                source_dir=source_dir,
                patch_dir=patch_dir,
                target=args.target,
                webrtc_source_dir=webrtc_source_dir,
                patch=args.patch,
                commit=args.commit,
            )

    if args.op == "diff":
        mkdir_p(source_dir)

        with cd(BASE_DIR):
            dir = get_depot_tools(source_dir, fetch=False)
            add_path(dir, is_after=True)
            diff_webrtc(
                source_dir=source_dir,
                webrtc_source_dir=webrtc_source_dir,
            )

    if args.op == "package":
        mkdir_p(package_dir)
        with cd(BASE_DIR):
            dir = get_depot_tools(source_dir, fetch=args.depottools_fetch)
            add_path(dir, is_after=True)

            package_webrtc(
                source_dir=source_dir,
                build_dir=build_dir,
                package_dir=package_dir,
                target=args.target,
                webrtc_source_dir=webrtc_source_dir,
                webrtc_build_dir=webrtc_build_dir,
                webrtc_package_dir=webrtc_package_dir,
            )

    if args.op == "test-link":
        if webrtc_source_dir is None:
            webrtc_source_dir = os.path.join(source_dir, "webrtc")
        if webrtc_build_dir is None:
            webrtc_build_dir = os.path.join(build_dir, "webrtc")
        mkdir_p(source_dir)
        with cd(BASE_DIR):
            dir = get_depot_tools(source_dir, fetch=False)
            add_path(dir, is_after=True)

            test_link(
                target=args.target,
                webrtc_src_dir=os.path.join(webrtc_source_dir, "src"),
                webrtc_build_dir=webrtc_build_dir,
            )


if __name__ == "__main__":
    main()
