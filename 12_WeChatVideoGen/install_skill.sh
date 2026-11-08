#!/usr/bin/env bash
# 从本仓库安装 iot-demo-video skill 到本机 WorkBuddy（任意电脑通用）
# 用法：bash install_skill.sh
set -e
REPO="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO/skill/iot-demo-video/SKILL.md"
DST="$HOME/.workbuddy/skills/iot-demo-video/SKILL.md"

if [ ! -f "$SRC" ]; then
  echo "仓库中未找到 skill 定义: $SRC" >&2
  exit 1
fi

mkdir -p "$(dirname "$DST")"
cp "$SRC" "$DST"
echo "已安装仓库版 skill → $DST"
echo "版本: $(grep -m1 '^version:' "$DST")"
