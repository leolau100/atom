#!/bin/bash
cd /Users/liulei/Product/ATOM
run() {
  local name="$1" url="$2" out="$3" clip="$4"
  if [ "$clip" = "0" ]; then
    node shot_core.js "$url" "shots/$out.png" >/dev/null 2>&1
  else
    node shot_core.js "$url" "shots/$out.png" 0 "$clip" >/dev/null 2>&1
  fi
  python3 png2b64webp.py "shots/$out.png" "shots/$out.webp" > "shots/$out.b64" 2>/dev/null
  echo "$name ($out): $(stat -f%z shots/$out.png)B png / $(stat -f%z shots/$out.b64)B b64"
}
# regenerate repo top-clip (code directory) for projects that have a distinct homepage
run "63 dgiot"    "https://github.com/dgiot/dgiot"          "63_dgiot_repo"    1200
run "64 ruff"     "https://github.com/ruffjs/ruff-runtime"  "64_ruff_repo"     1200
run "65 tdengine" "https://github.com/taosdata/TDengine"    "65_tdengine_repo" 1200
run "66 neuron"   "https://github.com/emqx/neuron"          "66_neuron_repo"   1200
run "70 thingskit" "https://gitee.com/thingskit/thingskit"  "70_thingskit_repo" 1200
echo "REPO CLIPS DONE"
