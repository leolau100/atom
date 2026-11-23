#!/bin/bash
# jianying-editor-skill 安装脚本
set -e

# 目标目录：优先命令行第一个参数，其次环境变量，最后回退到 WorkBuddy skills 目录。
# 用法：bash install.sh [目标skills目录]
SKILL_NAME="jianying-editor-skill"
INSTALL_DIR="${1:-${SKILLS_DIR:-${HOME}/.workbuddy/skills}}"

echo "=== 安装 $SKILL_NAME -> $INSTALL_DIR ==="

mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 若目标已存在同名软链（如 WorkBuddy 的软链安装），先移除再拷贝，避免 rsync 穿透软链写入源目录。
if [ -L "$INSTALL_DIR/$SKILL_NAME" ]; then
    rm -f "$INSTALL_DIR/$SKILL_NAME"
fi
rsync -avz --delete "$SCRIPT_DIR/../" "$INSTALL_DIR/$SKILL_NAME/"

echo "✅ 安装完成: $INSTALL_DIR/$SKILL_NAME"
echo "重启对应的 AI 客户端后即可使用"
