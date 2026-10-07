# aigc-video — 即梦 Seedance 2.5 提示词导演 skill

把想法翻译成 Seedance 2.5 听得懂的可见画面，在锁定项之外主动提升观感，多镜新稿先给一张能改的镜头表、确认后再成文，并把成片反馈整理成可写入经验库的观察。Claude Code 与 Codex 通用（只依赖 SKILL.md、python3 标准库、ffmpeg）。

当前为 v44（v44 按 2026-10-06 成片实测补证据、收窄绝对说法，打斗卡新增「节奏点」，见 CHANGELOG；v43 运镜由观看理由决定：说得出这镜为什么要动才写可见运镜，说不出就固定机位、不必申请；v42 默认做法与作者工作习惯对齐；v41、v40 见 CHANGELOG）：写法规则按证据压成正文的决策表 17 行（D01–D17）和建议行 10 行，v38 之前第零组到第十组的原文整份搬进附录 `references/writing-rules-annex.md`，编号不变，别处引用写「决策 Dxx」「附录第 N 条」；写稿前先过 SKILL.md 顶部的写前七问和原理页 `references/principles.md`，再按三张模式卡（多人对话、单主体动作与生物、白模或运镜参考）写；检查报告多存反模式命中、裁定、模式与提醒类别，用户评价成片后 `log_outcome.py` 记一行结果，「整理经验」先跑 `rule_stats.py` 看每条规则赚没赚到。v37 的反模式表 `references/antipatterns.md` 与三个降噪开关（`--mode 白模`、`--rewrite-authorized`、`--adjudicated`），v28 的「压缩审校」（三问删复述、常识、虚词；切线、方位、秒数、关键事件、情绪方向句等承重内容不碰）与「松紧旋钮」（默认 / 更放 / 更控）、复读 / 虚词 / 密度三条提示（密度参考线默认 200 字/秒，待 A/B 实测），v27 词库 11 张 989 条与拔高机制、v26 去处表、v25 全库审查定案全部保留，见 CHANGELOG。

## 安装

从 GitHub 克隆后运行 `install.sh` 建软链，见下文「同步与安装」。

安装位置：
- Codex：`~/.codex/skills/aigc-video/`
- Claude Code：`~/.claude/skills/aigc-video/`

抽帧需要 ffmpeg：`brew install ffmpeg`。

## 用法

- 写新提示词：说清人物、场景、动作、时长、素材（按上传顺序说明每张图 / 视频 / 音频是什么）。多镜新稿会先收到一张能改的镜头表，确认后再得到可粘贴进即梦的提示词代码块和下方一行质量放行结果；单镜稿或说"直接出"时一轮出成品。
- 改现有提示词 / 操作命令：贴原稿，说要改什么；延长、编辑、衔接、白模、宫格等直接说任务。改稿只动引出问题的那一句或那一段，不重写整段；检查时带上父稿（`--baseline`），父稿有、新稿没有的句子会被列出来提醒，新稿比父稿长 15% 以上只提醒检查必要信息与重复，不强制删减。用户认可的成功项绑定原话和版本，未经针对该项的授权不删弱；授权范围内可等义合并，逐字锁不变。
- 多轮任务：第二版起维护 asks.txt，交付前用 --asks 核对全部历史要求；格式、更新与撤回规则见 references/review/revise-rules.md 第 12 节。
- 输入「自检」：对最近一份提示词做质检，只出报告不改稿：一句结论 + 只列有问题的项（镜号｜项及来源｜缺口｜影响｜建议，用户质检表的项标 `表#N`）+ 人核提醒（意图复述、素材读没读到与矛盾、固定提醒）+ 脚本检查行。
- 输入「整理经验」：先看一份规则统计（每条反模式报了几次、裁了几次、在采用和不行的成片里各出现几次，每类提醒的裁定率），再跑一遍经验库体检，得到一份候选清单（哪几条被案例反复引用、哪几条像是能合并、哪几条互相修正、哪个分类太胖、哪几条已升级为规则或已撤回推荐），每条一句人话，你挑要升级成规则、合并还是保留；不点头不动库。
- 回传视频或截图 + 你的评价：得到逐句兑现表、归因、最小修法和一条待审观察；你说"写入经验库"才写进 `references/lessons/seedance-2.5.md`；你明确评价某版成片效果好时，按长期授权自动记一条成功观察。你对成片的评价（采用 / 部分 / 否）另记一行成片结果，给规则统计用。
- 问"这个效果叫什么 / 怎么写"：查词库直答；说“拔高 / 更细 / 更小众”：从词库给 3–5 个候选（效果名 + 画面上看到什么 + 题材），选定后成文。

