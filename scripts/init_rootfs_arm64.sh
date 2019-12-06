#!/bin/bash

if [ $# -lt 2 ]; then
  echo "$0 <target_dir> <config_file>"
  exit 1
fi

TARGET_DIR=$1
CONFIG_FILE=$2

set -ex

multistrap --no-auth -a arm64 -d $target_dir -f $config_file
find $target_dir/usr/lib/aarch64-linux-gnu -lname '/*' -printf '%p %l\n' | while read link target; do ln -snfv "../../..${target}" "${link}"; done
find $target_dir/usr/lib/aarch64-linux-gnu/pkgconfig -printf "%f\n" | while read target; do ln -snfv "../../lib/aarch64-linux-gnu/pkgconfig/${target}" $target_dir/usr/share/pkgconfig/${target}; done
unlink $target_dir/usr/lib/gcc/aarch64-linux-gnu/5/libgcc_s.so
ln -s ../../../../../lib64/aarch64-linux-gnu/libgcc_s.so.1 $target_dir/usr/lib/gcc/aarch64-linux-gnu/5/libgcc_s.so
