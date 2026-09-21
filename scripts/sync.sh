#!/usr/bin/env bash
# 一条命令同步 GitHub：提交本地改动 → 拉取合并 → 推送。任一宿主改完文件或写入经验后运行：bash scripts/sync.sh [备注]
# 需要代理才能连 GitHub 的机器：把代理地址写进 ~/.aigc-video-proxy（一行，如 http://127.0.0.1:7897），脚本会自动使用；没有这个文件就直连。
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f "$HOME/.aigc-video-proxy" ]; then P="$(head -1 "$HOME/.aigc-video-proxy" | tr -d "[:space:]")"; [ -n "$P" ] && export HTTPS_PROXY="$P" HTTP_PROXY="$P"; fi
git add -A
if ! git diff --cached --quiet; then git commit -q -m "sync: $(date '+%Y-%m-%d %H:%M') ${1:-}"; echo "已提交本地改动"; fi
git pull --rebase -q
git push -q
echo "已同步：$(git log --oneline -1)"
