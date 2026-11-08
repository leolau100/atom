#!/usr/bin/env bash
set -e

SRC=/Users/liulei/Product/WeChatArticle/2026/09
DST=/Users/liulei/Product/13_IoTDocs/public/iot-content

SLUGS=(thinger-io iotsharp neoindustrial fledge iec104 dlt698 dlt645 top10-tools modbus-sim gpt6)
FOLDERS=(
"2026-09-07-开源物联网平台盘点-17-Thinger.io （2026-9-8日发布，2026-9-9日上线）"
"2026-09-07-开源物联网平台盘点-16-IoTSharp （2026-9-7日发布，2026-9-8日上线）"
"2026-09-11-工业数采平台盘点-1-neoIndustrial（2026-09-12发布）"
"2026-09-05-开源物联网平台盘点-10-Fledge（LF Edge） （2026-9-6日发布，2026-9-7日上线）"
"2026-09-09-104协议IEC104-2-RichyP7 IEC60870-5-104-simulator（2026-09-10发布）"
"2026-09-09-698协议DLT698-9-电力698协议及测试工具资源库"
"2026-09-09-645协议DLT645-5-ems_simulate"
"2026-09-08-工控人必备十大工具"
"2026-09-07-Modbus模拟器盘点-18-soso7885-modbus_simulator（2026-9-9日发布，2026-9-10日上线）"
"2026-09-06-GPT-6跨领域玩法盘点（量子位风格）（2026-9-7日发布）"
)

for i in "${!SLUGS[@]}"; do
  slug="${SLUGS[$i]}"
  folder="$SRC/${FOLDERS[$i]}"
  mkdir -p "$DST/$slug"
  cp -R "$folder/." "$DST/$slug/"
  main=$(cd "$DST/$slug" && ls -1 *.md | grep -viE '备份|终稿|原文| - no|no-' | head -1)
  if [ -n "$main" ]; then
    cp "$DST/$slug/$main" "$DST/$slug/index.md"
    echo "OK  $slug -> $main"
  else
    echo "WARN $slug 未找到主 md"
  fi
done

echo "--- 复制完成 ---"
du -sh "$DST"
