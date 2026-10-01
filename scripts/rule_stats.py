#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rule_stats.py — 「整理经验」前先跑：每条反模式、每类提醒赚没赚到，看数。只读，不改任何文件。

用法：
  python3 rule_stats.py [--dir <报告目录>] [--days 30] [--today 2026-10-01]

读报告目录（默认环境变量 AIGC_GATE_DIR，没设就是 ~/.aigc-video-gate）里全部 check_prompt 报告（kind=light 的 *.json；
verify_delivery 的全套报告不计）和同目录的 outcomes.jsonl（log_outcome.py 写的成片结果），输出一份 Markdown，三节：
  一、反模式：每个编号的触发次数（一条提醒算一次，含已裁定的）、被裁定次数、在「采用」「部分」「否」成片里触发的次数
      （按 outcomes.jsonl 每行记的编号算，一行算一次）、正式还是候选（按现在的反模式表）。表里的正则行都列，没触发过的也列；
      报告里出现过、表里已经没有的编号排在后面，标「表里已没有」。
  二、提醒类别：总览句 / 父稿句消失 / 复读 / 密度 / 否定句 / 反模式 / 其它，各自总数（待裁定加已裁定）、已裁定条数、裁定率。
  三、最近 N 天（默认 30，含 --today 当天）：新增报告几份、涉及几份不同正文（按 delivered_sha256），有成片结果的几份、占比。
