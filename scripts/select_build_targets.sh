#!/bin/bash

set -eu

# workflow_dispatch の targets から、各ジョブへ渡す matrix を JSON で出す。
#
# push と tag では TARGETS を見ない。全ターゲットを出す。
# workflow_dispatch では BRANCH が必須で、ブランチ名またはタグ名を指定する。
# targets はカンマ区切りのトークンを受け付ける。
# 空文字と all は全ターゲットである。
#
# グループは次のとおり。
#   windows  windows_x86_64, windows_arm64
#   macos    macos_arm64
#   ios      ios, ios_sdk
#   android  android, android_sdk
#   linux    raspberry-pi-os と ubuntu
#
# グループ名のほか、ターゲット名そのものも指定できる。
# 正本はこの一覧であり、build ワークフローの matrix はここの JSON を使う。

catalog=$(cat <<'EOF'
windows_x86_64 windows windows {"name":"windows_x86_64","rust-target":"x86_64-pc-windows-msvc"}
windows_arm64 windows windows {"name":"windows_arm64","rust-target":"aarch64-pc-windows-msvc"}
macos_arm64 macos macos {"name":"macos_arm64","rust-target":"aarch64-apple-darwin"}
ios macos ios {"name":"ios","rust-target":"aarch64-apple-ios"}
ios_sdk macos ios {"name":"ios_sdk"}
raspberry-pi-os_armv8 linux linux {"name":"raspberry-pi-os_armv8","rust-target":"aarch64-unknown-linux-gnu","runs-on":"ubuntu-24.04"}
ubuntu-20.04_armv8 linux linux {"name":"ubuntu-20.04_armv8","rust-target":"aarch64-unknown-linux-gnu","runs-on":"ubuntu-24.04"}
ubuntu-22.04_armv8 linux linux {"name":"ubuntu-22.04_armv8","rust-target":"aarch64-unknown-linux-gnu","runs-on":"ubuntu-24.04"}
ubuntu-24.04_armv8 linux linux {"name":"ubuntu-24.04_armv8","rust-target":"aarch64-unknown-linux-gnu","runs-on":"ubuntu-24.04"}
ubuntu-26.04_armv8 linux linux {"name":"ubuntu-26.04_armv8","rust-target":"aarch64-unknown-linux-gnu","runs-on":"ubuntu-24.04"}
ubuntu-22.04_x86_64 linux linux {"name":"ubuntu-22.04_x86_64","rust-target":"x86_64-unknown-linux-gnu","runs-on":"ubuntu-22.04"}
ubuntu-24.04_x86_64 linux linux {"name":"ubuntu-24.04_x86_64","rust-target":"x86_64-unknown-linux-gnu","runs-on":"ubuntu-24.04"}
ubuntu-26.04_x86_64 linux linux {"name":"ubuntu-26.04_x86_64","rust-target":"x86_64-unknown-linux-gnu","runs-on":"ubuntu-26.04"}
android linux android {"name":"android","rust-target":"aarch64-linux-android","runs-on":"ubuntu-24.04"}
android_sdk linux android {"name":"android_sdk","runs-on":"ubuntu-24.04"}
EOF
)

# 第 1 列がターゲット名、第 2 列がジョブ、第 3 列がグループ、残りが JSON である。
is_known_token() {
  local token="$1"
  case "$token" in
    all | windows | macos | ios | android | linux)
      return 0
      ;;
  esac
  local name job group object
  # 呼び出し側が IFS をカンマにしているので、行の分割は空白に戻す。
  while IFS=' ' read -r name job group object; do
    if [ "$token" = "$name" ]; then
      return 0
    fi
  done <<EOF
$catalog
EOF
  return 1
}

wants_all=0
build_ref=""
if [ "${EVENT_NAME:-}" = "workflow_dispatch" ]; then
  # 前後と途中の空白は ref 名に含まれない。空白だけは未指定と同じにする。
  build_ref=$(printf '%s' "${BRANCH:-}" | tr -d ' \t')
  if [ -z "$build_ref" ]; then
    echo "branch or tag is required for workflow_dispatch" >&2
    exit 1
  fi
else
  wants_all=1
fi

# 空白は区切りのゆれなので除く。カンマ区切りだけを残す。
raw=$(printf '%s' "${TARGETS:-}" | tr -d ' \t')

if [ "$wants_all" -eq 0 ]; then
  if [ -z "$raw" ] || [ "$raw" = "all" ]; then
    wants_all=1
  fi
fi

if [ "$wants_all" -eq 0 ]; then
  saved_ifs=$IFS
  IFS=','
  for token in $raw; do
    if [ -z "$token" ]; then
      continue
    fi
    if [ "$token" = "all" ]; then
      wants_all=1
      break
    fi
    if ! is_known_token "$token"; then
      echo "unknown target: ${token}" >&2
      echo "expected all, windows, macos, ios, android, linux, or a target name" >&2
      exit 1
    fi
  done
  IFS=$saved_ifs
fi

json_windows=""
json_macos=""
json_linux=""
count_windows=0
count_macos=0
count_linux=0
selected_names=""

append_json() {
  local bucket="$1"
  local object="$2"
  local current=""
  case "$bucket" in
    windows) current=$json_windows ;;
    macos) current=$json_macos ;;
    linux) current=$json_linux ;;
  esac
  if [ -n "$current" ]; then
    object="${current},${object}"
  fi
  case "$bucket" in
    windows)
      json_windows=$object
      count_windows=$((count_windows + 1))
      ;;
    macos)
      json_macos=$object
      count_macos=$((count_macos + 1))
      ;;
    linux)
      json_linux=$object
      count_linux=$((count_linux + 1))
      ;;
  esac
}

wanted() {
  local name="$1"
  local group="$2"
  if [ "$wants_all" -eq 1 ]; then
    return 0
  fi
  case ",${raw}," in
    *,"${group}",* | *,"${name}",*)
      return 0
      ;;
  esac
  return 1
}

while IFS=' ' read -r name job group object; do
  if wanted "$name" "$group"; then
    append_json "$job" "$object"
    if [ -n "$selected_names" ]; then
      selected_names="${selected_names},"
    fi
    selected_names="${selected_names}${name}"
  fi
done <<EOF
$catalog
EOF

wrap_json() {
  local body="$1"
  if [ -z "$body" ]; then
    printf '%s' "[]"
  else
    printf '%s' "[${body}]"
  fi
}

windows_json=$(wrap_json "$json_windows")
macos_json=$(wrap_json "$json_macos")
linux_json=$(wrap_json "$json_linux")
windows_count=$count_windows
macos_count=$count_macos
linux_count=$count_linux

echo "selected targets: ${selected_names}"

write_output() {
  local key="$1"
  local value="$2"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    {
      echo "${key}<<EOF"
      echo "${value}"
      echo "EOF"
    } >>"$GITHUB_OUTPUT"
  else
    printf '%s=%s\n' "$key" "$value"
  fi
}

write_output build_ref "$build_ref"
write_output windows "$windows_json"
write_output windows_count "$windows_count"
write_output macos "$macos_json"
write_output macos_count "$macos_count"
write_output linux "$linux_json"
write_output linux_count "$linux_count"
