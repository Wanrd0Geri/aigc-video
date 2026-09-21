#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_prompt.py — Seedance 2.5 提示词文本检查（只查文本，不改稿，不验证画面语义）。

用法：
  python3 check_prompt.py --prompt 稿.txt [--task 生成|编辑|延长|衔接] [--total 秒] [--untimed] [--labels 图1,图2,视频1]
                          [--baseline 父稿.txt] [--format 四段|五段|六段|继承] [--partial] [--lock "台词"]... [--unchanged 1,3]
                          [--save-checked 合成稿.txt] [--report 报告.json]

两个维度分开表示：
  --task      最终命令的性质：生成（默认）/ 编辑 / 延长 / 衔接。决定时码规则和必填词。
  --baseline  给了父稿就是修订：默认 --format 继承（父稿有什么标题、什么顺序，新稿必须一样），
              并检查 --lock 锁定文字逐字保留、--unchanged 镜头逐字未改。
  --format    新稿默认 四段（主体 / 场景 / 风格 / 情节），不设概述段、也不设结尾标题：固定句
              “全片不添加BGM，不添加字幕。”是整份提示词的最后一行，而且末尾只有它这一行——
              它前面一行必须是普通正文（镜头内容或命令句），不能再有否定句、约束句、“保持…”句。
              五段（…… / 结尾）和六段（…… / 概述 / …… / 结尾）只留给旧稿显式检查；有 --baseline 时默认 继承。
  （旧写法 --task 修订 仍接受：按父稿的命令区——六段父稿看概述段，四段与五段父稿看情节段开头——判断它是生成 / 编辑 / 延长 / 衔接。）

--partial：稿只含被改的镜头。要求：只有镜头块，没有固定句和末尾收尾行；镜号不重复且都在父稿里；时码区间与父稿一致；
  不在 --unchanged 里。脚本把它放回父稿合成完整稿再检查，JSON 里 input_sha256 / baseline_sha256 / checked_sha256 分开给，
  --save-checked 可以把实际检查的合成稿存下来。

四段稿的收尾（v13.1）：末尾只有固定句一行，它上面不再另设收尾区域。倒数第二行匹配
  `^不|^禁止|^无|^保持|^全片|^要求延长自然` 就报错——必要的否定句写进相应镜头的正文，操作命令的必填句写进
  情节段开头的命令区（`情节：` 之后、第一个镜头标题之前）。五段 / 六段旧稿仍按 `结尾：` 段，继承模式按父稿。

固定检查：镜号从 1 连续不重复；时码不留空隙不重叠；固定句逐字恰好一次、不拆开、结束整份提示词——四段新稿用
  “全片不添加BGM，不添加字幕。”，五段 / 六段旧稿用旧句“不添加字幕，不添加背景音乐。”，继承模式按父稿用的那一句；
  新稿四段标题各恰好一次且顺序对（或显式检查旧五段 / 六段、继承父稿标题）；
  无文件名（含紧邻中文）、路径、UUID；引用性措辞（不扫台词与锁定文字）；内部术语与修改标记；
  操作类必填词与官方必填句——四段稿全部在情节段开头的命令区，六段旧稿在概述段与结尾段，五段旧稿按父稿，
  继承模式命令区与结尾段都接受。
素材引用：`@图片N`、`图片N`、`图N`、`@视频N`、`视频N`、`@音频N`、`音频N` 一律归一成键 `图N` / `视频N` / `音频N`
  （`--labels` 写 `图1` 或 `图片1` 都行，同样归一）；声明集合、首次出现位置、操作命令必填词都按归一后的键核对。
  **提示词里不写 @**（软件里粘贴后再 @ 出来）：四段新稿出现 @ 引用时提醒一次；继承模式按父稿（父稿用 @ 就不提醒）。
启发式扫描（空词、静止、景别、焦点落点、弱运镜措辞、动作密度、素材重复绑定、跨段重复长句、风格段里的时序与运镜）只给警告。动作密度：节拍数用时序词粗估，平均 ≤0.5 秒（每秒 2 拍以上）提醒；
用户实测（L064）模型多会加速完成密动作，但这是经验线索不是通过保证，仍要按动作依赖与可读性判断。
否定句：四段稿默认预算 0 条自写否定（固定句不计）。全文（固定句与引号内台词除外）里句首是
  `不出现|不添加|不得|不要|不能|不许|不可|禁止|避免` 的句子逐句给**提醒**（不是错误）；用 --negative-exception 逐句点名的不再提醒。
  “没有”“无”不当否定句抓。五段 / 六段 / 继承旧稿仍用结尾段预算：用户逐字锁不计入，新稿超过 4 条报错，
  除非 --negative-exception 逐句点名超出的必要否定（每句与结尾段里一条独立否定条款整句一致，重复声明和片段不计数）；
  修订与操作命令给警告，须由最终专业审查裁定。

--report：把这次机械检查的结果另存一份 JSON（`kind: "light"`，目录不存在会自动建），给 hooks/stop_gate.py 的守门用。
  报告里 delivered_sha256 = 实际交付出去的那段正文的哈希（非 --partial 时与 checked_sha256 相同），
  checked_sha256 = 实际检查的完整稿哈希（--partial 时是放回父稿合成后的稿）；两者都按"按行拆分再用换行拼回"规范化，
  与钩子对同一段正文算出的哈希一致。有错误时照样写报告（ready=false），退出码不变。
  created_at 是本次运行时间、session_id 取环境变量 AIGC_SESSION_ID（没设为 null），钩子用它们做本轮绑定。
  典型用法：--report ~/.aigc-video-gate/<时间戳>.json，每次检查用一个新路径。

