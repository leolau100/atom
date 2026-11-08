#!/usr/bin/env bash
# 把本机已安装的 iot-demo-video skill 同步回本仓库并推送到远端
# 用法：bash publish_skill.sh
# 注意：仅同步 SKILL.md（skill 定义），不同步 _skillhub_meta.json 等 WorkBuddy 内部元数据
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
SRC="$HOME/.workbuddy/skills/iot-demo-video/SKILL.md"
DST="$REPO/skill/iot-demo-video/SKILL.md"

if [ ! -f "$SRC" ]; then
  echo "未找到已安装的 skill: $SRC" >&2
  exit 1
fi

cp "$SRC" "$DST"
cd "$REPO"

if git diff --quiet -- "$DST"; then
  echo "skill 无变化，无需推送。"
  exit 0
fi

git add skill/iot-demo-video/SKILL.md
git commit -m "sync(iot-demo-video): 从本地安装副本同步 skill 定义"
git push
echo "已同步并推送到仓库: $(git remote get-url origin)"
echo "版本: $(grep -m1 '^version:' "$DST")"
