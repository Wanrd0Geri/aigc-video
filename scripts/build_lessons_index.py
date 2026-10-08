#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从主库九字段原样生成四列经验索引；--check 只读，不自动修复。

python3 -X utf8 scripts/build_lessons_index.py [--file 主库] [--index 索引] [--check]
默认主库相对本脚本定位；默认索引为主库同目录 index.md。归档不参与投影。
"""
import argparse
import difflib
import hashlib
import os
from pathlib import Path
import re
import sys
import tempfile

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "references/lessons/seedance-2.5.md"
LINE = re.compile(r"^(L\d{3,})\s*\|")
HEADER = (
    "# 经验结论索引（自动生成）\n\n"
    "只投影主库的编号、分类/主题、结论、置信度；索引不含现象、写法 A/B 和来源。"
    "读取与采用边界见 README「怎么用」。请由 build_lessons_index.py 重建，不手改。\n\n"
    "编号 | 分类/主题 | 结论 | 置信度\n---|---|---|---\n"
)


def parse_entries(text):
    """保持行序与列值；坏条目报错，非条目文本忽略。"""
    entries, seen = [], set()
    for number, line in enumerate(text.splitlines(), 1):
        fields = line.split(" | ")
        if len(fields) == 9 and not fields[0].strip():
            raise ValueError(f"主库第 {number} 行：九字段条目的经验编号为空")
        match = LINE.match(line)
        if not match:
            continue
        lid = match.group(1)
        if len(fields) != 9 or not re.fullmatch(r"L\d{3,}", fields[0]):
            raise ValueError(f"主库第 {number} 行 {lid}：须为用 ' | ' 分隔的九字段条目（实际 {len(fields)} 段）")
        if lid in seen:
            raise ValueError(f"主库第 {number} 行：重复经验编号 {lid}")
        seen.add(lid)
        entries.append((fields[0], fields[2], fields[6], fields[7]))
    return entries


def render_index(entries):
    """固定表头、四列原值和行序；不加时间戳，不摘要或归一化置信度。"""
    return HEADER + "".join(" | ".join(entry) + "\n" for entry in entries)


def check_index(source, index):
    """返回问题列表；按预期完整字节比对，检查头部、编号、顺序与所有列。"""
    source, index = Path(source).expanduser(), Path(index).expanduser()
    try:
        expected = render_index(parse_entries(source.read_text(encoding="utf-8")))
        actual_bytes = index.read_bytes()
        if actual_bytes == expected.encode("utf-8"):
            return []
        actual = actual_bytes.decode("utf-8")
        diff = list(difflib.unified_diff(actual.splitlines(), expected.splitlines(),
                                        fromfile="当前索引", tofile="主库应有投影", lineterm="", n=1))
        detail = "\n".join(diff[:24]) or "文本相同但字节/换行不同（索引要求 UTF-8、LF）。"
        return [f"索引不同步：{index}；请用 build_lessons_index.py --file 重建。\n{detail}"]
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"索引校验失败（主库 {source}，索引 {index}）：{exc}"]


def build_index(source, index):
    """先完整解析，再同目录临时写入并替换；生成中主库变更则拒绝发布。"""
    source, index = Path(source).expanduser().resolve(), Path(index).expanduser().resolve()
    if index in (source, source.with_name("archive.md")):
        raise ValueError("索引输出不能覆盖主库或归档 archive.md")
    original = source.read_bytes()
    entries = parse_entries(original.decode("utf-8"))
    content = render_index(entries).encode("utf-8")
    digest = hashlib.sha256(original).digest()
    index.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix="." + index.name + ".tmp.",
                                         dir=index.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if hashlib.sha256(source.read_bytes()).digest() != digest:
            raise ValueError("主库在生成期间发生变化，本次不发布索引；请重跑。")
        os.replace(temporary, index)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return len(entries)


def main():
    ap = argparse.ArgumentParser(description="生成或只读校验经验四列索引（含原始置信度）")
    ap.add_argument("--file", default=str(DEFAULT_FILE), help="九字段主库路径，不读取归档")
    ap.add_argument("--index", help="索引路径；默认主库同目录 index.md")
    ap.add_argument("--check", action="store_true", help="只读检查；缺失或不同退出1，一致退出0")
    args = ap.parse_args()
    source = Path(args.file).expanduser()
    index = Path(args.index).expanduser() if args.index else source.with_name("index.md")
    if args.check:
        problems = check_index(source, index)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        print(f"索引一致：{index}")
        return 0
    try:
        count = build_index(source, index)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"索引生成失败：{exc}", file=sys.stderr)
        return 1
    print(f"已生成 {count} 条经验索引：{index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
