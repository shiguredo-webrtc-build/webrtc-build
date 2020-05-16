#!/bin/bash

if [ $# -lt 5 ]; then
  echo "$0 <name> <branch> <commit> <revision> <maint>"
  exit 1
fi

set -ex

NAME=$1
BRANCH=$2
COMMIT=$3
REVISION=$4
MAINT=$5

cat <<EOF
package org.webrtc;
public interface $NAME {
    public static final String webrtc_branch = "$BRANCH";
    public static final String webrtc_commit = "$COMMIT";
    public static final String webrtc_revision = "$REVISION";
    public static final String maint_version = "$MAINT";
}
EOF
