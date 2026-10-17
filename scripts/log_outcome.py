#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
log_outcome.py — 用户评价成片之后，记一行「这份稿交出去，成片怎么样」，给 rule_stats.py 算每条规则赚没赚到。

用法：
  python3 log_outcome.py --sha <8 位 sha 或报告路径> --video "<成片文件名>" --verdict 采用|部分|否 [--note "..."] [--lesson L###]
可选：--dir <报告目录>（默认环境变量 AIGC_GATE_DIR，没设就是 ~/.aigc-video-gate，和 hooks/stop_gate.py 同一个目录）

--sha 写交付检查行里的 sha 短哈希（check_prompt 的 summary 末尾那 8 位），也可以直接给报告文件路径。
按 sha 找报告：报告目录里 delivered_sha256 或 checked_sha256 以它开头的报告，check_prompt 的轻量报告（kind=light）优先，
同一 sha 有几份时取最新的一份。找不到就报错退出 1，什么都不写。
写入：往报告目录下的 outcomes.jsonl 追加一行 JSON——时间、sha、报告、成片、评价、备注、经验编号、这份报告触发的反模式编号
（含已裁定的，去重保序）、裁定掉的反模式编号、模式、报告的 skill_version。v38 之前的报告没有 antipatterns / mode 字段：
反模式编号从提醒原文里取，模式记 null。
和记经验并列：用户评价一次成片，记经验用 log_lesson.py（要授权），记结果用本脚本，两条命令。
只追加，不改已有的行；记错了到 outcomes.jsonl 里手工删掉那一行。
"""
import argparse, datetime, json, os, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_prompt import ap_refs   # 提醒原文里的反模式编号（v38 之前的报告用）

VERDICTS = ("采用", "部分", "否")
OUTCOMES = "outcomes.jsonl"
SHA_RE = re.compile(r"[0-9a-f]{8,64}")


def gate_dir(arg):
    """报告目录：--dir，其次环境变量 AIGC_GATE_DIR，最后 ~/.aigc-video-gate（与 hooks/stop_gate.py 一致）。"""
    return Path(arg or os.environ.get("AIGC_GATE_DIR") or os.path.expanduser("~/.aigc-video-gate")).expanduser()


def load_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def find_reports(d, prefix):
    """报告目录里 sha 以 prefix 开头的报告 [(报告, 路径)]：轻量报告在前，同类里新的在前。"""
    found = []
    for p in sorted(d.glob("*.json")):
        rep = load_json(p)
        if rep is None:
            continue
        if any(str(rep.get(k) or "").startswith(prefix) for k in ("delivered_sha256", "checked_sha256")):
            t = rep.get("created_at")
            t = float(t) if isinstance(t, (int, float)) else p.stat().st_mtime
            found.append((rep.get("kind") == "light", t, p, rep))
    found.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [(rep, p) for _light, _t, p, rep in found]


def ap_ids(rep):
    """(触发的反模式编号, 裁定掉的反模式编号)，都去重保序。新报告读 antipatterns / adjudicated_ids，旧报告从提醒原文里取。"""
    if isinstance(rep.get("antipatterns"), list):
        fired = [it.get("id") for it in rep["antipatterns"] if isinstance(it, dict) and it.get("id")]
        adj = [x for x in rep.get("adjudicated_ids") or [] if isinstance(x, str)]
    else:
        warns = [w for w in rep.get("warnings") or [] if isinstance(w, str)]
        adjs = [w for w in rep.get("adjudicated") or [] if isinstance(w, str)]
        fired = [i for i, _shot in ap_refs(warns + adjs)]
        adj = [i for i, _shot in ap_refs(adjs)]
    return list(dict.fromkeys(fired)), list(dict.fromkeys(adj))


def main():
    ap = argparse.ArgumentParser(description="用户评价成片后，往报告目录的 outcomes.jsonl 记一行结果")
    ap.add_argument("--sha", required=True, help="交付检查行里的 sha 短哈希（8 位），或一份报告文件的路径")
    ap.add_argument("--video", required=True, help="成片文件名")
    ap.add_argument("--verdict", required=True, choices=VERDICTS, help="用户的评价：采用 / 部分 / 否")
    ap.add_argument("--note", default="", help="备注（用户原话摘录、哪里好哪里不好）")
    ap.add_argument("--lesson", default=None, help="这次评价记进经验库的编号 L###，没记就不写")
    ap.add_argument("--dir", default=None, help="报告目录，默认 AIGC_GATE_DIR 或 ~/.aigc-video-gate")
    a = ap.parse_args()
    if not a.video.strip():
        ap.error("--video 不能为空")
    if a.lesson is not None and not re.fullmatch(r"L\d{3,}", a.lesson):
        ap.error("--lesson 要写成经验库编号 L###")
    d = gate_dir(a.dir)
    given = Path(a.sha).expanduser()
    extra = ""
    if given.is_file():
        rep, path = load_json(given), given
        if rep is None:
            sys.exit(f"报告读不出来（不是 JSON 对象）：{given}")
    else:
        prefix = a.sha.strip().lower()
        if not SHA_RE.fullmatch(prefix):
            ap.error("--sha 要写交付检查行里的 8 位 sha（十六进制），或一份报告文件的路径")
        hits = find_reports(d, prefix) if d.is_dir() else []
        if not hits:
            n = len(list(d.glob("*.json"))) if d.is_dir() else 0
            sys.exit(f"找不到 sha {prefix} 对应的检查报告（在 {d} 里看了 {n} 份）；"
                     f"核对交付检查行里的 sha，或直接给报告文件路径。这次没有写入")
        rep, path = hits[0]
        if len(hits) > 1:
            extra = f"（同一 sha 有 {len(hits)} 份报告，取最新的 {path.name}）"
    fired, adj = ap_ids(rep)
    sha8 = str(rep.get("delivered_sha256") or rep.get("checked_sha256") or "")[:8] or None
    in_dir = path.resolve().parent == d.resolve()
    row = {
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sha": sha8, "report": path.name if in_dir else str(path.resolve()),
        "video": a.video.strip(), "verdict": a.verdict, "note": a.note.strip(), "lesson": a.lesson,
        "antipatterns": fired, "adjudicated_ids": adj,
        "mode": rep.get("mode"),                     # v38 之前的报告没有这个字段，记 null
        "skill_version": rep.get("skill_version"),   # 出这份报告的检查器版本
    }
    d.mkdir(parents=True, exist_ok=True)
    out = d / OUTCOMES
    with open(out, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"已记：sha {sha8}｜{a.verdict}｜{row['video']}｜反模式 {'、'.join(fired) or '无'}｜已裁定 {'、'.join(adj) or '无'}"
          f"｜模式 {row['mode'] or '未记录'}{extra} → {out}")


if __name__ == "__main__":
    main()
