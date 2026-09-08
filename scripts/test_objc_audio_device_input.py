"""実際の ObjC ADM と配布ライブラリを使って PCM 入力の回帰テストを実行する。"""

import argparse
import subprocess
import tempfile
from pathlib import Path

__all__: list[str] = []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webrtc-source-dir", type=Path)
    parser.add_argument("--webrtc-package-dir", required=True, type=Path)
    parser.add_argument("--dependency-source-dir", required=True, type=Path)
    parser.add_argument("--clang-path", required=True, type=Path)
    parser.add_argument("--sanitize", action="store_true")
    arguments = parser.parse_args()
    package = arguments.webrtc_package_dir.resolve()
    dependencies = arguments.dependency_source_dir.resolve()
    include = package / "include"
    test_source = (
        Path(__file__).resolve().parent.parent / "tests" / "objc_audio_device_input_test.mm"
    )
    sdk = subprocess.check_output(
        ["xcrun", "--sdk", "macosx", "--show-sdk-path"], text=True, timeout=10
    ).strip()

    # 配布ライブラリと同じ Chromium libc++ / ABI 設定でコンパイルする。
    command = [
        str(arguments.clang_path.resolve()),
        "-std=c++23",
        "-isysroot",
        sdk,
        "-mmacosx-version-min=14.0",
        "-fobjc-arc",
        "-fno-exceptions",
        "-nostdinc++",
        "-nostdlib++",
        "-DWEBRTC_POSIX",
        "-DWEBRTC_MAC",
        "-DWEBRTC_ENABLE_SYMBOL_EXPORT",
        "-DNDEBUG",
        "-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE",
        "-D_LIBCPP_DISABLE_VISIBILITY_ANNOTATIONS",
        "-I" + str(dependencies / "buildtools" / "third_party" / "libc++"),
        "-isystem",
        str(dependencies / "third_party" / "libc++" / "src" / "include"),
        "-isystem",
        str(dependencies / "third_party" / "libc++abi" / "src" / "include"),
        "-I" + str(include),
        "-I" + str(include / "third_party" / "abseil-cpp"),
        "-I" + str(include / "sdk" / "objc"),
        "-I" + str(include / "sdk" / "objc" / "base"),
        str(test_source),
    ]
    # 修正前後の比較時だけ、指定ソースの ObjC ADM を配布ライブラリより先にリンクする。
    # 通常実行と CI は配布ライブラリ内の実装そのものを検証する。
    if arguments.webrtc_source_dir is not None:
        source = arguments.webrtc_source_dir.resolve()
        command.append(str(source / "sdk" / "objc" / "native" / "src" / "objc_audio_device.mm"))
    command += [
        str(package / "lib" / "libwebrtc.a"),
        "-framework",
        "Foundation",
        "-framework",
        "AudioToolbox",
        "-framework",
        "CoreAudio",
        "-framework",
        "AppKit",
        "-framework",
        "Security",
        "-framework",
        "SystemConfiguration",
    ]
    if arguments.sanitize:
        command += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    with tempfile.TemporaryDirectory(prefix="objc-audio-input-") as temporary_directory:
        executable = Path(temporary_directory) / "input-test"
        subprocess.run([*command, "-o", str(executable)], check=True, timeout=120)
        subprocess.run([str(executable)], check=True, timeout=10)


if __name__ == "__main__":
    main()
