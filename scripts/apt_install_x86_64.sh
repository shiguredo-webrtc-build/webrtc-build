#!/bin/bash

set -ex

apt-get update
apt-get -y upgrade

# Ubuntu 18.04 では tzdata を noninteractive にしないと実行が止まってしまう
apt-get -y install tzdata
echo 'Asia/Tokyo' > /etc/timezone
dpkg-reconfigure -f noninteractive tzdata

# Ubuntu 20.04 では libwebrtc の install-build-deps.sh で snapcraft がインストールされるが、
# コンテナ内では snapd が動かないためインストールに失敗するので、失敗したときに "Skip" をデフォルト値として設定しておかないと実行が止まってしまう。
# snapcraft は依存関係として入るだけで、libwebrtc のビルド自体には使われないので、スキップしても問題ない。
# ただし、この変数は critical level で定義されているので、通常の方法では外部から設定できないため、やむなく debconf の db_get() をオーバーライドする。
echo 'db_get () { if [ "$@" = "snapcraft/snap-no-connectivity" ]; then RET="Skip"; else _db_cmd "GET $@"; fi }' >> /usr/share/debconf/confmodule
apt-get install -y snapcraft

apt-get -y install \
  git \
  libsdl2-dev \
  lsb-release \
  python \
  rsync \
  sudo \
  vim \
  wget
