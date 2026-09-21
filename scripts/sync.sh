#!/usr/bin/env bash
# 一条命令同步 GitHub：提交本地改动 → 拉取合并 → 推送。任一宿主改完文件或写入经验后运行：bash scripts/sync.sh [备注]
# 本机终端默认不走代理会连不上 GitHub，这里默认用本机代理；不需要时 AIGC_NO_PROXY=1 bash scripts/sync.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${AIGC_NO_PROXY:-}" ]; then export HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:7897}" HTTP_PROXY="${HTTP_PROXY:-http://127.0.0.1:7897}"; fi
git add -A
if ! git diff --cached --quiet; then git commit -q -m "sync: $(date '+%Y-%m-%d %H:%M') ${1:-}"; echo "已提交本地改动"; fi
git pull --rebase -q
git push -q
echo "已同步：$(git log --oneline -1)"
