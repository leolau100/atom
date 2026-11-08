#!/usr/bin/env bash
#
# 录音降噪 / 去杂音（人声录音清理）
#
# 处理链：
#   highpass   去掉低频隆隆声与工频嗡声
#   afftdn     FFT 自适应降噪，压制稳态底噪（嘶声、环境噪声）
#   adeclick   去掉突发爆音、咔哒声
#   equalizer  削一点低频浑浊、补一点 3kHz 清晰度
#   speechnorm 语音动态均衡，让音量更平
#   loudnorm   EBU R128 响度归一化到 -16 LUFS
#   后置        统一下采样回 48kHz 单声道 + 安全限幅（防削波）
#
# 预设：
#   light     轻度：只去低频噪声 + 弱降噪，最大程度保留自然感
#   standard  标准（推荐）：降噪 + 去爆音 + 轻微 EQ + 响度归一
#   strong    强力：afftdn 双级压得更狠，停顿处近乎全静音，人声可能略发闷
#   ml        先用 Demucs 分离出人声轨（对付非稳态杂音更有效），再套 standard
#
# 用法（在 14_AudioCut 根目录执行）：
#   ./scripts/clean_recording.sh "通世南路14号 4.m4a"
#   ./scripts/clean_recording.sh in.m4a -p strong -o output/myrec
#   ./scripts/clean_recording.sh in.m4a -p light -fs mp3
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PY="$PROJ_DIR/.venv/bin/python"

PRESET="standard"
OUTDIR=""
FORMATS="wav,mp3"
BITRATE="192k"
KEEP_INTERMEDIATE=0

usage() { sed -n '3,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
die() { echo "错误：$*" >&2; exit 1; }

[ $# -gt 0 ] || usage 1
case "${1:-}" in -h|--help) usage 0 ;; esac

INPUT="$1"; shift
while [ $# -gt 0 ]; do
  case "$1" in
    -o|--out)     OUTDIR="${2:?缺少参数}"; shift 2 ;;
    -p|--preset)  PRESET="${2:?缺少参数}"; shift 2 ;;
    -fs|--formats) FORMATS="${2:?缺少参数}"; shift 2 ;;
    -b|--bitrate) BITRATE="${2:?缺少参数}"; shift 2 ;;
    --keep-intermediate) KEEP_INTERMEDIATE=1; shift ;;
    -h|--help)    usage 0 ;;
    *) die "未知参数：$1（用 -h 查看用法）" ;;
  esac
done

command -v ffmpeg >/dev/null 2>&1 || die "未找到 ffmpeg"
[ -f "$INPUT" ] || die "音频文件不存在：$INPUT"

case "$PRESET" in
  light)
    CHAIN="highpass=f=80:poles=2,afftdn=nr=6:nf=-55:tn=1"
    ;;
  standard)
    CHAIN="highpass=f=80:poles=2,afftdn=nr=15:nf=-50:tn=1,adeclick=w=55:o=75:a=2,\
equalizer=f=200:width_type=q:w=1:g=-2,equalizer=f=3200:width_type=q:w=1.2:g=1.5,\
speechnorm=e=6:r=0.0001:l=1,loudnorm=I=-16:TP=-1.5:LRA=11"
    ;;
  strong)
    CHAIN="highpass=f=60:poles=2,afftdn=nr=30:nf=-40:tn=1,afftdn=nr=8:nf=-55:tn=1,\
adeclick=w=55:o=75:a=2,\
equalizer=f=200:width_type=q:w=1:g=-3,equalizer=f=3200:width_type=q:w=1.2:g=2,\
speechnorm=e=8:r=0.0001:l=1,loudnorm=I=-16:TP=-1.5:LRA=11"
    ;;
  ml)
    [ -x "$VENV_PY" ] || die "ml 预设需要 Demucs 环境，请先执行：
  cd \"$PROJ_DIR\" && uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python demucs numpy"
    CHAIN="highpass=f=80:poles=2,afftdn=nr=15:nf=-50:tn=1,adeclick=w=55:o=75:a=2,\
equalizer=f=200:width_type=q:w=1:g=-2,equalizer=f=3200:width_type=q:w=1.2:g=1.5,\
speechnorm=e=6:r=0.0001:l=1,loudnorm=I=-16:TP=-1.5:LRA=11"
    ;;
  *) die "未知预设：$PRESET（可选 light | standard | strong | ml）" ;;
