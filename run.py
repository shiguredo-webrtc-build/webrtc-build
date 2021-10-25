import subprocess
import json
import logging
import os
import urllib.parse
import zipfile
import tarfile
import shutil
import platform
import argparse
import collections
import re
from typing import Optional, Dict


logging.basicConfig(level=logging.DEBUG)


class ChangeDirectory(object):
    def __init__(self, cwd):
        self._cwd = cwd

    def __enter__(self):
        self._old_cwd = os.getcwd()
        logging.debug(f'pushd {self._cwd}')
        os.chdir(self._cwd)

    def __exit__(self, exctype, excvalue, trace):
        logging.debug(f'popd {self._old_cwd}')
        os.chdir(self._old_cwd)
        return False


def cd(cwd):
    return ChangeDirectory(cwd)


def cmd(args, **kwargs):
    logging.debug(f'+{args} {kwargs}')
    if 'check' not in kwargs:
        kwargs['check'] = True
    if 'resolve' in kwargs:
        resolve = kwargs['resolve']
        del kwargs['resolve']
    else:
        resolve = True
    if resolve:
        args = [shutil.which(args[0]), *args[1:]]
    return subprocess.run(args, **kwargs)


# 標準出力をキャプチャするコマンド実行。シェルの `cmd ...` や $(cmd ...) と同じ
def cmdcap(args, **kwargs):
    # 3.7 でしか使えない
    # kwargs['capture_output'] = True
    kwargs['stdout'] = subprocess.PIPE
    kwargs['stderr'] = subprocess.PIPE
    kwargs['encoding'] = 'utf-8'
    return cmd(args, **kwargs).stdout.strip()


def rm_rf(path: str):
    if not os.path.exists(path):
        return
    if os.path.isfile(path) or os.path.islink(path):
        os.remove(path)
    if os.path.isdir(path):
        shutil.rmtree(path)


def mkdir_p(path: str):
    os.makedirs(path, exist_ok=True)


if platform.system() == 'Windows':
    PATH_SEPARATOR = ';'
else:
    PATH_SEPARATOR = ':'


def add_path(path: str, is_after=False):
    if 'PATH' not in os.environ:
        os.environ['PATH'] = path
        return

    if is_after:
        os.environ['PATH'] = os.environ['PATH'] + PATH_SEPARATOR + path
    else:
        os.environ['PATH'] = path + PATH_SEPARATOR + os.environ['PATH']


def download(url: str, output_dir: Optional[str] = None, filename: Optional[str] = None) -> str:
    if filename is None:
        output_path = urllib.parse.urlparse(url).path.split('/')[-1]
    else:
        output_path = filename

    if output_dir is not None:
        output_path = os.path.join(output_dir, output_path)

    if os.path.exists(output_path):
        return output_path

    try:
        if shutil.which('curl') is not None:
            cmd(["curl", "-fLo", output_path, url])
        else:
            cmd(["wget", "-cO", output_path, url])
    except Exception:
        # ゴミを残さないようにする
        if os.path.exists(output_path):
            os.remove(output_path)
        raise

    return output_path


def read_version_file(path: str) -> Dict[str, str]:
    versions = {}

    lines = open(path).readlines()
    for line in lines:
        line = line.strip()

        # コメント行
        if line[:1] == '#':
            continue

        # 空行
        if len(line) == 0:
            continue

        [a, b] = map(lambda x: x.strip(), line.split('=', 2))
        versions[a] = b.strip('"')

    return versions


# dir 以下にある全てのファイルパスを、dir2 からの相対パスで返す
def enum_all_files(dir, dir2):
    for root, _, files in os.walk(dir):
        for file in files:
            yield os.path.relpath(os.path.join(root, file), dir2)


def get_depot_tools(source_dir, fetch=False):
    dir = os.path.join(source_dir, 'depot_tools')
    if os.path.exists(dir):
        if fetch:
            cmd(['git', 'fetch'])
            cmd(['git', 'checkout', '-f', 'origin/HEAD'])
    else:
        cmd(['git', 'clone', 'https://chromium.googlesource.com/chromium/tools/depot_tools.git', dir])
    return dir


PATCH_INFO = {
    'libjpeg_turbo_mangle_jpeg_names.patch': (1, ['third_party', 'libjpeg_turbo']),
    '4k.patch': (2, []),
    'macos_h264_encoder.patch': (2, []),
    'macos_screen_capture.patch': (2, []),
    'ios_bitcode.patch': (1, ['build']),
}