## 结构

```
SKILL.md                     入口：写前七问、关键底线、用户偏好、任务路由、字段深度、轻量/全套触发与交付条件
references/
  seedance-format.md         四段格式、素材引用、时间戳、声音、禁止项、硬限制、表头/镜头表/公开交付
  seedance-operations.md     延长、编辑、首尾帧、关键帧、宫格、白模、绿幕、衔接、成片
  writing-rules.md           正文：成文主规则 8 条、五道门、决策表 17 行（D01–D17：两条以上证据、官方或用户口径，照做）、建议行 10 行（单条证据）、去处表
  writing-rules-annex.md     附录：v38 之前第零组到第十组 78 条细则与例句，重复规则指向唯一维护处、编号不变；别处写「附录第 N 条」、正文写「第 N 条」都指这里
  modes/                     三张模式卡：多人对话、单主体动作与生物、白模或运镜参考；写新稿先选卡，卡里写必写 / 可省 / 禁写 / 检查参数 / 读哪几组细则
  principles.md              原理页：八条原理，写新稿和自检前先过一眼；每条一句原理、一句为什么、指向经验编号、决策行与反模式行
  antipatterns.md            反模式表：已知失效写法的唯一清单（触发正则、为什么、证据等级、改成），check_prompt 直接读它出提醒
  cases/                     官方案例库 + 我的成功案例（只给组织方式与句式样板；只读索引，my-cases 取一条、official-cases 取 1–2 条，知识在经验库）
  craft/                     10 张工艺卡：镜头、光影、表演、站位、运动物理、打斗、特效、场景氛围、题材配方、导演提案
  lexicon/                   11 张词库（989 条）：运镜与运镜组合、动作与打斗、运动、光线材质、表演、四张特效表（消散显形转化 / 能量光效 / 粒子液体火烟雾 / 变形残影空间时间）；读表按小类 grep，条目带题材标签、已试 / 未试；`lint_lexicon.py` 体检
  review/                    自检展示、成片诊断、改稿规则；quality-gate 唯一维护严格审九步与证据接口
  lessons/                   经验库（写前按题材 grep 分类；诊断后给一条观察，写入需要授权，成功评价自动记录）
scripts/
  check_prompt.py            格式、素材、时码、锁定与启发式提醒；参数见 --help，规则见正文/附录与 antipatterns，报告供钩子与统计使用
  verify_delivery.py         实际重跑检查，核对需求、专业审查和最终导出；--response 直接生成可粘贴的成品文件，--response-mode prompt-only 只出代码块不带交付行
  extract_frames.py          抽帧 + 切镜检测 + 拼图（macOS / Windows 通用；extract_frames.sh 只是转调它的薄封装）
  log_lesson.py              追加经验条目（--topic 必须是 `分类/主题`，脚本强制）
  log_outcome.py             用户评价成片后记一行结果：按交付检查行的 sha 找报告，往报告目录的 outcomes.jsonl 追加评价、成片、触发与裁定的反模式编号、模式
  merge_lessons.py           合并另一份经验库里的新条目（按 L 编号，不覆盖已有条目；来源缺分类前缀拒绝合并）
  lint_lessons.py            经验库体检：分类前缀合法 + L 编号连续（回归测试里有一项调用）
  lint_cases.py              案例库体检：可复用点必须带 `→ L0xx` 或标（样板）、引用的编号真的存在、索引与条目对得上（回归测试里有一项调用）
  rule_stats.py              「整理经验」先跑：每条反模式的触发、被裁定、在采用 / 部分 / 否成片里的次数，每类提醒的裁定率，最近 30 天有成片结果的占比；只读不改
  review_lessons.py          「整理经验」：列出可升级 / 可合并 / 可能冲突的经验候选、各分类条目数和已升级 / 已撤回推荐的条目，只读不改
hooks/
  stop_gate.py               Stop 钩子（Claude Code 与 Codex 通用）；三层判定与能拦什么见 hooks/README.md
  README.md                  两个宿主的装法、能拦什么、真实宿主验证清单
tests/cases.md               端到端用例
tests/run_check_tests.py     check_prompt 回归 + 经验库前缀强制 + 案例库体检 + 词库体检 + 度量回路（报告新字段、log_outcome、rule_stats）（819 项）
tests/test_revision_checks.py 修订格式、旧稿兼容与丢句匹配回归（18 项）
tests/test_delivery_gate.py  verify_delivery 放行行为回归（69 项）
tests/test_stop_gate.py      stop_gate 判定回归（71 项）
tests/test_lesson_scripts.py 经验库脚本行为回归：归档与证据状态、写入加锁与补充、合并退出码、编号扩位（9 项）
tests/test_rule_stats.py     成片旧记录的同目录回退与跨项目路径隔离（2 项）
```

