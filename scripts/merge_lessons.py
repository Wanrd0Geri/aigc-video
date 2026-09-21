#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_lessons.py — 把另一份经验库（通常是安装位）里的新条目合并进当前经验库，按 L 编号判断，不整份覆盖。

用法：
  python3 merge_lessons.py --from ~/.claude/skills/aigc-video/references/lessons/seedance-2.5.md \
      --into /path/to/candidate/references/lessons/seedance-2.5.md [--dry-run]

规则：--from 里有、--into 里没有的 L 编号 → 置信度写成"未试（合并待审）"追加到 --into 末尾；
      两边都有但内容不同的编号 → 不动，打印出来由人判断（候选版可能有意改写了那条）。
"""
import argparse, os, re, sys

LINE = re.compile(r"^(L\d{3})\s*\|", re.M)
SECTION = "## 七、诊断新增"


def entries(text):
    out = {}
    for ln in text.splitlines():
        m = LINE.match(ln)
        if m:
            if m.group(1) in out:
                raise ValueError("重复经验编号：" + m.group(1))
            out[m.group(1)] = ln.rstrip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--into", dest="dst", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    src = open(os.path.expanduser(a.src), encoding="utf-8").read()
    dst_path = os.path.expanduser(a.dst)
    dst = open(dst_path, encoding="utf-8").read()
    se, de = entries(src), entries(dst)
    new = [k for k in sorted(se) if k not in de]
    diff = [k for k in sorted(se) if k in de and se[k] != de[k]]
    print(f"来源 {len(se)} 条，目标 {len(de)} 条；新增 {len(new)} 条：{new}；两边都有但不同 {len(diff)} 条：{diff}（未裁定；保留目标内容，不代表冲突已解决）")
    if not new:
        return
    if SECTION not in dst:
        dst = dst.rstrip("\n") + f"\n\n{SECTION}\n\n"
    pending = []
    for k in new:
        parts = se[k].split(" | ")
        if len(parts) != 9:
            raise ValueError(f"{k} 不是九字段条目，未写入；先人工核对")
        parts[8] = f"{parts[8]}（原标：{parts[7]}）"
        parts[7] = "未试（合并待审）"
        pending.append(" | ".join(parts))
    if a.dry_run:
        return
    dst = dst.rstrip("\n") + "\n" + "\n".join(pending) + "\n"
    open(dst_path, "w", encoding="utf-8").write(dst)
    print(f"已追加 {len(new)} 条到 {dst_path}")


if __name__ == "__main__":
    main()
