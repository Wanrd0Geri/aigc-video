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
v31 起：编号从主库与同目录 archive.md 的合集里取最大值加一（归档只搬行、不腾编号）；写入后给三种非阻断提醒（stderr）：
  写法 A / B 超过 80 字（整句放案例库，这里只写关键短语）；来源只有一条成片、结论又没标"单次观察"；
  主库里 `<!-- 整理于 … L0xx -->` 标记之后新增满 10 条（该跑「整理经验」了）。
"""
import argparse, datetime, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lint_lessons import cats_hint, topic_error, archive_path_for  # 12 个分类的唯一代码副本在 lint_lessons.py（与 README 同步）

CONF = ["已试", "未试"]
SECTION = "## 七、诊断新增"
WAY_LIMIT = 80          # 写法 A / B 列的建议上限（字），超过只提醒。可调
TIDY_EVERY = 10         # 整理标记之后新增满这么多条就提醒跑「整理经验」。可调
TIDY_MARK = re.compile(r"<!--\s*整理于\s*(\d{4}-\d{2}-\d{2})\s*L(\d{3})\s*-->")
# 来源里像成片定位的东西：mp4 / mov / jimeng-… / 视频节点… / 截图；数到一个且没写"对照 / 两跑 / 三版"就算单条成片
SOURCE_FILE = re.compile(r"\.mp4|\.mov")
SOURCE_NAME = re.compile(r"jimeng-\d{4}-\d{2}-\d{2}-\d+|视频节点\s?\d+|截图")
SOURCE_MULTI = re.compile(r"对照|两跑|两次|三版|三跑|多版|各跑|[2-9]\s*条|[两三四五六七八九]条")


def reminders(a, text_after):
    """写入后的非阻断提醒，返回字符串列表。"""
    out = []
    for name, val in (("写法A", a.a), ("写法B", a.b)):
        if val != "—" and len(val) > WAY_LIMIT:
            out.append(f"{name} 列 {len(val)} 字，超过 {WAY_LIMIT} 字：这里只写关键短语，整句放案例库（references/cases/my-cases.md）")
    hits = len(SOURCE_FILE.findall(a.source)) or len(SOURCE_NAME.findall(a.source))   # 有扩展名按扩展名数，没有再按文件名样式数
    single = hits <= 1 and not SOURCE_MULTI.search(a.source) and "用户实测" not in a.source
    if single and "单次观察" not in a.conclusion:
        out.append("来源只有一条成片、结论没标「单次观察」：只有一次的观察可能是生成波动，结论开头写「单次观察」，"
                   "30 天内没有第二个来源会在整理时列为归档候选")
    m = list(TIDY_MARK.finditer(text_after))
    if m:
        last = int(m[-1].group(2))
        nums = [int(n) for n in re.findall(r"^L(\d{3})\s*\|", text_after, re.M)]
        added = len([n for n in nums if n > last])
        if added >= TIDY_EVERY:
            out.append(f"整理标记 L{last:03d} 之后主库已新增 {added} 条（≥{TIDY_EVERY}）：该跑「整理经验」了"
                       "（python3 scripts/review_lessons.py，改完更新标记）")
    return out


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
    apath = archive_path_for(path)
    if apath:   # 归档只搬行、不腾编号：取号要把 archive 里的编号一起算上
        nums += [int(n) for n in re.findall(r"^L(\d{3})\s*\|", open(apath, encoding="utf-8").read(), re.M)]
    nid = f"L{(max(nums) + 1) if nums else 1:03d}"
    line = f"{nid} | {a.date} | {a.topic} | {a.phenomenon} | {a.a} | {a.b} | {a.conclusion} | {a.confidence} | {a.source}"
    if SECTION not in text:
        text = text.rstrip("\n") + f"\n\n{SECTION}\n\n"
    text = text.rstrip("\n") + "\n" + line + "\n"
    open(path, "w", encoding="utf-8").write(text)
    print(nid)
    for r in reminders(a, text):
        print("提醒：" + r, file=sys.stderr)


if __name__ == "__main__":
    main()
