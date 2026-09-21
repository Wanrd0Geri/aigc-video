#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stop 钩子（Claude Code 与 Codex 通用）：模型准备结束回复时，保证回复里每一份"本轮交付的视频提示词"都过了机械检查——
要么有一份本轮的 ready=true 报告（全套的 verify_delivery 报告，或轻量路径的 check_prompt --report 报告），
要么由钩子当场代跑 scripts/check_prompt.py。比对的是提示词正文本身的 SHA-256，不是那行"交付校验通过"。

宿主：
  Claude Code  ~/.claude/settings.json →
    {"hooks": {"Stop": [{"hooks": [{"type": "command",
      "command": "python3 ~/.claude/skills/aigc-video/hooks/stop_gate.py"}]}]}}
    阻止 = 退出码 2 + stderr（Claude Code 会把 stderr 交给模型继续处理）。
  Codex        ~/.codex/hooks.json → Stop 事件挂同一脚本（按官方 hooks 文档，Stop 钩子必须输出 JSON）。
    阻止 = stdout 输出 {"decision": "block", "reason": "..."}。Codex 适配按官方文档字段实现，尚未在真实 Codex 会话验证。
两边传入的 stdin JSON 都可能有 transcript_path、last_assistant_message、session_id、stop_hook_active。

交付单元的契约（钩子只按这个契约认东西，SKILL 第 ⑨ 步、quality-gate.md、hooks/README.md 写的是同一套）：
  - 成品一律放 ```text 代码块（无语言标签、```prompt 同等对待）；这些代码块里像提示词的内容都要验收。
  - 引用旧稿用 ```quote，概念草案用 ```draft，工具输出用 ```diff/```json/```bash/```sh：一律不验收，也不受"原样粘贴"约束。
  - 代码块之外的纯文本同样扫描：完整稿（≥3 个段落标题，四段新壳与五段 / 六段旧壳都算）、局部镜头（镜头标题）、操作命令（视频N 或
    旧稿的 @视频N 附近有 编辑/延长/续写/衔接/替换/删除/增加）都算交付单元，不管回复里有没有合法代码块。表头、例外说明、
    变更摘要、待你定的问题写在代码块外，不会被当成提示词。
  - 算哈希前先删掉单元里的"交付校验通过（正文 xxxxxxxx｜需求 xxxxxxxx）"和首尾空行，再按 verify_delivery
    的方式规范化（按行拆分再用换行拼回）。

判定：
  1. 取最后一条助手消息（优先 last_assistant_message，否则读 transcript_path）。两者都拿不到 → 无法验收，阻止一次。
  2. 从 transcript 里取最后一条**用户真正打的**消息的时间 T_user（跳过 role=user 的工具返回行和钩子自己的拦截提示；`timestamp` ISO 字段；该条没有时间字段就退回 transcript 文件 mtime）。
  3. 按上面的契约取出所有交付单元，各自算 SHA-256，然后走**三层判定**：
     第 1 层｜有本轮报告 → 通过。在 AIGC_GATE_DIR（默认 ~/.aigc-video-gate）里找 ready=true 且 delivered_sha256 或
       checked_sha256 相等的报告（全套的 verify_delivery 报告，或轻量路径 check_prompt --report 写的 kind="light" 报告；
       kind 缺失视为全套）；报告还必须满足 created_at（缺失时用文件 mtime）≥ T_user，且 payload 与报告都带 session_id
       时两者相等。找到了就通过。报告存在但早于本轮 / 属于别的会话 → 直接阻止（旧稿冒充本轮），不代跑。
     第 2 层｜没有报告，单元是**完整稿**（≥3 个段落标题）→ 钩子自己跑一遍 scripts/check_prompt.py（把规范化后的正文写进
       临时文件；任务类型按正文推断：命令区或 视频N 附近有"向后延长/向前延长/续写"→ 延长，有"无缝衔接"→ 衔接，
       有 编辑视频N/替换/删除/增加 且出现 视频N → 编辑，否则 生成（视频N 带不带 @ 都认）；外壳按标题推断：有概述段 → 六段旧壳，
       只有结尾段 → 五段旧壳，两者都没有 → 不传 --format，用脚本默认的四段新壳）。
       钩子不知道素材集合、逐字锁、总时长和父稿，所以不传 --labels / --lock / --total / --baseline。
       有错误 → 阻止并把错误原文列给模型，要求修好后自己跑 `check_prompt.py --report <目录>/<时间戳>.json` 再交付；
       无错误 → 放行，但用 systemMessage 说明"这份稿由钩子代跑机械检查通过……作者本轮没有自己跑检查"。
     第 3 层｜没有报告，单元是**局部镜头或操作命令** → 钩子没有父稿，代跑没有意义，直接阻止，要求带 --baseline
       （局部再加 --partial）跑 `check_prompt.py --report` 再交付。
     拿不到 T_user（没有 transcript）时退回 24 小时窗口，并在放行时用 systemMessage 说明"本轮绑定较弱"。
  4. 回复里每一条"交付校验通过（正文 xxxxxxxx｜需求 xxxxxxxx）"都必须与某份已匹配报告成对一致（正文短哈希与
     checked/delivered 前 8 位一致，且需求短哈希是同一份报告的）；对不上就阻止，不再默默忽略。交付行本身不是放行依据，
     可以不显示（prompt-only）。
  5. 回复里每一条机械检查行"check_prompt 通过（…｜sha xxxxxxxx）"的短哈希，都必须对得上本轮已匹配到的某份 light 报告
     （delivered_sha256 或 checked_sha256 前 8 位）；对不上就阻止（不要手写检查行）。代跑通过的单元没有报告，所以
     那种情况下也不许自己写这行。全套报告匹配的单元不要求有这行。
  6. stop_hook_active=true（已经被本钩子拦过一次）：仍然检查；仍不通过时不再阻止（防死循环），改为放行并附系统消息
     "本次交付未经放行验收"，由用户看到。这是失败降级，不是硬阻断：Stop 钩子不能撤回已经显示出来的文字。
