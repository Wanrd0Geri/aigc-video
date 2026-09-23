#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_lexicon.py — 词库表体检：references/lexicon/*-terms.md 每张表的每一行都是五列，
理解度列只写“档名；证据”或证据（已试 / 未试），“可直接用的中文句”那一列不含空词、解释词、
画质词、引用性措辞和发力过程词。全部通过退出 0；tests/run_check_tests.py 里有一项调用它。
用法：python3 scripts/lint_lexicon.py [--dir references/lexicon]
"""
import argparse, glob, os, re, sys

HEADER_CELLS = 5
BANNED_IN_SENTENCE = re.compile(r"仿佛|似乎|营造|有一种|震撼|唯美|高级感|史诗感|8K|电影级|同上一镜|承接上一镜|转胯|转肩|蓄力过程|力从")
WARN_IN_SENTENCE = re.compile(r"始终|全程|任何时刻|几乎不可察觉|氛围|电影感|高清")
CONF_RE = re.compile(r"^(?:[^；;]*[；;]\s*)?(?:已试|未试)")  # “档名；证据”或只写证据；一格里几个术语各自定档也允许


def split_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def lint_file(path):
    errors, warnings, rows = [], [], 0
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    in_table, header_seen, checking = False, False, False
    for no, ln in enumerate(lines, 1):
        if not ln.startswith("|"):
            in_table = False
            continue
        cells = split_row(ln)
        if set("".join(cells)) <= set("-: "):
            continue  # 分隔行
        if not in_table:
            in_table = True
            # 只体检带“理解度”列的五列词条表；索引表、介质机制表（4 列）、形态词表（3 列）不在此列
            checking = len(cells) == HEADER_CELLS and any("理解度" in c for c in cells)
            header_seen = header_seen or checking
            continue
        if not checking:
            continue
        rows += 1
        if len(cells) != HEADER_CELLS:
            errors.append(f"{path}:{no} 行不是五列（{len(cells)} 列）：{cells[0][:30]}")
            continue
        conf = cells[4]
        if not CONF_RE.match(conf):
            errors.append(f"{path}:{no} 理解度列不合规：{conf[:40]}")
        sent = cells[3]
        m = BANNED_IN_SENTENCE.search(sent)
        if m:
            errors.append(f"{path}:{no} 可用句含禁用词「{m.group(0)}」：{sent[:40]}")
        w = WARN_IN_SENTENCE.search(sent)
        if w:
            warnings.append(f"{path}:{no} 可用句含需核对词「{w.group(0)}」：{sent[:40]}")
    if not header_seen:
        errors.append(f"{path} 没有找到带“理解度”列的五列词条表")
    return rows, errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "lexicon"))
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.dir, "*-terms.md")))
    total, errors, warnings = 0, [], []
    per = []
    for p in files:
        rows, e, w = lint_file(p)
        total += rows
        errors += e
        warnings += w
        per.append(f"{os.path.basename(p)} {rows} 条")
    for w in warnings:
        print("提醒 " + w)
    for e in errors:
        print("错误 " + e)
    print(f"词库 {len(files)} 张表、{total} 条：{'通过' if not errors else '不通过（' + str(len(errors)) + ' 处错误）'}｜" + "，".join(per))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
