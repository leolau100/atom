#!/usr/bin/env bash
set -e

SRV=root@47.102.41.227

echo "== mkdir iot-docs =="
ssh "$SRV" 'mkdir -p /www/wwwroot/iot-docs'

echo "== push IoT docs (dist) -> /www/wwwroot/iot-docs =="
scp -r /Users/liulei/Product/13_IoTDocs/dist/. "$SRV:/www/wwwroot/iot-docs/"

echo "== push nginx conf -> vhost =="
scp /Users/liulei/Product/06_NiceWeChatFile/deploy/wechat-md.conf "$SRV:/www/server/panel/vhost/nginx/wechat-md.conf"

echo "== fix perms (避免静态资源 403) =="
ssh "$SRV" 'chmod -R 755 /www/wwwroot/iot-docs'

echo "== reload nginx =="
ssh "$SRV" 'nginx -s reload && echo nginx-reloaded'

echo "== push portfolio (dist) -> /www/wwwroot/portfolio =="
scp -r /Users/liulei/Product/11_Portfolio/dist/. "$SRV:/www/wwwroot/portfolio/"

echo "== verify =="
ssh "$SRV" 'curl -sI https://hackertodo.com/iot/ | head -3; echo "---"; curl -sI https://hackertodo.com/ | head -1'
echo "== DONE =="
