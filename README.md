# aigc-video — 即梦 Seedance 2.5 提示词导演 skill

把想法翻译成 Seedance 2.5 听得懂的可见画面，在锁定项之外主动提升观感，要先看分镜时给一张能改的镜头表，并把成片反馈整理成可写入经验库的观察。Claude Code 与 Codex 通用（只依赖 SKILL.md、python3 标准库、ffmpeg）。

## 安装

只安装最终审查通过的冻结 ZIP：先核对交付包 SHA-256 与包内逐文件清单，备份当前安装目录；从该 ZIP 解压后再将整个 `aigc-video/` 目录放到以下位置，并核对安装后文件哈希。不要从仍在修改的开发目录复制，也不要把未审的新经验直接混入已验收包。候选交付本身不执行安装。

安装位置：
- Codex：`~/.codex/skills/aigc-video/`
- Claude Code：`~/.claude/skills/aigc-video/`（或项目内 `.claude/skills/`）

抽帧需要 ffmpeg：`brew install ffmpeg`。

## 用法

- 写新提示词：说清人物、场景、动作、时长、素材（按上传顺序说明每张图 / 视频 / 音频是什么）。想先看分镜就说"先看分镜"，会先收到一张能改的镜头表；否则直接得到可粘贴进即梦的提示词代码块，下方一行质量放行结果。
- 改现有提示词 / 操作命令：贴原稿，说要改什么；延长、编辑、衔接、白模、宫格等直接说任务。
- 输入「自检」：对最近一份提示词做质检。
- 输入「整理经验」：跑一遍经验库体检，得到一份候选清单（哪几条被案例反复引用、哪几条像是能合并、哪几条互相修正、哪个分类太胖），每条一句人话，你挑要升级成规则、合并还是保留；不点头不动库。
- 回传视频或截图 + 你的评价：得到逐句兑现表、归因、最小修法和一条待审观察；你说"写入经验库"才写进 `references/lessons/seedance-2.5.md`。
- 问"这个效果叫什么 / 怎么写"：查词库直答。

## 结构

```
SKILL.md                     入口：共享硬约束、路由、九步清单、分级、镜头表与交付格式
references/
  seedance-format.md         官方格式、素材引用、时间戳、声音、禁止项、硬限制
  seedance-operations.md     延长、编辑、首尾帧、关键帧、宫格、白模、绿幕、衔接、成片
  writing-rules.md           写法规则 60 条（三道门、只写当前画面…）
  cases/                     官方案例库 + 我的成功案例（只给组织方式与句式样板；只读索引再取一条，知识在经验库）
  craft/                     10 张工艺卡：镜头、光影、表演、站位、运动物理、打斗、特效、场景氛围、题材配方、导演提案
  lexicon/                   4 张词库：运镜、动作、光线材质特效、表演；带官方三档与已试 / 未试
  review/                    自检、成片诊断、改稿规则
  lessons/                   经验库（写前必读、诊断后必写）
scripts/
  check_prompt.py            格式、素材、时码及锁定检查
  verify_delivery.py         实际重跑检查，核对需求、专业审查和最终导出；--response 直接生成可粘贴的成品文件，--response-mode prompt-only 只出代码块不带交付行
  extract_frames.sh          抽帧 + 切镜检测 + 拼图
  log_lesson.py              追加经验条目（--topic 必须是 `分类/主题`，脚本强制）
  merge_lessons.py           合并另一份经验库里的新条目（按 L 编号，不覆盖已有条目；来源缺分类前缀拒绝合并）
  lint_lessons.py            经验库体检：分类前缀合法 + L 编号连续（回归测试里有一项调用）
  lint_cases.py              案例库体检：可复用点必须带 `→ L0xx` 或标（样板）、引用的编号真的存在、索引与条目对得上（回归测试里有一项调用）
  review_lessons.py          「整理经验」：列出可升级 / 可合并 / 可能冲突的经验候选清单，只读不改
hooks/
  stop_gate.py               Stop 钩子（Claude Code 与 Codex 通用）：三层判定——本轮报告（verify 或 check_prompt --report）对得上就放行；没报告的完整稿由钩子代跑 check_prompt，有错拦下、无错放行并提示"作者未自己跑检查"；局部镜头与操作命令没报告则拦下
  README.md                  两个宿主的装法、能拦什么、真实宿主验证清单
tests/cases.md               端到端用例
tests/run_check_tests.py     check_prompt 回归 + 经验库前缀强制 + 案例库体检（115 项）
tests/test_delivery_gate.py  verify_delivery 放行行为回归（42 项）
tests/test_stop_gate.py      stop_gate 判定回归（59 项）
```

