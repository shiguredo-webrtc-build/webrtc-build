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
  ca-certificates \
  curl \
  debian-archive-keyring \
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
  sudo \
  unzip \
  ubuntu-keyring \
  vim \
  xz-utils
