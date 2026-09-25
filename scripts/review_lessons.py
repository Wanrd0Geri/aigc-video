#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_lessons.py — 「整理经验」用的候选清单生成器：只读、只输出，不改任何文件。

用法：
  python3 review_lessons.py [--file <经验库>] [--cases <案例库>]

输出一份 Markdown 清单，六节：
  一、被 2 条以上案例引用的经验（多次复用，优先考虑升级成规则）
  二、同分类里主题相近、可能能合并的条目对
  三、结论里写了"修正"或"见 Lxxx"的条目（互相修正，可能已经冲突；三位编号都认，L100 以后的也算）
  四、各分类条目数（超过 15 条的点名）
  五、主库里还带着「已升级为规则」「已撤回推荐」「并入」标记没搬走的条目（v31 起这三种都该整行在 archive.md，主库里出现就是漏搬），
      以及 archive.md 现有条目数
  六、单次观察保质期：结论里标了「单次观察」、记录满 30 天、来源没有第二条成片或对照的条目——归档候选（用户 2026-09-25：
      经验库里有抽卡也有写得不到位的，要甄别；只出现过一次的观察不当定律）

清单只是候选，改不改、怎么改由用户挑（v31 起三种整理都是"标记 + 整行搬到 archive.md"，主库只留活条目，编号不腾不重用）：
  - 升级到 SKILL.md、writing-rules.md、review/revise-rules.md 或工艺卡的，把规则写进那份文件，原条目「结论」列末尾加
    `【已升级为规则：<文件> <节>】`，整行搬到 archive.md「已升级为规则」节；
  - 合并的，保留证据更强、结论更完整的那条（不看编号先后），把被并那条的要点用一句括进保留条的「结论」末尾
    `【L0yy 并入：…】`，被并那条「结论」末尾加 `【并入 L0xx】` 后整行搬到 archive.md「已并入」节；
  - 用户决定不再采用某条的推荐写法的，在它「结论」列最前面加 `【<日期> 已撤回推荐：<一句话>，见末尾注记】`，
    末尾写用户决定的注记，整行搬到 archive.md「已撤回推荐」节。
  改完：跑 lint_lessons.py（两文件合集查编号），把主库「## 七、诊断新增」下面的 `<!-- 整理于 <日期> L0xx -->` 更新成最新编号。