## hooks/（可选）

可选宿主钩子另见 `hooks/README.md`；本体流程与验收不依赖钩子。

## 反馈闭环

每次成片回传 → 抽帧 → 逐句兑现表 → 归因 → 修法 → 一条新观察 → 授权后 `log_lesson.py` 写入经验库（置信度只有两档：已试 / 未试）→ 词库理解度调整。经验采用统一按 `references/lessons/README.md`：没试过的照常可用，但说话时要说明是没试过的写法；已试也不等于一定成功。

## 质量交付

交付分两档（见 SKILL.md「流程分级」）：默认的**轻量路径**适用于绝大多数情况——新稿、改稿、成片反馈后的修改、操作命令，六域与落点核对在头脑里做完，跑一次 `scripts/check_prompt.py`，无错误、警告已裁定就交付，代码块外带一行机械检查结果，不产生放行报告。**全套路径**只在你说"严格审"、或事先约定了审核节点时启用（复杂稿和第一版都不自动触发，默认同样走轻量路径）：按 `references/review/quality-gate.md` 完成原始需求、六域专业审查、警告裁定与本版绑定，最多派一次新上下文的独立复核，并由 `scripts/verify_delivery.py` 放行。提示词正文及生成回执原样取自 response 文件。允许在代码块外写必要表头、问题、例外和变更摘要；这些说明不得混入可复制提示词。用户只要提示词时省略外部说明，内部检查不变。用户只要提示词时用 `--response-mode prompt-only`，成品只有代码块。检查器未执行、执行失败、版本不符、专业问题未解决、必要独立复核未完成时，不标成已验收成稿。机械检查通过不单独等于可交付。新稿也可用 --lock；全套路径里那一次独立复核必须在新上下文做（Claude Code 用 Agent 子代理，Codex 开新会话），且最多一次，复核后的修复由作者自查、重跑放行，不派第二轮。

## 当前用户偏好

新设计默认每镜有可见摄影运动，缓推或慢横移也须有真实幅度与画面变化；固定只有两种来源：你明确要求、既有摄影的保护范围。作者自己觉得该固定时不能自作主张，会说明理由、在表头"待你定"行问你一句；你明确同意之前，这一版照常交付可见运动方案，也不会为等这句话停住成稿。普通产品、对白或微距题材本身不自动触发固定建议。动作密度方面，平均每拍 0.5 秒是你实测出来的线索、不是保证：模型多会以加速方式完成密动作，可能牺牲可读性甚至漏动作，所以需要看清的动作仍然单独给时间。多音字允许在实际发音文本中同音同调替换，保留原台词与逐字映射。专业方法按当前任务适配度选择，不按"未试"标签禁用。上述偏好与逐镜摄影、发音映射的执行接口以 SKILL.md 和 references/review/quality-gate.md 为准。


## 同步与安装（GitHub 单一来源）

仓库 `https://github.com/Wanrd0Geri/aigc-video`（公开）是唯一来源；本机工作副本在 `~/Documents/Codex/aigc-video`，Claude Code 与 Codex 的 `skills/aigc-video` 都是指向它的软链，所以两边看到的永远是同一份文件，记进经验库的条目也立刻共享。

- 改完文件或写入经验后：`bash scripts/sync.sh 一句备注`（提交 → 拉取 → 推送）。需要代理的机器把代理地址写进 `~/.aigc-video-proxy`。
- 组员：直接克隆即可使用，不用登录；要往仓库推改动需要仓库所有者加为协作者，否则用 fork + Pull Request。
- 换机器：`git clone https://github.com/Wanrd0Geri/aigc-video ~/Documents/Codex/aigc-video && bash ~/Documents/Codex/aigc-video/install.sh`，再按 `hooks/README.md` 挂钩子。
- 不要在 skills 目录里另放一份拷贝，也不要 `git clone` 覆盖软链；拉取用 `git pull`。

**维护者改 skill 的地方**：改动在 `~/Documents/Codex/aigc-video-dev`（dev 分支的工作区）里做，三套测试跑过之后再合并到 main，然后在 `~/Documents/Codex/aigc-video` 跑 `bash scripts/sync.sh 备注`。main 是安装位（两个宿主的 skills 都软链到它），改到一半的文件不会影响正在使用的会话。
