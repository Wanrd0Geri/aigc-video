#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_lessons.py — 把另一份经验库（通常是安装位）里的新条目合并进当前经验库，按 L 编号判断，不整份覆盖。

用法：
  python3 merge_lessons.py --from ~/.claude/skills/aigc-video/references/lessons/seedance-2.5.md \
      --into /path/to/candidate/references/lessons/seedance-2.5.md [--dry-run]

规则：--from 里有、--into 里没有的 L 编号 → 置信度写成"未试（合并待审）"追加到 --into 末尾；
      两边都有但内容不同的编号 → 不动，打印出来由人判断（候选版可能有意改写了那条）。
      来源里只要有条目的主题列缺合法 `分类/主题` 前缀 → 整次合并拒绝，退出码 1，列出违规编号；
      不静默接受，先去来源里把前缀补上再合。
输出（stdout）四行：`新增 N 条：[...]`／`相同 N 条`／`冲突 N 条（同编号不同内容，未裁定，保留目标）：[...]`／
      `本次写入 N 条`（--dry-run 时是 `dry-run：未写入`）。目标文件先写同目录临时文件，再 os.replace 原子替换。
退出码：0 = 没有冲突；1 = 来源不合法，整次拒绝；3 = 有同编号不同内容的条目——新增条目照常写入（或 dry-run），
      冲突条目保留目标内容、未裁定，合并没算完，待人工裁定。
"""
import argparse, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lint_lessons import cats_hint, topic_error  # 12 个分类的唯一代码副本在 lint_lessons.py（与 README 同步）

LINE = re.compile(r"^(L\d{3,})\s*\|", re.M)
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
    # 目标同目录的 archive.md（v31）：已归档的编号不算"新增"，不会被加回主库
    darch = os.path.join(os.path.dirname(os.path.abspath(dst_path)), "archive.md")
    if os.path.isfile(darch):
        for k, v in entries(open(darch, encoding="utf-8").read()).items():
            de.setdefault(k, v)
    bad = []
    for k in sorted(se):
        parts = se[k].split(" | ")
        if len(parts) != 9:
            bad.append(f"{k}：不是九字段条目（实际 {len(parts)} 段）")
            continue
        err = topic_error(parts[2])
        if err:
            bad.append(f"{k}：{err}")
    if bad:
        sys.exit("来源经验库有条目的主题列不合法，拒绝合并（先在来源里补成 `分类/主题` 再合）：\n  "
                 + "\n  ".join(bad) + "\n" + cats_hint())
    new = [k for k in sorted(se) if k not in de]
    same = [k for k in sorted(se) if k in de and se[k] == de[k]]
    diff = [k for k in sorted(se) if k in de and se[k] != de[k]]
    print(f"新增 {len(new)} 条：{new}")
    print(f"相同 {len(same)} 条")
    print(f"冲突 {len(diff)} 条（同编号不同内容，未裁定，保留目标）：{diff}")
    pending = []
    for k in new:
        parts = se[k].split(" | ")
        if len(parts) != 9:
            raise ValueError(f"{k} 不是九字段条目，未写入；先人工核对")
        parts[8] = f"{parts[8]}（原标：{parts[7]}）"
        parts[7] = "未试（合并待审）"
        pending.append(" | ".join(parts))
    if a.dry_run:
        print("dry-run：未写入")
    elif pending:
        if SECTION not in dst:
            dst = dst.rstrip("\n") + f"\n\n{SECTION}\n\n"
        dst = dst.rstrip("\n") + "\n" + "\n".join(pending) + "\n"
        # 原子替换：先写同目录临时文件，再 os.replace；出错删掉临时文件（与 log_lesson.py 同一写法）
        tmp = dst_path + ".tmp." + str(os.getpid())
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(dst)
            os.replace(tmp, dst_path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        print(f"本次写入 {len(pending)} 条")
        print(f'提醒：主库已更新，请用 build_lessons_index.py --file "{os.path.abspath(dst_path)}" 重建同目录 index.md，再运行 lint_lessons.py。', file=sys.stderr)
    else:
        print("本次写入 0 条")
    if diff:   # 有同编号不同内容：新增已照常处理，但合并没算完，退出码 3 留给人工裁定
        sys.exit(3)


if __name__ == "__main__":
    main()
