#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
review_lessons.py — 「整理经验」用的候选清单生成器：只读、只输出，不改任何文件。

用法：
  python3 review_lessons.py [--file <经验库>] [--cases <案例库>]

输出一份 Markdown 清单，五节：
  一、被 2 条以上案例引用的经验（多次复用，优先考虑升级成规则）
  二、同分类里主题相近、可能能合并的条目对
  三、结论里写了"修正"或"见 L0xx"的条目（互相修正，可能已经冲突）
  四、各分类条目数（超过 15 条的点名）
  五、已经标了「已升级为规则」的条目

清单只是候选，改不改、怎么改由用户挑：
  - 升级到 SKILL.md 或工艺卡的，把规则写进那份文件，并在原条目「结论」列末尾加
    `【已升级为规则：<文件> <节>】`（其它列不动）；
  - 合并的，保留编号靠前的一条，后一条的「结论」列末尾加 `【并入 L0xx】`。
跑的频率：每新增约 10 条经验或 3 条案例跑一次，或用户随时喊「整理经验」。
"""
import argparse, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lint_cases import strip_fences, split_entries, LESSON_ID  # 案例解析与 lint_cases 共用

DEFAULT_LESSONS = os.path.join(HERE, "..", "references", "lessons", "seedance-2.5.md")
DEFAULT_CASES = os.path.join(HERE, "..", "references", "cases", "my-cases.md")
ENTRY = re.compile(r"^(L\d{3})\s*\|")
CJK = re.compile(r"[一-鿿]+")
BIG_CAT = 15


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
    a = ap.parse_args()
    lpath = os.path.abspath(os.path.expanduser(a.file))
    cpath = os.path.abspath(os.path.expanduser(a.cases))
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
           if "修正" in r["conclusion"] or re.search(r"见\s*L0", r["conclusion"])]
    out.append(f"## 三、结论里写了「修正」或「见 L0xx」的条目（{len(fix)} 条，可能互相冲突）")
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

    # 五、已升级
    up = [r for r in rows.values() if "已升级" in r["conclusion"]]
    out.append(f"## 五、已经标了「已升级为规则」的条目（{len(up)} 条）")
    out.append("")
    if up:
        for r in sorted(up, key=lambda r: r["id"]):
            m = re.search(r"【已升级为规则：([^】]*)】", r["conclusion"])
            out.append(f"- {r['id']} {r['topic']} → {m.group(1) if m else '（没写去向）'}")
        out.append("")
        out.append("这些条目仍会被 grep 到，不用专门跳过；同一件事以规则文件里的写法为准。")
    else:
        out.append("（没有）")
    out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
