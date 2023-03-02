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
from typing import Optional, Dict, List


logging.basicConfig(level=logging.INFO)


class ChangeDirectory(object):
    def __init__(self, cwd):
        self._cwd = cwd

    def __enter__(self):
        self._old_cwd = os.getcwd()
        logging.debug(f'pushd {self._old_cwd} --> {self._cwd}')
        os.chdir(self._cwd)

    def __exit__(self, exctype, excvalue, trace):
        logging.debug(f'popd {self._old_cwd} <-- {self._cwd}')
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
        logging.debug(f'rm -rf {path} => path not found')
        return
    if os.path.isfile(path) or os.path.islink(path):
        os.remove(path)
        logging.debug(f'rm -rf {path} => file removed')
    if os.path.isdir(path):
        shutil.rmtree(path)
        logging.debug(f'rm -rf {path} => directory removed')


def mkdir_p(path: str):
    if os.path.exists(path):
        logging.debug(f'mkdir -p {path} => already exists')
        return
    os.makedirs(path, exist_ok=True)
    logging.debug(f'mkdir -p {path} => directory created')


if platform.system() == 'Windows':
    PATH_SEPARATOR = ';'
else:
    PATH_SEPARATOR = ':'


def add_path(path: str, is_after=False):
    logging.debug(f'add_path: {path}')
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
    'macos_screen_capture.patch': (2, []),
    'macos_use_xcode_clang.patch': (1, ['build']),
    'windows_fix_optional.patch': (1, ['third_party']),
}

