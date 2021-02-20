#!/bin/bash

set -ex

SYSDIR=/root/rootfs

ln -sf libnvbuf_utils.so.1.0.0 $SYSDIR/usr/lib/aarch64-linux-gnu/tegra/libnvbuf_utils.so
ln -s libnvbuf_fdmap.so.1.0.0 $SYSDIR/usr/lib/aarch64-linux-gnu/tegra/libnvbuf_fdmap.so