## hooks/（可选）

可选宿主钩子另见 `hooks/README.md`；本体流程与验收不依赖钩子。

## 反馈闭环

每次成片回传 → 抽帧 → 逐句兑现表 → 归因 → 修法 → 一条结论（新观察 / 补充已有条目 / 反向证据 / 本次无新增）→ 授权后 `log_lesson.py` 写入或补充经验库（置信度只有两档：已试 / 未试）；你的评价另用 `log_outcome.py` 记一行成片结果→ 词库理解度调整。经验采用统一按 `references/lessons/README.md`：没试过的照常可用，但说话时要说明是没试过的写法；已试也不等于一定成功。

## 质量交付

交付分轻量与全套两档，触发条件只见 SKILL.md「流程分级」，全套细节只见 references/review/quality-gate.md。分别由 check_prompt 与 verify_delivery 记录真实检查结果；代码块、prompt-only 与检查行见 seedance-format 第 9 节。机械检查不证明成片效果。

## 当前用户偏好

偏好与改稿保护以 SKILL.md「用户偏好与改稿保护」为准。动作容量见 writing-rules 决策 D17；严格审的摄影与发音记录见 quality-gate。

## 同步与安装（GitHub 单一来源）

仓库 `https://github.com/Wanrd0Geri/aigc-video`（公开）是唯一来源；本机工作副本在 `~/Documents/Codex/aigc-video`，Claude Code 与 Codex 的 `skills/aigc-video` 都是指向它的软链，所以两边看到的永远是同一份文件，记进经验库的条目也立刻共享。

- 改完文件或写入经验后：`bash scripts/sync.sh 一句备注`（提交 → 拉取 → 推送）。需要代理的机器把代理地址写进 `~/.aigc-video-proxy`。
- 只想拿更新、不推本机改动：`bash scripts/sync.sh --pull`。
- 组员：直接克隆即可使用，不用登录；要往仓库推改动需要仓库所有者加为协作者，否则用 fork + Pull Request。
- 换机器：`git clone https://github.com/Wanrd0Geri/aigc-video ~/Documents/Codex/aigc-video && bash ~/Documents/Codex/aigc-video/install.sh`，再按 `hooks/README.md` 挂钩子。
- 不要在 skills 目录里另放一份拷贝，也不要 `git clone` 覆盖软链；拉取用 `bash scripts/sync.sh --pull`（或 `git pull`）。

**维护者改 skill 的地方**：改动在 `~/Documents/Codex/aigc-video-dev`（dev 分支的工作区）里做，五套测试跑过之后再合并到 main，然后在 `~/Documents/Codex/aigc-video` 跑 `bash scripts/sync.sh 备注`。main 是安装位（两个宿主的 skills 都软链到它），改到一半的文件不会影响正在使用的会话。
