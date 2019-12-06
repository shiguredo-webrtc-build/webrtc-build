#!/bin/bash

if [ $# -lt 1 ]; then
  echo "$0 <source_dir>"
  exit 1
fi

SOURCE_DIR=$1

set -ex

mkdir -p $SOURCE_DIR

pushd $SOURCE_DIR
  if [ -e depot_tools/.git ]; then
    pushd depot_tools
      git fetch
      git checkout -f origin/HEAD
    popd
  else
    git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
  fi
popd