PATCHES = {
    'windows': [
        '4k.patch',
        'windows_add_deps.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'macos_x86_64': [
        'add_dep_zlib.patch',
        '4k.patch',
        'macos_h264_encoder.patch',
        'macos_screen_capture.patch',
        'macos_simulcast.patch',
        'ios_simulcast.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'macos_arm64': [
        'add_dep_zlib.patch',
        '4k.patch',
        'macos_h264_encoder.patch',
        'macos_screen_capture.patch',
        'macos_simulcast.patch',
        'ios_simulcast.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'ios': [
        'add_dep_zlib.patch',
        '4k.patch',
        'macos_h264_encoder.patch',
        'macos_screen_capture.patch',
        'macos_simulcast.patch',
        'ios_manual_audio_input.patch',
        'ios_simulcast.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'ios_bitcode.patch',
    ],
    'android': [
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'android_webrtc_version.patch',
        'android_fixsegv.patch',
        'android_simulcast.patch',
    ],
    'raspberry-pi-os_armv6': [
        'nacl_armv6_2.patch',
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'raspberry-pi-os_armv7': [
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'raspberry-pi-os_armv8': [
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'ubuntu-18.04_armv8': [
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'ubuntu-18.04_x86_64': [
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'ubuntu-20.04_x86_64': [
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ]
}

def apply_patch(patch, dir, depth):
    with cd(dir):
        if platform.system() == 'Windows':
            cmd(['git', 'apply', f'-p{depth}', '--ignore-space-change', '--ignore-whitespace', '--whitespace=nowarn', patch])
        else:
            with open(patch) as stdin:
                cmd(['patch', f'-p{depth}'], stdin=stdin)


def get_webrtc(source_dir, patch_dir, version, target, force=False, fetch=False):
    webrtc_dir = os.path.join(source_dir, 'webrtc')
    if force:
        rm_rf(webrtc_dir)

    mkdir_p(webrtc_dir)
    if not os.path.exists(os.path.join(webrtc_dir, 'src')):
        with cd(webrtc_dir):
            cmd(['gclient'])
            cmd(['fetch', 'webrtc'])
            if target == 'android':
                with open('.gclient', 'a') as f:
                    f.write("target_os = [ 'android' ]\n")
            if target == 'ios':
                with open('.gclient', 'a') as f:
                    f.write("target_os = [ 'ios' ]\n")
            fetch = True

    src_dir = os.path.join(webrtc_dir, 'src')
    if fetch:
        with cd(src_dir):
            cmd(['git', 'checkout', '-f', version])
            cmd(['git', 'clean', '-df'])
            cmd(['gclient', 'sync', '-D', '--force', '--reset', '--with_branch_heads'])
            for patch in PATCHES[target]:
                depth, dirs = PATCH_INFO.get(patch, (1, ['.']))
                dir = os.path.join(src_dir, *dirs)
                apply_patch(os.path.join(patch_dir, patch), dir, depth)


def git_get_url_and_revision(dir):
    with cd(dir):
        rev = cmdcap(['git', 'rev-parse', 'HEAD'])
        url = cmdcap(['git', 'remote', 'get-url', 'origin'])
        return url, rev


VersionInfo = collections.namedtuple('VersionInfo', [
    'webrtc_version',
    'webrtc_commit',
    'webrtc_build_version',
])


def archive_objects(ar, dir, output):
    with cd(dir):
        files = cmdcap(['find', '.', '-name', '*.o']).splitlines()
        rm_rf(output)
        cmd([ar, '-rc', output, *files])


MultistrapConfig = collections.namedtuple('MultistrapConfig', [
    'config_file',
    'arch',
    'triplet'
])
MULTISTRAP_CONFIGS = {
    'raspberry-pi-os_armv6': MultistrapConfig(
        config_file=['raspberry-pi-os_armv6', 'rpi-raspbian.conf'],
        arch='armhf',
        triplet='arm-linux-gnueabihf'
    ),
    'raspberry-pi-os_armv7': MultistrapConfig(
        config_file=['raspberry-pi-os_armv7', 'rpi-raspbian.conf'],
        arch='armhf',
        triplet='arm-linux-gnueabihf'
    ),
    'raspberry-pi-os_armv8': MultistrapConfig(
        config_file=['raspberry-pi-os_armv8', 'rpi-raspbian.conf'],
        arch='arm64',
        triplet='aarch64-linux-gnu'
    ),
    'ubuntu-18.04_armv8': MultistrapConfig(
        config_file=['ubuntu-18.04_armv8', 'arm64.conf'],
        arch='arm64',
        triplet='aarch64-linux-gnu'
    ),
}


def init_rootfs(sysroot: str, config: MultistrapConfig, force=False):
    if force:
        rm_rf(sysroot)

    if os.path.exists(sysroot):
        return

    cmd(['multistrap', '--no-auth', '-a', config.arch, '-d', sysroot, '-f', os.path.join(*config.config_file)])

    lines = cmdcap(['find', f'{sysroot}/usr/lib/{config.triplet}', '-lname', '/*', '-printf', '%p %l\n']).splitlines()
    for line in lines:
        [link, target] = line.split()
        cmd(['ln', '-snfv', f'{sysroot}{target}', link])

    lines = cmdcap(['find', f'{sysroot}/usr/lib/gcc/{config.triplet}', '-lname', '/*', '-printf', '%p %l\n']).splitlines()
    for line in lines:
        [link, target] = line.split()
        cmd(['ln', '-snfv', f'{sysroot}{target}', link])

    lines = cmdcap(['find', f'{sysroot}/usr/lib/{config.triplet}/pkgconfig', '-printf', '%f\n']).splitlines()
    for line in lines:
        target = line.strip()
        cmd(['ln', '-snfv', f'../../lib/{config.triplet}/pkgconfig/{target}', f'{sysroot}/usr/share/pkgconfig/{target}'])


COMMON_GN_ARGS = [
    "rtc_include_tests=false",
    "rtc_use_h264=false",
    "is_component_build=false",
    'rtc_build_examples=false',
    "use_rtti=true",
    'rtc_build_tools=false',
]

WEBRTC_BUILD_TARGETS_MACOS_COMMON = [
    'api/audio_codecs:builtin_audio_decoder_factory',
    'api/task_queue:default_task_queue_factory',
    'sdk:native_api',
    'sdk:default_codec_factory_objc',
    'pc:peerconnection',
    'sdk:videocapture_objc',
]
WEBRTC_BUILD_TARGETS = {
    'macos_x86_64': [*WEBRTC_BUILD_TARGETS_MACOS_COMMON, 'sdk:mac_framework_objc'],
    'macos_arm64': [*WEBRTC_BUILD_TARGETS_MACOS_COMMON, 'sdk:mac_framework_objc'],
    'ios': [*WEBRTC_BUILD_TARGETS_MACOS_COMMON, 'sdk:framework_objc'],
    'android': ['sdk/android:libwebrtc', 'sd/android:libjingle_peerconnection_so', 'sdk:native_api'],
}


def get_build_targets(target):
    return [':default', *WEBRTC_BUILD_TARGETS.get(target, [])]



IOS_ARCHS=['arm64', 'x64']


def build_webrtc_ios(source_dir, build_dir, version_info, debug=False, gen=False, nobuild=False, nobuild_framework=False):
    build_webrtc_dir = os.path.join(build_dir, 'webrtc')
    mkdir_p(build_webrtc_dir)
    source_webrtc_dir = os.path.join(source_dir, 'webrtc', 'src')

    mkdir_p(os.path.join(build_webrtc_dir, 'framework'))
    # M92-M93 あたりで clang++: error: -gdwarf-aranges is not supported with -fembed-bitcode がでていたので use_code_clang=false をすることで修正
    # M94 で use_xcode_clang=true かつ --bitcode を有効にしてビルドが通り bitcode が有効になってることを確認
    # M95 で再度 clang++: error: -gdwarf-aranges is not supported with -fembed-bitcode エラーがでるようになった
    # https://webrtc-review.googlesource.com/c/src/+/232600 が影響している可能性があるため use_lld=false を追加
    gn_args_base = [
      'use_xcode_clang=true',
      'rtc_libvpx_build_vp9=true',
      'libcxx_abi_unstable=false',
      'enable_dsyms=true',
      *COMMON_GN_ARGS,
    ]

    # WebRTC.xcframework のビルド
    if not nobuild_framework:
        gn_args = [
            'use_lld=false',
            *gn_args_base,
        ]
        cmd([
            os.path.join(source_webrtc_dir, 'tools_webrtc', 'ios', 'build_ios_libs.sh'),
            '-o', os.path.join(build_webrtc_dir, 'framework'),
            '--build_config', 'debug' if debug else 'release',
            '--arch', *IOS_ARCHS,
            '--bitcode',
            '--extra-gn-args', ' '.join(gn_args)
        ])
        info = {}
        info['branch'] = 'M' + version_info.webrtc_version.split('.')[0]
        info['commit'] = version_info.webrtc_version.split('.')[2]
        info['revision'] = version_info.webrtc_commit
        info['maint'] = version_info.webrtc_build_version.split('.')[3]
        with open(os.path.join(build_webrtc_dir, 'framework', 'WebRTC.xcframework', 'build_info.json'), 'w') as f:
            f.write(json.dumps(info, indent=4))

    with cd(os.path.join(source_webrtc_dir, 'tools_webrtc', 'ios')):
        ios_deployment_target = cmdcap(['python3', '-c', 'from build_ios_libs import IOS_DEPLOYMENT_TARGET; print(IOS_DEPLOYMENT_TARGET["device"])'])

    for arch in IOS_ARCHS:
        work_dir = os.path.join(build_webrtc_dir, arch)
        if not os.path.exists(os.path.join(work_dir, 'args.gn')) or gen:
            gn_args = [
                f"is_debug={'true' if debug else 'false'}",
                'target_os="ios"',
                f'target_cpu="{arch}"',
                f'target_environment="{"device" if arch == "arm64" else "simulator"}"',
                f"ios_enable_code_signing=false",
                f'ios_deployment_target="{ios_deployment_target}"',
                'rtc_enable_symbol_export=true',
                'rtc_enable_objc_symbol_export=false',
                'enable_ios_bitcode=true',
                f"enable_stripping={'false' if debug else 'true'}",
                *gn_args_base,
            ]
            with cd(os.path.join(source_dir, 'webrtc', 'src')):
                cmd(['gn', 'gen', work_dir, '--args=' + ' '.join(gn_args)])
        if not nobuild:
            cmd(['ninja', '-C', work_dir, *get_build_targets('ios')])
            ar = '/usr/bin/ar'
            archive_objects(ar, os.path.join(work_dir, 'obj'), os.path.join(work_dir, 'libwebrtc.a'))

    libs = [os.path.join(build_webrtc_dir, arch, 'libwebrtc.a') for arch in IOS_ARCHS]
    cmd(['lipo', *libs, '-create', '-output', os.path.join(build_webrtc_dir, 'libwebrtc.a')])


ANDROID_ARCHS = ['armeabi-v7a', 'arm64-v8a']
ANDROID_TARGET_CPU = {
    'armeabi-v7a': 'arm',
    'arm64-v8a': 'arm64',
}


def build_webrtc_android(source_dir, build_dir, version_info: VersionInfo, debug=False, gen=False, nobuild=False, nobuild_aar=False):
    build_webrtc_dir = os.path.join(build_dir, 'webrtc')
    mkdir_p(build_webrtc_dir)

    # Java ファイル作成
    branch = 'M' + version_info.webrtc_version.split('.')[0]
    commit = version_info.webrtc_version.split('.')[2]
    revision = version_info.webrtc_commit
    maint = version_info.webrtc_build_version.split('.')[3]
    name = 'WebrtcBuildVersion'
    lines = []
    lines.append(f'package org.webrtc;')
    lines.append(f'public interface {name} {{')
    lines.append(f'    public static final String webrtc_branch = "{branch}";')
    lines.append(f'    public static final String webrtc_commit = "{commit}";')
    lines.append(f'    public static final String webrtc_revision = "{revision}";')
    lines.append(f'    public static final String maint_version = "{maint}";')
    lines.append(f'}}')
    with open(os.path.join(source_dir, 'webrtc', 'src', 'sdk', 'android', 'api', 'org', 'webrtc', f'{name}.java'), 'wb') as f:
        f.writelines(map(lambda x: (x + '\n').encode('utf-8'), lines))

    gn_args_base = [
        f"is_debug={'true' if debug else 'false'}",
        f"is_java_debug={'true' if debug else 'false'}",
        *COMMON_GN_ARGS
    ]

    # aar 生成
    if not nobuild_aar:
        work_dir = os.path.join(build_webrtc_dir, 'aar')
        mkdir_p(work_dir)
        gn_args = [*gn_args_base]
        with cd(os.path.join(source_dir, 'webrtc', 'src')):
            cmd(['python3', os.path.join(source_dir, 'webrtc', 'src', 'tools_webrtc', 'android', 'build_aar.py'),
                '--build-dir', work_dir,
                '--output', os.path.join(work_dir, 'libwebrtc.aar'),
                '--arch', *ANDROID_ARCHS,
                '--extra-gn-args', ' '.join(gn_args)])

    for arch in ANDROID_ARCHS:
        work_dir = os.path.join(build_webrtc_dir, arch)
        if not os.path.exists(os.path.join(work_dir, 'args.gn')) or gen:
            gn_args = [
                *gn_args_base,
                'target_os="android"',
                f'target_cpu="{ANDROID_TARGET_CPU[arch]}"',
            ]
            with cd(os.path.join(source_dir, 'webrtc', 'src')):
                cmd(['gn', 'gen', work_dir, '--args=' + ' '.join(gn_args)])
        if not nobuild:
            cmd(['ninja', '-C', work_dir, *get_build_targets('android')])
            ar = os.path.join(source_dir, 'webrtc/src/third_party/llvm-build/Release+Asserts/bin/llvm-ar')
            archive_objects(ar, os.path.join(work_dir, 'obj'), os.path.join(work_dir, 'libwebrtc.a'))


def build_webrtc(source_dir, build_dir, target: str, version_info: VersionInfo, debug=False, gen=False, nobuild=False, nobuild_macos_framework=False):
    build_webrtc_dir = os.path.join(build_dir, 'webrtc')
    mkdir_p(build_webrtc_dir)

    # ビルド
    if not os.path.exists(os.path.join(build_webrtc_dir, 'args.gn')) or gen:
        gn_args = [
            f"is_debug={'true' if debug else 'false'}",
            *COMMON_GN_ARGS,
        ]
        if target == 'windows':
            gn_args += [
                "use_custom_libcxx=false",
            ]
        elif target in ('macos_x86_64', 'macos_arm64'):
            gn_args += [
                'target_os="mac"',
                f'target_cpu="{"x64" if target == "macos_x86_64" else "arm64"}"',
                'mac_deployment_target="10.11"',
                'enable_stripping=true',
                'enable_dsyms=true',
                'rtc_libvpx_build_vp9=true',
                'rtc_enable_symbol_export=true',
                'rtc_enable_objc_symbol_export=false',
                'libcxx_abi_unstable=false',
            ]
        elif target in ('raspberry-pi-os_armv6', 'raspberry-pi-os_armv7', 'raspberry-pi-os_armv8', 'ubuntu-18.04_armv8'):
            sysroot = os.path.join(source_dir, 'rootfs')
            gn_args += [
                'target_os="linux"',
                f'target_cpu="{"arm64" if target in ("raspberry-pi-os_armv8", "ubuntu-18.04_armv8") else "arm"}"',
                f'target_sysroot="{sysroot}"',
                'rtc_use_pipewire=false',
            ]
            if target == 'raspberry-pi-os_armv6':
                gn_args += [
                    'arm_version=6',
                    'arm_arch="armv6"',
                    'arm_tune="arm1176jzf-s"',
                    'arm_fpu="vfpv2"',
                    'arm_float_abi="hard"',
                    'arm_use_neon=false',
                    'enable_libaom=false',
                ]
        elif target in ('ubuntu-18.04_x86_64', 'ubuntu-20.04_x86_64'):
            gn_args += [
                'target_os="linux"',
                'rtc_use_pipewire=false',
            ]
        else:
            raise Exception(f'Target {target} is not supported')

        with cd(os.path.join(source_dir, 'webrtc', 'src')):
            cmd(['gn', 'gen', build_webrtc_dir, '--args=' + ' '.join(gn_args)])

    if nobuild:
        return

    cmd(['ninja', '-C', build_webrtc_dir, *get_build_targets(target)])
    if target == 'windows':
        pass
    elif target in ('macos_x86_64', 'macos_arm64'):
        ar = '/usr/bin/ar'
    else:
        ar = os.path.join(source_dir, 'webrtc/src/third_party/llvm-build/Release+Asserts/bin/llvm-ar')

    # ar で libwebrtc.a を生成する
    if target != 'windows':
        archive_objects(ar, os.path.join(build_webrtc_dir, 'obj'), os.path.join(build_webrtc_dir, 'libwebrtc.a'))

    # macOS の場合は WebRTC.framework に追加情報を入れる
    if (target in ('macos_x86_64', 'macos_arm64')) and not nobuild_macos_framework:
        info = {}
        info['branch'] = 'M' + version_info.webrtc_version.split('.')[0]
        info['commit'] = version_info.webrtc_version.split('.')[2]
        info['revision'] = version_info.webrtc_commit
        info['maint'] = version_info.webrtc_build_version.split('.')[3]
        with open(os.path.join(build_webrtc_dir, 'WebRTC.framework', 'Resources', 'build_info.json'), 'w') as f:
            f.write(json.dumps(info, indent=4))

        # Info.plistの編集(tools_wertc/ios/build_ios_libs.py内の処理を踏襲)
        info_plist_path = os.path.join(build_webrtc_dir, 'WebRTC.framework', 'Resources', 'Info.plist')
        ver = cmdcap(['/usr/libexec/PlistBuddy', '-c', 'Print :CFBundleShortVersionString', info_plist_path], resolve=False)
        cmd(['/usr/libexec/PlistBuddy', '-c', f'Set :CFBundleVersion {ver}.0', info_plist_path], resolve=False, encoding='utf-8')
        cmd(['plutil', '-convert', 'binary1', info_plist_path])

        # xcframeworkの作成
        rm_rf(os.path.join(build_webrtc_dir, 'WebRTC.xcframework'))
        cmd(['xcodebuild', '-create-xcframework',
            '-framework', os.path.join(build_webrtc_dir, 'WebRTC.framework'),
            '-debug-symbols', os.path.join(build_webrtc_dir, 'WebRTC.dSYM'),
            '-output', os.path.join(build_webrtc_dir, 'WebRTC.xcframework')])



def copy_headers(source_webrtc_dir, package_webrtc_dir, target):
    if target == 'windows':
        # robocopy の戻り値は特殊なので、check=False にしてうまくエラーハンドリングする
        # https://docs.microsoft.com/ja-jp/troubleshoot/windows-server/backup-and-storage/return-codes-used-robocopy-utility
        r = cmd(['robocopy', source_webrtc_dir, os.path.join(package_webrtc_dir, 'include'), '*.h', '*.hpp', '/S', '/NP', '/NFL', '/NDL'], check=False)
        if r.returncode >= 4:
            raise Exception('robocopy failed')
    else:
        mkdir_p(os.path.join(package_webrtc_dir, 'include'))
        cmd(['rsync', '-amv', '--include=*/', '--include=*.h', '--include=*.hpp', '--exclude=*', os.path.join(source_webrtc_dir, '.'), os.path.join(package_webrtc_dir, 'include', '.')])


def generate_version_info(source_webrtc_dir, package_webrtc_dir):
    lines = []
    GIT_INFOS = [
        (['.'], ''),
        (['build'], 'BUILD'),
        (['buildtools'], 'BUILDTOOLS'),
        (['buildtools', 'third_party', 'libc++', 'trunk'], 'BUILDTOOLS_THIRD_PARTY_LIBCXX_TRUNK'),
        (['buildtools', 'third_party', 'libc++abi', 'trunk'], 'BUILDTOOLS_THIRD_PARTY_LIBCXXABI_TRUNK'),
        (['buildtools', 'third_party', 'libunwind', 'trunk'], 'BUILDTOOLS_THIRD_PARTY_LIBUNWIND_TRUNK'),
        (['third_party'], 'THIRD_PARTY'),
        (['tools'], 'TOOLS'),
    ]
    for dirs, name in GIT_INFOS:
        url, rev = git_get_url_and_revision(os.path.join(source_webrtc_dir, *dirs))
        prefix = 'WEBRTC_SRC_' + (f'{name}_' if len(name) != 0 else '')
        lines += [
            f'{prefix}URL={url}',
            f'{prefix}COMMIT={rev}',
        ]
    shutil.copyfile('VERSION', os.path.join(package_webrtc_dir, 'VERSIONS'))
    with open(os.path.join(package_webrtc_dir, 'VERSIONS'), 'ab') as f:
        f.writelines(map(lambda x: (x + '\n').encode('utf-8'), lines))


def package_webrtc(source_dir, base_build_dir, package_dir, target, configuration):
    build_webrtc_dir = os.path.join(base_build_dir, configuration, 'webrtc')
    source_webrtc_dir = os.path.join(source_dir, 'webrtc', 'src')
    package_webrtc_dir = os.path.join(package_dir, 'webrtc')
    rm_rf(package_webrtc_dir)
    mkdir_p(package_webrtc_dir)

    # ライセンス生成
    if target == 'android':
        dirs = []
        for arch in ANDROID_ARCHS:
            dirs += [
                os.path.join(build_webrtc_dir, arch),
                os.path.join(build_webrtc_dir, 'aar', arch) 
            ]
    elif target == 'ios':
        dirs = []
        for arch in IOS_ARCHS:
            dirs += [
                os.path.join(build_webrtc_dir, arch),
                os.path.join(build_webrtc_dir, 'framework', f'{"device" if arch == "arm64" else "simulator"}', f'{arch}_libs') 
            ]
    else:
        dirs = [build_webrtc_dir]
    ts = []
    for t in get_build_targets(target):
        ts += ['--target', t]
    cmd(['python3', os.path.join(source_webrtc_dir, 'tools_webrtc', 'libs', 'generate_licenses.py'),
        *ts, package_webrtc_dir, *dirs])
    os.rename(os.path.join(package_webrtc_dir, 'LICENSE.md'), os.path.join(package_webrtc_dir, 'NOTICE'))

    # ヘッダーファイルをコピー
    copy_headers(source_webrtc_dir, package_webrtc_dir, target)

    # バージョン情報
    generate_version_info(source_webrtc_dir, package_webrtc_dir)

    # ライブラリ
    if target == 'windows':
        files = [
            (['obj', 'webrtc.lib'], ['lib', 'webrtc.lib']),
        ]
    elif target in ('macos_x86_64', 'macos_arm64'):
        files = [
            (['libwebrtc.a'], ['lib', 'libwebrtc.a']),
            (['WebRTC.xcframework'], ['Frameworks', 'WebRTC.xcframework']),
        ]
    elif target == 'ios':
        files = [
            (['libwebrtc.a'], ['lib', 'libwebrtc.a']),
            (['framework', 'WebRTC.xcframework'], ['Frameworks', 'WebRTC.xcframework']),
        ]
    elif target == 'android':
        # aar を展開して classes.jar を取り出す
        tmp = os.path.join(build_webrtc_dir, 'tmp')
        rm_rf(tmp)
        mkdir_p(tmp)
        with cd(tmp):
            cmd(['unzip', os.path.join(build_webrtc_dir, 'aar', 'libwebrtc.aar')])
            dstpath = os.path.join(build_webrtc_dir, 'aar', 'webrtc.jar')
            rm_rf(dstpath)
            os.rename('classes.jar', dstpath)
        rm_rf(tmp)

        files = [
            (['aar', 'libwebrtc.aar'], ['aar', 'libwebrtc.aar']),
            (['aar', 'webrtc.jar'], ['jar', 'webrtc.jar']),
        ]
        for arch in ANDROID_ARCHS:
            files.append(([arch, 'libwebrtc.a'], ['lib', arch, 'libwebrtc.a']))
    else:
        files = [
            (['libwebrtc.a'], ['lib', 'libwebrtc.a']),
        ]
    for src, dst in files:
        dstpath = os.path.join(package_webrtc_dir, *dst)
        mkdir_p(os.path.dirname(dstpath))
        srcpath = os.path.join(build_webrtc_dir, *src)
        if os.path.isdir(srcpath):
            shutil.copytree(srcpath, dstpath)
        else:
            shutil.copy2(os.path.join(build_webrtc_dir, *src), dstpath)

    # 圧縮
    with cd(package_dir):
        if target == 'windows':
            with zipfile.ZipFile('webrtc.zip', 'w') as f:
                for file in enum_all_files('webrtc', '.'):
                    f.write(filename=file, arcname=file)
        else:
            with tarfile.open('webrtc.tar.gz', 'w:gz') as f:
                for file in enum_all_files('webrtc', '.'):
                    f.add(name=file, arcname=file)


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TARGETS = [
    'windows',
    'macos_x86_64',
    'macos_arm64',
    'ubuntu-18.04_x86_64',
    'ubuntu-20.04_x86_64',
    'ubuntu-18.04_armv8',
    'raspberry-pi-os_armv6',
    'raspberry-pi-os_armv7',
    'raspberry-pi-os_armv8',
    'android',
    'ios',
]

def check_target(target):
    logging.debug(f'uname: {platform.uname()}')

    if platform.system() == 'Windows':
        logging.info(f'OS: {platform.system()}')
        return target == 'windows'
    elif platform.system() == 'Darwin':
        logging.info(f'OS: {platform.system()}')
        return target in ('macos_x86_64', 'macos_arm64', 'ios')
    elif platform.system() == 'Linux':
        release = read_version_file('/etc/os-release')
        os = release['NAME']
        logging.info(f'OS: {os}')
        if os != 'Ubuntu':
            return False

        # x86_64 環境以外ではビルド不可
        arch = platform.machine()
        logging.info(f'Arch: {arch}')
        if arch not in ('AMD64', 'x86_64'):
            return False

        # クロスコンパイルなので Ubuntu だったら任意のバージョンでビルド可能（なはず）
        if target in ('ubuntu-18.04_armv8', 'raspberry-pi-os_armv6', 'raspberry-pi-os_armv7', 'raspberry-pi-os_armv8', 'android'):
            return True

        # x86_64 用ビルドはバージョンが合っている必要がある
        osver = release['VERSION_ID']
        logging.info(f'OS Version: {osver}')
        if target == 'ubuntu-18.04_x86_64' and osver == '18.04':
            return True
        if target == 'ubuntu-20.04_x86_64' and osver == '20.04':
            return True

        return False
    else:
        return False


def main():
    """
    メモ

    ビルド方針:
        - 引数無しで実行した場合、ビルドのみ行う
            - もし必要とするファイルが存在しなければ取得や生成を行うが、新しい更新があるかどうかは確認しない。
        - 各種引数を渡すと、更新や生成を行う。
            - --fetch-depottools - depot_tools を更新する
            - --fetch-webrtc - WebRTC のソースを更新する
                - 既存の変更は全て破棄され、パッチのみが当たった状態になる
            - --force-webrtc - 既存の WebRTC のソースを捨てて新しく取得し直す
                - どうしてもうまくいかなくなった時に使う。基本的には不要なはず
            - --gen - gn gen をやり直す
            - --nobuild - ビルドを行わない
    """
    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers()
    bp = sp.add_parser('build')
    bp.set_defaults(op='build')
    bp.add_argument("target", choices=TARGETS)
    bp.add_argument("--debug", action='store_true')
    bp.add_argument("--force-rootfs", action='store_true')
    bp.add_argument('--fetch-depottools', action='store_true')
    bp.add_argument("--fetch-webrtc", action='store_true')
    bp.add_argument("--force-webrtc", action='store_true')
    bp.add_argument("--gen", action='store_true')
    bp.add_argument("--nobuild", action='store_true')
    bp.add_argument("--nobuild-ios-framework", action='store_true')
    bp.add_argument("--nobuild-android-aar", action='store_true')
    pp = sp.add_parser('package')
    pp.set_defaults(op='package')
    pp.add_argument("target", choices=TARGETS)
    pp.add_argument("--debug", action='store_true')
    args = parser.parse_args()

    if not hasattr(args, 'op'):
        parser.error('Required subcommand')

    if not check_target(args.target):
        raise Exception(f'Target {args.target} is not supported on your platform')

    configuration = 'debug' if args.debug else 'release'

    if args.target == 'windows':
        # $SOURCE_DIR の下に置きたいが、webrtc のパスが長すぎると動かない問題と、
        # GitHub Actions の D:\ の容量が少なくてビルド出来ない問題があるので
        # このパスにソースを配置する
        source_dir = 'C:\\webrtc'
        # また、WebRTC のビルドしたファイルは同じドライブに無いといけないっぽいので、
        # BUILD_DIR とは別で用意する
        base_build_dir = f'C:\\webrtc-build'
    else:
        source_dir = os.path.join(BASE_DIR, '_source', args.target)
        base_build_dir = os.path.join(BASE_DIR, '_build', args.target)
    package_dir = os.path.join(BASE_DIR, '_package', args.target)

    mkdir_p(source_dir)
    mkdir_p(package_dir)
    patch_dir = os.path.join(BASE_DIR, 'patches')

    if args.target == 'windows':
        # Windows の WebRTC ビルドに必要な環境変数の設定
        mkdir_p(base_build_dir)
        download("https://github.com/microsoft/vswhere/releases/download/2.8.4/vswhere.exe", base_build_dir)
        path = cmdcap([os.path.join(base_build_dir, 'vswhere.exe'), '-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'])
        if len(path) == 0:
            raise Exception('Visual Studio not installed')
        path = os.path.join(path, 'Common7', 'Tools', 'VsDevCmd.bat')
        stdout = cmdcap(['cmd', '/c', f'{path}', '&&', 'set'])
        for m in re.finditer(r'(\w+)=(.*)', stdout):
            os.environ[m.group(1)] = m.group(2)

        os.environ['GYP_MSVS_VERSION'] = "2019"
        os.environ['DEPOT_TOOLS_WIN_TOOLCHAIN'] = "0"
        os.environ['PYTHONIOENCODING'] = "utf-8"

    version_file = read_version_file('VERSION')
    version_info = VersionInfo(webrtc_version=version_file['WEBRTC_VERSION'], webrtc_commit=version_file['WEBRTC_COMMIT'], webrtc_build_version=version_file['WEBRTC_BUILD_VERSION'])

    if args.op == 'build':
        configuration = 'debug' if args.debug else 'release'
        build_dir = os.path.join(base_build_dir, configuration)
        mkdir_p(build_dir)

        with cd(BASE_DIR):
            if args.target in MULTISTRAP_CONFIGS:
                sysroot = os.path.join(source_dir, 'rootfs')
                init_rootfs(sysroot, MULTISTRAP_CONFIGS[args.target], args.force_rootfs)

            dir = get_depot_tools(source_dir, fetch=args.fetch_depottools)
            add_path(dir)

            # ソース取得
            get_webrtc(source_dir, patch_dir, version_info.webrtc_commit, args.target, fetch=args.fetch_webrtc, force=args.force_webrtc)

            # ビルド
            build_webrtc_args = {
                'source_dir': source_dir,
                'build_dir': build_dir,
                'version_info': version_info,
                'debug': args.debug,
                'gen': args.gen,
                'nobuild': args.nobuild,
            }
            # 特殊すぎるので別枠行き
            if args.target == 'ios':
                build_webrtc_ios(nobuild_framework=args.nobuild_ios_framework, **build_webrtc_args)
            elif args.target == 'android':
                build_webrtc_android(nobuild_aar=args.nobuild_android_aar, **build_webrtc_args)
            else:
                build_webrtc(target=args.target, **build_webrtc_args)

    if args.op == 'package':
        with cd(BASE_DIR):
            package_webrtc(source_dir, base_build_dir, package_dir, args.target, configuration)


if __name__ == '__main__':
    main()