v38 之前的报告没有 antipatterns / hint_types 字段：反模式编号从提醒原文里取，类别用 check_prompt.hint_type 现分。
数字只说明检查器报了什么、作者裁了什么、成片怎么样，不说明因果：采用的成片里触发过某条，不等于那条提醒错了；
改反模式表或写法规则仍按 references/lessons/README.md 的升级门槛。
"""
import argparse, datetime, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_prompt as CP   # 分类函数 hint_type / hint_counts、旧报告用的 ap_refs、反模式表 load_antipatterns

VERDICTS = ("采用", "部分", "否")
OUTCOMES = "outcomes.jsonl"


def gate_dir(arg):
    """报告目录：--dir，其次环境变量 AIGC_GATE_DIR，最后 ~/.aigc-video-gate（与 hooks/stop_gate.py 一致）。"""
    return Path(arg or os.environ.get("AIGC_GATE_DIR") or os.path.expanduser("~/.aigc-video-gate")).expanduser()


def load_reports(d):
    """(轻量报告 [(文件名, 时间, 报告)], 全套报告份数, 读不出的份数)。时间取 created_at，没有就用文件修改时间。"""
    light, full, bad = [], 0, 0
    for p in sorted(d.glob("*.json")) if d.is_dir() else []:
        try:
            rep = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            bad += 1
            continue
        if not isinstance(rep, dict):
            bad += 1
            continue
        if rep.get("kind") != "light":
            full += 1
            continue
        t = rep.get("created_at")
        light.append((p.name, float(t) if isinstance(t, (int, float)) else p.stat().st_mtime, rep))
    return light, full, bad


def load_outcomes(d):
    """(成片结果行, 读不出的行数)。"""
    rows, bad = [], 0
    f = d / OUTCOMES
    if not f.is_file():
        return rows, bad
    for ln in f.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            bad += 1
            continue
        if isinstance(r, dict) and r.get("verdict") in VERDICTS:
            rows.append(r)
        else:
            bad += 1
    return rows, bad


def ap_items(rep):
    """这份报告的反模式提醒 [(编号, 是否已裁定)]：新报告读 antipatterns，旧报告从提醒原文里取。"""
    if isinstance(rep.get("antipatterns"), list):
        return [(it["id"], bool(it.get("adjudicated"))) for it in rep["antipatterns"]
                if isinstance(it, dict) and isinstance(it.get("id"), str)]
    warns = [w for w in rep.get("warnings") or [] if isinstance(w, str)]
    adjs = [w for w in rep.get("adjudicated") or [] if isinstance(w, str)]
    return [(i, False) for i, _s in CP.ap_refs(warns)] + [(i, True) for i, _s in CP.ap_refs(adjs)]


def type_counts(rep):
    """(各类总数, 各类已裁定条数)。新报告的总数读 hint_types，旧报告现分；已裁定的都按 adjudicated 原文现分。"""
    adjs = [w for w in rep.get("adjudicated") or [] if isinstance(w, str)]
    total = rep.get("hint_types")
    if not (isinstance(total, dict) and all(isinstance(total.get(k), int) for k in CP.HINT_TYPES)):
        total = CP.hint_counts([w for w in rep.get("warnings") or [] if isinstance(w, str)] + adjs)
    return total, CP.hint_counts(adjs)


def pct(n, d):
    return f"{n * 100 / d:.0f}%" if d else "—"


def ap_key(i):
    m = re.fullmatch(r"AP(\d+)", i)
    return (int(m.group(1)) if m else 10 ** 6, i)


def main():
    ap = argparse.ArgumentParser(description="汇总报告目录里的检查报告与成片结果，输出 Markdown（只读）")
    ap.add_argument("--dir", default=None, help="报告目录，默认 AIGC_GATE_DIR 或 ~/.aigc-video-gate")
    ap.add_argument("--days", type=int, default=30, help="第三节看最近几天，默认 30")
    ap.add_argument("--today", default=None, help="把哪天当今天（YYYY-MM-DD），默认今天；测试用")
    a = ap.parse_args()
    try:
        today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    except ValueError:
        ap.error("--today 要写成 YYYY-MM-DD")
    if a.days < 1:
        ap.error("--days 至少 1")
    d = gate_dir(a.dir)
    reports, n_full, n_bad = load_reports(d)
    outcomes, n_bad_out = load_outcomes(d)
    table, _notes = CP.load_antipatterns()
    status = {r["id"]: ("候选" if r["candidate"] else "正式") for r in (table or {}).get("rows", [])}
    for i, r in (table or {}).get("code_rows", {}).items():   # 提醒带编号的代码行（AP09）也列；其余代码行的提醒不带编号，不列
        if i in CP.AP_CODE_TAGGED:
            status[i] = "候选" if r["candidate"] else "正式"

    # 一、反模式
    fired, adjudged = {}, {}
    for _name, _t, rep in reports:
        for i, adj in ap_items(rep):
            fired[i] = fired.get(i, 0) + 1
            if adj:
                adjudged[i] = adjudged.get(i, 0) + 1
    by_verdict = {v: {} for v in VERDICTS}
    for r in outcomes:
        for i in dict.fromkeys(x for x in r.get("antipatterns") or [] if isinstance(x, str)):
            by_verdict[r["verdict"]][i] = by_verdict[r["verdict"]].get(i, 0) + 1
    seen = set(fired) | {i for v in by_verdict.values() for i in v}
    ids = sorted(status, key=ap_key) + sorted(seen - set(status), key=ap_key)
    old = sum(1 for _n, _t, rep in reports if not isinstance(rep.get("antipatterns"), list))

    out = ["# 规则统计（rule_stats.py，只读）", "",
           f"报告目录：{d}" + ("（不存在）" if not d.is_dir() else ""),
           f"check_prompt 报告 {len(reports)} 份" + (f"（v38 之前的 {old} 份没有新字段，反模式与类别按提醒原文现算）" if old else "")
           + f"；全套报告 {n_full} 份不计" + (f"；读不出的文件 {n_bad} 份" if n_bad else "") + "。",
           f"成片结果 {len(outcomes)} 条（{OUTCOMES}）："
           + "、".join(f"{v} {sum(1 for r in outcomes if r['verdict'] == v)}" for v in VERDICTS)
           + (f"；读不出的行 {n_bad_out} 行" if n_bad_out else "") + "。"]
    if table is None:
        out.append("反模式表没读出来，下表的「正式 / 候选」列空着。")
    out += ["", "## 一、反模式", "",
            "| 编号 | 正式 / 候选 | 触发 | 被裁定 | 采用成片里触发 | 部分成片里触发 | 否成片里触发 |",
            "|---|---|---|---|---|---|---|"]
    for i in ids:
        out.append(f"| {i} | {status.get(i, '表里已没有' if table else '—')} | {fired.get(i, 0)} | {adjudged.get(i, 0)} | "
                   + " | ".join(str(by_verdict[v].get(i, 0)) for v in VERDICTS) + " |")
    out += ["", "触发 = 检查器报了几条（一镜一条，含已裁定）；成片三列 = outcomes.jsonl 里几行记了这个编号。"
                "代码实现的索引行里只有 AP09 的提醒带编号、列在表里；AP10–AP16 的提醒不带编号，这里不计。"]

    # 二、提醒类别
    tot, adj = dict.fromkeys(CP.HINT_TYPES, 0), dict.fromkeys(CP.HINT_TYPES, 0)
    for _name, _t, rep in reports:
        t_rep, a_rep = type_counts(rep)
        for k in CP.HINT_TYPES:
            tot[k] += t_rep.get(k, 0)
            adj[k] += a_rep.get(k, 0)
    out += ["", "## 二、提醒类别", "", "| 类别 | 总数 | 已裁定 | 裁定率 |", "|---|---|---|---|"]
    for k in CP.HINT_TYPES:
        out.append(f"| {k} | {tot[k]} | {adj[k]} | {pct(adj[k], tot[k])} |")
    st, sa = sum(tot.values()), sum(adj.values())
    out += [f"| 合计 | {st} | {sa} | {pct(sa, st)} |", "",
            "总数 = 待裁定加已裁定；裁定率 = 已裁定 ÷ 总数（只有带 --adjudicated 跑的检查才有已裁定）。密度只算字数密度。"]

    # 三、最近 N 天
    first = today - datetime.timedelta(days=a.days - 1)
    start = datetime.datetime.combine(first, datetime.time.min).timestamp()
    end = datetime.datetime.combine(today + datetime.timedelta(days=1), datetime.time.min).timestamp()
    recent = [(name, rep) for name, t, rep in reports if start <= t < end]
    out_shas = {str(r.get("sha"))[:8] for r in outcomes if r.get("sha")}
    out_reports = {Path(str(r.get("report"))).name for r in outcomes if r.get("report")}
    texts = {}
    for name, rep in recent:
        key = str(rep.get("delivered_sha256") or rep.get("checked_sha256") or name)
        texts[key] = texts.get(key, False) or key[:8] in out_shas or name in out_reports
    with_outcome = sum(1 for v in texts.values() if v)
    out += ["", f"## 三、最近 {a.days} 天（{first.isoformat()} 到 {today.isoformat()}）", "",
            f"新增报告 {len(recent)} 份，涉及 {len(texts)} 份不同正文；有成片结果的 {with_outcome} 份，"
            f"占 {pct(with_outcome, len(texts))}。"]
    print("\n".join(out))


if __name__ == "__main__":
    main()
