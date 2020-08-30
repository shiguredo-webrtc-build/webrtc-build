#!/bin/bash

if [ $# -lt 2 ]; then
  echo "$0 <source_dir> <arm | x86_64>"
fi

SOURCE_DIR=$1

set -ex

pushd $SOURCE_DIR/webrtc
  if [ "$2" = "arm" ]; then
    bash src/build/install-build-deps.sh
  elif [ "$2" = "android" ]; then
    pushd src
      bash build/install-build-deps-android.sh
      gclient runhooks
    popd
  elif [ "$2" = "centos" ]; then
    # https://chromium.googlesource.com/chromium/src/+/master/docs/linux/build_instructions.md#fedora
    # 以下のようなエラーが出たのでいくつか消している
    #17 2.119 No match for argument: brlapi-devel
    #17 2.122 No match for argument: bluez-libs-devel
    #17 2.127 No match for argument: gperf
    #17 2.133 No match for argument: libgnome-keyring-devel
    #17 2.138 No match for argument: libxkbcommon-x11-devel
    #17 2.144 No match for argument: python-psutil
    #17 2.147 No match for argument: wdiff
    su -c 'yum -y install git python2 bzip2 tar pkgconfig atk-devel alsa-lib-devel \
      bison binutils bzip2-devel cairo-devel \
      cups-devel dbus-devel dbus-glib-devel expat-devel fontconfig-devel \
      freetype-devel gcc-c++ glib2-devel glibc.i686 glib2-devel \
      gtk3-devel java-1.*.0-openjdk-devel libatomic libcap-devel libffi-devel \
      libgcc.i686 libjpeg-devel libstdc++.i686 libX11-devel \
      libXScrnSaver-devel libXtst-devel ncurses-compat-libs \
      nspr-devel nss-devel pam-devel pango-devel pciutils-devel \
      pulseaudio-libs-devel zlib.i686 httpd mod_ssl php php-cli \
      xorg-x11-server-Xvfb'
  else
    sed -i -e 's/sudo/sudo -E/g' src/build/install-build-deps.sh
    bash ./src/build/install-build-deps.sh --no-arm --no-chromeos-fonts
    pushd src/build
      git reset --hard
    popd
  fi
popd
