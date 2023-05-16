#!/usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
import os
import json

base_dir = 'patchdev'
work_dir = os.getcwd()


def rtc_src_dir(platform):
    return os.path.join("..", "..", "_source", platform, "webrtc", "src")


def rtc_src_file(platform, source):
    return os.path.join(rtc_src_dir(platform), source)


def init(args):
    project_name = args.project_name
    project_dir = os.path.join(base_dir, project_name)
    os.makedirs(project_dir, exist_ok=True)
    os.makedirs(os.path.join(project_dir, "src"), exist_ok=True)

    # Makefile
    makefile_content = """
PYTHON = python3
TOP_DIR = ../../
PATCHDEV = scripts/patchdev.py

.PHONY: sync build diff patch clean

sync:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) sync

build:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) build

diff:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) diff

patch:
\t@$(PYTHON) $(TOP_DIR)$(PATCHDEV) patch

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
        "platform": "ios",
        "build_flags": "--debug",
        "sources": [],
    }
    with open(os.path.join(project_dir, "config.json"), 'w') as f:
        json.dump(config_content, f, indent=4)

    print("Initialized project in:", project_dir)


def build(args):
    with open("config.json") as f:
        config = json.load(f)

    platform = config["platform"]
    sources = config["sources"]
    check_all_files(platform, sources)

    for source in sources:
        shutil.copy2(f"src/{source}", rtc_src_file(platform, source))

    orig_dir = os.getcwd()
    os.chdir("../../")
    build_flags = config["build_flags"]
    cmd = f"python3 run.py build {platform} {build_flags}\n"
    print(f"exec: {cmd}")
    os.system(cmd)
    os.chdir(orig_dir)


def generate(args):
    # config.jsonをロード
    with open("config.json") as f:
        config = json.load(f)

    # platformの値を取得
    platform = config["platform"]
    sources = config["sources"]
    check_all_files(platform, sources)

    # パッチファイルのリスト
    patch_files = []

    # 各ソースファイルに対して操作を実行
    for source in sources:
        target = rtc_src_file(platform, source)
        shutil.copy2(os.path.join('src', source), target)
        os.chdir(os.path.dirname(target))
        cmd = ['git', 'add', '-N', os.path.basename(target)]
        subprocess.check_output(cmd)
        cmd = ['git', 'diff', os.path.basename(target)]
        diff = subprocess.check_output(cmd).decode('utf-8')
        os.chdir(work_dir)
        patch_file = os.path.join('_build/patches', f'{source}.patch')
        os.makedirs(os.path.dirname(patch_file), exist_ok=True)
        with open(patch_file, 'w') as f:
            f.write(diff)
        patch_files.append(patch_file)

    # パッチファイルを結合
    with open(os.path.join('_build', config["output"]), 'w') as outfile:
        for patch_file in patch_files:
            with open(patch_file) as infile:
                outfile.write(infile.read())


def clean(args):
    shutil.rmtree('_build', ignore_errors=True)

    with open("config.json") as f:
        config = json.load(f)

    platform = config["platform"]
    for source in config["sources"]:
        source_path = rtc_src_file(platform, source)
        os.chdir(os.path.dirname(source_path))
        os.system(f"git checkout -- {os.path.basename(source_path)}")
        os.chdir(work_dir)
        destination_dir = os.path.join('_build/orig', os.path.dirname(source))
        os.makedirs(destination_dir, exist_ok=True)
        shutil.copy2(source_path, destination_dir)


def diff(args):
    # config.jsonをロード
    with open("config.json") as f:
        config = json.load(f)

    # platformの値を取得
    platform = config["platform"]
    sources = config["sources"]
    check_all_files(platform, sources)

    for source in sources:
        target = rtc_src_file(platform, source)
        shutil.copy2(os.path.join('src', source), target)
        os.chdir(os.path.dirname(target))
        cmd = ['git', 'add', '-N', os.path.basename(target)]
        subprocess.check_output(cmd)
        cmd = ['git', 'diff', os.path.basename(target)]
        diff = subprocess.check_output(cmd).decode('utf-8')
        os.chdir(work_dir)
        print(diff)


def sync(args):
    patch_dir = os.getcwd()
    config_path = os.path.join(patch_dir, "config.json")

    # config.json のロード
    with open(config_path, "r") as json_file:
        config = json.load(json_file)

    platform = config['platform']
    copied_files = 0
    for source in config['sources']:
        # コピー先のファイルパス
        destination_path_in_src = os.path.join(patch_dir, "src", source)

        # コピー先ディレクトリの生成
        os.makedirs(os.path.dirname(destination_path_in_src), exist_ok=True)

        # ファイルが存在しなければオリジナルからコピー
        if not os.path.isfile(destination_path_in_src):
            # パッチ対象ファイルのオリジナルのパス
            original_path = rtc_src_file(platform, source)
            shutil.copy2(original_path, destination_path_in_src)
            print(f"パッチ対象ファイルをコピーしました: {destination_path_in_src}")
            copied_files += 1


def check_newline_at_eof(file_path):
    if not os.path.isfile(file_path):
        print(f"Error: The file {file_path} does not exist.")
        sys.exit(1)

    with open(file_path, 'rb') as f:
        f.seek(-2, os.SEEK_END)
        last_two_bytes = f.read(2)

    if last_two_bytes[-1:] != b'\n':
        print(
            f"Error: The file {file_path} does not end with a newline character.")
        sys.exit(1)


def check_all_files(platform, sources):
    for source in sources:
        file_path = rtc_src_file(platform, source)
        shutil.copy2(f"src/{source}", file_path)
        check_newline_at_eof(file_path)


def main():
    parser = argparse.ArgumentParser(
        description="パッチ開発用コマンドラインツール",
        epilog="詳細については、PATCH_DEVELOP.mdを参照してください。"
    )

    subparsers = parser.add_subparsers(
        title="サブコマンド", help="実行するサブコマンドを選択してください。")

    # init サブコマンド
    parser_init = subparsers.add_parser("init", help="パッチ開発ディレクトリを初期化します。")
    parser_init.add_argument("project_name", help="新しいパッチの名前")
    parser_init.set_defaults(func=init)

    # build サブコマンド
    parser_build = subparsers.add_parser("build", help="パッチを適用してビルドします。")
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
    parser_diff = subparsers.add_parser('sync')
    parser_diff.set_defaults(func=sync)

    args = parser.parse_args()

    if len(sys.argv) <= 1:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