跑的频率：每新增约 10 条经验或 3 条案例跑一次（log_lesson.py 会在标记之后满 10 条时提醒），或用户随时喊「整理经验」。
"""
import datetime
import argparse, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lint_cases import strip_fences, split_entries, LESSON_ID  # 案例解析与 lint_cases 共用

DEFAULT_LESSONS = os.path.join(HERE, "..", "references", "lessons", "seedance-2.5.md")
DEFAULT_CASES = os.path.join(HERE, "..", "references", "cases", "my-cases.md")
ENTRY = re.compile(r"^(L\d{3})\s*\|")
CJK = re.compile(r"[一-鿿]+")
BIG_CAT = 15
SINGLE_DAYS = 30        # 单次观察满这么多天还没第二个来源就列为归档候选。可调
MERGED_MARK = re.compile(r"【并入\s*(L\d{3})】")
SINGLE_MARK = "单次观察"
SOURCE_MULTI = re.compile(r"对照|两跑|两次|三版|三跑|多版|各跑|[2-9]\s*条|[两三四五六七八九]条|用户实测")
# 「结论」列最前面的撤回标注：【<日期> 已撤回推荐：<一句话>，见末尾注记】
WITHDRAWN = re.compile(r"【(\d{4}-\d{2}-\d{2})\s*已撤回推荐[：:]([^】]*)】")
# 结论里点到别的条目：“见 L071”“见L101”（三位编号，L100 以后也认）
SEE_OTHER = re.compile(r"见\s*L\d{3}")
# 升级去向标记：【已升级为规则：…】与后来补的【规则位置更新：…】，多个时最后一个是规则现在的位置
UPGRADE_MARK = re.compile(r"【(已升级为规则|规则位置更新)[：:]([^】]*)】")


def read_lessons(path):
    rows = {}
    for ln in open(path, encoding="utf-8"):
        if not ENTRY.match(ln):
            continue
        p = [x.strip() for x in ln.rstrip("\n").split(" | ")]
        if len(p) != 9:
            continue
        cat, _, sub = p[2].partition("/")
        rows[p[0]] = dict(id=p[0], date=p[1], cat=cat, sub=sub, topic=p[2],
                          phenomenon=p[3], a=p[4], b=p[5], conclusion=p[6],
                          confidence=p[7], source=p[8])
    return rows


def read_case_refs(path):
    """返回 {案例编号: set(引用到的 L 编号)}，只看「关联经验」行与「可复用点」的每条。"""
    lines = strip_fences(open(path, encoding="utf-8").read())
    refs = {}
    for mid, _start, body in split_entries(lines):
        used = set()
        in_reuse = False
        for ln in body:
            if ln.startswith("关联经验："):
                used |= {"L" + n for n in LESSON_ID.findall(ln)}
            if ln.startswith("可复用点："):
                in_reuse = True
                continue
            if ln.startswith("提示词原文"):
                in_reuse = False
            if in_reuse and ln.startswith("- "):
                used |= {"L" + n for n in LESSON_ID.findall(ln)}
        refs[mid] = used
    return refs


def bigrams(s):
    out = set()
    for run in CJK.findall(s):
        for i in range(len(run) - 1):
            out.add(run[i:i + 2])
    return out


def main():
    ap = argparse.ArgumentParser(description="整理经验：生成候选清单，不做修改")
    ap.add_argument("--file", default=DEFAULT_LESSONS)
    ap.add_argument("--cases", default=DEFAULT_CASES)
    ap.add_argument("--archive", default=None, help="归档路径；不给取 --file 同目录的 archive.md")
    ap.add_argument("--today", default=None, help="第六节按这个日期算天数（默认今天），测试用")
    a = ap.parse_args()
    lpath = os.path.abspath(os.path.expanduser(a.file))
    cpath = os.path.abspath(os.path.expanduser(a.cases))
    apath = os.path.abspath(os.path.expanduser(a.archive)) if a.archive else os.path.join(os.path.dirname(lpath), "archive.md")
    arch = read_lessons(apath) if os.path.isfile(apath) else {}
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    rows = read_lessons(lpath)
    refs = read_case_refs(cpath)

    out = ["# 整理经验候选清单", "",
           f"经验库 {len(rows)} 条｜案例 {len(refs)} 条｜只读清单，不改任何文件。", ""]

    # 一、被多条案例引用
    by_lesson = {}
    for mid, used in refs.items():
        for lid in used:
            by_lesson.setdefault(lid, []).append(mid)
    hot = sorted((l, sorted(m)) for l, m in by_lesson.items() if len(set(m)) >= 2)
    out.append(f"## 一、被 2 条以上案例引用的经验（{len(hot)} 条）")
    out.append("")
    if hot:
        out.append("| 编号 | 分类/主题 | 引用它的案例 | 置信度 | 结论摘要 |")
        out.append("|---|---|---|---|---|")
        for lid, mids in hot:
            r = rows.get(lid)
            topic = r["topic"] if r else "（经验库里没有这条）"
            conf = r["confidence"] if r else "—"
            concl = (r["conclusion"][:60] + "…") if r and len(r["conclusion"]) > 60 else (r["conclusion"] if r else "—")
            out.append(f"| {lid} | {topic} | {'、'.join(mids)} | {conf} | {concl} |")
    else:
        out.append("（没有被 2 条以上案例引用的条目）")
    out.append("")

    # 二、可能能合并的相近条目
    ids = sorted(rows)
    pairs = []
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            rx, ry = rows[x], rows[y]
            why = []
            if rx["cat"] == ry["cat"]:
                shared = bigrams(rx["sub"]) & bigrams(ry["sub"])
                if len(shared) >= 2:
                    why.append("同分类，主题共用词：" + "、".join(sorted(shared)))
            if y in rx["conclusion"] and x in ry["conclusion"]:
                why.append("两条的结论互相点名对方")
            if why:
                pairs.append((x, y, "；".join(why)))
    out.append(f"## 二、同分类里主题相近、可能能合并的条目（{len(pairs)} 对）")
    out.append("")
    if pairs:
        out.append("| 条目 A | 条目 B | 为什么像 |")
        out.append("|---|---|---|")
        for x, y, why in pairs:
            out.append(f"| {x} {rows[x]['topic']} | {y} {rows[y]['topic']} | {why} |")
    else:
        out.append("（没有触发合并启发式的条目对）")
    out.append("")

    # 三、互相修正 / 可能冲突
    fix = [r for r in rows.values()
           if "修正" in r["conclusion"] or SEE_OTHER.search(r["conclusion"])]
    out.append(f"## 三、结论里写了「修正」或「见 Lxxx」的条目（{len(fix)} 条，可能互相冲突）")
    out.append("")
    if fix:
        out.append("| 编号 | 分类/主题 | 结论里点到的条目 | 置信度 |")
        out.append("|---|---|---|---|")
        for r in sorted(fix, key=lambda r: r["id"]):
            pointed = sorted({"L" + n for n in LESSON_ID.findall(r["conclusion"])} - {r["id"]})
            out.append(f"| {r['id']} | {r['topic']} | {'、'.join(pointed) or '—'} | {r['confidence']} |")
    else:
        out.append("（没有）")
    out.append("")

    # 四、分类条目数
    counts = {}
    for r in rows.values():
        counts[r["cat"]] = counts.get(r["cat"], 0) + 1
    big = [c for c, n in counts.items() if n > BIG_CAT]
    out.append("## 四、各分类条目数")
    out.append("")
    out.append("| 分类 | 条目数 | 是否超过 15 条 |")
    out.append("|---|---|---|")
    for c, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        out.append(f"| {c} | {n} | {'超过，建议拆细或合并' if n > BIG_CAT else '—'} |")
    out.append("")
    out.append("超过 15 条的分类：" + ("、".join(big) if big else "无"))
    out.append("")

    # 五、主库里还带标记没搬走的（漏搬），以及 archive 现状
    up = [r for r in rows.values() if UPGRADE_MARK.search(r["conclusion"])]
    wd = [r for r in rows.values() if WITHDRAWN.search(r["conclusion"])]
    mg = [r for r in rows.values() if MERGED_MARK.search(r["conclusion"])]
    out.append(f"## 五、主库里带「已升级为规则」「已撤回推荐」「并入」标记还没搬到 archive 的条目（{len(up)} + {len(wd)} + {len(mg)} 条）")
    out.append("")
    if up or wd or mg:
        for r in sorted(up, key=lambda r: r["id"]):
            marks = UPGRADE_MARK.findall(r["conclusion"])
            kind, where = marks[-1] if marks else ("", "")
            note = f"（{len(marks)} 个标记，显示最后一个：{kind}）" if len(marks) > 1 else ""
            out.append(f"- {r['id']} {r['topic']} → {where.strip() or '（没写去向）'}{note}")
        for r in sorted(wd, key=lambda r: r["id"]):
            m = WITHDRAWN.search(r["conclusion"])
            out.append(f"- {r['id']} {r['topic']} → 已撤回推荐（{m.group(1)}）：{m.group(2)}")
        for r in sorted(mg, key=lambda r: r["id"]):
            out.append(f"- {r['id']} {r['topic']} → 并入 {MERGED_MARK.search(r['conclusion']).group(1)}")
        out.append("")
        out.append("这些条目已经有了去向，整行搬到 archive.md 对应的节里；主库只留活条目，grep 分类时就不会再翻到它们。")
    else:
        out.append("（没有；三种标记的条目都已在 archive.md）")
    out.append("")
    if arch:
        kinds = {"已升级为规则": 0, "已撤回推荐": 0, "已并入": 0, "其它": 0}
        for r in arch.values():
            c = r["conclusion"]
            k = ("已并入" if MERGED_MARK.search(c) else "已撤回推荐" if WITHDRAWN.search(c)
                 else "已升级为规则" if UPGRADE_MARK.search(c) else "其它")
            kinds[k] += 1
        out.append(f"archive.md 现有 {len(arch)} 条：" + "、".join(f"{k} {n}" for k, n in kinds.items() if n))
        out.append("")

    # 六、单次观察保质期
    aged = []
    for r in rows.values():
        if SINGLE_MARK not in r["conclusion"] or SOURCE_MULTI.search(r["source"]):
            continue
        try:
            days = (today - datetime.date.fromisoformat(r["date"])).days
        except ValueError:
            continue
        if days >= SINGLE_DAYS:
            aged.append((days, r))
    out.append(f"## 六、单次观察满 {SINGLE_DAYS} 天还没有第二个来源的条目（{len(aged)} 条，归档候选）")
    out.append("")
    if aged:
        out.append("| 编号 | 分类/主题 | 记录日期 | 已过天数 | 结论摘要 |")
        out.append("|---|---|---|---|---|")
        for days, r in sorted(aged, key=lambda x: -x[0]):
            concl = (r["conclusion"][:60] + "…") if len(r["conclusion"]) > 60 else r["conclusion"]
            out.append(f"| {r['id']} | {r['topic']} | {r['date']} | {days} | {concl} |")
        out.append("")
        out.append("只见过一次的现象可能是生成波动。再遇到同题材时优先验证这几条：复现了就在来源里补第二条成片，"
                   "没复现或用不上就搬到 archive.md（结论开头加【<日期> 单次观察到期归档】），不当定律留在主库里。")
    else:
        out.append("（没有）")
    out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
