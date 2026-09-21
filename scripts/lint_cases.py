#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_cases.py — 案例库体检：可复用点必须落到经验编号或标成样板，索引与条目必须对得上。

用法：
  python3 lint_cases.py [--file <案例库路径>] [--lessons <经验库路径>]

检查项（规则见 references/cases/my-cases.md 头部「写入规则」）：
  1. 条目字段齐全且顺序固定：素材 → 成片文件名 → 我的评价 → 关联经验 → 可复用点 → 提示词原文。
  2. 「关联经验」行非空。
  3. 「可复用点」至少一条，每条要么带 `→ L0xx`（知识，结论在经验库），要么带 `（样板）`（组织方式）。
  4. 条目里引用的每个 L 编号都要在经验库里真的存在。
  5. 索引里每个编号都有条目，每个条目都在索引里；索引每行的「什么时候选它」非空。

全部通过：打印一行统计，退出 0；有问题：逐条打到 stderr，退出 1。
围栏代码块（提示词原文、条目模板）里的内容不参与检查。
"""
import argparse, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CASES = os.path.join(HERE, "..", "references", "cases", "my-cases.md")
DEFAULT_LESSONS = os.path.join(HERE, "..", "references", "lessons", "seedance-2.5.md")

FENCE = re.compile(r"^(`{3,})")
HEADING = re.compile(r"^(#{2,6})\s+(.*)$")
CASE_HEADING = re.compile(r"^(#{2,6})\s+(M\d{3})\s*[｜|]")
INDEX_ROW = re.compile(r"^\|\s*(M\d{3})\s*\|")
LESSON_ID = re.compile(r"L(\d{3})")
KNOWLEDGE = re.compile(r"→\s*L\d{3}")
FIELDS = ["素材：", "成片文件名：", "我的评价：", "关联经验：", "可复用点：", "提示词原文"]


def strip_fences(text):
    """把围栏代码块里的行清空（保留行数，方便报行号）。"""
    lines = text.splitlines()
    out, open_len = [], None
    for ln in lines:
        m = FENCE.match(ln)
        if open_len is None:
            if m:
                open_len = len(m.group(1))
                out.append("")
            else:
                out.append(ln)
        else:
            if m and len(m.group(1)) >= open_len and not ln[len(m.group(1)):].strip():
                open_len = None
            out.append("")
    return out


def lesson_ids(path):
    ids = set()
    for ln in open(path, encoding="utf-8"):
        m = re.match(r"^(L\d{3})\s*\|", ln)
        if m:
            ids.add(m.group(1))
    return ids


def split_entries(lines):
    """返回 [(编号, 起始行号, 行列表)]，按案例标题切开。"""
    starts = [(i, m.group(2)) for i, ln in enumerate(lines) for m in [CASE_HEADING.match(ln)] if m]
    entries = []
    for k, (i, mid) in enumerate(starts):
        end = len(lines)
        for j in range(i + 1, len(lines)):
            if HEADING.match(lines[j]):
                end = j
                break
        entries.append((mid, i + 1, lines[i + 1:end]))
    return entries


def index_rows(lines):
    """返回 [(编号, 行号, 「什么时候选它」单元格)]。"""
    header_cols = None
    rows = []
    for i, ln in enumerate(lines):
        if header_cols is None and ln.startswith("|") and "什么时候选它" in ln:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            header_cols = cells.index("什么时候选它")
            continue
        m = INDEX_ROW.match(ln)
        if m:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            cell = cells[header_cols] if (header_cols is not None and header_cols < len(cells)) else ""
            rows.append((m.group(1), i + 1, cell))
    return rows, header_cols


def lint(text, ids):
    lines = strip_fences(text)
    problems = []

    rows, header_cols = index_rows(lines)
    if header_cols is None:
        problems.append("索引表找不到「什么时候选它」表头")
    indexed = [r[0] for r in rows]
    for mid, lineno, cell in rows:
        if not cell:
            problems.append(f"索引第 {lineno} 行 {mid}：「什么时候选它」是空的")
    for mid in indexed:
        if indexed.count(mid) > 1:
            problems.append(f"索引里 {mid} 出现多次")
            break

    entries = split_entries(lines)
    seen = [e[0] for e in entries]
    for mid in seen:
        if seen.count(mid) > 1:
            problems.append(f"条目 {mid} 出现多次")
            break
    for mid in indexed:
        if mid not in seen:
            problems.append(f"索引里的 {mid} 没有对应条目")
    for mid in seen:
        if mid not in indexed:
            problems.append(f"条目 {mid} 不在索引里")

    for mid, start, body in entries:
        pos = {}
        for i, ln in enumerate(body):
            for f in FIELDS:
                if f not in pos and ln.startswith(f):
                    pos[f] = i
        missing = [f for f in FIELDS if f not in pos]
        if missing:
            problems.append(f"{mid}：缺字段 " + "、".join(x.rstrip("：") for x in missing))
            continue
        order = [pos[f] for f in FIELDS]
        if order != sorted(order):
            problems.append(f"{mid}：字段顺序不对，应当是 " + " → ".join(x.rstrip("：") for x in FIELDS))

        rel = body[pos["关联经验："]][len("关联经验："):].strip()
        if not rel:
            problems.append(f"{mid}：「关联经验」是空的")

        bullets = [(i, ln) for i, ln in enumerate(body[pos["可复用点："] + 1:pos["提示词原文"]], pos["可复用点："] + 1)
                   if ln.startswith("- ")]
        if not bullets:
            problems.append(f"{mid}：「可复用点」下面一条都没有")
        for i, ln in bullets:
            if not (KNOWLEDGE.search(ln) or "（样板）" in ln):
                problems.append(f"{mid} 第 {start + i} 行：可复用点既没有 → L0xx 也没有标（样板）：{ln[:40]}")

        used = set(LESSON_ID.findall(body[pos["关联经验："]]))
        for _, ln in bullets:
            used |= set(LESSON_ID.findall(ln))
        for n in sorted(used):
            if f"L{n}" not in ids:
                problems.append(f"{mid}：引用的 L{n} 在经验库里不存在")

    return len(entries), len(rows), problems


def main():
    ap = argparse.ArgumentParser(description="案例库可复用点与索引检查")
    ap.add_argument("--file", default=DEFAULT_CASES)
    ap.add_argument("--lessons", default=DEFAULT_LESSONS)
    a = ap.parse_args()
    path = os.path.abspath(os.path.expanduser(a.file))
    lessons = os.path.abspath(os.path.expanduser(a.lessons))
    ids = lesson_ids(lessons)
    n, rows, problems = lint(open(path, encoding="utf-8").read(), ids)
    if problems:
        print(f"案例库 {path} 有 {len(problems)} 处问题：", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        print("规则：可复用点要么是知识（带 → L0xx，结论写在经验库里），要么是样板（标（样板））；"
              "关联经验非空；索引与条目一一对应。", file=sys.stderr)
        sys.exit(1)
    print(f"案例库 {n} 条（索引 {rows} 行）：可复用点编号、关联经验与索引对应关系通过")


if __name__ == "__main__":
    main()
