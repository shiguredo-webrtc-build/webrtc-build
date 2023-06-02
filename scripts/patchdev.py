#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
import os
import json

# トップレベルのパス
top_dir = os.path.normpath(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..'))
patchdev_dir = os.path.join(top_dir, 'patchdev')


def init_project_with_cur_dir():
    init_project(os.path.basename(os.getcwd()))


def init_project(name):
    global project_dir, project_src_dir, project_build_dir, project_build_patches_dir, config_file
    project_dir = os.path.join(patchdev_dir, name)
    project_src_dir = os.path.join(project_dir, 'src')
    project_build_dir = os.path.join(project_dir, '_build')
    project_build_patches_dir = os.path.join(project_build_dir, 'patches')
    config_file = os.path.join(project_dir, "config.json")


def rtc_src_dir(platform):
    return os.path.join(top_dir, "_source", platform, "webrtc", "src")


def rtc_src_file(platform, source):
    return os.path.join(rtc_src_dir(platform), source)


def load_config():
    with open(config_file) as f:
        return Config(json.load(f))


class Config:
    def __init__(self, json):
        self.output = json["output"]
        self.platform = json["platform"]
        self.build_flags = json["build_flags"]
        self.sources = [os.path.normpath(path) for path in json["sources"]]
        self.jni_classpaths = [os.path.normpath(path) for path in json["jni_classpaths"]]
        self.jni_classes = {class_name: os.path.normpath(output) for class_name, output in json["jni_classes"].items()}


def init(args):
    project_name = args.project_name
    init_project(project_name)
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(project_src_dir, exist_ok=True)

    # Makefile
    makefile_content = """
PYTHON = python3
TOP_DIR = ../../
PATCHDEV = scripts/patchdev.py

.PHONY: sync build build-skip-patch jni diff patch clean check

sync:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) sync

build:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) build

build-skip-patch:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) build --skip-patch

jni:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) jni

diff:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) diff

patch:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) patch

check:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) check

clean:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) clean
"""
    with open(os.path.join(project_dir, "Makefile"), 'w') as f:
        f.write(makefile_content)

    # README.md
    open(os.path.join(project_dir, "README.md"), 'w').close()

    # config.json
    config_content = {
        "output": project_name + ".patch",
        "platform": args.platform,
        "build_flags": "--debug",
        "sources": [],
        "jni_classpaths": ["sdk/android/api"],
        "jni_classes": {
            "org.webrtc.Example": "sdk/android/src/jni/example.h"
        }
    }
    with open(config_file, 'w') as f:
        json.dump(config_content, f, indent=4)

    print("Initialized project in:", project_dir)

    if not args.nobuild:
        orig_dir = os.getcwd()
        os.chdir(top_dir)
        cmd = f"python3 run.py build {args.platform} --webrtc-fetch\n"
        print(f"exec: {cmd}")
        os.system(cmd)
        os.chdir(orig_dir)


def build(args):
    config = load_config()

    if not args.skip_patch:
        check_all_files(config.sources)
        for source in config.sources:
            shutil.copy2(os.path.join(project_src_dir, source), rtc_src_file(config.platform, source))

    orig_dir = os.getcwd()
    os.chdir(top_dir)
    cmd = f"python3 run.py build {config.platform} {config.build_flags}\n"
    print(f"exec: {cmd}")
    os.system(cmd)
    os.chdir(orig_dir)


def generate(args):
    config = load_config()
    check_all_files(config.sources)

    # パッチファイルのリスト
    patch_files = []

    # 各ソースファイルに対して操作を実行
    for source in config.sources:
        target = rtc_src_file(config.platform, source)
        shutil.copy2(os.path.join(project_src_dir, source), target)
        os.chdir(os.path.dirname(target))
        cmd = ['git', 'add', '-N', os.path.basename(target)]
        subprocess.check_output(cmd)
        cmd = ['git', 'diff', os.path.basename(target)]
        diff = subprocess.check_output(cmd).decode('utf-8')
        os.chdir(project_dir)
        patch_file = os.path.join(project_build_patches_dir, f'{source}.patch')
        os.makedirs(os.path.dirname(patch_file), exist_ok=True)
        with open(patch_file, 'w') as f:
            f.write(diff)
        patch_files.append(patch_file)

    # パッチファイルを結合
    with open(os.path.join(project_build_dir, config.output), 'w') as outfile:
        for patch_file in patch_files:
            with open(patch_file) as infile:
                outfile.write(infile.read())


def clean(args):
    config = load_config()

    shutil.rmtree(project_build_dir, ignore_errors=True)

    for source in config.sources:
        source_path = rtc_src_file(config.platform, source)
        os.chdir(os.path.dirname(source_path))
        os.system(f"git checkout -- {os.path.basename(source_path)}")


def diff(args):
    config = load_config()

    check_all_files(config.sources)

    for source in config.sources:
        target = rtc_src_file(config.platform, source)
        shutil.copy2(os.path.join(project_src_dir, source), target)
        os.chdir(os.path.dirname(target))
        cmd = ['git', 'add', '-N', os.path.basename(target)]
        subprocess.check_output(cmd)
        cmd = ['git', 'diff', os.path.basename(target)]
        diff = subprocess.check_output(cmd).decode('utf-8')
        os.chdir(project_dir)
        print(diff)


def sync(args):
    config = load_config()

    copied_files = 0
    for source in config.sources:
        # コピー先のファイルパス
        destination_path_in_src = os.path.join(project_src_dir, source)

        # コピー先ディレクトリの生成
        os.makedirs(os.path.dirname(destination_path_in_src), exist_ok=True)

        # ファイルが存在しなければオリジナルからコピー
        if not os.path.isfile(destination_path_in_src):
            # パッチ対象ファイルのオリジナルのパス
            original_path = rtc_src_file(config.platform, source)
            if os.path.isfile(original_path):
                shutil.copy2(original_path, destination_path_in_src)
                print(f"Copied: {destination_path_in_src}")
            else:
                # オリジナルが存在しなければ空のファイルを作る
                with open(destination_path_in_src, 'w') as f:
                    f.write('\n')
                print(f"Created: {destination_path_in_src}")
            copied_files += 1
    if copied_files == 0:
        print("No files copied.")


def check(args):
    config = load_config()
    check_all_files(config.sources)


def check_newline_at_eof(file_path):
    if not os.path.isfile(file_path):
        print(f"Error: The file {file_path} does not exist.")
        sys.exit(1)

    with open(file_path, 'rb') as f:
        if f.read(1) == b'':
            return False
        f.seek(-1, os.SEEK_END)
        last = f.read(1)

    return last == b'\n'


def jni(args):
    config = load_config()

    # Java のソースコードのみオリジナルにコピーする
    check_all_files(config.sources)
    for source in config.sources:
        if source.endswith('.java'):
            shutil.copy2(os.path.join(project_src_dir, source), rtc_src_file(config.platform, source))

    for class_name, output in config.jni_classes.items():
        cmd = ['javah']
        for classpath in config.jni_classpaths:
            cmd.append('-classpath')
            cmd.append(os.path.join(rtc_src_dir(config.platform), classpath))

        src_output = os.path.join(project_src_dir, output)
        cmd.append('-o')
        cmd.append(src_output)

        cmd.append(class_name)
        print(f"exec: {' '.join(cmd)}")
        subprocess.check_output(cmd)


def check_all_files(sources):
    has_error = False
    for source in sources:
        file_path = os.path.join(project_src_dir, source)
        print('Checking:', file_path)
        error = not check_newline_at_eof(file_path)
        if error:
            print(f"Error: The file {file_path} does not end with a newline.")
            has_error = True
    if has_error:
        sys.exit(1)


def main():
    init_project_with_cur_dir()

    # カレントディレクトリをトップレベルに変更
    os.chdir(top_dir)

    parser = argparse.ArgumentParser(
        description="パッチ開発用コマンドラインツール",
        epilog="詳細は PATCH_DEVELOP_TOOL.md を参照してください。"
    )

    subparsers = parser.add_subparsers(
        title="サブコマンド", help="実行するサブコマンドを選択してください。")

    # init サブコマンド
    parser_init = subparsers.add_parser("init", help="パッチ開発ディレクトリを初期化します。"
                                        "ソースコードをダウンロードし、パッチを適用せずにビルドします。")
    parser_init.add_argument("platform", help="プラットフォーム")
    parser_init.add_argument("project_name", help="新しいパッチの名前")
    parser_init.add_argument("--nobuild", action="store_true",
                             help="ソースコードをダウンロード・ビルドしません。")
    parser_init.set_defaults(func=init)

    # build サブコマンド
    parser_build = subparsers.add_parser("build", help="パッチを適用してビルドします。")
    parser_build.add_argument("--skip-patch", action="store_true",
                              help="パッチの適用をスキップします。")
    parser_build.set_defaults(func=build)

    # patch サブコマンド
    parser_patch = subparsers.add_parser("patch", help="パッチを生成します。")
    parser_patch.set_defaults(func=generate)

    # clean サブコマンド
    parser_clean = subparsers.add_parser("clean", help="パッチディレクトリをクリーンします。")
    parser_clean.set_defaults(func=clean)

    # diff サブコマンド
    parser_diff = subparsers.add_parser("diff", help="差分を表示します。")
    parser_diff.set_defaults(func=diff)

    # sync
    parser_sync = subparsers.add_parser('sync')
    parser_sync.set_defaults(func=sync)

    # check
    parser_check = subparsers.add_parser(
        'check', help='ファイル終端の改行コードの有無をチェックします。')
    parser_check.set_defaults(func=check)

    # JNI
    parser_jni = subparsers.add_parser(
        'jni', help='JNI のヘッダーファイルを生成します。')
    parser_jni.set_defaults(func=jni)

    args = parser.parse_args()

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
