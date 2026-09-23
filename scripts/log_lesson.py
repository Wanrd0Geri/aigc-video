#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
log_lesson.py — 向经验库追加一条记录，自动编号。

用法：
  python3 log_lesson.py --topic "景别与画外/画外人物" --phenomenon "写了曲伯仍在原位，曲伯进了特写" \
      --a "写画外人物状态→被拉进画面" --b "删掉该句→未出现" \
      --conclusion "画外人物不写" --confidence 已试 --source "0916 jimeng-...-3612.mp4"
可选：--date 2026-09-17  --file <经验库路径>
`--topic` 必须写成 `分类/主题`，分类只能用 12 个固定分类之一，脚本强制校验，不合规不写入。
置信度只有两档：已试（本项目有能定位的成片或截图对得上，或用户本人的实测反馈——来源注明“用户实测，未绑定具体成片”并写日期）/ 未试（没有）。
只在获得当次授权后运行；来源要能定位（模型版本、提交稿、成片文件名）。
"""
import argparse, datetime, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lint_lessons import cats_hint, topic_error  # 12 个分类的唯一代码副本在 lint_lessons.py（与 README 同步）

CONF = ["已试", "未试"]
SECTION = "## 七、诊断新增"


def main():
    ap = argparse.ArgumentParser()
    for k in ("topic", "phenomenon", "a", "conclusion", "confidence", "source"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--b", default="—")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--file", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "lessons", "seedance-2.5.md"))
    a = ap.parse_args()
    err = topic_error(a.topic)
    if err:
        sys.exit(f"--topic 必须写成 `分类/主题`：{err}\n" + cats_hint())
    if a.confidence not in CONF:
        sys.exit(f"置信度必须是 {CONF} 之一")
    if any("\n" in x or " | " in x for x in (a.date, a.topic, a.phenomenon, a.a, a.b, a.conclusion, a.source)):
        sys.exit("条目字段不能含换行或字段分隔符")
    path = os.path.abspath(a.file)
    text = open(path, encoding="utf-8").read()
    nums = [int(n) for n in re.findall(r"^L(\d{3})\s*\|", text, re.M)]
    nid = f"L{(max(nums) + 1) if nums else 1:03d}"
    line = f"{nid} | {a.date} | {a.topic} | {a.phenomenon} | {a.a} | {a.b} | {a.conclusion} | {a.confidence} | {a.source}"
    if SECTION not in text:
        text = text.rstrip("\n") + f"\n\n{SECTION}\n\n"
    text = text.rstrip("\n") + "\n" + line + "\n"
    open(path, "w", encoding="utf-8").write(text)
    print(nid)


if __name__ == "__main__":
    main()
