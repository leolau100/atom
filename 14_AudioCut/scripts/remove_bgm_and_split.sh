#!/usr/bin/env bash
#
# 去除音频背景音（人声分离），并把纯人声切成指定时长的片段
#
# 原理：
#   1) ffmpeg 先把任意格式的音频统一解码成 44.1kHz 立体声 WAV；
#   2) Demucs（htdemucs 模型）做两轨分离，只取 vocals（人声）轨，丢掉伴奏/背景音乐；
#   3) ffmpeg 把 vocals.wav 按指定秒数切段，输出到 vocals_<N>s/ 目录。
#
# 用法：
#   ./remove_bgm_and_split.sh <音频文件> [选项]
#
# 选项：
#   -o, --out <目录>        输出目录（默认：output/<音频名>/）
#   -s, --segment <秒>      分段时长（默认：15）
#   -n, --model <模型>      Demucs 模型（默认：htdemucs，可选 htdemucs_ft / mdx_extra 等）
#   -d, --device <设备>     推理设备：auto | mps | cpu | cuda（默认：auto）
#   -f, --format <格式>     分段输出格式：mp3 | wav（默认：mp3）
#   -b, --bitrate <码率>    mp3 码率（默认：192k，仅 -f mp3 有效）
#       --loudnorm          对分段人声做 EBU R128 响度归一化（默认关闭）
#       --keep-source       保留中间文件 source.wav 与分离出的 no_vocals.wav
#   -h, --help              显示帮助
#
# 示例（在项目根目录 14_AudioCut 下执行）：
#   ./scripts/remove_bgm_and_split.sh "audio/别傻了，我们这辈子都过不上想要的生活.mp3"
#   ./scripts/remove_bgm_and_split.sh audio/in.mp3 -s 30 -o output/demo --loudnorm
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJ_DIR/.venv"
PY="$VENV_DIR/bin/python"

SEGMENT=15
MODEL="htdemucs"
DEVICE="auto"
FORMAT="mp3"
BITRATE="192k"
LOUDNORM=0
KEEP_SOURCE=0
OUTDIR=""

usage() {
  sed -n '3,26p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

die() { echo "错误：$*" >&2; exit 1; }

# ---------- 解析参数 ----------
[ $# -gt 0 ] || usage 1
case "${1:-}" in
  -h|--help) usage 0 ;;
esac

INPUT="$1"; shift
while [ $# -gt 0 ]; do
  case "$1" in
    -o|--out)      OUTDIR="${2:?缺少参数}"; shift 2 ;;
    -s|--segment)  SEGMENT="${2:?缺少参数}"; shift 2 ;;
    -n|--model)    MODEL="${2:?缺少参数}"; shift 2 ;;
    -d|--device)   DEVICE="${2:?缺少参数}"; shift 2 ;;
    -f|--format)   FORMAT="${2:?缺少参数}"; shift 2 ;;
    -b|--bitrate)  BITRATE="${2:?缺少参数}"; shift 2 ;;
    --loudnorm)    LOUDNORM=1; shift ;;
    --keep-source) KEEP_SOURCE=1; shift ;;
    -h|--help)     usage 0 ;;
    *) die "未知参数：$1（用 -h 查看用法）" ;;
  esac
done

# ---------- 环境检查 ----------
command -v ffmpeg  >/dev/null 2>&1 || die "未找到 ffmpeg，请先安装：brew install ffmpeg"
command -v ffprobe >/dev/null 2>&1 || die "未找到 ffprobe"
[ -f "$INPUT" ] || die "音频文件不存在：$INPUT"
[ -x "$PY" ] || die "未找到虚拟环境 $VENV_DIR，请先执行：
  cd \"$PROJ_DIR\" && uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python demucs numpy"

# 数值与格式校验
case "$SEGMENT" in
  ''|*[!0-9.]*) die "--segment 需要是数字，当前为：$SEGMENT" ;;
esac
case "$FORMAT" in
  mp3|wav) ;;
  *) die "--format 只支持 mp3 或 wav，当前为：$FORMAT" ;;
