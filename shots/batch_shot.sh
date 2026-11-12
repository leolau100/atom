#!/bin/bash
cd /Users/liulei/Product/ATOM
SHOTS=shots
run() {
  local name="$1" url="$2" out="$3" clip="$4"
  if [ "$clip" = "0" ]; then
    node shot_core.js "$url" "$SHOTS/$out.png" >/dev/null 2>&1
  else
    node shot_core.js "$url" "$SHOTS/$out.png" 0 "$clip" >/dev/null 2>&1
  fi
  local sz=$(stat -f%z "$SHOTS/$out.png" 2>/dev/null || echo 0)
  python3 png2b64webp.py "$SHOTS/$out.png" "$SHOTS/$out.webp" > "$SHOTS/$out.b64" 2>/dev/null
  echo "$name ($out): png=${sz}B"
}

# name  home_url  repo_url
run "63 dgiot"    "https://dgiot.com"                       "63_dgiot_home"    1000
run "63 dgiot"    "https://github.com/dgiot/dgiot"          "63_dgiot_repo"    0

run "64 ruff"     "https://ruff.io"                         "64_ruff_home"     1000
run "64 ruff"     "https://github.com/ruffjs/ruff-runtime"  "64_ruff_repo"     0

run "65 tdengine" "https://www.tdengine.com"                "65_tdengine_home" 1000
run "65 tdengine" "https://github.com/taosdata/TDengine"    "65_tdengine_repo" 0

run "66 neuron"   "https://neuron.emqx.com"                 "66_neuron_home"   1000
run "66 neuron"   "https://github.com/emqx/neuron"          "66_neuron_repo"   0

run "67 dc3"      "https://github.com/pnoker/iot-dc3"       "67_dc3_home"      1100
run "67 dc3"      "https://github.com/pnoker/iot-dc3"       "67_dc3_repo"      0

run "68 sagoo"    "https://github.com/sagoo-cloud/sagooiot" "68_sagoo_home"    1100
run "68 sagoo"    "https://github.com/sagoo-cloud/sagooiot" "68_sagoo_repo"    0

run "70 thingskit" "https://www.thingskit.com"              "70_thingskit_home" 1000
run "70 thingskit" "https://gitee.com/thingskit/thingskit"  "70_thingskit_repo" 0

run "71 iotmaster" "https://github.com/god-jason/iot-master" "71_iotmaster_home" 1100
run "71 iotmaster" "https://github.com/god-jason/iot-master" "71_iotmaster_repo" 0

echo "ALL DONE"
