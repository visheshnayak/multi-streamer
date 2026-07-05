#!/usr/bin/env bash
set -euo pipefail

echo "sending stream..."
streamIndex=$((( RANDOM % 2 )+1))
ffmpeg -re -stream_loop -1 -i vid$streamIndex.mp4 -c copy -f flv rtmp://192.168.1.69/live/stream$streamIndex