退出码：0 放行；2 阻止（Claude Code）。Codex 模式下阻止用 JSON decision=block、退出码 0。
边界：报告文件不是运行签名；能拦住"改稿不重查""没跑检查""多贴一份""旧稿冒充本轮""假交付行""手写检查行"，
拦不住手工伪造报告文件。代跑只覆盖机械文本不变量，不核对素材标签、锁定台词、总时长与父稿——所以代跑通过也要带提示。
"""
import hashlib, json, os, re, subprocess, sys, tempfile, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "check_prompt.py"
GATE_DIR = Path(os.environ.get("AIGC_GATE_DIR", os.path.expanduser("~/.aigc-video-gate")))
FENCE = re.compile(r"```(?P<lang>[^\n]*)\n(?P<body>(?:.|\n)*?)\n```", re.M)
RECEIPT = re.compile(r"交付校验通过（正文 ([0-9a-f]{8})｜需求 ([0-9a-f]{8})）")
RECEIPT_ANY = re.compile(r"交付校验通过（正文 [0-9a-f]{8}｜需求 [0-9a-f]{8}）")
SHOT_HEAD = re.compile(r"(?m)^\s*(镜头\s*\d+\s*[（(:：]|【阶段[一二三四五六七八九十\d]+】|第[一二三四五六七八九十\d]+阶段|\d+(?:\.\d+)?\s*(?:s|秒)?\s*[-–—~到]\s*\d+(?:\.\d+)?\s*(?:s|秒)\s*[:：])")
SECTION = re.compile(r"(?m)^\s*(主体|概述|场景|风格|情节|结尾)\s*[：:]")
VERB = "编辑|延长|续写|衔接|替换|删除|增加"
# 素材引用：提示词里写 视频N（软件里再 @），旧稿的 @视频N 也认；仍要求动词邻近，免得把闲聊里的"视频1"当成命令
VIDEO_REF = r"@?视频\s?\d+"
OPERATION = re.compile(VIDEO_REF + r"[^\n]{0,40}(?:" + VERB + r")|(?:" + VERB + r")[^\n]{0,40}" + VIDEO_REF)
# 只有这些语言标签的围栏不验收：引用旧稿、概念草案、工具输出。其余（text/prompt/无标签/未知）都是成品候选。
NON_DELIVERY_LANGS = {"quote", "draft", "diff", "json", "bash", "sh"}
DAY = 86400
# 机械检查行（check_prompt 的 summary）：只取里面的 sha 短哈希，用来核对它不是手写的
CHECK_LINE = re.compile(r"check_prompt\s*(?:通过|有\s*\d+\s*处错误)（[^）\n]*?sha\s*([0-9a-f]{8})[^）\n]*）")
# 代跑时推断任务类型用：命令区 = 概述段，或情节段开头到第一个镜头 / 阶段标题之前
COMMAND_ZONE = re.compile(
    r"(?:概述|情节)[：:](.*?)(?=\n\s*(?:镜头\s*\d+|【阶段|第[一二三四五六七八九十\d]+阶段)|\n(?:主体|场景|风格|结尾)[：:]|\Z)", re.S)
NEAR_VIDEO = re.compile(r"[^\n]{0,40}" + VIDEO_REF + r"[^\n]{0,40}")
SELF_RUN_NOTE = ("aigc-video 守门：这份稿由钩子代跑机械检查通过（未核对素材标签、锁定台词、总时长与父稿），"
                 "作者本轮没有自己跑检查。")


def is_full_draft(body):
    """完整稿：至少 3 个段落标题（四段新壳与五段 / 六段旧壳都算）。局部镜头和操作命令不是。"""
    return len(SECTION.findall(body)) >= 3


def infer_task(body):
    """代跑时按正文推断 check_prompt 的 --task（钩子拿不到用户给的任务类型）。"""
    zone = "\n".join(COMMAND_ZONE.findall(body) + NEAR_VIDEO.findall(body))
    if re.search(r"向后延长|向前延长|续写", zone):
        return "延长"
    if "无缝衔接" in body:
        return "衔接"
    if re.search(r"编辑" + VIDEO_REF + r"|替换|删除|增加", zone) and re.search(VIDEO_REF, body):
        return "编辑"
    return "生成"


def run_checker(body):
    """钩子代跑 scripts/check_prompt.py。返回 (状态, 说明列表)：
    'ok' 无错误；'errors' 有错误（说明列表是错误原文）；'unavailable' 根本没跑起来。"""
    if not CHECKER.exists():
        return "unavailable", [f"找不到检查脚本 {CHECKER}"]
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as fh:
            fh.write(body + "\n")
            tmp = fh.name
        cmd = [sys.executable, "-X", "utf8", str(CHECKER), "--prompt", tmp, "--task", infer_task(body)]
        # 外壳按标题推断：有概述段 = 六段旧壳；只有结尾段 = 五段旧壳；都没有就不传，用脚本默认的四段新壳
        if re.search(r"(?m)^\s*概述\s*[：:]", body):
            cmd += ["--format", "六段"]
        elif re.search(r"(?m)^\s*结尾\s*[：:]", body):
            cmd += ["--format", "五段"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return "unavailable", [f"代跑 check_prompt.py 失败：{exc}"]
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    try:
        data = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return "unavailable", [f"check_prompt.py 的输出读不懂（退出码 {proc.returncode}）：{detail[-1][:200] if detail else '无输出'}"]
    errors = [e for e in (data.get("errors") or []) if isinstance(e, str)]
    return ("ok" if not errors else "errors"), errors


def digest(text):
    return hashlib.sha256(("\n".join(text.splitlines())).encode("utf-8")).hexdigest()


def normalize(body):
    """删掉交付行与首尾空行，剩下的就是要核对哈希的正文。"""
    lines = []
    for raw in body.splitlines():
        line = RECEIPT_ANY.sub("", raw)
        if line != raw and not line.strip():
            continue
        lines.append(line)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def looks_like_prompt(body):
    # 固定句：新句"全片不添加BGM，不添加字幕"与旧句"不添加字幕，不添加背景音乐"都认
    return bool(SHOT_HEAD.search(body) or len(SECTION.findall(body)) >= 3 or OPERATION.search(body)
                or ("不添加字幕" in body and ("不添加背景音乐" in body or "BGM" in body)))


def plain_looks_like_prompt(body):
    """纯文本只认三类交付单元：完整稿、局部镜头、操作命令。"""
    return bool(len(SECTION.findall(body)) >= 3 or SHOT_HEAD.search(body) or OPERATION.search(body))


def delivery_units(text):
    """代码块内部与外部一起取：成品候选代码块 + 代码块外连续的提示词段落。"""
    units = []
    for m in FENCE.finditer(text):
        lang = m.group("lang").strip().lower()
        lang = lang.split()[0] if lang else ""
        if lang in NON_DELIVERY_LANGS:
            continue
        if looks_like_prompt(m.group("body")):
            units.append(m.group("body"))
    rest = FENCE.sub("\n", text)
    run = []
    for para in re.split(r"\n[ \t]*\n", rest):
        if plain_looks_like_prompt(para):
            run.append(para.strip("\n"))
        elif run:
            units.append("\n\n".join(run))
            run = []
    if run:
        units.append("\n\n".join(run))
    return units


def parse_time(value):
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return None


def read_transcript(path):
    """返回解析后的行列表；读不到返回 None。"""
    if not path:
        return None
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    rows = []
    for ln in lines:
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return rows


def entry_role(obj):
    m = obj.get("message", obj)
    return m.get("role") if isinstance(m, dict) else None


HOOK_FEEDBACK_MARKS = ("Stop hook feedback", "aigc-video 放行钩子", "aigc-video 守门")


def is_real_user_message(obj):
    """只有用户真正打的那条才算"本轮用户消息"。
    Claude Code 的 transcript 里工具返回（tool_result）也是 role=user 的行，钩子自己上一次的拦截提示也会以
    user 身份出现；这两类都发生在作者跑完检查之后，拿它们的时间去和报告比，会把本轮刚生成的报告误判成"早于本轮"。"""
    if entry_role(obj) != "user":
        return False
    m = obj.get("message", obj)
    content = m.get("content") if isinstance(m, dict) else None
    if isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
            return False
        if not any(isinstance(c, dict) and c.get("type") in ("text", "image") for c in content):
            return False
    text = entry_text(obj).lstrip()
    if any(text.startswith(mark) or mark in text[:80] for mark in HOOK_FEEDBACK_MARKS):
        return False
    return True


def entry_text(obj):
    m = obj.get("message", obj)
    content = m.get("content", []) if isinstance(m, dict) else []
    if isinstance(content, str):
        return content
    return "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")


def last_user_time(rows, path):
    """最后一条 user 消息的时间；该条没有时间字段时退回 transcript 文件 mtime（偏严，不放宽）。"""
    if rows is None:
        return None
    for obj in reversed(rows):
        if not is_real_user_message(obj):
            continue
        m = obj.get("message", obj)
        stamp = obj.get("timestamp") or (m.get("timestamp") if isinstance(m, dict) else None)
        t = parse_time(stamp)
        if t is not None:
            return t
        try:
            return Path(path).stat().st_mtime
        except OSError:
            return None
    return None


def last_assistant_text(payload, rows):
    msg = payload.get("last_assistant_message")
    if isinstance(msg, str) and msg.strip():
        return msg
    if rows is None:
        return None
    for obj in reversed(rows):
        if entry_role(obj) == "assistant":
            return entry_text(obj)
    return None


def load_reports():
    out = []
    if not GATE_DIR.exists():
        return out
    now = time.time()
    for p in sorted(GATE_DIR.glob("*.json")):
        try:
            mtime = p.stat().st_mtime
            rep = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if not isinstance(rep, dict) or rep.get("ready") is not True:
            continue
        created = rep.get("created_at")
        created = float(created) if isinstance(created, (int, float)) else mtime
        if now - created > DAY:
            continue
        out.append((rep, created))
    return out


def check(text, t_user, session_id):
    """返回 (ok, 原因, 系统提示列表)。系统提示只在放行时输出（例如代跑通过的告知）。"""
    units = delivery_units(text)
    receipts = RECEIPT.findall(text)
    # 机械检查行只在成品候选区域里认：引用/草案/工具输出围栏（```json、```bash 等）里的 summary 不算交付行
    scan = FENCE.sub(lambda m: "\n" if (m.group("lang").strip().lower().split() or [""])[0] in NON_DELIVERY_LANGS else m.group(0), text)
    check_lines = CHECK_LINE.findall(scan)
    if not units and not receipts and not check_lines:
        return True, "", []
    reports = load_reports()
    matched, notes = [], []
    for i, body in enumerate(units, 1):
        norm = normalize(body)
        h = digest(norm)
        same = [(r, ts) for r, ts in reports
                if r.get("delivered_sha256") == h or r.get("checked_sha256") == h]
        stale = session_bad = False
        good = []
        for rep, ts in same:
            if t_user is not None and ts < t_user:
                stale = True
                continue
            rs = rep.get("session_id")
            if session_id and rs and rs != session_id:
                session_bad = True
                continue
            good.append(rep)
        if good:                                        # 第 1 层：本轮报告对得上
            matched.extend(good)
            continue
        if stale:
            return False, (f"第 {i} 份提示词（正文哈希 {h[:8]}）的检查报告早于本轮用户消息，请为本轮要求重新检查："
                           "旧稿曾经通过不能证明它满足当前要求；轻量路径重跑 check_prompt.py --report，"
                           "全套路径重新建 requirements.json 并重跑 verify_delivery.py。"), notes
        if session_bad:
            return False, (f"第 {i} 份提示词（正文哈希 {h[:8]}）的检查报告来自另一个会话（session_id 不一致），"
                           "请在本会话为本轮要求重新运行检查脚本。"), notes
        if not is_full_draft(norm):                     # 第 3 层：局部镜头或操作命令，钩子没有父稿
            return False, (f"第 {i} 份提示词（正文哈希 {h[:8]}）是局部镜头或操作命令，在 {GATE_DIR} 里没有本轮"
                           "ready=true 且正文一致的检查报告；钩子拿不到父稿，代跑没有意义。"
                           "请自己跑：python3 scripts/check_prompt.py --prompt <正文.txt> --baseline <父稿.txt>"
                           "（只交部分镜头再加 --partial）--report " + str(GATE_DIR) + "/<时间戳>.json，"
                           "然后原样粘贴检查过的正文。改过稿必须重跑。"), notes
        state, detail = run_checker(norm)               # 第 2 层：完整稿，钩子代跑
        if state == "errors":
            listed = "\n".join("- " + e for e in detail)
            return False, (f"第 {i} 份提示词（正文哈希 {h[:8]}）没有本轮检查报告，钩子代跑 scripts/check_prompt.py "
                           f"发现 {len(detail)} 处错误：\n{listed}\n"
                           "修好后自己跑 `python3 scripts/check_prompt.py --prompt <正文.txt> --report "
                           + str(GATE_DIR) + "/<时间戳>.json` 再交付。"), notes
        if state == "unavailable":
            return False, (f"第 {i} 份提示词（正文哈希 {h[:8]}）没有本轮检查报告，钩子也没能代跑机械检查"
                           f"（{detail[0] if detail else '原因不明'}）。请自己跑 `python3 scripts/check_prompt.py "
                           "--prompt <正文.txt> --report " + str(GATE_DIR) + "/<时间戳>.json` 再交付。"), notes
        notes.append(SELF_RUN_NOTE)
    for pre_body, pre_req in receipts:
        if not any((str(r.get("checked_sha256", "")).startswith(pre_body)
                    or str(r.get("delivered_sha256", "")).startswith(pre_body))
                   and str(r.get("requirements_sha256", "")).startswith(pre_req) for r in matched):
            return False, (f"交付行与放行报告不一致，不要手写交付行（正文 {pre_body}｜需求 {pre_req} 对不上本轮任何一份已匹配报告）；"
                           "照抄 verify_delivery.py --response 生成的成品。"), notes
    light = [r for r in matched if r.get("kind") == "light"]
    for pre in check_lines:
        if not any(str(r.get("delivered_sha256", "")).startswith(pre)
                   or str(r.get("checked_sha256", "")).startswith(pre) for r in light):
            return False, (f"机械检查行与 check_prompt 报告不一致，不要手写检查行（sha {pre} 对不上本轮任何一份已匹配的 "
                           "check_prompt 报告）；照抄 `check_prompt.py --report …` 真实输出的那行 summary。"), notes
    if receipts and len(receipts) < len(units) and len(units) > 1:
        return False, f"回复里有 {len(units)} 份提示词，但交付行只有 {len(receipts)} 条；每份提示词都要各自放行。", notes
    return True, "", notes


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    codex_mode = "last_assistant_message" in payload or "turn_id" in payload or payload.get("hook_event_name") == "Stop" and "cwd" in payload and "transcript_path" in payload and payload.get("transcript_path") is None
    path = payload.get("transcript_path")
    rows = read_transcript(path)
    text = last_assistant_text(payload, rows)
    t_user = last_user_time(rows, path)
    weak = rows is None and text is not None and bool(delivery_units(text) or RECEIPT.findall(text))  # 没有交付单元就不提示
    if text is None:
        ok, reason, notes = False, "读不到最后一条助手消息（transcript_path 不可读且没有 last_assistant_message），无法核对是否有未验收的提示词。", []
    else:
        ok, reason, notes = check(text, t_user, payload.get("session_id"))
    if ok:
        msgs = []
        if weak:
            msgs.append("aigc-video 放行钩子：本轮绑定较弱（无 transcript，拿不到本轮用户消息时间），只按 24 小时窗口核对了正文哈希。")
        msgs.extend(dict.fromkeys(notes))
        if msgs:
            print(json.dumps({"systemMessage": " ".join(msgs)}, ensure_ascii=False))
        elif codex_mode:
            print("{}")
        return 0
    if payload.get("stop_hook_active"):
        # 已拦过一次仍不通过：放行但明确告诉用户，不把失败改写成通过
        print(json.dumps({"systemMessage": "aigc-video 放行钩子：本次回复里的提示词未通过放行验收（" + reason + "）。这份稿只能算待验证候选。"}, ensure_ascii=False))
        return 0
    if codex_mode:
        print(json.dumps({"decision": "block", "reason": "aigc-video 放行钩子：" + reason}, ensure_ascii=False))
        return 0
    print("aigc-video 放行钩子：" + reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
