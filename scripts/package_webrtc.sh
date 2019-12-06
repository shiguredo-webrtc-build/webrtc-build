#!/bin/bash

if [ $# -lt 3 ]; then
  echo "$0 <source_dir> <build_dir> <package_dir>"
  exit 1
fi

SOURCE_DIR=$1
BUILD_DIR=$2
PACKAGE_DIR=$3

rm -rf $BUILD_DIR/package/webrtc
mkdir -p $BUILD_DIR/package/webrtc/lib
mkdir -p $BUILD_DIR/package/webrtc/include

# webrtc のヘッダ類
rsync -amv '--include=*/' '--include=*.h' '--include=*.hpp' '--exclude=*' $SOURCE_DIR/webrtc/src/. $BUILD_DIR/package/webrtc/include/.

# libwebrtc.a
cp $BUILD_DIR/webrtc/libwebrtc.a $BUILD_DIR/package/webrtc/lib/

# 各種情報を拾ってくる
touch $BUILD_DIR/package/webrtc/VERSIONS
pushd $SOURCE_DIR/webrtc/src
  echo "WEBRTC_SRC_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/build
  echo "WEBRTC_SRC_BUILD_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/third_party
  echo "WEBRTC_SRC_THIRD_PARTY_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/tools
  echo "WEBRTC_SRC_TOOLS_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd

mkdir -p $PACKAGE_DIR
pushd $BUILD_DIR/package
  tar czf $PACKAGE_DIR/webrtc.tar.gz webrtc
popd
