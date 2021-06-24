#!/bin/bash

cd `dirname $0`
source VERSION
SCRIPT_DIR="`pwd`"

PACKAGE_NAME=ios
SOURCE_DIR="`pwd`/_source/$PACKAGE_NAME"
BUILD_DIR="`pwd`/_build/$PACKAGE_NAME"
PACKAGE_DIR="`pwd`/_package/$PACKAGE_NAME"

set -ex

# ======= ここまでは全ての build.*.sh で共通（PACKAGE_NAME だけ変える）

TARGET_ARCHS="arm64 x64"
TARGET_BUILD_CONFIGS="debug release"

./scripts/get_depot_tools.sh $SOURCE_DIR
export PATH="$SOURCE_DIR/depot_tools:$PATH"

./scripts/prepare_webrtc.sh $SOURCE_DIR $WEBRTC_COMMIT
echo "target_os = [ 'ios' ]" >> $SOURCE_DIR/webrtc/.gclient
pushd $SOURCE_DIR/webrtc
  gclient sync
popd

pushd $SOURCE_DIR/webrtc/src
  patch -p1 < $SCRIPT_DIR/patches/add_dep_zlib.patch
  patch -p2 < $SCRIPT_DIR/patches/4k.patch
  patch -p2 < $SCRIPT_DIR/patches/macos_h264_encoder.patch
  patch -p1 < $SCRIPT_DIR/patches/macos_simulcast.patch
  patch -p1 < $SCRIPT_DIR/patches/ios_manual_audio_input.patch
  patch -p1 < $SCRIPT_DIR/patches/ios_simulcast.patch
popd

for build_config in $TARGET_BUILD_CONFIGS; do
  mkdir -p $BUILD_DIR/$build_config
done

pushd $SOURCE_DIR/webrtc/src
  for build_config in $TARGET_BUILD_CONFIGS; do

    if [ $build_config = "release" ]; then
      _is_debug="false"
    else
      _is_debug="true"
    fi

    ./tools_webrtc/ios/build_ios_libs.sh -o $BUILD_DIR/webrtc/$build_config --build_config $build_config --arch $TARGET_ARCHS --bitcode --extra-gn-args " \
      rtc_libvpx_build_vp9=true \
      rtc_include_tests=false \
      rtc_build_examples=false \
      rtc_use_h264=false \
      use_rtti=true \
      libcxx_abi_unstable=false \
      enable_dsyms=$_is_debug \
    "
    _branch="M`echo $WEBRTC_VERSION | cut -d'.' -f1`"
    _commit="`echo $WEBRTC_VERSION | cut -d'.' -f3`"
    _revision=$WEBRTC_COMMIT
    _maint="`echo $WEBRTC_BUILD_VERSION | cut -d'.' -f4`"

    cat <<EOF > $BUILD_DIR/webrtc/$build_config/WebRTC.framework/build_info.json
{
    "webrtc_version": "$_branch",
    "webrtc_commit": "$_commit",
    "webrtc_maint": "$_maint",
    "webrtc_revision": "$_revision"
}
EOF
  done

popd

pushd $SOURCE_DIR/webrtc/src
  pushd ./tools_webrtc/ios/
    IOS_DEPLOYMENT_TARGET=`python -c 'from build_ios_libs import IOS_DEPLOYMENT_TARGET; print(IOS_DEPLOYMENT_TARGET)'`
  popd

  for build_config in $TARGET_BUILD_CONFIGS; do
    _libs=""
    _dirs=""

    if [ $build_config = "release" ]; then
      _is_debug="false"
    else
      _is_debug="true"
    fi

    for arch in $TARGET_ARCHS; do
      gn gen $BUILD_DIR/webrtc/$build_config/${arch}_libs --args="
        target_os=\"ios\"
        target_cpu=\"$arch\"
        ios_enable_code_signing=false
        use_xcode_clang=true
        is_component_build=false
        ios_deployment_target=\"$IOS_DEPLOYMENT_TARGET\"
        rtc_libvpx_build_vp9=true
        enable_ios_bitcode=true

        is_debug=$_is_debug
        rtc_include_tests=false
        rtc_build_examples=false
        rtc_use_h264=false
        use_rtti=true
        libcxx_abi_unstable=false
      "
      ninja -C $BUILD_DIR/webrtc/$build_config/${arch}_libs
      ninja -C $BUILD_DIR/webrtc/$build_config/${arch}_libs \
        builtin_audio_decoder_factory \
        default_task_queue_factory \
        native_api \
        default_codec_factory_objc \
        peerconnection \
        videocapture_objc \
        framework_objc
      pushd $BUILD_DIR/webrtc/$build_config/${arch}_libs/obj
        /usr/bin/ar -rc $BUILD_DIR/webrtc/$build_config/${arch}_libs/libwebrtc.a `find . -name '*.o'`
        _libs="$_libs $BUILD_DIR/webrtc/$build_config/${arch}_libs/libwebrtc.a"
      popd
      _dirs="$_dirs $BUILD_DIR/webrtc/$build_config/${arch}_libs"
    done
    lipo $_libs -create -output $BUILD_DIR/webrtc/$build_config/libwebrtc.a
  done
  python tools_webrtc/libs/generate_licenses.py --target //sdk:framework_objc $BUILD_DIR/webrtc/ $_dirs
popd

./scripts/package_webrtc_ios.sh $SCRIPT_DIR/static $SOURCE_DIR $BUILD_DIR $PACKAGE_DIR $SCRIPT_DIR/VERSION