退出码 0 = 无错误，1 = 有错误，2 = 参数错误。summary 一行可直接贴到交付里；它带 delivered_sha256 前 8 位
（非 --partial 时即 checked_sha256 前 8 位），必须来自真实运行结果，可与报告、工具日志和正文核对；哈希不是执行签名或质量证明。
脚本只报告机械结果；最终交付还须运行 verify_delivery.py 核对专业审查及警告裁定。
"""
import argparse, hashlib, json, os, re, sys, time
from pathlib import Path

CJK_NUM = "零一二三四五六七八九十百"
HEAD_PATTERNS = {
    "镜头N（a-b秒）：": re.compile(r"^\s*镜头\s*(\d+)\s*[（(]\s*(\d+(?:\.\d+)?)\s*(?:s|秒)?\s*[-–—~到]\s*(\d+(?:\.\d+)?)\s*(?:s|秒)?\s*[)）]\s*[:：]"),
    "镜头N：": re.compile(r"^\s*镜头\s*(\d+)\s*[:：]"),
    "a-bs：": re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:s|秒)?\s*[-–—~到]\s*(\d+(?:\.\d+)?)\s*(?:s|秒)\s*[:：]"),
    "【阶段N】": re.compile(r"^\s*【阶段([" + CJK_NUM + r"\d]+)】"),
    "第N阶段：a-b秒": re.compile(r"^\s*第([" + CJK_NUM + r"\d]+)阶段\s*[:：]?\s*(\d+(?:\.\d+)?)\s*[-–—~到]\s*(\d+(?:\.\d+)?)\s*秒"),
}
FOUR_SECTION_LABELS = ["主体", "场景", "风格", "情节"]
FIVE_SECTION_LABELS = ["主体", "场景", "风格", "情节", "结尾"]
SIX_SECTION_LABELS = ["主体", "概述", "场景", "风格", "情节", "结尾"]
SECTION_LABELS = SIX_SECTION_LABELS  # 识别用全集（含旧六段的概述与旧壳的结尾）
FORMAT_LABELS = {"四段": FOUR_SECTION_LABELS, "五段": FIVE_SECTION_LABELS, "六段": SIX_SECTION_LABELS}
KNOWN_HEADER = re.compile(r"^\s*(主体|概述|场景|风格|情节|结尾)\s*[：:]")
BARE_HEADER = re.compile(r"^\s*([^\s：:（(【]{1,8})\s*[：:]\s*$")
LABEL_RE = re.compile(r"(@?)(图片|视频|音频|图)\s?(\d+)")
LABEL_FULL_RE = re.compile(r"^@?(图片|视频|音频|图)\s?(\d+)$")
ASSET_KIND = {"图片": "图", "图": "图", "视频": "视频", "音频": "音频"}
# 素材绑定动词：一句里同时出现素材与这些词，就算这一段"写了这份素材的职责"。
# 情节里的纯指代（没有绑定动词）不算。词表可调。
BIND_VERBS = ["用于", "定义", "采用", "参考", "只负责", "负责", "提供", "作为"]
# 风格段只写画面质感与镜头性格（画风与渲染、材质与表面、光的质感与层次、焦段景深手持还是稳定）。
# 下面两组词出现在风格段就提醒：时序属于镜内，具体运镜路径与动作也属于镜内。两组词表可调。
STYLE_SEQUENCE_WORDS = ["先", "随即", "接着", "然后", "紧接着", "最后", "开场", "收尾时", "第一秒", "之后"]
STYLE_MOVE_WORDS = ["推近", "推进", "后拉", "拉远", "横移", "环绕", "升降", "跟随", "俯冲", "甩",
                    "横扫", "扑向", "蹬", "抓", "砸", "扑下", "后退下降"]
# 镜头性格词不算运镜路径（手持、跟拍感、浅景深）；这些片段扫描前先挖掉，免得"优先"里的"先"之类误报。
STYLE_SAFE_WORDS = ["优先", "手持", "跟拍感", "跟拍", "浅景深", "大景深", "焦段"]
PUNCT_RE = re.compile(r"[\W_]+", re.U)          # 去掉标点与空白，只留字与数字，用于跨段重复长句的比对
EXT = r"(png|jpe?g|webp|heic|gif|mp4|mov|m4v|webm|avi|mkv|wav|mp3|m4a|flac|aac|ogg)"
LEAK_RES = [
    (re.compile(r"(?<![A-Za-z0-9])[\w\-一-鿿]+\." + EXT + r"(?![A-Za-z0-9])", re.I), "文件名泄露"),
    (re.compile(r"(/Users/|/home/|/tmp/|/var/|/private/|[A-Za-z]:\\)"), "路径泄露"),
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I), "UUID 泄露"),
    (re.compile(r"@(?!图片|视频|音频|图)\S+"), "非法 @ 引用（新稿不写 @，写 图N/视频N/音频N；旧稿的 @图片N/@视频N/@音频N 仍合法）"),
]
REF_ERR = ["同上一镜", "承接上一镜", "继续刚才", "如上", "上一镜", "上一个镜头", "上一版", "上次", "上一次", "上一轮", "像上次", "之前那样", "这次改", "这一版", "不要像"]
REF_WARN = ["刚才", "再次"]
INTERNAL = ["可见清单", "锁定项", "执行回执", "FightBeat", "接触台账", "L1 ", "L2 ", "L3 ", "理解度", "导演提案", "【本轮修改】", "【联动修改】", "已完成内部全量校验"]
EMPTY_WORDS = ["高级感", "氛围拉满", "史诗感", "震撼", "美丽", "灵动"]
OFFSCREEN_RE = re.compile(r"画外[^，。；\n]{0,8}正在")
MOTION_WORDS = ["飘", "晃", "摇", "流", "滴", "落", "升", "飞", "滚", "掠", "扫", "涟漪", "风", "雨", "雾", "烟", "尘", "火", "光斑", "闪", "跳", "颤", "摆", "抖", "吹", "涌", "散", "燃", "波", "呼吸", "眨", "滑", "翻", "卷", "溅", "拂", "漾", "抽", "推", "退", "冲", "转", "起伏", "凝结", "飘落", "闪烁", "进入", "入画", "出画", "走", "跑", "奔", "移动", "经过", "靠近", "逼近", "后退", "起身", "坐下", "抬", "垂"]
QUALITY_ONLY = re.compile(r"(8K|4K|高清|精美|电影感|高级感|电影级|超清)")
# 固定句：四段新稿用新句，五段 / 六段旧稿用旧句，继承模式按父稿用的那一句。匹配容忍 BGM 前后的空格与末尾句号。
CLOSING_NEW = "全片不添加BGM，不添加字幕"
CLOSING_OLD = "不添加字幕，不添加背景音乐"
CLOSING_NEW_RE = re.compile(r"全片\s*不添加\s*BGM\s*，\s*不添加字幕")
CLOSING_OLD_RE = re.compile(r"不添加字幕，不添加背景音乐")
CLOSING_SPEC = {
    "new": (CLOSING_NEW, CLOSING_NEW_RE, [re.compile(r"不添加\s*BGM"), re.compile(r"不添加字幕")]),
    "old": (CLOSING_OLD, CLOSING_OLD_RE, [re.compile(r"不添加字幕"), re.compile(r"不添加背景音乐")]),
}
CLOSING_ANY_RE = re.compile(r"不添加字幕|不添加背景音乐|不添加\s*BGM")
EXTEND_REQUIRED = ["延长自然", "动作衔接流畅", "禁止生硬切镜", "禁止物体凭空出现"]
EXTEND_CONSTRAINT = "要求延长自然、动作衔接流畅，禁止生硬切镜、禁止物体凭空出现"
# 收尾行：否定句、约束句、"保持…"句、固定句。四段稿里固定句上面一行不许是这种行；旧壳稿用它从正文末尾连续向上取结尾段。
TAIL_ZONE_LINE = re.compile(r"^\s*(?:不|禁止|无|保持|全片)|^\s*要求延长自然")
# 四段稿逐句提醒用：句首的否定词。"没有""无"不抓（误报太多）。
NEG_SENT_RE = re.compile(r"^(不出现|不添加|不得|不要|不能|不许|不可|禁止|避免)")
DIALOGUE_RE = re.compile(r"“[^”]*”|\"[^\"\n]*\"|「[^」]*」|『[^』]*』|\{[^}]*\}")
CJK_MAP = {c: i for i, c in enumerate("零一二三四五六七八九")}


def cjk_to_int(s):
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if "十" in s:
        a, b = s.split("十", 1)
        return (CJK_MAP.get(a, 1) if a else 1) * 10 + (CJK_MAP.get(b, 0) if b else 0)
    return CJK_MAP.get(s, 0)


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def asset_key(kind, num):
    """把 @图片N / 图片N / 图N / @视频N / 视频N / @音频N / 音频N 统一成 图N / 视频N / 音频N。"""
    return f"{ASSET_KIND.get(kind, kind)}{int(num)}"


def asset_keys(text):
    """文本里用到的素材键集合（已归一）。"""
    return {asset_key(m.group(2), m.group(3)) for m in LABEL_RE.finditer(text)}


def norm_label(raw):
    """--labels 里的一项：`图片1` 与 `图1`（带不带 @ 都行）归一成同一个键；认不出就原样返回。"""
    m = LABEL_FULL_RE.match(raw.strip())
    return asset_key(m.group(1), m.group(2)) if m else raw.strip()


def split_sections(text):
    """{段落名: 段落正文}；只取四段 / 五段 / 六段那几个已知标题，取不到的段不出现。"""
    out = {}
    for lab in SECTION_LABELS:
        m = re.search(lab + r"[：:](.*?)(?=\n(?:主体|概述|场景|风格|情节|结尾)[：:]|$)", text, re.S)
        if m:
            out[lab] = m.group(1)
    return out


def clauses_of(body):
    """按句号、分号、逗号切成子句，返回 [(原文, 去掉标点与空白后的形态)]。"""
    out = []
    for raw in re.split(r"[，,。.；;：:！!？?、\n]", body):
        s = raw.strip()
        if s:
            out.append((s, PUNCT_RE.sub("", s)))
    return out


def parse_heads(lines):
    heads = []
    for i, ln in enumerate(lines):
        for style, rx in HEAD_PATTERNS.items():
            m = rx.match(ln)
            if not m:
                continue
            sid = s = e = None
            if style == "镜头N（a-b秒）：":
                sid, s, e = int(m.group(1)), float(m.group(2)), float(m.group(3))
            elif style == "镜头N：":
                sid = int(m.group(1))
            elif style == "a-bs：":
                s, e = float(m.group(1)), float(m.group(2))
            elif style == "【阶段N】":
                sid = cjk_to_int(m.group(1))
            elif style == "第N阶段：a-b秒":
                sid, s, e = cjk_to_int(m.group(1)), float(m.group(2)), float(m.group(3))
            heads.append((i, style, sid, s, e))
            break
    return heads


def is_tail_line(ln):
    return bool(re.match(r"^\s*结尾\s*[：:]", ln)) or bool(CLOSING_ANY_RE.search(ln))


def tail_zone_bounds(lines):
    """旧壳口径的结尾段位置：正文末尾连续的否定 / 约束行（最后一行应当是固定句）。
    四段新稿（v13.1）末尾只有固定句，不走这里。返回左闭右开区间 (start, end)；没有时 start == end。"""
    end = len(lines)
    while end > 0 and not lines[end - 1].strip():
        end -= 1
    start = end
    while start > 0 and (not lines[start - 1].strip() or TAIL_ZONE_LINE.search(lines[start - 1])):
        start -= 1
    while start < end and not lines[start].strip():
        start += 1
    return start, end


def shot_blocks(lines, heads, tail_start=None):
    """[(head, body_lines, tail_lines)]；最后一块在 结尾：、固定句或旧壳结尾段第一行切开，切开后的部分是全局尾部。"""
    if tail_start is None:
        tail_start = tail_zone_bounds(lines)[0]
    blocks = []
    for k, h in enumerate(heads):
        start = h[0]
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        body = lines[start:end]
        cut = len(body)
        for j, ln in enumerate(body):
            if j > 0 and (is_tail_line(ln) or start + j >= tail_start):
                cut = j
                break
        blocks.append((h, body[:cut], body[cut:]))
    return blocks


def headers_of(lines, heads):
    head_idx = {h[0] for h in heads}
    out = []
    for i, ln in enumerate(lines):
        if i in head_idx:
            continue
        m = KNOWN_HEADER.match(ln) or BARE_HEADER.match(ln)
        if m:
            out.append(m.group(1))
    return out


def norm_lock(s):
    return s.replace("\r", "").replace("\n", "")


def norm_shot(lines):
    return "\n".join(ln.rstrip() for ln in lines if ln.strip())


def strip_dialogue(text):
    return DIALOGUE_RE.sub("“”", text)


def negative_sentences(text, closing_re, locks):
    """四段口径：全文里句首是否定词的句子，逐句列出（固定句、引号内台词、用户逐字锁不算）。"""
    t = strip_dialogue(text)
    for lk in sorted(locks, key=len, reverse=True):
        t = t.replace(lk, "")
    t = closing_re.sub("", t)
    out = []
    for raw in re.split(r"[。！？!?；;\n]", t):
        s = raw.strip()
        if s and NEG_SENT_RE.match(s):
            out.append(s)
    return out


def operation_text(text):
    """命令区：六段旧稿取概述段；四段新稿与五段旧稿取情节段开头到第一个镜头 / 阶段标题之前。"""
    m = re.search(r"概述[：:](.*?)(?=\n(?:主体|场景|风格|情节|结尾)[：:]|\Z)", text, re.S)
    if m:
        return m.group(1)
    m = re.search(r"情节[：:](.*?)(?=\n\s*(?:镜头\s*\d+|【阶段|第[" + CJK_NUM + r"\d]+阶段)|\n(?:主体|场景|风格|结尾)[：:]|\Z)", text, re.S)
    if m:
        return m.group(1)
    # 兼容继承的无标题操作稿：只看第一个镜头 / 阶段之前的命令区，不让镜内叙事误判任务类型。
    prefix = []
    for line in text.splitlines():
        if any(rx.match(line) for rx in HEAD_PATTERNS.values()):
            break
        prefix.append(line)
    return "\n".join(prefix)


def infer_task(baseline_text):
    ov = operation_text(baseline_text)
    if any(w in ov for w in ["向后延长", "向前延长", "续写"]) or re.search(r"延续@?视频\s?\d", ov):
        return "延长"
    if re.search(r"(?:编辑|删除|去掉|移除)@?视频\s?\d|替换", ov):
        return "编辑"
    if "无缝衔接" in ov or "衔接起来" in ov:
        return "衔接"
    return "生成"


def synthesize(baseline_lines, cand_lines, errors, unchanged_ids):
    """校验局部替换段，再放回父稿。返回合成后的行列表。"""
    b_heads = parse_heads(baseline_lines)
    c_heads = parse_heads(cand_lines)
    if not c_heads:
        errors.append("局部替换段里没有找到镜头标题")
        return baseline_lines
    pre = "".join(cand_lines[:c_heads[0][0]]).strip()
    if pre:
        errors.append(f"局部替换段开头有无法归属的文字，不能静默丢弃：{pre[:40]}")
    c_ids = [h[2] for h in c_heads]
    if any(i is None for i in c_ids):
        errors.append("局部替换段的镜头标题没有镜号，无法定位到父稿")
        return baseline_lines
    dup = sorted({i for i in c_ids if c_ids.count(i) > 1})
    if dup:
        errors.append(f"局部替换段里镜号重复：{dup}")
    c_blocks = shot_blocks(cand_lines, c_heads)
    for h, _body, tail in c_blocks:
        if "".join(tail).strip():
            errors.append(f"局部镜头 {h[2]} 后有固定句或收尾行，不能丢弃；收尾有改动请交付全稿")
    for sid in c_ids:
        if sid in unchanged_ids:
            errors.append(f"镜头 {sid} 被标为未改（--unchanged），局部替换段却改了它")
    b_ids = {h[2]: h for h in b_heads if h[2] is not None}
    b_blocks = shot_blocks(baseline_lines, b_heads)
    repl = {}
    for (h, body, _tail) in c_blocks:
        sid = h[2]
        if sid not in b_ids:
            errors.append(f"局部替换的镜头 {sid} 不在父稿里")
            continue
        bh = b_ids[sid]
        if h[3] is not None and bh[3] is not None and (abs(h[3] - bh[3]) > 1e-6 or abs(h[4] - bh[4]) > 1e-6):
            errors.append(f"镜头 {sid} 的时码 {h[3]}-{h[4]} 与父稿 {bh[3]}-{bh[4]} 不一致；改时码要先改父稿总时长并交付全稿")
        repl[sid] = body
    out = []
    first = b_heads[0][0] if b_heads else len(baseline_lines)
    out.extend(baseline_lines[:first])
    for (h, body, tail) in b_blocks:
        out.extend(repl.get(h[2], body))
        out.extend(tail)
    return out


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--task", default="生成", choices=["生成", "编辑", "延长", "衔接", "修订"])
    ap.add_argument("--format", dest="fmt", default=None, choices=["四段", "五段", "六段", "继承"])
    ap.add_argument("--total", type=float, default=None)
    ap.add_argument("--untimed", action="store_true")
    ap.add_argument("--labels", default="", help="本次素材集合，逗号分开；`图1` 与 `图片1` 两种写法都接受（归一成 图N / 视频N / 音频N 再核对）")
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--lock", action="append", default=[])
    ap.add_argument("--unchanged", default="")
    ap.add_argument("--save-checked", default=None)
    ap.add_argument("--report", default=None, help="把机械检查结果另存为 JSON（kind=light），供 hooks/stop_gate.py 守门核对；有错误也写（ready=false）")
    ap.add_argument("--negative-exception", default="", help="要逐句点名的必要否定句本身，多句用“；”分开。四段稿：点名的镜内否定句不再提醒（其余每句给一条提醒）；五段 / 六段 / 继承旧稿：每句必须与结尾段里一条独立否定条款整句一致，数量要覆盖超出 4 条预算的部分。最终放行仍须审查")
    a = ap.parse_args()

    def bail(msg):
        print(json.dumps({"ok": False, "errors": [msg], "warnings": [], "checked": []}, ensure_ascii=False, indent=2))
        sys.exit(2)
    if a.task == "修订" and not a.baseline:
        bail("--task 修订 必须给 --baseline 父稿（推荐写法：--task 生成|编辑|延长|衔接 加 --baseline）")
    if a.partial and not a.baseline:
        bail("--partial 必须给 --baseline 父稿")
    if a.unchanged and not a.baseline:
        bail("--unchanged 需要 --baseline 父稿；--lock 可单独保护新稿")
    if a.fmt == "继承" and not a.baseline:
        bail("--format 继承 需要 --baseline 父稿")
    if any(not lk.strip() for lk in a.lock):
        bail("--lock 不能是空文字")

    raw = open(a.prompt, encoding="utf-8").read()
    cand_lines = raw.splitlines()
    baseline_text = open(a.baseline, encoding="utf-8").read() if a.baseline else None
    baseline_lines = baseline_text.splitlines() if a.baseline else None
    task = infer_task(baseline_text) if a.task == "修订" else a.task
    revision = a.baseline is not None
    fmt = a.fmt or ("继承" if revision else "四段")
    untimed = a.untimed or task == "衔接"
    unchanged_ids = [int(x) for x in re.findall(r"\d+", a.unchanged)]

    errors, warnings, checked = [], [], []
    if a.task == "修订":
        checked.append(f"--task 修订 已按父稿判断为「{task}」")
    if a.partial:
        lines = synthesize(baseline_lines, cand_lines, errors, unchanged_ids)
        checked.append("局部替换段已校验并放回父稿合成完整稿检查")
    else:
        lines = cand_lines
    text = "\n".join(lines)
    if a.save_checked:
        open(a.save_checked, "w", encoding="utf-8").write(text)
    scan_text = strip_dialogue(text)

    # --- 镜头标题与镜号 ---
    heads = parse_heads(lines)
    styles = {h[1] for h in heads}
    if len(styles) > 1:
        errors.append(f"镜头标题风格不统一：{sorted(styles)}")
    ids = [h[2] for h in heads if h[2] is not None]
    if ids:
        if ids != list(range(1, len(ids) + 1)):
            errors.append(f"镜号必须从 1 连续且不重复，实际：{ids}")
        else:
            checked.append(f"镜号 1-{len(ids)} 连续")
    first_head = heads[0][0] if heads else None
    # 四段稿末尾只有固定句：镜头块只在固定句那一行切开，写在镜内的否定句仍属于那一镜的正文。
    blocks = shot_blocks(lines, heads, len(lines) if fmt == "四段" else None)
    for h, body, _tail in blocks:
        first = re.split(r"[:：]", body[0], maxsplit=1)
        content = (first[1] if len(first) == 2 else "") + "\n" + "\n".join(body[1:])
        if not content.strip():
            errors.append(f"镜头 {h[2]} 缺少正文")

    # --- 时码 ---
    timed = [h for h in heads if h[3] is not None]
    if task == "编辑" and timed:
        checked.append("编辑命令：时码按原视频区间，不检查从 0 开始与总和")
        for h in timed:
            if h[4] <= h[3]:
                errors.append(f"时码区间无效：{h[3]}-{h[4]}")
        for p, n in zip(timed, timed[1:]):
            if n[3] < p[4] - 1e-6:
                errors.append(f"编辑区间重叠：{p[3]}-{p[4]} 与 {n[3]}-{n[4]}")
    elif not untimed:
        if timed:
            if timed[0][3] != 0:
                errors.append(f"时码未从 0 开始：{timed[0][3]}")
            for p, n in zip(timed, timed[1:]):
                if n[3] < p[4] - 1e-6 or n[3] - p[4] > 0.15:
                    errors.append(f"时码不连续或重叠：{p[3]}-{p[4]} 后接 {n[3]}-{n[4]}")
            for h in timed:
                if h[4] <= h[3]:
                    errors.append(f"时码区间无效：{h[3]}-{h[4]}")
            if a.total is not None and abs(timed[-1][4] - a.total) > 0.15:
                errors.append(f"时码总和 {timed[-1][4]} 不等于 --total {a.total}")
            checked.append(f"时码 0-{timed[-1][4]:g} 连续")
        elif a.total is not None:
            warnings.append("给了 --total 但没有找到带时码的镜头标题；时码无法核对")
        elif heads:
            warnings.append("镜头标题没有时码；若这是白模预演或衔接，请加 --untimed 明确")
    else:
        checked.append("无时码模式：不检查时码")

    # --- 外壳 ---
    hdrs = headers_of(lines, heads)
    if fmt in FORMAT_LABELS:
        expected_labels = FORMAT_LABELS[fmt]
        bad = False
        for lab in expected_labels:
            c = hdrs.count(lab)
            if c == 0:
                errors.append(f"缺少段落标题：{lab}："); bad = True
            elif c > 1:
                errors.append(f"段落标题重复：{lab}： 出现 {c} 次"); bad = True
        unexpected = [h for h in hdrs if h in SECTION_LABELS and h not in expected_labels]
        if unexpected:
            hints = []
            if "结尾" in unexpected and fmt == "四段":
                hints.append("新稿不设结尾标题，末尾只有固定句一行；必要的否定句写进相应镜头的正文，操作命令的必填句写进情节段开头的命令区")
            if "概述" in unexpected and fmt in ("四段", "五段"):
                hints.append("新稿不设概述段，总览信息写进情节段开头或删除（时长、风格、镜头数在情节段和风格段已有，不重复）")
            tip = "；确实要检查旧稿请显式加 --format 五段 或 --format 六段" if hints else ""
            errors.append(f"{fmt}格式含多余段落标题：{unexpected}"
                          + ("；" + "；".join(hints) + tip if hints else ""))
            bad = True
        order = [h for h in hdrs if h in SECTION_LABELS]
        if not bad and order != expected_labels:
            errors.append(f"段落标题顺序不对，应为 {' → '.join(expected_labels)}，实际：{order}"); bad = True
        if not heads:
            errors.append("情节段里没有镜头标题（镜头N（a-b秒）： / 镜头N： / 【阶段N】 之一）"); bad = True
        if not bad:
            checked.append(f"{fmt}外壳各一次、顺序正确")
        section_starts = [(i, KNOWN_HEADER.match(ln)) for i, ln in enumerate(lines) if KNOWN_HEADER.match(ln)]
        for k, (i, match) in enumerate(section_starts):
            end = section_starts[k + 1][0] if k + 1 < len(section_starts) else len(lines)
            content = lines[i][match.end():] + "\n" + "\n".join(lines[i + 1:end])
            if not content.strip():
                errors.append(f"段落内容为空：{match.group(1)}")
    else:
        b_hdrs = headers_of(baseline_lines, parse_heads(baseline_lines))
        if hdrs != b_hdrs:
            errors.append(f"外壳没有继承父稿：父稿标题 {b_hdrs}，新稿标题 {hdrs}；修订默认继承父稿外壳，不为通过检查迁移格式；"
                          f"要换成新标准（四段：无结尾标题、末尾只有固定句那一行）须本次明确授权并加 --format 四段")
        else:
            checked.append(f"外壳与父稿一致：{b_hdrs}")

    # --- 操作类必填词 ---
    overview = operation_text(text)
    command_zone = "情节段开头的命令区（情节：之后、第一个镜头标题之前）"
    if fmt == "四段" and task == "生成" and overview.strip():
        head = " / ".join(l.strip() for l in overview.strip().splitlines() if l.strip())[:40]
        warnings.append(f"情节段开头有总览句：「{head}」；生成类新稿情节段直接从镜头标题开始，时长与镜数由镜头标题表达，"
                        "控制句写进主体段或镜内，确认是重复就删掉")
    command_location = "概述段" if re.search(r"^\s*概述[：:]", text, re.M) else command_zone
    # 必填句的落点：四段新稿一律在命令区；五段 / 六段旧稿在结尾段；继承模式两处都接受（按父稿）
    m_tail = re.search(r"结尾[：:](.*)$", text, re.S)
    zone_start, zone_end = (len(lines), len(lines)) if fmt == "四段" else tail_zone_bounds(lines)
    if fmt == "四段":
        tail_text, tail_name, has_tail = "", "末尾", False
    elif m_tail:
        tail_text, tail_name, has_tail = m_tail.group(1), "结尾段", True
    elif zone_start < zone_end:
        tail_text, tail_name, has_tail = "\n".join(lines[zone_start:zone_end]), "结尾段", True
    else:
        tail_text, tail_name, has_tail = text[-400:], "结尾段", False
    # 四段只认命令区；继承模式命令区或结尾段都行；旧壳只认结尾段
    required_zone = overview if fmt == "四段" else (overview + "\n" + tail_text if fmt == "继承" else tail_text)
    misplaced_hint = ("操作命令的必填句写在情节段开头的命令区，末尾只留固定句" if fmt == "四段"
                      else f"操作命令的官方约束句要写在末尾固定句之前（{tail_name}），不能写在别处或固定句之后")
    zone_name = command_zone if fmt == "四段" else (f"命令区或{tail_name}" if fmt == "继承" else tail_name)
    if task == "延长":
        if not any(w in overview for w in ["向后延长", "向前延长", "续写", "延续"]):
            errors.append(f"延长命令的{command_location}缺少必填词：向后延长 / 向前延长 / 续写")
        if not re.search(r"@?视频\s?\d+", overview):
            errors.append(f"延长命令要在{command_location}直接写 视频N")
        if re.search(r"参考\s*@?视频\s?\d+", overview):
            errors.append("延长命令不能写成“参考视频N”，会被判为参考任务")
        miss = [w for w in EXTEND_REQUIRED if w not in required_zone]
        if miss and all(w in text for w in EXTEND_REQUIRED):
            errors.append(f"{misplaced_hint}；延长的官方约束句要整句写在{zone_name}：{EXTEND_CONSTRAINT}")
        elif miss:
            errors.append(f"延长命令的{zone_name}官方约束句不完整，缺：{miss}（应为：{EXTEND_CONSTRAINT}）")
        else:
            checked.append(f"延长必填词齐全，官方约束句在{zone_name}")
    if task == "编辑":
        if not any(w in overview for w in ["编辑", "替换", "删除", "去掉", "增加", "加上", "修改", "改成", "移除"]):
            errors.append(f"编辑命令的{command_location}缺少必填词：编辑 / 替换 / 删除 / 增加 / 修改")
        if not re.search(r"@?视频\s?\d+", overview):
            errors.append(f"编辑命令要在{command_location}直接写 视频N")
        if re.search(r"参考\s*@?视频\s?\d+", overview) and not re.search(r"编辑\s*@?视频\s?\d+", overview):
            errors.append("编辑命令不能只写“参考视频N”，要直接写“编辑视频N”")
        must = overview if fmt == "四段" else text
        if not any(w in must for w in ["唯一编辑母版", "唯一母版", "编辑母版"]):
            errors.append("编辑命令没有在" + (command_zone if fmt == "四段" else "稿里")
                          + "声明唯一编辑母版（视频N是唯一编辑母版，负责……）")
        if not any(w in must for w in ["保持", "不变"]):
            errors.append("编辑命令的“保持…不变”句" + (f"要写在{command_zone}，末尾只留固定句" if fmt == "四段" else "没有写"))
        if not errors or not any("编辑命令" in e for e in errors):
            checked.append("编辑必填词、母版与保持内容齐全" + ("，都在命令区" if fmt == "四段" else ""))
    if task == "衔接":
        must = overview if fmt == "四段" else text
        if not any(w in must for w in ["无缝衔接", "衔接起来", "无缝转场"]):
            errors.append("衔接命令缺少“无缝衔接”" + (f"（写在{command_zone}）" if fmt == "四段" else ""))
        if "不修改" not in must:
            errors.append("衔接命令没有写“不修改视频1和视频2”" + (f"（写在{command_zone}）" if fmt == "四段" else ""))
        else:
            checked.append("衔接必填词齐全" + ("，都在命令区" if fmt == "四段" else ""))

    # --- 固定句：逐字一次、不拆开、结束整份提示词 ---
    if fmt == "四段":
        closing_kind = "new"
    elif fmt in ("五段", "六段"):
        closing_kind = "old"
    elif CLOSING_NEW_RE.search(baseline_text or ""):
        closing_kind = "new"
    elif CLOSING_OLD_RE.search(baseline_text or ""):
        closing_kind = "old"
    else:
        closing_kind = "new" if CLOSING_NEW_RE.search(text) else "old"
        warnings.append("父稿里找不到固定句，继承模式按新稿的固定句核对；父稿用的是哪一句请自行确认")
    CLOSING, closing_re, closing_parts = CLOSING_SPEC[closing_kind]
    want = f"{CLOSING}。"
    strict_end = closing_kind == "new"          # 新句必须独占最后一行，前后都不能再有内容
    n_exact = len(closing_re.findall(text))
    part_counts = [len(p.findall(text)) for p in closing_parts]
    nonblank = [ln for ln in lines if ln.strip()]
    last_line = nonblank[-1] if nonblank else ""
    m_last = closing_re.search(last_line)
    other = CLOSING_SPEC["old" if closing_kind == "new" else "new"]
    if n_exact == 0:
        if other[1].search(text):
            src = "父稿" if fmt == "继承" else ("四段新稿" if fmt == "四段" else f"{fmt}旧稿")
            errors.append(f"固定句用错了句式：{src}必须逐字写“{want}”，这里写成了“{other[0]}。”；"
                          f"换句式须本次明确授权并改 --format")
        elif any(part_counts) or CLOSING_ANY_RE.search(text):
            errors.append(f"固定句被拆开或改写：必须逐字写“{want}”，并让它单独成为整份提示词的最后一行")
        else:
            errors.append(f"缺少固定句：{want}（必须是整份提示词的最后一行）")
    elif n_exact > 1 or max(part_counts) > 1:
        errors.append(f"固定句重复：出现 {max([n_exact] + part_counts)} 次；整份提示词只写一次（{want}）")
    elif not m_last:
        errors.append(f"固定句不在正文最后一行；它之后不能再另起一行写内容（规范句：{want}）")
    elif strict_end and (last_line[:m_last.start()].strip() or last_line[m_last.end():].strip(" 。.；;")):
        errors.append(f"固定句所在行还有别的内容；固定句要单独成行结束整份提示词，末尾不写别的句子（规范句：{want}）")
    elif fmt in ("五段", "六段") and m_tail and not closing_re.search(m_tail.group(1)):
        errors.append("固定句没有放在 结尾： 段里")
    else:
        checked.append(f"固定句逐字一次且是最后一行（{want}）")

    # --- 四段稿：末尾只有固定句一行，它前面一行必须是普通正文 ---
    if fmt == "四段" and m_last and len(nonblank) >= 2:
        prev = nonblank[-2].strip()
        if TAIL_ZONE_LINE.search(prev):
            errors.append(f"末尾只留固定句：倒数第二行是否定 / 约束 / “保持…”句「{prev[:40]}」；"
                          f"必要的否定句写进相应镜头的正文，操作命令的必填句写进{command_zone}")
        else:
            checked.append("末尾只有固定句一行，它前面是正文")

    # --- 素材（@图片N / 图片N / 图N 等一律归一成 图N / 视频N / 音频N）---
    used = {}
    for m in LABEL_RE.finditer(text):
        key = asset_key(m.group(2), m.group(3))
        used.setdefault(key, {"at": 0, "plain": 0, "first_line": text[:m.start()].count("\n")})
        used[key]["at" if m.group(1) else "plain"] += 1
    if used and first_head is not None:
        late = sorted(k for k, v in used.items() if v["first_line"] > first_head)
        if late:
            errors.append(f"这些素材第一次出现在第一个镜头标题之后，素材映射应前置：{late}")
    # 提示词里不写 @（即梦软件里粘贴后再 @ 出来）；继承模式按父稿：父稿用 @ 就不提醒
    at_used = sorted(k for k, v in used.items() if v["at"])
    baseline_has_at = bool(re.search(r"@(?:图片|视频|音频|图)\s?\d", baseline_text or ""))
    if at_used and fmt in ("四段", "继承") and not baseline_has_at:
        warnings.append(f"新稿不写 @（软件里再 @），写 图N / 视频N / 音频N：{at_used}")
    if a.labels:
        declared = {norm_label(x) for x in a.labels.split(",") if x.strip()}
        missing = sorted(declared - set(used))
        extra = sorted(set(used) - declared)
        if missing:
            errors.append(f"声明了但未使用的素材：{missing}")
        if extra:
            errors.append(f"使用了但未声明的素材：{extra}")
        if not missing and not extra:
            checked.append(f"素材 {sorted(declared)} 匹配")
    else:
        warnings.append("没有给 --labels，素材集合未核对")

    # --- 泄露 ---
    for rx, label in LEAK_RES:
        for m in rx.finditer(text):
            errors.append(f"{label}：{m.group(0)[:60]}")

    # --- 引用性措辞、内部术语、空词（台词与锁定文字不扫）---
    lock_free = scan_text
    for lk in a.lock:
        lock_free = lock_free.replace(lk, "")
    for w in REF_ERR:
        if w in lock_free:
            errors.append(f"引用性措辞：{w}")
    for w in REF_WARN:
        if w in lock_free:
            warnings.append(f"可能的引用性措辞：{w}（确认是否指向上一镜）")
    for m in OFFSCREEN_RE.finditer(lock_free):
        errors.append(f"画外内容写成了正在发生：{m.group(0)}")
    for w in INTERNAL:
        if w in text:
            errors.append(f"内部术语或修改标记泄露：{w.strip()}")
    for w in EMPTY_WORDS:
        if w in lock_free:
            warnings.append(f"空词：{w}（翻译成可见句或删）")

    # --- 锁定文字与未改镜头（原文匹配，只忽略换行）---
    flat = norm_lock(text)
    for lk in a.lock:
        if norm_lock(lk) not in flat:
            errors.append(f"锁定文字不在稿里或被改动：{lk[:40]}")
    if a.lock and not any(e.startswith("锁定文字") for e in errors):
        checked.append(f"锁定文字 {len(a.lock)} 条逐字保留")
    if revision:
        b_heads = parse_heads(baseline_lines)
        b_map = {h[2]: norm_shot(body) for (h, body, _t) in shot_blocks(baseline_lines, b_heads) if h[2] is not None}
        c_map = {h[2]: norm_shot(body) for (h, body, _t) in blocks if h[2] is not None}
        for sid in unchanged_ids:
            if sid not in b_map:
                errors.append(f"--unchanged 指定的镜头 {sid} 不在父稿里")
            elif sid not in c_map:
                errors.append(f"未改镜头 {sid} 在新稿里消失了")
            elif b_map[sid] != c_map[sid]:
                errors.append(f"未改镜头 {sid} 的正文与父稿不一致（逐字比对，只忽略行尾空白）")
        if unchanged_ids and not any("未改镜头" in e or "--unchanged" in e for e in errors):
            checked.append(f"未改镜头 {unchanged_ids} 与父稿逐字一致")
        b_labels, c_labels = asset_keys(baseline_text), asset_keys(text)
        if b_labels != c_labels:
            warnings.append(f"素材标签与父稿不同：父稿 {sorted(b_labels)}，新稿 {sorted(c_labels)}；确认是有意替换")
        if len(b_heads) != len(heads):
            warnings.append(f"镜头数与父稿不同：父稿 {len(b_heads)}，新稿 {len(heads)}；确认是授权的结构改动")
        checked.append("父稿已加载")

    # --- 每镜动态词扫描（提醒）---
    for k, (h, body_lines, _t) in enumerate(blocks):
        body = "\n".join(body_lines)
        if not any(w in body for w in MOTION_WORDS):
            warnings.append(f"镜{h[2] or k + 1} 未识别到运动描述；按逐镜摄影记录核对镜头，不要求添加环境或附属材料动态")
        tag = f"镜{h[2] or k + 1}"
        if re.search(r"(摄影机|镜头|机位)[^。；\n]{0,20}(几乎不可察觉|几乎察觉不到|微微(推|移|摇|晃|升|降)|轻微(晃动|抖动|浮动)|微抖)", body):
            warnings.append(f"{tag} 运镜用了弱措辞（几乎不可察觉 / 微微 / 轻微晃动）；本用户要可辨认的运动幅度，核对是否有实际画面变化，不用微抖冒充运镜")
        if h[3] is not None and h[4] is not None and h[4] > h[3]:
            dur = h[4] - h[3]
            beats = 1 + len(re.findall(r"先|接着|紧接着|随后|然后|最后|同时|再(?=[抬伸迈转抢踏收送压])", body))
            if dur / beats <= 0.5:
                warnings.append(f"{tag} 约 {beats} 个动作节拍挤在 {dur:g} 秒里（平均 ≤0.5 秒，即每秒 2 拍以上）；用户实测模型多会加速完成，但可能牺牲可读性或漏动作，按实际依赖与可读性判断（L064 只是经验线索，不是通过条件）")

    # --- 景别与内容（提醒；按实际取景判断，焦距不等于景别）---
    TIGHT, BODY_WIDE = ["特写", "大特写"], ["全身", "双脚", "脚下的", "整个房间", "整条街", "远处的山", "整片"]
    WIDE, BODY_TIGHT = ["大全景", "远景"], ["毛孔", "血珠", "睫毛", "瞳孔", "唇纹"]
    for k, (h, body_lines, _t) in enumerate(blocks):
        body = "\n".join(body_lines)
        tag = f"镜{h[2] or k + 1}"
        if any(w in body for w in TIGHT) and any(w in body for w in BODY_WIDE):
            warnings.append(f"{tag} 特写同时写了全身或远景内容，检查取景是否装得下")
        if any(w in body for w in WIDE) and any(w in body for w in BODY_TIGHT):
            warnings.append(f"{tag} 远景同时写了毛孔血珠这类特写细节，检查取景")
        if "浅景深" in body and ("前后都清楚" in body or "前景和背景都清晰" in body):
            warnings.append(f"{tag} 浅景深与前后景都清楚矛盾")
        if "固定机位" in body and any(w in body for w in ["跟随", "跟拍", "推近", "环绕", "横移"]):
            warnings.append(f"{tag} 固定机位与运镜词同时出现（固定机位不等于固定焦距，确认是不是有意的变焦）")
        if "焦点" in body and ("合实" in body or "散开" in body or "失焦" in body) and not re.search(r"焦点[^。；\n]{0,30}(落在|停在|移到|转到|回到|在)[^。；\n]{0,12}(上|里|处)", body):
            warnings.append(f"{tag} 焦点变化没有实物落点，写清每段焦点落在哪个部位或物件上")

    # --- 否定句：四段稿全文逐句提醒（默认预算 0 条自写否定）；旧壳与继承稿仍用结尾段预算 ---
    neg = 0
    exc_raw = [s.strip().rstrip("。；;") for s in a.negative_exception.replace(";", "；").split("；") if s.strip()]
    exc = list(dict.fromkeys(exc_raw))  # 去重
    neg_note = f"自写否定计数 {neg} 条"
    if fmt == "四段":
        found = negative_sentences(text, closing_re, a.lock)
        named = [s for s in found if s.rstrip("。；;") in exc]
        rest = [s for s in found if s.rstrip("。；;") not in exc]
        neg = len(rest)
        for s in rest:
            warnings.append(f"否定句：{s[:40]}；确认是特殊情况且无正向写法，否则改成要什么"
                            f"（能改成正向的写进主体、场景、风格或镜内）")
        stray = [s for s in exc if not any(x.rstrip("。；;") == s for x in found)]
        if stray:
            errors.append(f"--negative-exception 点名的句子在稿里找不到；要与镜内那一句整句一致，不能是片段或不存在的句子：{stray}")
        if named:
            checked.append(f"镜内否定 {len(named)} 句已用 --negative-exception 逐句点名")
        if not found:
            checked.append("全稿没有自写否定句，末尾只有固定句")
        neg_note = f"镜内否定提醒 {neg} 句"  # summary 一行里不写全角括号：Stop 钩子的检查行正则按「）」截断
    elif has_tail:
        counted = tail_text.replace("禁止项", "")
        # 用户原文锁不参与自写否定预算；它们仍接受存在性和语义冲突审查。
        for lk in sorted(a.lock, key=len, reverse=True):
            counted = counted.replace(lk, "")
        counted = closing_re.sub("", counted)
        for w in EXTEND_REQUIRED:
            counted = counted.replace(w, "")
        neg = len(re.findall(r"禁止|不添加|不出现|不要|不得|不允许|不能|不修改|不新增", counted)) + (1 if n_exact and not any(closing_re.search(lk) for lk in a.lock) else 0)
        if neg > 4:
            msg = f"{tail_name}否定句 {neg} 条，超过上限 4（固定句合算 1 条；操作类官方约束句不计）；能改成正向的搬到主体、场景、风格或镜内"
            # 结尾里独立的否定条款（按句号/分号切开，去掉固定句与操作约束句）
            clauses = {c.strip().rstrip("。；;") for c in re.split(r"[。；;\n]", counted) if re.match(r"^\s*(不|禁止|别)", c.strip())}
            exc_bad = [s for s in exc if s not in clauses]
            if task == "生成" and not revision:
                if exc and not exc_bad and len(exc) >= neg - 4:
                    warnings.append(msg + f"；已逐句声明 {len(exc)} 条必要例外（去重后），放行前逐句审查针对性与无正向写法")
                elif exc_bad:
                    errors.append(msg + f"；这些例外不是{tail_name}里独立的否定条款（要整句一致，不能是片段或不存在的句子）：{exc_bad}")
                elif exc:
                    errors.append(msg + f"；例外去重后只有 {len(exc)} 条，超出部分有 {neg - 4} 条，逐句点名")
                else:
                    errors.append(msg + "；用户明确要求的用 --lock，自写的必要例外用 --negative-exception 逐句点名")
            else:
                warnings.append(msg + "；必须审查必要性，用户锁定的否定不删")
        elif neg == 4:
            warnings.append(f"{tail_name}否定句已到上限 4，确认每条都没有正向写法")
        neg_note = f"自写否定计数 {neg} 条"

    # --- 段落级重复与分工（都是提醒）---
    secs = split_sections(text)
    # 1）素材重复绑定：同一素材的职责句（带绑定动词）出现在两个段落；情节里的纯指代不算
    bound = {}
    for name, body in secs.items():
        for sent in re.split(r"[。；;！!？?\n]", body):
            if not any(v in sent for v in BIND_VERBS):
                continue
            for key in asset_keys(sent):
                bound.setdefault(key, {})[name] = sent.strip()
    for key in sorted(bound):
        names = list(bound[key])
        if len(names) > 1:
            warnings.append(f"素材 {key} 在{'和'.join(n + '段' for n in names)}都写了职责；只在用它的那一段写一次")
    # 2）跨段重复长句：去掉标点与空白后 ≥12 字、在两个段落里完全相同的子句（台词不参与）
    seen = {}
    for name, body in secs.items():
        for raw, flat in clauses_of(strip_dialogue(body)):
            if len(flat) >= 12:
                seen.setdefault(flat, {}).setdefault(name, raw)
    for flat, hits in [(f, h) for f, h in seen.items() if len(h) > 1][:5]:
        sample = next(iter(hits.values()))
        warnings.append(f"跨段重复：「{sample[:24]}」出现在{'与'.join(n + '段' for n in hits)}；同一件事只写一次")
    # 3）风格段只写画面质感与镜头性格：时序与具体运镜路径、动作写进镜内
    if "风格" in secs:
        scan = strip_dialogue(secs["风格"])
        for w in STYLE_SAFE_WORDS:
            scan = scan.replace(w, "")
        hit = [w for w in STYLE_SEQUENCE_WORDS + STYLE_MOVE_WORDS if w in scan]
        if hit:
            warnings.append("风格段里有时序或具体运镜/动作：" + "".join(f"「{w}」" for w in hit)
                            + "；风格段只写画面质感与镜头性格，运镜路径与动作写进镜内")
    m = re.search(r"风格[：:](.*?)(?:\n情节[：:]|\n镜头|$)", text, re.S)
    if m and QUALITY_ONLY.search(m.group(1)) and len(re.sub(r"\s", "", m.group(1))) < 60:
        warnings.append("风格段只有画质词、缺少材质与光的具体句")

    checked_sha = sha(text)
    # 交付出去的那段正文（--partial 时是局部段本身，否则就是整稿）；规范化方式与 hooks/stop_gate.py 的 digest 一致
    delivered_sha = sha("\n".join(cand_lines))
    parts = [f"{len(heads)} 镜"]
    if timed:
        time_errors = [e for e in errors if "时码" in e or "编辑区间" in e]
        parts.append("时码失败" if time_errors else ("编辑区间已核对" if task == "编辑" else "-".join(f"{x:g}" for x in [timed[0][3]] + [h[4] for h in timed]) + " 连续"))
    if a.labels:
        parts.append(f"素材 {a.labels} " + ("匹配" if declared == set(used) else "不匹配"))
    else:
        parts.append("素材集合未核对")
    parts.append(neg_note)
    parts.append(f"待裁定提醒 {len(warnings)} 条")
    parts.append(f"sha {delivered_sha[:8]}")
    summary = ("check_prompt 通过" if not errors else f"check_prompt 有 {len(errors)} 处错误") + "（" + "｜".join(parts) + "）"
    out = {
        "ok": not errors, "task": task, "revision": revision, "format": fmt, "partial": a.partial,
        "errors": errors, "warnings": warnings, "checked": checked,
        "stats": {"shots": len(heads), "heading_style": sorted(styles), "total_seconds": timed[-1][4] if timed else None,
                  "labels_used": sorted(used), "chars": len(text)},
        "input_sha256": sha(raw), "baseline_sha256": sha(baseline_text) if baseline_text is not None else None,
        "checked_sha256": checked_sha, "delivered_sha256": delivered_sha, "summary": summary,
        "limits": "只检查文本不变量；不验证画面语义、素材内容或成片效果；检查后改过的稿必须重跑",
    }
    if a.report:
        rp = Path(a.report)
        if rp.parent and str(rp.parent) not in ("", "."):
            rp.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "kind": "light", "ready": not errors,
            "checked_sha256": checked_sha, "delivered_sha256": delivered_sha,
            "task": task, "format": fmt, "partial": bool(a.partial),
            "errors": errors, "warnings": warnings,
            "labels": sorted(x.strip() for x in a.labels.split(",") if x.strip()), "locks": len(a.lock),
            "baseline_sha256": sha(baseline_text) if baseline_text is not None else None,
            "summary": summary,
            "created_at": time.time(), "session_id": os.environ.get("AIGC_SESSION_ID") or None,
            "limits": "只是机械文本检查；没核对素材标签之外的内容、画面语义与成片效果；报告文件不是运行签名",
        }
        rp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
