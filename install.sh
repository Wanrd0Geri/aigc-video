#!/usr/bin/env bash
# 把本仓库挂到 Claude Code 与 Codex 的 skills 目录（软链），两边读的是同一份文件。
# 安装位已有真实目录时先搬到 ~/Documents/Codex/skill-backups/ 再建软链。换机器：git clone 后跑一次即可。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
BK="$HOME/Documents/Codex/skill-backups"; mkdir -p "$BK"
for d in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
  mkdir -p "$d"; t="$d/aigc-video"; host="$(basename "$(dirname "$d")")"
  if [ -L "$t" ]; then rm "$t"
  elif [ -e "$t" ]; then mv "$t" "$BK/aigc-video-${host}-before-link-$(date +%Y%m%d-%H%M)"; echo "已备份原目录到 $BK"; fi
  ln -s "$ROOT" "$t"; echo "已挂载 $t -> $ROOT"
done
echo "钩子命令路径：python3 -X utf8 $HOME/.claude/skills/aigc-video/hooks/stop_gate.py（软链解析后即本仓库）"
