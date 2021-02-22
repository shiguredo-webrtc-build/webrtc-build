#!/bin/bash

cd `dirname $0`
source VERSION
SCRIPT_DIR="`pwd`"

PACKAGE_NAME=macos_arm64
SOURCE_DIR="`pwd`/_source/$PACKAGE_NAME"
BUILD_DIR="`pwd`/_build/$PACKAGE_NAME"
PACKAGE_DIR="`pwd`/_package/$PACKAGE_NAME"

set -ex

# ======= ここまでは全ての build.*.sh で共通（PACKAGE_NAME だけ変える）

./scripts/get_depot_tools.sh $SOURCE_DIR
export PATH="$SOURCE_DIR/depot_tools:$PATH"

./scripts/prepare_webrtc.sh $SOURCE_DIR $WEBRTC_COMMIT

pushd $SOURCE_DIR/webrtc/src
  patch -p2 < $SCRIPT_DIR/patches/4k.patch
  patch -p2 < $SCRIPT_DIR/patches/macos_h264_encoder.patch
  patch -p2 < $SCRIPT_DIR/patches/macos_av1.patch
  patch -p2 < $SCRIPT_DIR/patches/macos_screen_capture.patch
  patch -p1 < $SCRIPT_DIR/patches/macos_simulcast.patch
popd

pushd $SOURCE_DIR/webrtc/src
  gn gen $BUILD_DIR/webrtc --args='
    target_os="mac"
    target_cpu="arm64"
    is_debug=false
    rtc_include_tests=false
    rtc_build_examples=false
    rtc_use_h264=false
    is_component_build=false
    use_rtti=true
    libcxx_abi_unstable=false
  '
  ninja -C $BUILD_DIR/webrtc
  ninja -C $BUILD_DIR/webrtc \
    builtin_audio_decoder_factory \
    default_task_queue_factory \
    native_api \
    default_codec_factory_objc \
    peerconnection \
    videocapture_objc \
    mac_framework_objc

  python2 tools_webrtc/libs/generate_licenses.py --target //sdk:mac_framework_objc $BUILD_DIR/webrtc/ $BUILD_DIR/webrtc/
popd

pushd $BUILD_DIR/webrtc/obj
  /usr/bin/ar -rc $BUILD_DIR/webrtc/libwebrtc.a `find . -name '*.o'`
popd

./scripts/package_webrtc.sh $SCRIPT_DIR/static $SOURCE_DIR $BUILD_DIR $PACKAGE_DIR $SCRIPT_DIR/VERSION
