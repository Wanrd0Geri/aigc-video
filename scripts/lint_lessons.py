#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_lessons.py — 经验库体检：每条的第 3 列必须是合法的 `分类/主题`，L 编号必须从 L001 起连续递增。

用法：
  python3 lint_lessons.py [--file <经验库路径>]

全部通过：打印一行统计，退出 0；有问题：逐条打到 stderr，退出 1。
本文件同时是 12 个分类在代码侧的唯一副本，log_lesson.py 与 merge_lessons.py 从这里导入。
"""
import argparse, os, re, sys

# 12 个分类：唯一定义在 references/lessons/README.md 的分类表，改那边时同步改这里（与 README 同步）。
CATS = ["打斗", "多人与站位", "摄影", "景别与画外", "特效与形态", "表演与对白",
        "光影与风格", "素材与参考", "操作命令", "密度与节奏", "声音与文字", "通用"]

LINE = re.compile(r"^(L\d{3})\s*\|")
DEFAULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "references", "lessons", "seedance-2.5.md")


def cats_hint():
    return ("12 个分类（定义见 references/lessons/README.md）："
            + "、".join(CATS)
            + "\n正确示例：--topic \"景别与画外/画外人物\"")


def topic_error(topic):
    """主题列合法返回 None，否则返回一句说明。"""
    t = (topic or "").strip()
    if "/" not in t:
        return f"主题列「{t}」没有分类前缀"
    cat, _, sub = t.partition("/")
    if cat not in CATS:
        return f"分类「{cat}」不在 12 个分类里"
    if not sub.strip():
        return f"主题列「{t}」只有分类没有主题"
    return None


def entry_lines(text):
    return [ln.rstrip() for ln in text.splitlines() if LINE.match(ln)]


def lint(text):
    """返回 (条目数, 问题列表)。"""
    rows = entry_lines(text)
    problems = []
    for i, ln in enumerate(rows, 1):
        nid = LINE.match(ln).group(1)
        parts = ln.split(" | ")
        if len(parts) != 9:
            problems.append(f"{nid}：不是九字段条目（实际 {len(parts)} 段）")
        else:
            err = topic_error(parts[2])
            if err:
                problems.append(f"{nid}：{err}")
        if int(nid[1:]) != i:
            problems.append(f"{nid}：编号不连续，按出现顺序这里应当是 L{i:03d}")
    return len(rows), problems


def main():
    ap = argparse.ArgumentParser(description="经验库分类前缀与编号连续性检查")
    ap.add_argument("--file", default=DEFAULT_FILE)
    a = ap.parse_args()
    path = os.path.abspath(os.path.expanduser(a.file))
    n, problems = lint(open(path, encoding="utf-8").read())
    if problems:
        print(f"经验库 {path} 有 {len(problems)} 处问题：", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        print(cats_hint(), file=sys.stderr)
        sys.exit(1)
    print(f"经验库 {n} 条：分类前缀与编号连续性通过")


if __name__ == "__main__":
    main()
