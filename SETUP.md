# aigc-video 换机安装与同步指南（给另一台电脑上的 AI 助手看）

你正在帮用户 Gerry 在一台新电脑上装好 `aigc-video` 这个 skill，并让它和 GitHub 保持同步。按顺序做，每步做完要验证；本文档里的路径不要改。

## 0 这套东西的结构（先理解再动手）

- **唯一来源**：公开仓库 `https://github.com/Wanrd0Geri/aigc-video`。克隆不需要登录；推送需要是协作者。
- **本机唯一副本**：`~/Documents/Codex/aigc-video`，从仓库克隆。
- **两个宿主的 skills 目录都是软链**：`~/.claude/skills/aigc-video` 和 `~/.codex/skills/aigc-video` → 指向本机副本。两边读同一份文件，经验库 `references/lessons/seedance-2.5.md` 也是同一份。
- **禁止**：在 skills 目录里放拷贝；用 `git clone` 覆盖软链；手工改软链指向；`git pull` 之外的方式"更新"。
- **同步动作**：改完文件或写入经验后运行 `bash ~/Documents/Codex/aigc-video/scripts/sync.sh 一句备注`（提交 → 拉取 → 推送）。两台电脑之间不自动同步，在哪台改就在哪台跑；换到另一台用之前先跑一次。

## 1 前置条件

- Python 3（`python3 --version`）。
- ffmpeg（`ffmpeg -version`；没有就 `brew install ffmpeg`），成片抽帧用。
- git、GitHub CLI `gh`（没有就 `brew install gh`）。
- 网络：这台电脑访问 GitHub 是否需要代理，先测 `curl -sI https://github.com --max-time 10`。超时就要代理；用户笔记本上的代理是 `http://127.0.0.1:7897`，新电脑端口可能不同，问用户。

## 2 登录 GitHub（只有要往仓库推改动的人才需要；只用不改可以跳过）

让用户自己在终端跑（不要替用户输入账号密码或验证码）：

```bash
gh auth login -h github.com -p https -w
```

需要代理时前面加 `HTTPS_PROXY=http://127.0.0.1:<端口> HTTP_PROXY=http://127.0.0.1:<端口>`。它会显示一个 8 位一次性码，用户在浏览器 `https://github.com/login/device` 输入并授权。验证：`gh auth status` 显示已登录。不是仓库所有者 Wanrd0Geri 的话，推送前要请所有者把这个账号加为协作者，或者改用 fork + Pull Request。

## 3 克隆并挂载

```bash
git clone https://github.com/Wanrd0Geri/aigc-video ~/Documents/Codex/aigc-video && bash ~/Documents/Codex/aigc-video/install.sh
```

`install.sh` 会：在 `~/.claude/skills` 和 `~/.codex/skills` 各建一条软链 `aigc-video` 指向克隆目录；那里原本有真实目录的话先搬到 `~/Documents/Codex/skill-backups/` 再建软链。

验证：

```bash
ls -l ~/.claude/skills/aigc-video ~/.codex/skills/aigc-video
cd ~/.claude/skills/aigc-video && python3 -X utf8 tests/run_check_tests.py | tail -1 && python3 -X utf8 tests/test_revision_checks.py 2>&1 | tail -1 && python3 -X utf8 tests/test_delivery_gate.py 2>&1 | tail -1 && python3 -X utf8 tests/test_stop_gate.py 2>&1 | tail -1
```

期望：两条 `->` 指向 `~/Documents/Codex/aigc-video`；每行都没有失败（项数随版本增加）。

## 4 挂守门钩子（Claude Code；可选但推荐）

钩子配置不在仓库里，每台电脑单独挂。它在模型交付提示词时自动核对：有本轮检查报告就放行；没有报告的四段完整稿由钩子代跑 `scripts/check_prompt.py`（一律按四段新稿查），有错打回、无错放行并提示"作者未自己跑检查"；局部镜头、不带四段外壳的裸命令和五段 / 六段旧壳没报告则打回。第二次仍不过会放行并附警告，不会死锁。

编辑 `~/.claude/settings.json`：在 `hooks.Stop` 数组里**追加**一项（用户已有别的 Stop 钩子时不要替换、不要删）；没有 `hooks` 或 `Stop` 键就新建：

```json
{"hooks": [{"type": "command", "command": "python3 -X utf8 $HOME/.claude/skills/aigc-video/hooks/stop_gate.py", "timeout": 30}]}
```

改之前先备份 settings.json。验证（临时目录，不污染真实报告目录）：

```bash
T=$(mktemp -d); printf '{"transcript_path":null,"last_assistant_message":"好的。","stop_hook_active":false}' | AIGC_GATE_DIR=$T python3 -X utf8 ~/.claude/skills/aigc-video/hooks/stop_gate.py; echo "exit=$?"
```

期望：输出 `{}` 或无输出，`exit=0`。更多用例见 `hooks/README.md` 的验证清单。Codex 侧的钩子按 `hooks/README.md` 里 Codex 一节配置，那部分只按官方文档写过、没有真实验证，装完要自测。

## 5 日常同步

- 改了任何文件、或用 `scripts/log_lesson.py` 写了经验：`bash ~/Documents/Codex/aigc-video/scripts/sync.sh 备注`。
- 开始用之前想拿到另一台电脑的改动：同样跑 `sync.sh`（它先拉后推）。
- 这台电脑连 GitHub 需要代理的话，把代理地址写进 `~/.aigc-video-proxy`（一行，例如 `http://127.0.0.1:7897`），`sync.sh` 会自动使用；不需要代理就不建这个文件。
- 拉取时报冲突：只会发生在两台电脑改了同一行。经验库冲突时保留双方条目、编号只递增（可用 `scripts/merge_lessons.py` 按编号合并），改完 `git add -A && git rebase --continue` 再 `git push`。不要用 `--force`。

## 6 常见错误

| 现象 | 原因 | 处理 |
|---|---|---|
| `gh auth login` 卡住后报 `operation timed out` | 终端没走代理 | 命令前加 `HTTPS_PROXY=... HTTP_PROXY=...` |
| `git push` 报 403 | 没登录，或登录的账号不是协作者 | 重做第 2 步；请所有者加协作者，或 fork + Pull Request |
| skills 目录里已有 `aigc-video` 真实目录 | 旧版拷贝 | 直接跑 `install.sh`，它会备份后换成软链 |
| 钩子每次都拦、提示"没有本轮检查报告" | 交付的是局部镜头、不带四段外壳的裸操作命令或五段 / 六段旧壳稿，且没跑 `check_prompt.py --report` | 局部镜头与旧稿修订按提示带 `--baseline`（局部再加 `--partial`）；操作命令装进四段（旧稿修订按父稿外壳）并按任务带 `--task 延长`、`--task 编辑` 或 `--task 衔接`，没有时码的加 `--untimed`（见 `references/seedance-operations.md` 第 0.5 节末尾）；跑一次并 `--report` 到 `~/.aigc-video-gate/<时间戳>.json` |
| 两边经验编号撞号 | 两台电脑或两个组员各记了一条 | `merge_lessons.py` 合并，后写的改成下一个编号 |

## 7 做完后报告给用户

一句话说清：软链指向哪里、四套测试结果、钩子挂没挂、需不需要代理。不要把 skill 目录换成别的位置，不要改仓库里的路径。

## 8 维护 skill 本身（改 skill 的人看）

改 skill 的文件在 `~/Documents/Codex/aigc-video-dev`（dev 分支的工作区）里改，四套测试跑过之后再合并到 main 并 `sync.sh`。main 是安装位，改到一半的文件不会影响正在使用的会话。
