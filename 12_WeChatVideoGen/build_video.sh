#!/usr/bin/env bash
# 把截图序列合成为演示视频：每张图配一段中文字幕，带 Ken Burns 缓慢缩放
# 用法: ./build_video.sh <caption_file> <output.mp4>
# caption_file 每行格式: 图片路径<TAB>这一屏的中文解说文字
set -euo pipefail

CAP="$1"
OUT="${2:-/Users/liulei/Workbuddy/2026-09-03-21-25-37/magistrala-demo/demo.mp4}"
WORK="/Users/liulei/Workbuddy/2026-09-03-21-25-37/magistrala-demo/.build"
W=1440; H=900; FPS=30

rm -rf "$WORK"; mkdir -p "$WORK"
i=0
while IFS=$'\t' read -r img text; do
  [ -z "${img:-}" ] && continue
  i=$((i+1))
  seg="$WORK/$(printf '%03d' $i).mp4"
  # 转义 drawtext 特殊字符
  safe=$(printf '%s' "$text" | sed 's/\\/\\\\/g; s/:/\\:/g; s/%/%%/g; s/'"'"'/\\'"'"'/g')
  ffmpeg -y -loop 1 -i "$img" -t 12 -r $FPS \
    -vf "scale=1920:1200:force_original_aspect_ratio=decrease,pad=1920:1200:(ow-iw)/2:(oh-ih)/2:color=0x0d1117,\
zoompan=z='min(zoom+0.0006,1.12)':d=12*30:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1440x900:fps=30,\
drawbox=y=ih-120:color=black@0.62:width=iw:height=120:t=fill,\
drawtext=fontfile=/System/Library/Fonts/PingFang.ttc:text='$safe':fontcolor=white:fontsize=34:x=(w-tw)/2:y=h-88" \
    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p "$seg" </dev/null
  echo "file '$seg'" >> "$WORK/list.txt"
done < "$CAP"

ffmpeg -y -f concat -safe 0 -i "$WORK/list.txt" -c copy "$OUT"
echo "输出: $OUT"
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT"
