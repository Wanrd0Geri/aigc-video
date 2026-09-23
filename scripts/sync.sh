#!/usr/bin/env bash
# 一条命令同步 GitHub：提交本地改动 → 拉取合并 → 推送。任一宿主改完文件或写入经验后运行：bash scripts/sync.sh [备注]
# 需要代理才能连 GitHub 的机器：把代理地址写进 ~/.aigc-video-proxy（一行，如 http://127.0.0.1:7897），脚本会自动使用；没有这个文件就直连。
# 只在 main 分支上跑：在 dev 工作区（aigc-video-dev）或别的分支上会把没测完的改动一起 add、commit、推上去，所以拒绝执行。
set -euo pipefail
cd "$(dirname "$0")/.."
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
if [ "${BRANCH}" != "main" ]; then
  echo "拒绝执行：当前分支是「${BRANCH:-不是 git 仓库}」（$(pwd -P)），sync.sh 只在 main 分支上同步。" >&2
  echo "dev 分支的改动测完后快进合并进 main，再到主线仓库跑 bash scripts/sync.sh。" >&2
  exit 1
fi
if [ -f "${HOME}/.aigc-video-proxy" ]; then P="$(head -1 "${HOME}/.aigc-video-proxy" | tr -d "[:space:]")"; [ -n "${P}" ] && export HTTPS_PROXY="${P}" HTTP_PROXY="${P}"; fi
git add -A
if ! git diff --cached --quiet; then git commit -q -m "sync: $(date '+%Y-%m-%d %H:%M') ${1:-}"; echo "已提交本地改动"; fi
git pull --rebase -q
git push -q
echo "已同步：$(git log --oneline -1)"
