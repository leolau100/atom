#!/usr/bin/env bash
# GPT-6 Astra 文章配套视频下载脚本
# 说明：当前沙箱环境的网络出口（代理）屏蔽了 x.com / api.x.com / pbs.twimg.com，
#       因此只能在【能正常访问 X 的机器】上运行本脚本。
# 用法：
#   1) 安装 yt-dlp：  pip install yt-dlp   （并建议 brew install ffmpeg 或 apt install ffmpeg）
#   2) 在终端进入本目录：  cd assets/video
#   3) 运行：  bash download_videos.sh
#   下载完成后，mp4 会出现在同目录，文件名与文章内引用的本地路径一致。
set -e

dl() {
  local url="$1"; local out="$2"
  echo ">>> 下载 $out"
  yt-dlp --retries 5 --socket-timeout 60 -f "b[ext=mp4]" "$url" -o "$out" || \
  yt-dlp --retries 5 --socket-timeout 60 "$url" -o "$out"
}

dl "https://x.com/mattshumer_/status/2095609734845927525/video/1" "01_manhattan.mp4"
dl "https://x.com/flowith/status/2095750768204877858/video/1"     "02_compare.mp4"
dl "https://x.com/goofyninjaaa/status/2095592572286533644/video/1" "03_house_unreal.mp4"
dl "https://x.com/GoGoFly23/status/2096436525110309251/video/1"    "04_pcb_kicad.mp4"
dl "https://x.com/NFT_Chen/status/2096143589151756638/video/1"     "05_hangzhou_threejs.mp4"
dl "https://x.com/ashebytes/status/2096221988763173186/video/1"    "06_tesla_anatomy.mp4"
dl "https://x.com/zhengli/status/2096048421543272893/video/1"      "07_prompt_40min.mp4"
dl "https://x.com/adamdotnew/status/2096053889141489669/video/1"   "08_agentic_cad.mp4"
dl "https://x.com/earthtojake/status/2096020381547008327/video/1"  "09_text2cad.mp4"

echo "=== 下载完成，本目录文件：==="
ls -lh *.mp4
