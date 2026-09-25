#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_lessons.py — 经验库体检：每条的第 3 列必须是合法的 `分类/主题`，主库与 archive.md 合起来的 L 编号必须从 L001 起连续递增。

用法：
  python3 lint_lessons.py [--file <经验库路径>] [--archive <归档路径>]

--archive 不给时，取 --file 同目录下的 archive.md（存在才读）。归档里的条目同样要九字段、分类合法；
同一编号两边都有算问题；编号连续性按两边合集查（v31 起，归档只搬行、不腾编号）。
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


def archive_path_for(path):
    """主库同目录下的 archive.md（v31 归档出口）；不存在返回 None。"""
    cand = os.path.join(os.path.dirname(os.path.abspath(path)), "archive.md")
    return cand if os.path.isfile(cand) else None


def lint(text, archive_text=""):
    """返回 (主库条目数, 问题列表)。archive_text 是归档全文（可空）：格式各查各的，编号连续性按合集查。"""
    rows = entry_lines(text)
    arch = entry_lines(archive_text) if archive_text else []
    problems = []
    for where, lines in (("", rows), ("archive ", arch)):
        for ln in lines:
            nid = LINE.match(ln).group(1)
            parts = ln.split(" | ")
            if len(parts) != 9:
                problems.append(f"{where}{nid}：不是九字段条目（实际 {len(parts)} 段）")
            else:
                err = topic_error(parts[2])
                if err:
                    problems.append(f"{where}{nid}：{err}")
    main_ids = [LINE.match(ln).group(1) for ln in rows]
    arch_ids = [LINE.match(ln).group(1) for ln in arch]
    for nid in sorted(set(main_ids) & set(arch_ids)):
        problems.append(f"{nid}：主库和 archive 里都有，归档要搬行不是复制")
    for name, ids in (("主库", main_ids), ("archive", arch_ids)):
        dup = sorted({x for x in ids if ids.count(x) > 1})
        if dup:
            problems.append(f"{name}编号重复：{dup}")
    all_ids = sorted(set(main_ids) | set(arch_ids), key=lambda x: int(x[1:]))
    for i, nid in enumerate(all_ids, 1):
        if int(nid[1:]) != i:
            problems.append(f"{nid}：编号不连续，主库与 archive 合起来这里应当是 L{i:03d}"
                            + ("" if not arch else "（归档只搬行、不腾编号）"))
            break
    return len(rows), problems


def main():
    ap = argparse.ArgumentParser(description="经验库分类前缀与编号连续性检查")
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--archive", default=None, help="归档路径；不给取 --file 同目录的 archive.md")
    a = ap.parse_args()
    path = os.path.abspath(os.path.expanduser(a.file))
    apath = os.path.abspath(os.path.expanduser(a.archive)) if a.archive else archive_path_for(path)
    atext = open(apath, encoding="utf-8").read() if apath and os.path.isfile(apath) else ""
    n, problems = lint(open(path, encoding="utf-8").read(), atext)
    if problems:
        print(f"经验库 {path} 有 {len(problems)} 处问题：", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        print(cats_hint(), file=sys.stderr)
        sys.exit(1)
    na = len(entry_lines(atext)) if atext else 0
    print(f"经验库 {n} 条" + (f"（archive 另有 {na} 条，编号合集连续）" if atext else "") + "：分类前缀与编号连续性通过")


if __name__ == "__main__":
    main()
