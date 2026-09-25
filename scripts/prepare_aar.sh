#!/bin/bash

set -eu

# JitPack のビルド時に実行し、 Release の webrtc.android_sdk.tar.gz から
# libwebrtc.aar を取り出してローカルの Maven リポジトリに登録するスクリプト
#
# JitPack はビルド対象のタグ名を環境変数 VERSION に設定する (例: m155.8059.1.0)
# 登録した artifact は com.github.shiguredo-webrtc-build:webrtc-build として公開される

SDK_URL="https://github.com/shiguredo-webrtc-build/webrtc-build/releases/download/${VERSION}/webrtc.android_sdk.tar.gz"

echo "VERSION=${VERSION}"
echo "SDK_URL=${SDK_URL}"

curl -fsSL -o webrtc.android_sdk.tar.gz "${SDK_URL}"
tar -xzf webrtc.android_sdk.tar.gz webrtc/aar/libwebrtc.aar

mvn install:install-file \
    -Dfile=webrtc/aar/libwebrtc.aar \
    -Dpackaging=aar \
    -Dversion="${VERSION}" \
    -DgroupId=com.github.shiguredo-webrtc-build \
    -DartifactId=webrtc-build