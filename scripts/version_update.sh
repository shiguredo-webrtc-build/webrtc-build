#!/bin/bash

set -ex

cd $(dirname $0)

# VERSION ファイルを適切なバージョンに更新するスクリプト
# GitHub Actions から実行されることを想定している

if [ "$GITHUB_ACTIONS" == "true" ]; then
  git config --global user.name "${GITHUB_ACTOR}"
  git config --global user.email "${GITHUB_ACTOR}@users.noreply.github.com"
fi

git checkout master
REMOTE=$(git remote)

# run.py に version_list や version_update が存在しないブランチにチェックアウトしてしまう可能性があるので、
# master ブランチの run.py の内容をコピーして利用する
cp run.py _run.py

LINES=$(python3 _run.py version_list | head -n 3)
while read -r milestone branch position commit; do
  echo "${milestone} ${branch} ${position} ${commit}"
  STATUS=$(git branch -a | grep -q "remotes/${REMOTE}/feature/${milestone}.${branch}"; echo $?)
  if [ "$STATUS" == "0" ]; then
    git checkout "feature/${milestone}.${branch}"
    CREATED=0
  else
    git checkout -b "feature/${milestone}.${branch}" master
    CREATED=1
  fi

  source VERSION
  python3 _run.py version_update ${milestone}
  STATUS=$(git diff --exit-code --quiet VERSION; echo $?)
  if [ "$STATUS" == "1" ]; then
    git add VERSION
    if [ "$CREATED" == "0" ]; then
      git commit -m "[update] Update version m$WEBRTC_VERSION to ${milestone}.${branch}.${position}"
    else
      git commit -m "[create] Create new branch feature/${milestone}.${branch}"
    fi
  fi
done <<< "$LINES"

# GitHub Actions から実行する場合は push までやる
if [ "$GITHUB_ACTIONS" == "true" ]; then
  git push $REMOTE --all
fi

git checkout master