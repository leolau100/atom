#!/usr/bin/env bash
#
# 批量生成一篇文章的所有分段配音（逐段串行，避免抢 GPU）
#
# 用法（在 14_AudioCut 根目录执行）：
#   ./scripts/run_narration.sh "2026/9/2026-9-19-当下的力量-76" --parts 7
#   ./scripts/run_narration.sh "<项目目录>" --parts 7 --comma-ms 300 --period-ms 500
#
# 说明：
#   - 文本来自 <项目目录>/chunks/chunk_XX.txt（先用 split_text.py 切好）
#   - 已完成的段落会跳过（想重跑加 --force）
#   - 每段产物：out/part_XX.wav + .mp3，中间文件在 raw/ prep/
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAGE_DIR=""
PARTS=5
FORCE=0
EXTRA=()
SUFFIX=""

[ $# -gt 0 ] || { echo "用法: $0 <项目目录> [--parts N] [--comma-ms N] [--period-ms N] [--min-gap-ms N] [--post-only 后缀] [--force]"; exit 1; }
PAGE_DIR="$1"; shift
while [ $# -gt 0 ]; do
  case "$1" in
    --parts)     PARTS="$2"; shift 2 ;;
    --force)     FORCE=1; shift ;;
    --post-only) SUFFIX="_$2"; EXTRA+=(--reuse-raw --out-suffix "$SUFFIX"); shift 2 ;;
    --comma-ms|--period-ms|--para-ms|--seed|--keep-ms|--min-gap-ms|--instruct|--max-chunk-chars) EXTRA+=("$1" "$2"); shift 2 ;;
    --personality|--no-extend|--reuse-raw) EXTRA+=("$1"); shift ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

[ -d "$ROOT/$PAGE_DIR/chunks" ] || { echo "找不到 $ROOT/$PAGE_DIR/chunks"; exit 1; }
[ ${#EXTRA[@]} -eq 0 ] && EXTRA=(--comma-ms 300 --period-ms 500)

cd "$ROOT"
echo "项目: $PAGE_DIR   段数: $PARTS   停顿配方: ${EXTRA[*]}"
START=$(date +%s)

for i in $(seq 1 "$PARTS"); do
  TAG=$(printf "part_%02d" "$i")
  SRC="$PAGE_DIR/chunks/chunk_$(printf '%02d' "$i").txt"
  OUT="$PAGE_DIR/out/$TAG$SUFFIX.mp3"
  if [ "$FORCE" -eq 0 ] && [ -f "$OUT" ]; then
    echo "[skip] $TAG 已存在"
    continue
  fi
  echo ""
  echo "──────── $TAG  ($(date '+%H:%M:%S')) ────────"
  if ! .venv/bin/python scripts/narrate_chunk.py --text "$SRC" --outdir "$PAGE_DIR" \
        --tag "$TAG" "${EXTRA[@]}"; then
    echo "!! $TAG 失败，继续后面的段落"
  fi
done

echo ""
echo "全部结束，用时 $(( $(date +%s) - START ))s"
ls -la "$PAGE_DIR/out" | grep -E "part_.*\.mp3"
