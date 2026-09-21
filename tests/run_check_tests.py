#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_prompt.py 回归：python3 tests/run_check_tests.py  （全部通过退出 0）"""
import hashlib, json, pathlib, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parent.parent
C = ROOT / "tests" / "check_cases"
S = ROOT / "scripts" / "check_prompt.py"
T = ROOT / "tests"
CASES = [
    # (名称, 文件, 参数, 期望退出码)
    ("五段新稿合法 12 秒两镜", "control_valid.txt", ["--total", "12"], 0),
    # ---- 五段外壳（新稿默认）与六段旧壳的继承 ----
    ("六段新稿无父稿：默认五段会拦", "six_section_new.txt", ["--total", "12"], 1),
    ("六段新稿显式 --format 六段 通过", "six_section_new.txt", ["--format", "六段", "--total", "12"], 0),
    ("六段父稿修订成五段：外壳没有继承父稿", "control_valid.txt", ["--baseline", str(C / "six_section_new.txt"), "--total", "12"], 1),
    ("六段父稿修订仍是六段：通过", "six_section_revised.txt", ["--baseline", str(C / "six_section_new.txt"), "--total", "12"], 0),
    ("五段延长：必填词在情节段开头，通过", "extend_ok.txt", ["--task", "延长", "--total", "5", "--labels", "视频1"], 0),
    ("五段延长：情节段开头缺必填词", "extend_five_missing_command.txt", ["--task", "延长", "--total", "5", "--labels", "视频1"], 1),
    ("五段编辑：必填词在情节段开头，通过", "edit_ok.txt", ["--task", "编辑", "--labels", "视频1,图片1"], 0),
    ("时间空隙", "timeline_gap.txt", ["--total", "12"], 1),
    ("时间空隙 + 情节段开头含“增加”", "timeline_gap_with_increase.txt", ["--total", "12"], 1),
    ("总时长错 + 情节段开头含“增加”", "timeline_wrong_total_with_increase.txt", ["--total", "12"], 1),
    ("重复镜号", "duplicate_shot_id.txt", ["--total", "12"], 1),
    ("跳号", "skipped_shot_id.txt", ["--total", "12"], 1),
    ("没有外壳", "missing_shell.txt", ["--total", "12"], 1),
    ("泄露 m4a", "leak_m4a.txt", ["--total", "12"], 1),
    ("泄露 flac", "leak_flac.txt", ["--total", "12"], 1),
    ("泄露 /tmp 路径", "leak_tmp_path.txt", ["--total", "12"], 1),
    ("固定句重复", "duplicate_closing.txt", ["--total", "12"], 1),
    ("台词里的“上次”合法", "legit_dialogue_shangci.txt", ["--total", "12"], 0),
    ("台词外的“像上次”仍拦", "ref_wording_outside_dialogue.txt", ["--total", "12"], 1),
    ("未声明素材", "labels_two_used.txt", ["--total", "12", "--labels", "图片1"], 1),
    ("素材声明匹配", "labels_two_used.txt", ["--total", "12", "--labels", "图片1,图片2"], 0),
    ("结尾 4 条否定（合算）通过", "four_negatives_ok.txt", ["--total", "12"], 0),
    ("结尾 5 条否定拦下", "five_negatives.txt", ["--total", "12"], 1),
    ("修改标记泄露", "marker_leak.txt", ["--total", "12"], 1),
    ("修订继承旧四段外壳", "inherit_old_changed.txt", ["--task", "生成", "--baseline", str(C / "inherit_old_source.txt"), "--total", "12"], 0),
    ("旧写法 --task 修订 仍可用", "inherit_old_changed.txt", ["--task", "修订", "--baseline", str(C / "inherit_old_source.txt"), "--total", "12"], 0),
    ("旧四段稿按六段检查会拦（对照）", "inherit_old_changed.txt", ["--task", "生成", "--baseline", str(C / "inherit_old_source.txt"), "--format", "六段", "--total", "12"], 1),
    ("锁定台词被改", "lock_changed.txt", ["--task", "生成", "--baseline", str(C / "lock_source.txt"), "--lock", "等我回来。", "--total", "12"], 1),
    ("锁定台词保留", "lock_source.txt", ["--task", "生成", "--baseline", str(C / "lock_source.txt"), "--lock", "等我回来。", "--total", "12"], 0),
    ("未改镜头 1 被动", "lock_kept_shot1_changed.txt", ["--task", "生成", "--baseline", str(C / "lock_source.txt"), "--unchanged", "1", "--total", "12"], 1),
    ("未改镜头 1 未动", "lock_kept_shot1_changed.txt", ["--task", "生成", "--baseline", str(C / "lock_source.txt"), "--unchanged", "2", "--total", "12"], 0),
    ("局部替换镜头 2", "partial_shot2.txt", ["--task", "生成", "--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], 0),
    ("局部替换镜号不在父稿", "partial_shot3_missing.txt", ["--task", "生成", "--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], 1),
    ("局部替换改了时码", "partial_shot2_retimed.txt", ["--task", "生成", "--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], 1),
    ("局部替换段自带固定句（合成后重复）", "partial_shot2_with_closing.txt", ["--task", "生成", "--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], 1),
    ("白模预演无时码", "untimed_baimo.txt", ["--untimed", "--labels", "视频1,图片1"], 0),
    ("有意静止只给警告", "static_locked.txt", ["--total", "12"], 0),
        ("延长缺官方约束句", "extend_missing_constraint.txt", ["--task", "延长", "--total", "5"], 1),
    ("延长写成参考", "extend_as_reference.txt", ["--task", "延长", "--total", "5"], 1),
    ("编辑命令区间不从 0 开始", "edit_ok.txt", ["--task", "编辑", "--labels", "视频1,图片1"], 0),
    # ---- 复审补充的组合边界（B/C 编号沿用复审报告）----
    ("C06 文件名后接标点", "C06_leak_punct.txt", ["--total", "12"], 1),
    ("C07 锁定英文台词被改", "C07_lock_changed_en.txt", ["--baseline", str(C / "english_source.txt"), "--lock", "I am ready.", "--total", "12"], 1),
    ("B01 旧稿标题全删仍算继承？", "B01_inherited_headings_removed.txt", ["--baseline", str(C / "inherit_old_source.txt"), "--total", "12"], 1),
    ("B01b 旧稿标题乱序", "old_shell_reordered.txt", ["--baseline", str(C / "inherit_old_source.txt"), "--total", "12"], 1),
    ("B02 六段标题重复（显式六段）", "B02_duplicate_six_section.txt", ["--format", "六段", "--total", "12"], 1),
    ("B03 局部段前缀带文件名", "B03_partial_prefix_leak.txt", ["--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], 1),
    ("B04 局部段尾部带结尾", "B04_partial_tail_leak.txt", ["--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], 1),
    ("B05 局部段镜号重复", "B05_partial_duplicate_shot.txt", ["--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], 1),
    ("B06 局部模式改了 --unchanged 镜头", "partial_shot2.txt", ["--baseline", str(C / "control_valid.txt"), "--partial", "--unchanged", "2", "--total", "12"], 1),
    ("B07 旧四段稿替换末镜保留固定句", "partial_shot2.txt", ["--baseline", str(C / "inherit_old_source.txt"), "--partial", "--total", "12"], 0),
    ("B08 固定句拆开", "B08_reversed_closing.txt", ["--total", "12"], 1),
    ("B09 固定句后另起一行", "B09_nonterminal_closing.txt", ["--total", "12"], 1),
    ("固定句同一行后接其他否定（合法）", "closing_same_line_extra.txt", ["--total", "12"], 0),
    ("B10 文件名紧邻中文 m4a", "B10_chinese_adjacent_m4a.txt", ["--total", "12"], 1),
    ("B11 文件名紧邻中文 png", "B11_chinese_adjacent_png.txt", ["--total", "12"], 1),
    ("B12 编辑命令作为修订稿", "edit_ok.txt", ["--task", "编辑", "--baseline", str(C / "edit_ok.txt"), "--labels", "视频1,图片1"], 0),
    ("B12b 编辑命令用旧写法 --task 修订", "edit_ok.txt", ["--task", "修订", "--baseline", str(C / "edit_ok.txt"), "--labels", "视频1,图片1"], 0),
    ("B13 延长约束句只写一半", "B13_extend_half_sentence.txt", ["--task", "延长", "--total", "5"], 1),
    ("B14 延长稿修订时删掉约束句", "B14_extend_revision_no_constraint.txt", ["--task", "修订", "--baseline", str(C / "extend_ok.txt"), "--total", "5"], 1),
    ("B15 锁定英文台词空格被删", "B15_lock_whitespace.txt", ["--baseline", str(C / "english_source.txt"), "--lock", "I am ready.", "--total", "12"], 1),
    ("B16 未改镜头英文空格被删", "B15_lock_whitespace.txt", ["--baseline", str(C / "english_source.txt"), "--unchanged", "2", "--total", "12"], 1),
    # ---- 第五版补充 ----
    ("Q02 两镜局部段中间夹结尾与文件名", "Q02_partial_mid_tail.txt", ["--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], 1),
    ("Q02b 两镜局部段合法", "Q02b_partial_two_shots_ok.txt", ["--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], 0),
    ("Q05 六段全空（显式六段）", "Q05_empty_sections.txt", ["--format", "六段", "--total", "12"], 1),
    ("Q05b 镜头只有标题", "Q05b_empty_shot.txt", ["--total", "12"], 1),
    ("五条否定：按句声明例外后放行", "five_negatives.txt", ["--total", "12", "--negative-exception", "不出现现代物品。"], 0),
    ("五条否定：例外句不在结尾里", "five_negatives.txt", ["--total", "12", "--negative-exception", "不出现猫。"], 1),
    ("五条否定：只写理由不点句仍拦", "five_negatives.txt", ["--total", "12", "--negative-exception", "质量需要"], 1),
    ("g02 例外重复同一句不计数", "six_negatives.txt", ["--total", "12", "--negative-exception", "不出现水印。；不出现水印。"], 1),
    ("g03 例外写成片段不计数", "six_negatives.txt", ["--total", "12", "--negative-exception", "水；印"], 1),
    ("六条否定：两条独立整句例外放行", "six_negatives.txt", ["--total", "12", "--negative-exception", "不出现水印。；不出现反光。"], 0),
    ("密度：每秒 2 拍也提醒（只提醒）", "dense_two_per_second.txt", ["--total", "12"], 0),
    ("弱运镜措辞只提醒", "weak_motion.txt", ["--total", "12"], 0),
    ("动作过密只提醒", "dense_beats.txt", ["--total", "12"], 0),
    ("B17 修订稿锁定 5 条否定只提醒", "five_negatives.txt", ["--baseline", str(C / "five_negatives.txt"), "--lock", "不添加字幕，不添加背景音乐。不出现第二个人。不出现文字水印。不出现多余武器。不出现现代物品。", "--total", "12"], 0),
    ("样例：打斗 12 秒", "../sample-combat-12s.txt", ["--total", "12", "--labels", "图片1,图片2,图片3"], 0),
    ("样例：对话 12 秒", "../sample-dialogue-12s.txt", ["--total", "12", "--labels", "图片1,图片2"], 0),
]
fails = 0
for name, f, args, want in CASES:
    p = subprocess.run([sys.executable, str(S), "--prompt", str(C / f), *args], text=True, capture_output=True)
    try:
        d = json.loads(p.stdout)
    except Exception:
        d = {"errors": [p.stderr.strip()[:200]]}
    ok = p.returncode == want
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {name} | exit {p.returncode} (期望 {want}) | errors={d.get('errors', [])[:2]}")
# 弱运镜与密度提醒必须真的出现在 warnings 里
for f, key in [("weak_motion.txt", "弱措辞"), ("dense_beats.txt", "节拍"), ("dense_two_per_second.txt", "节拍")]:
    p = subprocess.run([sys.executable, str(S), "--prompt", str(C / f), "--total", "12"], text=True, capture_output=True)
    d = json.loads(p.stdout); ok = any(key in w for w in d["warnings"]); fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {f} 触发“{key}”提醒 |", [w for w in d["warnings"] if key in w][:1])

# ---- --report：写出的 JSON 要能被 hooks/stop_gate.py 直接用 ----
def hook_digest(text):
    """与 hooks/stop_gate.py 的 digest(normalize(body)) 同源：按行拆分再用换行拼回后取 SHA-256。"""
    return hashlib.sha256("\n".join(text.splitlines()).encode("utf-8")).hexdigest()


REPORT_CASES = [
    # (名称, 文件, 参数, 期望 ready, 期望退出码)
    ("--report 合法稿：ready=true", "control_valid.txt", ["--total", "12"], True, 0),
    ("--report 有错误的稿：ready=false 但照样写报告", "duplicate_shot_id.txt", ["--total", "12"], False, 1),
    ("--report 局部段：delivered 与 checked 分开", "partial_shot2.txt",
     ["--baseline", str(C / "control_valid.txt"), "--partial", "--total", "12"], True, 0),
]
with tempfile.TemporaryDirectory() as tmp:
    for i, (name, f, args, want_ready, want_code) in enumerate(REPORT_CASES):
        rp = pathlib.Path(tmp) / f"新建目录{i}" / "r.json"      # 目录不存在也要能写
        p = subprocess.run([sys.executable, str(S), "--prompt", str(C / f), *args, "--report", str(rp)],
                           text=True, capture_output=True)
        body = (C / f).read_text(encoding="utf-8")
        why = []
        if p.returncode != want_code:
            why.append(f"退出码 {p.returncode}（期望 {want_code}）")
        if not rp.exists():
            why.append("报告没写出来")
        else:
            rep = json.loads(rp.read_text(encoding="utf-8"))
            out = json.loads(p.stdout)
            if rep.get("kind") != "light":
                why.append(f"kind={rep.get('kind')}")
            if rep.get("ready") is not want_ready:
                why.append(f"ready={rep.get('ready')}（期望 {want_ready}）")
            if bool(rep.get("errors")) != (not want_ready):
                why.append("errors 与 ready 不一致")
            if rep.get("errors") != out.get("errors"):
                why.append("报告的 errors 与 stdout 不一致")
            if rep.get("delivered_sha256") != hook_digest(body):
                why.append("delivered_sha256 与钩子 digest 对不上")
            if rep.get("checked_sha256") != out.get("checked_sha256"):
                why.append("checked_sha256 与 stdout 对不上")
            if "--partial" in args:
                if rep["delivered_sha256"] == rep["checked_sha256"]:
                    why.append("--partial 时 delivered 应当是局部段、checked 应当是合成完整稿，两者不该相同")
                if f"sha {rep['delivered_sha256'][:8]}" not in rep.get("summary", ""):
                    why.append("summary 的 sha 短哈希不是 delivered 前 8 位")
            else:
                if rep["delivered_sha256"] != rep["checked_sha256"]:
                    why.append("非 --partial 时 delivered 应当等于 checked")
                if rep.get("checked_sha256") != hook_digest(body):
                    why.append("checked_sha256 与钩子 digest 对不上")
            if not isinstance(rep.get("created_at"), (int, float)):
                why.append("created_at 不是时间戳")
            if "session_id" not in rep:
                why.append("缺 session_id")
        fails += 0 if not why else 1
        print(("PASS" if not why else "FAIL"), f"| {name} |", "；".join(why) or "ok")

TOTAL = len(CASES) + 3 + len(REPORT_CASES)
print(f"\n{TOTAL - fails}/{TOTAL} 通过")
sys.exit(1 if fails else 0)
