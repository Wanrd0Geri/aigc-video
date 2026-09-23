#!/usr/bin/env bash
# 把本仓库挂到 Claude Code 与 Codex 的 skills 目录（软链），两边读的是同一份文件。
# 安装位已有真实目录时先搬到 ~/Documents/Codex/skill-backups/ 再建软链。换机器：git clone 到 ~/Documents/Codex/aigc-video 后跑一次即可。
# 只从主线仓库 ${HOME}/Documents/Codex/aigc-video 的 main 分支安装：在 dev 工作区（aigc-video-dev）或别的分支上跑，会把
# 两个宿主挂到还没测完的改动上，所以拒绝执行。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
EXPECT="${HOME}/Documents/Codex/aigc-video"
EXPECT_REAL="$(cd "${EXPECT}" 2>/dev/null && pwd -P || echo "${EXPECT}")"
if [ "${ROOT}" != "${EXPECT_REAL}" ]; then
  echo "拒绝执行：install.sh 只从主线仓库 ${EXPECT} 安装，当前位置是 ${ROOT}。" >&2
  echo "dev 工作区的改动先测完、快进合并进 main，再到 ${EXPECT} 跑 bash install.sh；换机器请 git clone 到 ${EXPECT}。" >&2
  exit 1
fi
BRANCH="$(git -C "${ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
if [ "${BRANCH}" != "main" ]; then
  echo "拒绝执行：当前分支是「${BRANCH:-不是 git 仓库}」，install.sh 只在 main 分支上安装（两个宿主读的就是这份文件）。" >&2
  echo "先 git -C ${ROOT} switch main，再跑 bash install.sh。" >&2
  exit 1
fi
BK="${HOME}/Documents/Codex/skill-backups"; mkdir -p "${BK}"
for d in "${HOME}/.claude/skills" "${HOME}/.codex/skills"; do
  mkdir -p "${d}"; t="${d}/aigc-video"; host="$(basename "$(dirname "${d}")")"
  if [ -L "${t}" ]; then rm "${t}"
  elif [ -e "${t}" ]; then mv "${t}" "${BK}/aigc-video-${host}-before-link-$(date +%Y%m%d-%H%M)"; echo "已备份原目录到 ${BK}"; fi
  ln -s "${ROOT}" "${t}"; echo "已挂载 ${t} -> ${ROOT}"
done
echo "钩子命令路径：python3 -X utf8 ${HOME}/.claude/skills/aigc-video/hooks/stop_gate.py（软链解析后即本仓库）"
