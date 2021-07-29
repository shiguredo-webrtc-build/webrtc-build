# syntax = docker/dockerfile:experimental
FROM ubuntu:20.04 AS builder

ARG PACKAGE_NAME=android

ENV SOURCE_DIR "/root/_source/$PACKAGE_NAME"
ENV BUILD_DIR "/root/_build/$PACKAGE_NAME"
ENV PACKAGE_DIR "/root/_package/$PACKAGE_NAME"

COPY scripts/apt_install_x86_64.sh /root/scripts/
RUN /root/scripts/apt_install_x86_64.sh \
  && sudo apt-get install -y openjdk-11-jdk

COPY scripts/get_depot_tools.sh /root/scripts/
RUN /root/scripts/get_depot_tools.sh $SOURCE_DIR

ENV PATH "$SOURCE_DIR/depot_tools:$PATH"

ARG WEBRTC_COMMIT
COPY scripts/prepare_webrtc.sh /root/scripts/
RUN /root/scripts/prepare_webrtc.sh $SOURCE_DIR $WEBRTC_COMMIT

RUN cd $SOURCE_DIR/webrtc/src \
  && echo "target_os = [ 'android' ]" >> ../.gclient \
  && gclient sync

COPY scripts/install_webrtc_build_deps.sh /root/scripts/
RUN /root/scripts/install_webrtc_build_deps.sh $SOURCE_DIR android

COPY patches/add_dep_zlib.patch /root/patches/
COPY patches/4k.patch /root/patches/
COPY patches/android_webrtc_version.patch /root/patches/
COPY patches/android_fixsegv.patch /root/patches/
COPY patches/android_simulcast.patch /root/patches/
COPY android/WebrtcBuildVersion.java $SOURCE_DIR/webrtc/src/sdk/android/api/org/webrtc/
RUN cd $SOURCE_DIR/webrtc/src \
  && patch -p1 < /root/patches/add_dep_zlib.patch \
  && patch -p2 < /root/patches/4k.patch \
  && patch -p1 < /root/patches/android_webrtc_version.patch \
  && patch -p1 < /root/patches/android_fixsegv.patch \
  && patch -p1 < /root/patches/android_simulcast.patch

# aar
RUN cd /root/_source/android/webrtc/src \
  && python $SOURCE_DIR/webrtc/src/tools_webrtc/android/build_aar.py \
      --build-dir $BUILD_DIR/webrtc_android \
      --output $BUILD_DIR//webrtc_android/libwebrtc.aar \
      --arch armeabi-v7a arm64-v8a \
      --extra-gn-args ' \
        is_java_debug=false \
        rtc_include_tests=false \
        rtc_use_h264=false \
        is_component_build=false \
        use_rtti=true \
        rtc_build_examples=false \
      '

# armeabi-v7a 用の libwebrtc.a
RUN cd $SOURCE_DIR/webrtc/src \
  && gn gen $BUILD_DIR/webrtc_armeabi-v7a --args=' \
    target_os="android" \
    target_cpu="arm" \
    is_debug=false \
    rtc_use_h264=false \
    rtc_include_tests=false \
    rtc_build_json=true \
    use_rtti=true \
    rtc_build_examples=false \
  ' \
  && ninja -C $BUILD_DIR/webrtc_armeabi-v7a \
  && ninja -C $BUILD_DIR/webrtc_armeabi-v7a native_api

RUN cd $BUILD_DIR/webrtc_armeabi-v7a/obj \
  && $SOURCE_DIR/webrtc/src/third_party/llvm-build/Release+Asserts/bin/llvm-ar -rc $BUILD_DIR/webrtc_armeabi-v7a/libwebrtc.a `find . -name '*.o'`

# arm64-v8a 用の libwebrtc.a
RUN cd $SOURCE_DIR/webrtc/src \
  && gn gen $BUILD_DIR/webrtc_arm64-v8a --args=' \
    target_os="android" \
    target_cpu="arm64" \
    is_debug=false \
    rtc_use_h264=false \
    rtc_include_tests=false \
    rtc_build_json=true \
    use_rtti=true \
    rtc_build_examples=false \
  ' \
  && ninja -C $BUILD_DIR/webrtc_arm64-v8a \
  && ninja -C $BUILD_DIR/webrtc_arm64-v8a native_api

RUN cd $BUILD_DIR/webrtc_arm64-v8a/obj \
  && $SOURCE_DIR/webrtc/src/third_party/llvm-build/Release+Asserts/bin/llvm-ar -rc $BUILD_DIR/webrtc_arm64-v8a/libwebrtc.a `find . -name '*.o'`

ENV STATIC_DIR "/root/static"

COPY scripts/package_webrtc_android.sh /root/scripts/
COPY VERSION /root/
RUN /root/scripts/package_webrtc_android.sh $STATIC_DIR $SOURCE_DIR $BUILD_DIR $PACKAGE_DIR /root/VERSION

RUN mv $PACKAGE_DIR/webrtc.tar.gz /

FROM ubuntu:20.04

COPY --from=builder /webrtc.tar.gz /
