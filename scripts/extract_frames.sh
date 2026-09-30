#!/usr/bin/env bash
# 薄封装：转调跨平台的 extract_frames.py（用法、参数、产出与退出码不变）。SKILL.md 与 diagnose.md 直接指向 extract_frames.py。
# extract_frames.sh <视频> [输出目录] [每秒帧数] [切镜阈值]
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
if command -v py >/dev/null 2>&1 && py -3 -c "" >/dev/null 2>&1; then PY="py -3"
elif command -v python3 >/dev/null 2>&1; then PY=python3
else PY=python; fi
exec $PY -X utf8 "$HERE/extract_frames.py" "$@"
