#!/bin/bash

set -ex

# grub-efi-amd64-signed がエラーになるので hold で回避する
# ref: https://github.com/community/community/discussions/47863
apt-mark hold grub-efi-amd64-signed
apt-get update --fix-missing
# apt-get upgrade

# Ubuntu 18.04 では tzdata を noninteractive にしないと実行が止まってしまう
apt-get -y install tzdata
echo 'Asia/Tokyo' > /etc/timezone
dpkg-reconfigure -f noninteractive tzdata

export DEBIAN_FRONTEND=noninteractive

apt-get -y install \
  build-essential \
  curl \
  git \
  gtk+-3.0 \
  lbzip2 \
  libgtk-3-dev \
  libstdc++6 \
  locales \
  lsb-release \
  ninja-build \
  python3 \
  python3-setuptools \
  rsync \
  software-properties-common \
  sudo \
  unzip \
  vim \
  xz-utils

# multistrap は Ubuntu 26.04 のリポジトリに存在しないため、24.04 の .deb からインストールする
if ! apt-get -y install multistrap 2>/dev/null; then
  wget -q "http://archive.ubuntu.com/ubuntu/pool/universe/m/multistrap/multistrap_2.2.11_all.deb" -O /tmp/multistrap.deb
  apt-get -y install libconfig-auto-perl libparse-debian-packages-perl
  dpkg -i /tmp/multistrap.deb
  apt-get -f -y install
fi

# Ubuntu 18.04 で multistrap が動かない問題の修正。
# https://github.com/volumio/Build/issues/348#issuecomment-462271607 を参照
sed -e 's/Apt::Get::AllowUnauthenticated=true/Apt::Get::AllowUnauthenticated=true";\n$config_str .= " -o Acquire::AllowInsecureRepositories=true/' -i /usr/sbin/multistrap

# Ubuntu 18.04 では GLIBCXX_3.4.26 が無いためエラーになったので、
# 新しい libstdc++6 のパッケージがある場所からインストールする
add-apt-repository -y ppa:ubuntu-toolchain-r/test
apt-get update
apt-get install -y --only-upgrade libstdc++6