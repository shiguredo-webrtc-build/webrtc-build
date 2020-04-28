#!/bin/bash

if [ $# -lt 5 ]; then
  echo "$0 <static_dir> <source_dir> <build_dir> <package_dir> <version_file> [<additional_build_name>...]"
  exit 1
fi

set -ex

STATIC_DIR=$1
SOURCE_DIR=$2
BUILD_DIR=$3
PACKAGE_DIR=$4
VERSION_FILE=$5
shift 5
ADDITIONAL_BUILD_NAMES="$*"

rm -rf $BUILD_DIR/package/webrtc
mkdir -p $BUILD_DIR/package/webrtc/lib
mkdir -p $BUILD_DIR/package/webrtc/include

# webrtc のヘッダ類
rsync -amv '--include=*/' '--include=*.h' '--include=*.hpp' '--exclude=*' $SOURCE_DIR/webrtc/src/. $BUILD_DIR/package/webrtc/include/.

# libwebrtc.a
cp $BUILD_DIR/webrtc/libwebrtc.a $BUILD_DIR/package/webrtc/lib/
for name in $ADDITIONAL_BUILD_NAMES; do
  cp $BUILD_DIR/webrtc_$name/libwebrtc.a $BUILD_DIR/package/webrtc/lib/libwebrtc_$name.a
done
# NOTICE
cp $BUILD_DIR/webrtc/LICENSE.md "$BUILD_DIR/package/webrtc/NOTICE"

# 各種情報を拾ってくる
cp $VERSION_FILE $BUILD_DIR/package/webrtc/VERSIONS
pushd $SOURCE_DIR/webrtc/src
  echo "WEBRTC_SRC_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
  echo "WEBRTC_SRC_URL=`git remote get-url origin`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/build
  echo "WEBRTC_SRC_BUILD_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
  echo "WEBRTC_SRC_BUILD_URL=`git remote get-url origin`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/buildtools
  echo "WEBRTC_SRC_BUILDTOOLS_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
  echo "WEBRTC_SRC_BUILDTOOLS_URL=`git remote get-url origin`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/buildtools/third_party/libc++/trunk
  # 後方互換性のために残す。どこかで消す
  echo "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXX_TRUNK=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS

  echo "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXX_TRUNK_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
  echo "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXX_TRUNK_URL=`git remote get-url origin`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/buildtools/third_party/libc++abi/trunk
  # 後方互換性のために残す。どこかで消す
  echo "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXXABI_TRUNK=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS

  echo "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXXABI_TRUNK_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
  echo "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBCXXABI_TRUNK_URL=`git remote get-url origin`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/buildtools/third_party/libunwind/trunk
  # 後方互換性のために残す。どこかで消す
  echo "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBUNWIND_TRUNK=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS

  echo "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBUNWIND_TRUNK_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
  echo "WEBRTC_SRC_BUILDTOOLS_THIRD_PARTY_LIBUNWIND_TRUNK_URL=`git remote get-url origin`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/third_party
  echo "WEBRTC_SRC_THIRD_PARTY_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
  echo "WEBRTC_SRC_THIRD_PARTY_URL=`git remote get-url origin`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd
pushd $SOURCE_DIR/webrtc/src/tools
  echo "WEBRTC_SRC_TOOLS_COMMIT=`git rev-parse HEAD`" >> $BUILD_DIR/package/webrtc/VERSIONS
  echo "WEBRTC_SRC_TOOLS_URL=`git remote get-url origin`" >> $BUILD_DIR/package/webrtc/VERSIONS
popd

mkdir -p $PACKAGE_DIR
pushd $BUILD_DIR/package
  tar czf $PACKAGE_DIR/webrtc.tar.gz webrtc
popd