PATCHES = {
    'windows_x86_64': [
        '4k.patch',
        'add_license_dav1d.patch',
        'windows_add_deps.patch',
        'windows_silence_warnings.patch',
        'windows_fix_optional.patch',
        'windows_fix_audio_device.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ],
    'windows_arm64': [
        '4k.patch',
        'add_license_dav1d.patch',
        'windows_add_deps.patch',
        'windows_silence_warnings.patch',
        'windows_fix_optional.patch',
        'windows_fix_audio_device.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ],
    'macos_arm64': [
        'add_dep_zlib.patch',
        '4k.patch',
        'add_license_dav1d.patch',
        'macos_screen_capture.patch',
        'ios_simulcast.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'macos_use_xcode_clang.patch',
    ],
    'ios': [
        'add_dep_zlib.patch',
        '4k.patch',
        'add_license_dav1d.patch',
        'macos_screen_capture.patch',
        'ios_manual_audio_input.patch',
        'ios_simulcast.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'ios_build.patch',
        'ios_proxy.patch',
    ],
    'android': [
        'add_dep_zlib.patch',
        '4k.patch',
        'add_license_dav1d.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'android_webrtc_version.patch',
        'android_fixsegv.patch',
        'android_simulcast.patch',
        'android_hardware_video_encoder.patch',
        'android_proxy.patch',
    ],
    'raspberry-pi-os_armv6': [
        'nacl_armv6_2.patch',
        'add_dep_zlib.patch',
        '4k.patch',
        'add_license_dav1d.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ],
    'raspberry-pi-os_armv7': [
        'add_dep_zlib.patch',
        '4k.patch',
        'add_license_dav1d.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ],
    'raspberry-pi-os_armv8': [
        'add_dep_zlib.patch',
        '4k.patch',
        'add_license_dav1d.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ],
    'ubuntu-18.04_armv8': [
        'add_dep_zlib.patch',
        '4k.patch',
        'add_license_dav1d.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ],
    'ubuntu-20.04_armv8': [
        'add_dep_zlib.patch',
        '4k.patch',
        'add_license_dav1d.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ],
    'ubuntu-20.04_x86_64': [
        '4k.patch',
        'add_license_dav1d.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ],
    'ubuntu-22.04_x86_64': [
        '4k.patch',
        'add_license_dav1d.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ]
}


def apply_patch(patch, dir, depth):
    with cd(dir):
        logging.info(f'patch -p{depth} < {patch}')
        if platform.system() == 'Windows':
            cmd(['git', 'apply', f'-p{depth}',
                '--ignore-space-change', '--ignore-whitespace', '--whitespace=nowarn',
                 patch])
        else:
            with open(patch) as stdin:
                cmd(['patch', f'-p{depth}'], stdin=stdin)


def get_webrtc(source_dir, patch_dir, version, target,
               webrtc_source_dir=None, force=False, fetch=False):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, 'webrtc')
    if force:
        rm_rf(webrtc_source_dir)

    mkdir_p(webrtc_source_dir)

    if not os.path.exists(os.path.join(webrtc_source_dir, 'src')):
        with cd(webrtc_source_dir):
            cmd(['gclient'])
            cmd(['fetch', 'webrtc'])
            if target == 'android':
                with open('.gclient', 'a') as f:
                    f.write("target_os = [ 'android' ]\n")
            if target == 'ios':
                with open('.gclient', 'a') as f:
                    f.write("target_os = [ 'ios' ]\n")
            fetch = True

    src_dir = os.path.join(webrtc_source_dir, 'src')
    if fetch:
        with cd(src_dir):
            cmd(['git', 'fetch'])
            if version == 'HEAD':
                cmd(['git', 'checkout', '-f', 'origin/HEAD'])
            else:
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
        config_file=['multistrap', 'raspberry-pi-os_armv6.conf'],
        arch='armhf',
        triplet='arm-linux-gnueabihf'
    ),
    'raspberry-pi-os_armv7': MultistrapConfig(
        config_file=['multistrap', 'raspberry-pi-os_armv7.conf'],
        arch='armhf',
        triplet='arm-linux-gnueabihf'
    ),
    'raspberry-pi-os_armv8': MultistrapConfig(
        config_file=['multistrap', 'raspberry-pi-os_armv8.conf'],
        arch='arm64',
        triplet='aarch64-linux-gnu'
    ),
    'ubuntu-18.04_armv8': MultistrapConfig(
        config_file=['multistrap', 'ubuntu-18.04_armv8.conf'],
        arch='arm64',
        triplet='aarch64-linux-gnu'
    ),
    'ubuntu-20.04_armv8': MultistrapConfig(
        config_file=['multistrap', 'ubuntu-20.04_armv8.conf'],
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

    lines = cmdcap(['find', f'{sysroot}/usr/lib/gcc/{config.triplet}',
                   '-lname', '/*', '-printf', '%p %l\n']).splitlines()
    for line in lines:
        [link, target] = line.split()
        cmd(['ln', '-snfv', f'{sysroot}{target}', link])

    lines = cmdcap(['find', f'{sysroot}/usr/lib/{config.triplet}/pkgconfig', '-printf', '%f\n']).splitlines()
    for line in lines:
        target = line.strip()
        cmd(['ln', '-snfv', f'../../lib/{config.triplet}/pkgconfig/{target}',
             f'{sysroot}/usr/share/pkgconfig/{target}'])


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
    'macos_arm64': [*WEBRTC_BUILD_TARGETS_MACOS_COMMON, 'sdk:mac_framework_objc'],
    'ios': [*WEBRTC_BUILD_TARGETS_MACOS_COMMON, 'sdk:framework_objc'],
    'android': ['sdk/android:libwebrtc', 'sdk/android:libjingle_peerconnection_so', 'sdk/android:native_api'],
}


def get_build_targets(target):
    ts = [':default']
    if target not in ('windows_x86_64', 'windows_arm64', 'ios', 'macos_arm64'):
        ts += ['buildtools/third_party/libc++']
    ts += WEBRTC_BUILD_TARGETS.get(target, [])
    return ts


IOS_ARCHS = ['simulator:x64', 'device:arm64']
IOS_FRAMEWORK_ARCHS = ['simulator:x64', 'simulator:arm64', 'device:arm64']


def to_gn_args(gn_args: List[str], extra_gn_args: str) -> str:
    s = ' '.join(gn_args)
    if len(extra_gn_args) == 0:
        return s
    return s + ' ' + extra_gn_args


def gn_gen(webrtc_src_dir: str, webrtc_build_dir: str, gn_args: List[str], extra_gn_args: str):
    with cd(webrtc_src_dir):
        args = ['gn', 'gen', webrtc_build_dir, '--args=' + to_gn_args(gn_args, extra_gn_args)]
        logging.info(' '.join(args))
        return cmd(args)


def get_webrtc_version_info(version_info: VersionInfo):
    xs = version_info.webrtc_version.split('.')
    ys = version_info.webrtc_build_version.split('.')
    if len(xs) >= 3 and len(ys) >= 4:
        branch = 'M' + version_info.webrtc_version.split('.')[0]
        commit = version_info.webrtc_version.split('.')[2]
        revision = version_info.webrtc_commit
        maint = version_info.webrtc_build_version.split('.')[3]
    else:
        # HEAD ビルドだと正しくバージョンが取れないので、その場合は適当に空文字を入れておく
        branch = ''
        commit = ''
        revision = ''
        maint = ''
    return [branch, commit, revision, maint]


def build_webrtc_ios(
        source_dir, build_dir, version_info: VersionInfo, extra_gn_args,
        webrtc_source_dir=None, webrtc_build_dir=None,
        debug=False,
        gen=False, gen_force=False,
        nobuild=False, nobuild_framework=False,
        overlap_build_dir=False):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, 'webrtc')
    if webrtc_build_dir is None:
        webrtc_build_dir = os.path.join(build_dir, 'webrtc')

    webrtc_src_dir = os.path.join(webrtc_source_dir, 'src')

    mkdir_p(webrtc_build_dir)

    mkdir_p(os.path.join(webrtc_build_dir, 'framework'))
    # - M92-M93 あたりで clang++: error: -gdwarf-aranges is not supported with -fembed-bitcode
    #   がでていたので use_xcode_clang=false をすることで修正
    # - M94 で use_xcode_clang=true かつ --bitcode を有効にしてビルドが通り bitcode が有効になってることを確認
    # - M95 で再度 clang++: error: -gdwarf-aranges is not supported with -fembed-bitcode エラーがでるようになった
    # - https://webrtc-review.googlesource.com/c/src/+/232600 が影響している可能性があるため use_lld=false を追加
    gn_args_base = [
        'rtc_libvpx_build_vp9=true',
        'enable_dsyms=true',
        'use_custom_libcxx=false',
        'use_lld=false',
        'rtc_enable_objc_symbol_export=true',
        'treat_warnings_as_errors=false',
        *COMMON_GN_ARGS,
    ]

    # WebRTC.xcframework のビルド
    if not nobuild_framework:
        gn_args = [
            *gn_args_base,
        ]
        cmd([
            os.path.join(webrtc_src_dir, 'tools_webrtc', 'ios', 'build_ios_libs.sh'),
            '-o', os.path.join(webrtc_build_dir, 'framework'),
            '--build_config', 'debug' if debug else 'release',
            '--arch', *IOS_FRAMEWORK_ARCHS,
            '--extra-gn-args', to_gn_args(gn_args, extra_gn_args)
        ])
        info = {}
        branch, commit, revision, maint = get_webrtc_version_info(version_info)
        info['branch'] = branch
        info['commit'] = commit
        info['revision'] = revision
        info['maint'] = maint
        with open(os.path.join(webrtc_build_dir, 'framework', 'WebRTC.xcframework', 'build_info.json'), 'w') as f:
            f.write(json.dumps(info, indent=4))

    libs = []
    for device_arch in IOS_ARCHS:
        [device, arch] = device_arch.split(':')
        if overlap_build_dir:
            work_dir = os.path.join(webrtc_build_dir, 'framework', device, f'{arch}_libs')
        else:
            work_dir = os.path.join(webrtc_build_dir, device, arch)
        if gen_force:
            rm_rf(work_dir)

        with cd(os.path.join(webrtc_src_dir, 'tools_webrtc', 'ios')):
            ios_deployment_target = cmdcap(
                ['python3', '-c',
                 f'from build_ios_libs import IOS_DEPLOYMENT_TARGET; print(IOS_DEPLOYMENT_TARGET["{device}"])'])

        if not os.path.exists(os.path.join(work_dir, 'args.gn')) or gen or overlap_build_dir:
            gn_args = [
                f"is_debug={'true' if debug else 'false'}",
                'target_os="ios"',
                f'target_cpu="{arch}"',
                f'target_environment="{device}"',
                "ios_enable_code_signing=false",
                f'ios_deployment_target="{ios_deployment_target}"',
                f"enable_stripping={'false' if debug else 'true'}",
                *gn_args_base,
            ]
            gn_gen(webrtc_src_dir, work_dir, gn_args, extra_gn_args)
        if not nobuild:
            cmd(['ninja', '-C', work_dir, *get_build_targets('ios')])
            ar = '/usr/bin/ar'
            archive_objects(ar, os.path.join(work_dir, 'obj'), os.path.join(work_dir, 'libwebrtc.a'))
        libs.append(os.path.join(work_dir, 'libwebrtc.a'))

    cmd(['lipo', *libs, '-create', '-output', os.path.join(webrtc_build_dir, 'libwebrtc.a')])


ANDROID_ARCHS = ['armeabi-v7a', 'arm64-v8a']
ANDROID_TARGET_CPU = {
    'armeabi-v7a': 'arm',
    'arm64-v8a': 'arm64',
}


def build_webrtc_android(
        source_dir, build_dir, version_info: VersionInfo, extra_gn_args,
        webrtc_source_dir=None, webrtc_build_dir=None,
        debug=False,
        gen=False, gen_force=False,
        nobuild=False, nobuild_aar=False):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, 'webrtc')
    if webrtc_build_dir is None:
        webrtc_build_dir = os.path.join(build_dir, 'webrtc')

    webrtc_src_dir = os.path.join(webrtc_source_dir, 'src')

    mkdir_p(webrtc_build_dir)

    # Java ファイル作成
    branch, commit, revision, maint = get_webrtc_version_info(version_info)
    name = 'WebrtcBuildVersion'
    lines = []
    lines.append('package org.webrtc;')
    lines.append(f'public interface {name} {{')
    lines.append(f'    public static final String webrtc_branch = "{branch}";')
    lines.append(f'    public static final String webrtc_commit = "{commit}";')
    lines.append(f'    public static final String webrtc_revision = "{revision}";')
    lines.append(f'    public static final String maint_version = "{maint}";')
    lines.append('}')
    with open(os.path.join(webrtc_src_dir, 'sdk', 'android', 'api', 'org', 'webrtc', f'{name}.java'), 'wb') as f:
        f.writelines(map(lambda x: (x + '\n').encode('utf-8'), lines))

    gn_args_base = [
        f"is_debug={'true' if debug else 'false'}",
        f"is_java_debug={'true' if debug else 'false'}",
        *COMMON_GN_ARGS
    ]

    # aar 生成
    if not nobuild_aar:
        work_dir = os.path.join(webrtc_build_dir, 'aar')
        mkdir_p(work_dir)
        gn_args = [*gn_args_base]
        with cd(webrtc_src_dir):
            cmd(['python3', os.path.join(webrtc_src_dir, 'tools_webrtc', 'android', 'build_aar.py'),
                '--build-dir', work_dir,
                 '--output', os.path.join(work_dir, 'libwebrtc.aar'),
                 '--arch', *ANDROID_ARCHS,
                 '--extra-gn-args', to_gn_args(gn_args, extra_gn_args)])

    for arch in ANDROID_ARCHS:
        work_dir = os.path.join(webrtc_build_dir, arch)
        if gen_force:
            rm_rf(work_dir)
        if not os.path.exists(os.path.join(work_dir, 'args.gn')) or gen:
            gn_args = [
                *gn_args_base,
                'target_os="android"',
                f'target_cpu="{ANDROID_TARGET_CPU[arch]}"',
            ]
            gn_gen(webrtc_src_dir, work_dir, gn_args, extra_gn_args)
        if not nobuild:
            cmd(['ninja', '-C', work_dir, *get_build_targets('android')])
            ar = os.path.join(webrtc_src_dir, 'third_party/llvm-build/Release+Asserts/bin/llvm-ar')
            archive_objects(ar, os.path.join(work_dir, 'obj'), os.path.join(work_dir, 'libwebrtc.a'))


def build_webrtc(
        source_dir, build_dir, target: str, version_info: VersionInfo, extra_gn_args,
        webrtc_source_dir=None, webrtc_build_dir=None,
        debug=False,
        gen=False, gen_force=False,
        nobuild=False, nobuild_macos_framework=False):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, 'webrtc')
    if webrtc_build_dir is None:
        webrtc_build_dir = os.path.join(build_dir, 'webrtc')

    webrtc_src_dir = os.path.join(webrtc_source_dir, 'src')

    mkdir_p(webrtc_build_dir)

    # ビルド
    if gen_force:
        rm_rf(webrtc_build_dir)
    if not os.path.exists(os.path.join(webrtc_build_dir, 'args.gn')) or gen:
        gn_args = [
            f"is_debug={'true' if debug else 'false'}",
            *COMMON_GN_ARGS,
        ]
        if target in ['windows_x86_64', 'windows_arm64']:
            gn_args += [
                'target_os="win"',
                f'target_cpu="{"x64" if target == "windows_x86_64" else "arm64"}"',
                "use_custom_libcxx=false",
            ]
        elif target in ('macos_arm64',):
            gn_args += [
                'target_os="mac"',
                'target_cpu="arm64"',
                'mac_deployment_target="10.11"',
                'enable_stripping=true',
                'enable_dsyms=true',
                'rtc_libvpx_build_vp9=true',
                'rtc_enable_symbol_export=true',
                'rtc_enable_objc_symbol_export=false',
                'use_custom_libcxx=false',
                'treat_warnings_as_errors=false',
                'clang_use_chrome_plugins=false',
                'use_lld=false',
            ]
        elif target in ('raspberry-pi-os_armv6',
                        'raspberry-pi-os_armv7',
                        'raspberry-pi-os_armv8',
                        'ubuntu-18.04_armv8',
                        'ubuntu-20.04_armv8'):
            sysroot = os.path.join(source_dir, 'rootfs')
            arm64_set = ("raspberry-pi-os_armv8", "ubuntu-18.04_armv8", "ubuntu-20.04_armv8")
            gn_args += [
                'target_os="linux"',
                f'target_cpu="{"arm64" if target in arm64_set else "arm"}"',
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
        elif target in ('ubuntu-20.04_x86_64', 'ubuntu-22.04_x86_64'):
            gn_args += [
                'target_os="linux"',
                'rtc_use_pipewire=false',
            ]
        else:
            raise Exception(f'Target {target} is not supported')

        gn_gen(webrtc_src_dir, webrtc_build_dir, gn_args, extra_gn_args)

    if nobuild:
        return

    cmd(['ninja', '-C', webrtc_build_dir, *get_build_targets(target)])
    if target in ['windows_x86_64', 'windows_arm64']:
        pass
    elif target in ('macos_arm64',):
        ar = '/usr/bin/ar'
    else:
        ar = os.path.join(webrtc_src_dir, 'third_party/llvm-build/Release+Asserts/bin/llvm-ar')

    # ar で libwebrtc.a を生成する
    if target not in ['windows_x86_64', 'windows_arm64']:
        archive_objects(ar, os.path.join(webrtc_build_dir, 'obj'), os.path.join(webrtc_build_dir, 'libwebrtc.a'))

    # macOS の場合は WebRTC.framework に追加情報を入れる
    if (target in ('macos_arm64',)) and not nobuild_macos_framework:
        branch, commit, revision, maint = get_webrtc_version_info(version_info)
        info = {}
        info['branch'] = branch
        info['commit'] = commit
        info['revision'] = revision
        info['maint'] = maint
        with open(os.path.join(webrtc_build_dir, 'WebRTC.framework', 'Resources', 'build_info.json'), 'w') as f:
            f.write(json.dumps(info, indent=4))

        # Info.plistの編集(tools_wertc/ios/build_ios_libs.py内の処理を踏襲)
        info_plist_path = os.path.join(webrtc_build_dir, 'WebRTC.framework', 'Resources', 'Info.plist')
        ver = cmdcap(['/usr/libexec/PlistBuddy', '-c', 'Print :CFBundleShortVersionString', info_plist_path],
                     resolve=False)
        cmd(['/usr/libexec/PlistBuddy', '-c',
            f'Set :CFBundleVersion {ver}.0', info_plist_path], resolve=False, encoding='utf-8')
        cmd(['plutil', '-convert', 'binary1', info_plist_path])

        # xcframeworkの作成
        rm_rf(os.path.join(webrtc_build_dir, 'WebRTC.xcframework'))
        cmd(['xcodebuild', '-create-xcframework',
            '-framework', os.path.join(webrtc_build_dir, 'WebRTC.framework'),
             '-debug-symbols', os.path.join(webrtc_build_dir, 'WebRTC.dSYM'),
             '-output', os.path.join(webrtc_build_dir, 'WebRTC.xcframework')])


def copy_headers(webrtc_src_dir, webrtc_package_dir, target):
    if target in ['windows_x86_64', 'windows_arm64']:
        # robocopy の戻り値は特殊なので、check=False にしてうまくエラーハンドリングする
        # https://docs.microsoft.com/ja-jp/troubleshoot/windows-server/backup-and-storage/return-codes-used-robocopy-utility
        r = cmd(['robocopy', webrtc_src_dir, os.path.join(webrtc_package_dir, 'include'),
                '*.h', '*.hpp', '/S', '/NP', '/NFL', '/NDL'], check=False)
        if r.returncode >= 4:
            raise Exception('robocopy failed')
    else:
        mkdir_p(os.path.join(webrtc_package_dir, 'include'))
        cmd(['rsync', '-amv', '--include=*/', '--include=*.h', '--include=*.hpp', '--exclude=*',
            os.path.join(webrtc_src_dir, '.'), os.path.join(webrtc_package_dir, 'include', '.')])


def generate_version_info(webrtc_src_dir, webrtc_package_dir):
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
        url, rev = git_get_url_and_revision(os.path.join(webrtc_src_dir, *dirs))
        prefix = 'WEBRTC_SRC_' + (f'{name}_' if len(name) != 0 else '')
        lines += [
            f'{prefix}URL={url}',
            f'{prefix}COMMIT={rev}',
        ]
    shutil.copyfile('VERSION', os.path.join(webrtc_package_dir, 'VERSIONS'))
    with open(os.path.join(webrtc_package_dir, 'VERSIONS'), 'ab') as f:
        f.writelines(map(lambda x: (x + '\n').encode('utf-8'), lines))


def package_webrtc(source_dir, build_dir, package_dir, target,
                   webrtc_source_dir=None, webrtc_build_dir=None, webrtc_package_dir=None,
                   overlap_ios_build_dir=False):
    if webrtc_source_dir is None:
        webrtc_source_dir = os.path.join(source_dir, 'webrtc')
    if webrtc_build_dir is None:
        webrtc_build_dir = os.path.join(build_dir, 'webrtc')
    if webrtc_package_dir is None:
        webrtc_package_dir = os.path.join(package_dir, 'webrtc')

    webrtc_src_dir = os.path.join(webrtc_source_dir, 'src')

    rm_rf(webrtc_package_dir)
    mkdir_p(webrtc_package_dir)

    # ライセンス生成
    if target == 'android':
        dirs = []
        for arch in ANDROID_ARCHS:
            dirs += [
                os.path.join(webrtc_build_dir, arch),
                os.path.join(webrtc_build_dir, 'aar', arch)
            ]
    elif target == 'ios':
        dirs = []
        for device_arch in IOS_FRAMEWORK_ARCHS:
            [device, arch] = device_arch.split(':')
            dirs.append(os.path.join(webrtc_build_dir,
                                     'framework', device, f'{arch}_libs'))
        if not overlap_ios_build_dir:
            for device_arch in IOS_ARCHS:
                [device, arch] = device_arch.split(':')
                dirs.append(os.path.join(webrtc_build_dir, device, arch))
    else:
        dirs = [webrtc_build_dir]
    ts = []
    for t in get_build_targets(target):
        ts += ['--target', t]
    cmd(['python3', os.path.join(webrtc_src_dir, 'tools_webrtc', 'libs', 'generate_licenses.py'),
        *ts, webrtc_package_dir, *dirs])
    os.rename(os.path.join(webrtc_package_dir, 'LICENSE.md'), os.path.join(webrtc_package_dir, 'NOTICE'))

    # ヘッダーファイルをコピー
    copy_headers(webrtc_src_dir, webrtc_package_dir, target)

    # バージョン情報
    generate_version_info(webrtc_src_dir, webrtc_package_dir)

    # ライブラリ
    if target in ['windows_x86_64', 'windows_arm64']:
        files = [
            (['obj', 'webrtc.lib'], ['lib', 'webrtc.lib']),
        ]
    elif target in ('macos_arm64',):
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
        tmp = os.path.join(webrtc_build_dir, 'tmp')
        rm_rf(tmp)
        mkdir_p(tmp)
        with cd(tmp):
            cmd(['unzip', os.path.join(webrtc_build_dir, 'aar', 'libwebrtc.aar')])
            dstpath = os.path.join(webrtc_build_dir, 'aar', 'webrtc.jar')
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
        dstpath = os.path.join(webrtc_package_dir, *dst)
        mkdir_p(os.path.dirname(dstpath))
        srcpath = os.path.join(webrtc_build_dir, *src)
        if os.path.isdir(srcpath):
            shutil.copytree(srcpath, dstpath)
        else:
            shutil.copy2(os.path.join(webrtc_build_dir, *src), dstpath)

    # 圧縮
    with cd(package_dir):
        if target in ['windows_x86_64', 'windows_arm64']:
            with zipfile.ZipFile(f'webrtc.{target}.zip', 'w') as f:
                for file in enum_all_files('webrtc', '.'):
                    f.write(filename=file, arcname=file)
        else:
            with tarfile.open(f'webrtc.{target}.tar.gz', 'w:gz') as f:
                for file in enum_all_files('webrtc', '.'):
                    f.add(name=file, arcname=file)


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TARGETS = [
    'windows_x86_64',
    'windows_arm64',
    'macos_arm64',
    'ubuntu-20.04_x86_64',
    'ubuntu-22.04_x86_64',
    'ubuntu-18.04_armv8',
    'ubuntu-20.04_armv8',
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
        return target in ['windows_x86_64', 'windows_arm64']
    elif platform.system() == 'Darwin':
        logging.info(f'OS: {platform.system()}')
        return target in ('macos_arm64', 'ios')
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
        if target in ('ubuntu-18.04_armv8',
                      'ubuntu-20.04_armv8',
                      'raspberry-pi-os_armv6',
                      'raspberry-pi-os_armv7',
                      'raspberry-pi-os_armv8',
                      'android'):
            return True

        # x86_64 用ビルドはバージョンが合っている必要がある
        osver = release['VERSION_ID']
        logging.info(f'OS Version: {osver}')
        if target == 'ubuntu-20.04_x86_64' and osver == '20.04':
            return True
        if target == 'ubuntu-22.04_x86_64' and osver == '22.04':
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
            - fetch 系: 各種ソースを更新する
            - fetch-force 系: 一旦全て削除してから取得し直す
            - gen 系: 既存のビルドディレクトリの上に gn gen を行う
            - gen-force 系: 既存のビルドディレクトリは完全に削除してから gn gen をやり直す
            - nobuild 系: ビルドを行わない
    """
    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers()
    bp = sp.add_parser('build')
    bp.set_defaults(op='build')
    bp.add_argument("target", choices=TARGETS)
    bp.add_argument("--debug", action='store_true')
    bp.add_argument("--source-dir")
    bp.add_argument("--build-dir")
    bp.add_argument("--rootfs-fetch-force", action='store_true')
    bp.add_argument('--depottools-fetch', action='store_true')
    bp.add_argument("--webrtc-fetch", action='store_true')
    bp.add_argument("--webrtc-fetch-force", action='store_true')
    bp.add_argument("--webrtc-gen", action='store_true')
    bp.add_argument("--webrtc-gen-force", action='store_true')
    bp.add_argument("--webrtc-extra-gn-args", default='')
    bp.add_argument("--webrtc-nobuild", action='store_true')
    bp.add_argument("--webrtc-nobuild-ios-framework", action='store_true')
    bp.add_argument("--webrtc-nobuild-android-aar", action='store_true')
    bp.add_argument("--webrtc-overlap-ios-build-dir", action='store_true')
    bp.add_argument("--webrtc-build-dir")
    bp.add_argument("--webrtc-source-dir")
    # 現在 build と package を分ける意味は無いのだけど、
    # 今後複数のビルドを纏めてパッケージングする時に備えて別コマンドにしておく
    pp = sp.add_parser('package')
    pp.set_defaults(op='package')
    pp.add_argument("target", choices=TARGETS)
    pp.add_argument("--debug", action='store_true')
    pp.add_argument("--source-dir")
    pp.add_argument("--build-dir")
    pp.add_argument("--package-dir")
    pp.add_argument("--webrtc-build-dir")
    pp.add_argument("--webrtc-source-dir")
    pp.add_argument("--webrtc-package-dir")
    pp.add_argument("--webrtc-overlap-ios-build-dir", action='store_true')
    args = parser.parse_args()

    if not hasattr(args, 'op'):
        parser.error('Required subcommand')

    if not check_target(args.target):
        raise Exception(f'Target {args.target} is not supported on your platform')

    configuration = 'debug' if args.debug else 'release'

    source_dir = os.path.join(BASE_DIR, '_source', args.target)
    build_dir = os.path.join(BASE_DIR, '_build', args.target, configuration)
    package_dir = os.path.join(BASE_DIR, '_package', args.target)
    patch_dir = os.path.join(BASE_DIR, 'patches')

    if args.source_dir is not None:
        source_dir = os.path.abspath(args.source_dir)
    if args.build_dir is not None:
        build_dir = os.path.abspath(args.build_dir)

    webrtc_source_dir = os.path.abspath(args.webrtc_source_dir) if args.webrtc_source_dir is not None else None
    webrtc_build_dir = os.path.abspath(args.webrtc_build_dir) if args.webrtc_build_dir is not None else None

    if args.op == 'package':
        if args.package_dir is not None:
            package_dir = args.package_dir
        webrtc_package_dir = os.path.abspath(args.webrtc_package_dir) if args.webrtc_package_dir is not None else None

    if args.target in ['windows_x86_64', 'windows_arm64']:
        # Windows の WebRTC ビルドに必要な環境変数の設定
        mkdir_p(build_dir)
        download("https://github.com/microsoft/vswhere/releases/download/2.8.4/vswhere.exe", build_dir)
        path = cmdcap([os.path.join(build_dir, 'vswhere.exe'), '-latest',
                       '-products', '*',
                       '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64',
                       '-property', 'installationPath'])
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
    version_info = VersionInfo(
        webrtc_version=version_file['WEBRTC_VERSION'],
        webrtc_commit=version_file['WEBRTC_COMMIT'],
        webrtc_build_version=version_file['WEBRTC_BUILD_VERSION'])

    if args.op == 'build':
        mkdir_p(source_dir)
        mkdir_p(build_dir)

        with cd(BASE_DIR):
            if args.target in MULTISTRAP_CONFIGS:
                sysroot = os.path.join(source_dir, 'rootfs')
                init_rootfs(sysroot, MULTISTRAP_CONFIGS[args.target], args.rootfs_fetch_force)

            dir = get_depot_tools(source_dir, fetch=args.depottools_fetch)
            add_path(dir)
            if args.target in ['windows_x86_64', 'windows_arm64']:
                cmd(['git', 'config', '--global', 'core.longpaths', 'true'])

            # ソース取得
            get_webrtc(source_dir, patch_dir, version_info.webrtc_commit, args.target,
                       webrtc_source_dir=webrtc_source_dir,
                       fetch=args.webrtc_fetch, force=args.webrtc_fetch_force)

            # ビルド
            build_webrtc_args = {
                'source_dir': source_dir,
                'build_dir': build_dir,
                'version_info': version_info,
                'extra_gn_args': args.webrtc_extra_gn_args,
                'webrtc_source_dir': webrtc_source_dir,
                'webrtc_build_dir': webrtc_build_dir,
                'debug': args.debug,
                'gen': args.webrtc_gen,
                'gen_force': args.webrtc_gen_force,
                'nobuild': args.webrtc_nobuild,
            }
            # iOS と Android は特殊すぎるので別枠行き
            if args.target == 'ios':
                build_webrtc_ios(**build_webrtc_args,
                                 nobuild_framework=args.webrtc_nobuild_ios_framework,
                                 overlap_build_dir=args.webrtc_overlap_ios_build_dir)
            elif args.target == 'android':
                build_webrtc_android(**build_webrtc_args, nobuild_aar=args.webrtc_nobuild_android_aar)
            else:
                build_webrtc(**build_webrtc_args, target=args.target)

    if args.op == 'package':
        mkdir_p(package_dir)
        with cd(BASE_DIR):
            package_webrtc(source_dir, build_dir, package_dir, args.target,
                           webrtc_source_dir=webrtc_source_dir,
                           webrtc_build_dir=webrtc_build_dir,
                           webrtc_package_dir=webrtc_package_dir,
                           overlap_ios_build_dir=args.webrtc_overlap_ios_build_dir)


if __name__ == '__main__':
    main()
