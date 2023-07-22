#!/bin/bash

set -ex

# grub-efi-amd64-signed がエラーになるので hold で回避する
# ref: https://github.com/community/community/discussions/47863
apt-mark hold grub-efi-amd64-signed
apt-get update --fix-missing
apt-get upgrade

# tzdata を noninteractive にしないと実行が止まってしまう
apt-get -y install tzdata
echo 'Asia/Tokyo' > /etc/timezone
dpkg-reconfigure -f noninteractive tzdata

export DEBIAN_FRONTEND=noninteractive

apt-get -y install \
  binutils \
  git \
  locales \
  lsb-release \
  ninja-build \
  pkg-config \
  python3 \
  python3-setuptools \
  rsync \
  sudo \
  unzip \
  vim \
  wget \
  xz-utils