esac

# 设备自动选择：Apple Silicon 用 mps，其余用 cpu
if [ "$DEVICE" = "auto" ]; then
  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    DEVICE="mps"
  else
    DEVICE="cpu"
  fi
fi

# ---------- 准备工作目录 ----------
INPUT_ABS="$(cd "$(dirname "$INPUT")" && pwd)/$(basename "$INPUT")"
BASE="$(basename "$INPUT")"; BASE="${BASE%.*}"
[ -n "$OUTDIR" ] || OUTDIR="$PROJ_DIR/output/$BASE"
mkdir -p "$OUTDIR"
SEP_DIR="$OUTDIR/separated"
CHUNK_DIR="$OUTDIR/vocals_${SEGMENT}s"
SRC_WAV="$OUTDIR/source.wav"
VOCALS_WAV="$SEP_DIR/$MODEL/source/vocals.wav"
NOVOCALS_WAV="$SEP_DIR/$MODEL/source/no_vocals.wav"

DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$INPUT_ABS" 2>/dev/null || echo '')"
echo "=============================================="
echo "输入：$INPUT_ABS"
echo "时长：${DUR:-未知} 秒"
echo "输出：$OUTDIR"
echo "模型：$MODEL    设备：$DEVICE    分段：${SEGMENT}s    格式：$FORMAT"
echo "=============================================="

# ---------- 1. 统一转成 44.1kHz 立体声 WAV ----------
echo "[1/3] 解码音频 -> source.wav"
ffmpeg -y -v error -i "$INPUT_ABS" -vn -ac 2 -ar 44100 -c:a pcm_s16le "$SRC_WAV"

# ---------- 2. Demucs 人声分离 ----------
echo "[2/3] Demucs 分离人声（首次运行会自动下载模型，请稍候）"
rm -rf "$SEP_DIR"
"$PY" -m demucs --two-stems=vocals -n "$MODEL" -d "$DEVICE" -o "$SEP_DIR" "$SRC_WAV"
[ -f "$VOCALS_WAV" ] || die "未生成人声轨：$VOCALS_WAV"

# ---------- 3. 按 N 秒切分 ----------
echo "[3/3] 切分为 ${SEGMENT}s 片段 -> $CHUNK_DIR"
rm -rf "$CHUNK_DIR"; mkdir -p "$CHUNK_DIR"

AF_OPT=""
if [ "$LOUDNORM" = "1" ]; then
  AF_OPT="-af loudnorm=I=-16:TP=-1.5:LRA=11"
fi

if [ "$FORMAT" = "mp3" ]; then
  ffmpeg -y -v error -i "$VOCALS_WAV" $AF_OPT \
    -c:a libmp3lame -b:a "$BITRATE" \
    -f segment -segment_time "$SEGMENT" -reset_timestamps 1 \
    "$CHUNK_DIR/part_%03d.mp3"
else
  ffmpeg -y -v error -i "$VOCALS_WAV" $AF_OPT \
    -c:a pcm_s16le \
    -f segment -segment_time "$SEGMENT" -reset_timestamps 1 \
    "$CHUNK_DIR/part_%03d.wav"
fi

# ---------- 清理与汇总 ----------
if [ "$KEEP_SOURCE" != "1" ]; then
  rm -f "$SRC_WAV" "$NOVOCALS_WAV"
fi

COUNT="$(find "$CHUNK_DIR" -maxdepth 1 -type f | wc -l | tr -d ' ')"
TOTAL_SIZE="$(du -sh "$CHUNK_DIR" | cut -f1)"
echo "----------------------------------------------"
echo "完成：共 $COUNT 个片段，合计 $TOTAL_SIZE"
echo "人声片段：$CHUNK_DIR"
[ "$KEEP_SOURCE" = "1" ] && echo "分离原始轨：$SEP_DIR"
echo "可试听第一段：$(find "$CHUNK_DIR" -maxdepth 1 -type f | sort | head -1)"