esac

# 后置链：loudnorm 内部会升到 192kHz，这里统一下采样回 48kHz 单声道，并加安全限幅防削波
POST="aresample=48000,aformat=channel_layouts=mono,alimiter=limit=0.95:level=0"

INPUT_ABS="$(cd "$(dirname "$INPUT")" && pwd)/$(basename "$INPUT")"
BASE="$(basename "$INPUT")"; BASE="${BASE%.*}"
[ -n "$OUTDIR" ] || OUTDIR="$PROJ_DIR/output/$BASE"
mkdir -p "$OUTDIR"

# 统一用 48kHz 单声道中间 WAV，避免不同容器解码差异
WORK="$OUTDIR/_work"; mkdir -p "$WORK"
SRC_WAV="$WORK/01_source.wav"
ffmpeg -y -v error -i "$INPUT_ABS" -vn -ac 1 -ar 48000 -c:a pcm_s16le "$SRC_WAV"

# ml 预设：先分离人声
ML_WAV="$SRC_WAV"
if [ "$PRESET" = "ml" ]; then
  DEVICE="cpu"
  if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    DEVICE="mps"
  fi
  echo "[ml] Demucs 分离人声（模型 htdemucs / 设备 ${DEVICE}）…"
  if ! "$VENV_PY" -m demucs --two-stems=vocals -n htdemucs -d "$DEVICE" -o "$WORK/sep" "$SRC_WAV" > "$WORK/demucs.log" 2>&1; then
    tail -5 "$WORK/demucs.log" >&2
    die "Demucs 分离失败（日志：$WORK/demucs.log）"
  fi
  ML_WAV="$WORK/sep/htdemucs/01_source/vocals.wav"
  [ -f "$ML_WAV" ] || die "Demucs 未生成人声轨（日志：$WORK/demucs.log）"
fi

# 指标函数：整体 RMS 与噪声底
metrics() {
  ffmpeg -hide_banner -i "$1" -af astats=metadata=1:reset=0 -f null - 2>&1 \
    | grep -E "RMS level dB|Noise floor dB|Peak level dB" | head -3 \
    | sed 's/.*\] //' | tr '\n' ' '
}

echo "=============================================="
echo "输入：$INPUT_ABS"
echo "预设：$PRESET      输出：$OUTDIR"
echo "处理前：$(metrics "$SRC_WAV")"
echo "=============================================="

OUT_WAV="$OUTDIR/$(echo "$BASE" | tr ' ' '_')_${PRESET}.wav"
echo "[处理] ffmpeg 滤镜链执行中…"
ffmpeg -y -v error -i "$ML_WAV" -af "$CHAIN,$POST" -c:a pcm_s16le "$OUT_WAV"

echo "处理后：$(metrics "$OUT_WAV")"
echo "输出规格：$(ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate,channels -of csv=p=0 "$OUT_WAV" | tr ',' '/') Hz/声道"

# 输出其它格式
IFS=',' read -ra FMTS <<< "$FORMATS"
for f in "${FMTS[@]}"; do
  case "$f" in
    wav) ;;
    mp3)
      OUT_MP3="${OUT_WAV%.wav}.mp3"
      ffmpeg -y -v error -i "$OUT_WAV" -c:a libmp3lame -b:a "$BITRATE" "$OUT_MP3"
      echo "已生成：$OUT_MP3" ;;
    m4a)
      OUT_M4A="${OUT_WAV%.wav}.m4a"
      ffmpeg -y -v error -i "$OUT_WAV" -c:a aac -b:a "$BITRATE" "$OUT_M4A"
      echo "已生成：$OUT_M4A" ;;
    *) die "不支持的格式：$f（可选 wav,mp3,m4a）" ;;
  esac
done

[ "$KEEP_INTERMEDIATE" = "1" ] || rm -rf "$WORK"
echo "----------------------------------------------"
echo "完成：$OUT_WAV"
[ "$KEEP_INTERMEDIATE" = "1" ] && echo "中间文件保留在：$WORK"
