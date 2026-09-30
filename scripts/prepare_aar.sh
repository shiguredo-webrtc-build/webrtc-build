#!/bin/bash

set -eu

# JitPack のビルド時に実行し、 Release に添付した libwebrtc.aar を
# ローカルの Maven リポジトリに登録するスクリプト
#
# JitPack はビルド対象のタグ名を環境変数 VERSION に設定する (例: m155.8059.1.0)
# 登録した artifact は com.github.shiguredo-webrtc-build:webrtc-build として公開される

AAR_URL="https://github.com/shiguredo-webrtc-build/webrtc-build/releases/download/${VERSION}/libwebrtc.aar"

echo "VERSION=${VERSION}"
echo "AAR_URL=${AAR_URL}"

curl -fsSL -o libwebrtc.aar "${AAR_URL}"

mvn install:install-file \
    -Dfile=libwebrtc.aar \
    -Dpackaging=aar \
    -Dversion="${VERSION}" \
    -DgroupId=com.github.shiguredo-webrtc-build \
    -DartifactId=webrtc-build