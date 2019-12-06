#!/bin/bash

if [ $# -lt 2 ]; then
  echo "$0 <source_dir> <webrtc_commit>"
fi

SOURCE_DIR=$1
WEBRTC_COMMIT=$2

mkdir -p $SOURCE_DIR/webrtc

pushd $SOURCE_DIR/webrtc
  gclient

  if [ ! -e src ]; then
    fetch webrtc
  fi
popd

pushd $SOURCE_DIR/webrtc/src
  git reset --hard
  git clean -xdf

  pushd third_party
    git reset --hard
    git clean -xdf
  popd

  git fetch
  git checkout -f $WEBRTC_COMMIT
  gclient sync
popd
