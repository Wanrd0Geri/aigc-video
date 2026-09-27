#!/usr/bin/env bash
# 一条命令同步 GitHub：提交本地改动 → 拉取合并 → 推送。任一宿主改完文件或写入经验后运行：bash scripts/sync.sh [备注]
# 只拉不推：bash scripts/sync.sh --pull（本机有未提交改动时先列出来并退出 1，不自动提交；干净时拉取并报变化，不推送）。
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

# 拉取后报变化：HEAD 变了就列出拉到的文件；其中有规则或脚本时提醒先跑测试
report_pulled() {
  local files
  if [ "$(git rev-parse HEAD)" != "$1" ]; then
    files="$(git diff --name-only "$1" HEAD)"
    echo "拉到了别处的改动："
    echo "${files}"
    # 经验库（references/lessons/）只是数据，不算规则或脚本改动；不用 grep -q，避免 pipefail 下被提前关管道误判
    if [ -n "$(grep -vE '^references/lessons/' <<< "${files}" | grep -E '^(SKILL\.md$|scripts/|tests/|references/)' || true)" ]; then
      echo "其中有规则或脚本改动，用之前跑一遍五套测试（见 SETUP.md 第 3 节）"
    fi
  fi
}

if [ "${1:-}" = "--pull" ]; then   # 只拉不推：有未提交改动先列出来让人决定，不替人提交
  if [ -n "$(git status --porcelain)" ]; then
    echo "本地有未提交改动，先决定提交还是丢弃：" >&2
    git status --short >&2
    exit 1
  fi
  BEFORE="$(git rev-parse HEAD)"
  git pull --rebase -q
  report_pulled "${BEFORE}"
  echo "已拉取（未推送）：$(git log --oneline -1)"
  exit 0
fi

git add -A
if ! git diff --cached --quiet; then
  echo "本次将提交："
  git status --short
  git commit -q -m "sync: $(date '+%Y-%m-%d %H:%M') ${1:-}"; echo "已提交本地改动"
fi
BEFORE="$(git rev-parse HEAD)"
git pull --rebase -q
report_pulled "${BEFORE}"
git push -q
echo "已同步：$(git log --oneline -1)"
