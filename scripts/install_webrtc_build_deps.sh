#!/bin/bash

if [ $# -lt 2 ]; then
  echo "$0 <source_dir> <arm | x86_64>"
fi

SOURCE_DIR=$1

set -ex

pushd $SOURCE_DIR/webrtc
  if [ "$2" = "arm" ]; then
    bash src/build/install-build-deps.sh
  elif [ "$2" = "android" ]; then
    pushd src
      bash build/install-build-deps-android.sh
      gclient runhooks
    popd
  else
    sed -i -e 's/sudo/sudo -E/g' src/build/install-build-deps.sh
    bash ./src/build/install-build-deps.sh --no-arm --no-chromeos-fonts
    pushd src/build
      git reset --hard
    popd
  fi
popd
