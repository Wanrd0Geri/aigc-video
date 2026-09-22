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
    ("四段新稿合法 12 秒两镜（末行固定句）", "control_valid.txt", ["--total", "12"], 0),
    # ---- 四段外壳（新稿默认）与旧壳（五段 / 六段）的继承 ----
    ("四段新稿写了结尾标题：拦下", "four_with_end_heading.txt", ["--total", "12"], 1),
    ("四段新稿用旧固定句：拦下", "four_old_closing.txt", ["--total", "12"], 1),
    ("四段固定句不在最后一行：拦下", "B09_nonterminal_closing.txt", ["--total", "12"], 1),
    ("四段固定句被拆开：拦下", "B08_reversed_closing.txt", ["--total", "12"], 1),
    ("四段固定句同一行后接否定：拦下", "closing_same_line_extra.txt", ["--total", "12"], 1),
    ("四段末尾放否定句：拦下（末尾只留固定句）", "tail_negatives_blocked.txt", ["--total", "12"], 1),
    ("四段否定写在镜内：通过（逐句提醒）", "inline_negative.txt", ["--total", "12"], 0),
    ("四段镜内否定用 --negative-exception 点名：通过且不再提醒", "inline_negative.txt", ["--total", "12", "--negative-exception", "不出现第二个白猿。"], 0),
    ("六段新稿无父稿：默认四段会拦", "six_section_new.txt", ["--total", "12"], 1),
    ("六段新稿显式 --format 六段 通过", "six_section_new.txt", ["--format", "六段", "--total", "12"], 0),
    ("五段旧稿显式 --format 五段 通过", "five_section_old.txt", ["--format", "五段", "--total", "12"], 0),
    ("五段旧稿无父稿：默认四段会拦", "five_section_old.txt", ["--total", "12"], 1),
    ("六段父稿修订成四段：外壳没有继承父稿", "control_valid.txt", ["--baseline", str(C / "six_section_new.txt"), "--total", "12"], 1),
    ("六段父稿修订仍是六段旧句：通过", "six_section_revised.txt", ["--baseline", str(C / "six_section_new.txt"), "--total", "12"], 0),
    ("六段父稿修订改成新固定句：未授权迁移，拦下", "six_section_new_closing.txt", ["--baseline", str(C / "six_section_new.txt"), "--total", "12"], 1),
    ("五段父稿修订仍是五段旧句：通过", "five_section_revised.txt", ["--baseline", str(C / "five_section_old.txt"), "--total", "12"], 0),
    ("五段父稿修订成四段新句：未授权迁移，拦下", "five_section_migrated.txt", ["--baseline", str(C / "five_section_old.txt"), "--total", "12"], 1),
    ("四段延长：必填词与约束句都在命令区，通过", "extend_ok.txt", ["--task", "延长", "--total", "5", "--labels", "视频1"], 0),
    ("四段延长：情节段开头缺必填词", "extend_five_missing_command.txt", ["--task", "延长", "--total", "5", "--labels", "视频1"], 1),
    ("四段延长：约束句写在固定句之后", "extend_constraint_after_closing.txt", ["--task", "延长", "--total", "5", "--labels", "视频1"], 1),
    ("四段延长：约束句写在末尾固定句之前", "extend_constraint_at_tail.txt", ["--task", "延长", "--total", "5", "--labels", "视频1"], 1),
    ("四段编辑：必填句都在命令区，通过", "edit_ok.txt", ["--task", "编辑", "--labels", "视频1,图片1"], 0),
    # ---- v16：素材写 图N / 视频N / 音频N（不写 @），每份只绑一次；风格段只写画面质感 ----
    ("四段新稿不写 @、各绑一次：通过且无相关提醒", "no_at_refs.txt", ["--total", "12", "--labels", "图1,图2,音频1"], 0),
    ("四段新稿写了 @：通过但提醒不写 @", "at_refs_in_new_draft.txt", ["--total", "12", "--labels", "图1,图2,音频1"], 0),
    ("素材在两段都写职责：通过但提醒", "asset_bound_twice.txt", ["--total", "12", "--labels", "图1,图4"], 0),
    ("跨段重复长句：通过但提醒", "cross_section_dup.txt", ["--total", "12"], 0),
    ("风格段含时序与俯冲：通过但提醒", "style_has_sequence.txt", ["--total", "12"], 0),
    ("风格段只有质感与镜头性格：通过", "style_clean.txt", ["--total", "12"], 0),
    ("编辑命令不写 @（编辑视频1）：通过", "edit_no_at.txt", ["--task", "编辑", "--labels", "视频1,图1"], 0),
    ("--labels 短写法 图1,图2：通过", "labels_short_form.txt", ["--total", "12", "--labels", "图1,图2"], 0),
    ("--labels 长写法 图片1,图片2 归一后同样匹配", "labels_short_form.txt", ["--total", "12", "--labels", "图片1,图片2"], 0),
    ("旧夹具的 @ 写法仍然通过（只多一条提醒）", "labels_two_used.txt", ["--total", "12", "--labels", "图1,图2"], 0),
    ("四段编辑：“保持…”句写在末尾固定句之前", "edit_keep_at_tail.txt", ["--task", "编辑", "--labels", "视频1,图片1"], 1),
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
    ("五段旧壳结尾段 4 条否定（合算）通过", "five_section_four_negatives.txt", ["--format", "五段", "--total", "12"], 0),
    ("五段旧壳结尾段 5 条否定拦下", "five_section_five_negatives.txt", ["--format", "五段", "--total", "12"], 1),
    ("四段旧式结尾（4 条否定 + 固定句）：末尾只留固定句，拦下", "legacy_tail_four_negatives.txt", ["--total", "12"], 1),
    ("修改标记泄露", "marker_leak.txt", ["--total", "12"], 1),
    ("修订继承旧壳（无结尾标题、旧固定句）", "inherit_old_changed.txt", ["--task", "生成", "--baseline", str(C / "inherit_old_source.txt"), "--total", "12"], 0),
    ("旧写法 --task 修订 仍可用", "inherit_old_changed.txt", ["--task", "修订", "--baseline", str(C / "inherit_old_source.txt"), "--total", "12"], 0),
    ("旧壳稿按六段检查会拦（对照）", "inherit_old_changed.txt", ["--task", "生成", "--baseline", str(C / "inherit_old_source.txt"), "--format", "六段", "--total", "12"], 1),
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
    ("B07 旧壳（无结尾标题）稿替换末镜保留固定句", "partial_shot2.txt", ["--baseline", str(C / "inherit_old_source.txt"), "--partial", "--total", "12"], 0),
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
    ("五段结尾段五条否定：按句声明例外后放行", "five_section_five_negatives.txt", ["--format", "五段", "--total", "12", "--negative-exception", "不出现现代物品。"], 0),
    ("五段结尾段五条否定：例外句不在结尾段里", "five_section_five_negatives.txt", ["--format", "五段", "--total", "12", "--negative-exception", "不出现猫。"], 1),
    ("五段结尾段五条否定：只写理由不点句仍拦", "five_section_five_negatives.txt", ["--format", "五段", "--total", "12", "--negative-exception", "质量需要"], 1),
    ("g02 例外重复同一句不计数", "five_section_six_negatives.txt", ["--format", "五段", "--total", "12", "--negative-exception", "不出现水印。；不出现水印。"], 1),
    ("g03 例外写成片段不计数", "five_section_six_negatives.txt", ["--format", "五段", "--total", "12", "--negative-exception", "水；印"], 1),
    ("六条否定：两条独立整句例外放行", "five_section_six_negatives.txt", ["--format", "五段", "--total", "12", "--negative-exception", "不出现水印。；不出现反光。"], 0),
    ("密度：每秒 2 拍也提醒（只提醒）", "dense_two_per_second.txt", ["--total", "12"], 0),
    ("弱运镜措辞只提醒", "weak_motion.txt", ["--total", "12"], 0),
    ("四段生成稿情节段开头有总览句：只提醒", "four_section_overview_warning.txt", ["--total", "12"], 0),
    ("动作过密只提醒", "dense_beats.txt", ["--total", "12"], 0),
    ("B17 四段修订仍拦末尾约束，逐字锁不豁免摆放规则", "five_negatives.txt", ["--baseline", str(C / "five_negatives.txt"), "--lock", "不出现第二个人。\n不出现文字水印。\n不出现多余武器。\n不出现现代物品。\n全片不添加BGM，不添加字幕。", "--total", "12"], 1),
    # ---- v17 A：要求清单 --asks（多轮任务从第二版起维护）----
    ("要求清单 2 条有效全部有落点：通过", "asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_ok.txt")], 0),
    ("要求清单有一条在正文里没落点：拦下", "asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_missing.txt")], 1),
    ("要求清单里那条已标撤回：不再核对，通过", "asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_withdrawn.txt")], 0),
    ("要求清单列数不对 / 状态不是有效或撤回：拦下", "asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_bad_format.txt")], 1),
    ("要求清单文件不存在：参数错误", "asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_不存在.txt")], 2),
    # ---- v17 B：改稿不丢句（消失句与长度稀释都只提醒，不拦）----
    ("父稿两句在新稿里消失：只提醒不拦", "revise_dropped_two.txt", ["--baseline", str(C / "revise_parent.txt"), "--total", "12"], 0),
    ("只改一句：通过", "revise_one_sentence.txt", ["--baseline", str(C / "revise_parent.txt"), "--total", "12"], 0),
    ("新稿比父稿长 30%：只提醒不拦", "revise_padded.txt", ["--baseline", str(C / "revise_parent.txt"), "--total", "12"], 0),
    ("局部替换丢了一句：只提醒不拦", "revise_partial_shot2.txt", ["--baseline", str(C / "revise_parent.txt"), "--partial", "--total", "12"], 0),
    # ---- v18：机制词、尺度名词、绝对化的空或黑、解释词、距离链（五类都只提醒，不拦）----
    ("机制词（力从…传到手腕）：只提醒", "mechanism_words.txt", ["--total", "12"], 0),
    ("中景里的尺度名词（织纹）：只提醒", "micro_scale_in_medium.txt", ["--total", "12"], 0),
    ("特写里的尺度名词：不提醒也不拦", "micro_scale_in_closeup.txt", ["--total", "12"], 0),
    ("绝对化的空或黑（压死的黑）：只提醒", "absolute_void.txt", ["--total", "12"], 0),
    ("同一镜里尽头 + 贴着镜头掠过：只提醒", "far_near_conflict.txt", ["--total", "12"], 0),
    ("远处→逼近→贴镜写全（仍提醒，但必须通过）", "far_near_ok.txt", ["--total", "12"], 0),
    ("解释词（仿佛、似乎）：并入空词，只提醒", "explain_words.txt", ["--total", "12"], 0),
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
WARN_CASES = [("weak_motion.txt", [], "弱措辞"), ("dense_beats.txt", [], "节拍"), ("dense_two_per_second.txt", [], "节拍"),
              ("four_section_overview_warning.txt", [], "总览句"),
              ("at_refs_in_new_draft.txt", [], "新稿不写 @"), ("asset_bound_twice.txt", [], "都写了职责"),
              ("cross_section_dup.txt", [], "跨段重复"), ("style_has_sequence.txt", [], "风格段里有时序"),
              # v17 B：父稿句子消失、局部替换里消失、长度稀释
              ("revise_dropped_two.txt", ["--baseline", str(C / "revise_parent.txt")], "在新稿里消失"),
              ("revise_dropped_two.txt", ["--baseline", str(C / "revise_parent.txt")],
               "「镜头缓缓推近到胸口高度」「后景虚化成一片柔光」"),
              ("revise_dropped_two.txt", ["--baseline", str(C / "revise_parent.txt")], "核对删改授权与控制落点"),
              ("revise_partial_shot2.txt", ["--baseline", str(C / "revise_parent.txt"), "--partial"],
               "「后景虚化成一片柔光」"),
              ("revise_padded.txt", ["--baseline", str(C / "revise_parent.txt")], "仅核对新增必要信息与重复补丁"),
              # v18：五类新提醒各要真的出现在 warnings 里
              ("mechanism_words.txt", [], "机制词：「力从」"),
              ("micro_scale_in_medium.txt", [], "尺度名词「织纹」出现在非特写镜头里"),
              ("absolute_void.txt", [], "绝对化的空或黑：「压死的黑」"),
              ("far_near_conflict.txt", [], "同一镜里既有远处位置又有贴镜动作"),
              ("explain_words.txt", [], "空词：仿佛")]
for f, extra, key in WARN_CASES:
    p = subprocess.run([sys.executable, str(S), "--prompt", str(C / f), "--total", "12", *extra], text=True, capture_output=True)
    d = json.loads(p.stdout); ok = any(key in w for w in d["warnings"]); fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {f} 触发“{key}”提醒 |", [w for w in d["warnings"] if key in w][:1])
# 反面：干净的稿不许被这几条提醒误伤（镜头性格词、各绑一次、不写 @；改一句不算消失、没变长不报稀释）
NO_WARN_CASES = [("no_at_refs.txt", ["--labels", "图1,图2,音频1"], "新稿不写 @"),
                 ("no_at_refs.txt", ["--labels", "图1,图2,音频1"], "都写了职责"),
                 ("no_at_refs.txt", ["--labels", "图1,图2,音频1"], "跨段重复"),
                 ("no_at_refs.txt", ["--labels", "图1,图2,音频1"], "风格段里有时序"),
                 ("style_clean.txt", [], "风格段里有时序"),
                 # v17 B：只改一句不算消失；局部替换只换一个词也不算；没变长不报稀释
                 ("revise_one_sentence.txt", ["--baseline", str(C / "revise_parent.txt")], "在新稿里消失"),
                 ("revise_one_sentence.txt", ["--baseline", str(C / "revise_parent.txt")], "新稿比父稿长"),
                 ("partial_shot2.txt", ["--baseline", str(C / "control_valid.txt"), "--partial"], "在新稿里消失"),
                 ("revise_padded.txt", ["--baseline", str(C / "revise_parent.txt")], "在新稿里消失"),
                 ("revise_dropped_two.txt", ["--baseline", str(C / "revise_parent.txt")], "新稿比父稿长"),
                 # v18：特写镜头里的尺度名词不提醒；干净稿不被五类新提醒误伤
                 ("micro_scale_in_closeup.txt", [], "尺度名词"),
                 ("control_valid.txt", [], "机制词"),
                 ("control_valid.txt", [], "绝对化的空或黑"),
                 ("control_valid.txt", [], "既有远处位置又有贴镜动作"),
                 ("style_clean.txt", [], "尺度名词"),
                 ("control_valid.txt", [], "空词：")]
for f, extra, key in NO_WARN_CASES:
    p = subprocess.run([sys.executable, str(S), "--prompt", str(C / f), "--total", "12", *extra], text=True, capture_output=True)
    d = json.loads(p.stdout); hit = [w for w in d["warnings"] if key in w]; ok = not hit; fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {f} 不触发“{key}”提醒 |", hit[:1] or "ok")

# ---- 四段稿的否定提醒：镜内一条给一条提醒；--negative-exception 点名后不再提醒 ----
for args, want_n, label in [([], 1, "镜内否定：提醒 1 条"),
                            (["--negative-exception", "不出现第二个白猿。"], 0, "点名后：提醒 0 条")]:
    p = subprocess.run([sys.executable, str(S), "--prompt", str(C / "inline_negative.txt"), "--total", "12", *args],
                       text=True, capture_output=True)
    d = json.loads(p.stdout)
    hits = [w for w in d["warnings"] if w.startswith("否定句：")]
    ok = p.returncode == 0 and len(hits) == want_n
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {label} | exit {p.returncode} | {hits}")
# summary 里四段用"镜内否定提醒 N 句"，旧壳仍用"自写否定计数 N 条"；一行里不放全角括号（钩子正则按「）」截断）
SUMMARY_CASES = [("inline_negative.txt", ["--total", "12"], "镜内否定提醒 1 句"),
                 ("control_valid.txt", ["--total", "12"], "镜内否定提醒 0 句"),
                 ("five_section_four_negatives.txt", ["--format", "五段", "--total", "12"], "自写否定计数 4 条"),
                 # v17 A：要求清单进 summary
                 ("asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_ok.txt")], "要求清单 2 条有效全部有落点"),
                 ("asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_withdrawn.txt")], "要求清单 2 条有效全部有落点"),
                 ("asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_missing.txt")], "要求清单 3 条有效，1 条没有落点"),
                 ("asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_bad_format.txt")], "要求清单格式错误")]
for f, args, needle in SUMMARY_CASES:
    p = subprocess.run([sys.executable, str(S), "--prompt", str(C / f), *args], text=True, capture_output=True)
    d = json.loads(p.stdout); ok = needle in d["summary"] and "（" not in d["summary"][d["summary"].index("（") + 1:]
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {f} summary 含“{needle}” |", d["summary"])

# ---- v17 A：错误措辞与撤回条目；B：已由 A 报的那一句不重复报 ----
ASK_DETAIL_CASES = [
    ("没落点的错误写清编号、原话、关键词与两条出路", "asks_draft.txt", ["--asks", str(C / "asks_missing.txt")], "errors",
     "要求 R3「头在镜头前摇晃时焦点在头和衣服之间切换」在正文里没有落点（关键词：焦点/移焦）；要么补回，要么用户明确撤回后在清单里标撤回"),
    ("撤回条目在 checked 行里点名", "asks_draft.txt", ["--asks", str(C / "asks_withdrawn.txt")], "checked",
     "要求清单 2 条有效全部有落点，1 条已标撤回：R3"),
    ("列数不对报格式错误", "asks_draft.txt", ["--asks", str(C / "asks_bad_format.txt")], "errors", "列数不对"),
    ("状态不是有效 / 撤回报格式错误", "asks_draft.txt", ["--asks", str(C / "asks_bad_format.txt")], "errors",
     "状态不是「有效」或「撤回（时间＋用户原话）」"),
    ("消失的句子已被 A 的错误覆盖：不重复报", "revise_dropped_two.txt",
     ["--baseline", str(C / "revise_parent.txt"), "--asks", str(C / "asks_lost_overlap.txt")], "warnings",
     "父稿有 1 句在新稿里消失：「后景虚化成一片柔光」"),
]
for name, f, args, field, needle in ASK_DETAIL_CASES:
    p = subprocess.run([sys.executable, str(S), "--prompt", str(C / f), "--total", "12", *args], text=True, capture_output=True)
    d = json.loads(p.stdout); hit = [x for x in d[field] if needle in x]; ok = bool(hit); fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {name} |", hit[:1] or d[field])

# --report 里记 asks_checked（没给 --asks 时是 null）
with tempfile.TemporaryDirectory() as tmp:
    for args, want in [(["--asks", str(C / "asks_ok.txt")], 2), ([], None)]:
        rp = pathlib.Path(tmp) / f"asks{want}.json"
        subprocess.run([sys.executable, str(S), "--prompt", str(C / "asks_draft.txt"), "--total", "12",
                        "--report", str(rp), *args], text=True, capture_output=True)
        rep = json.loads(rp.read_text(encoding="utf-8"))
        ok = "asks_checked" in rep and rep["asks_checked"] == want; fails += 0 if ok else 1
        print(("PASS" if ok else "FAIL"), f"| --report 的 asks_checked = {want} |", rep.get("asks_checked", "缺字段"))

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

# ---- 经验库分类前缀：log_lesson 写入强制、merge_lessons 合并强制、lint_lessons 体检 ----
LOG = ROOT / "scripts" / "log_lesson.py"
MERGE = ROOT / "scripts" / "merge_lessons.py"
LINT = ROOT / "scripts" / "lint_lessons.py"
LESSONS = ROOT / "references" / "lessons" / "seedance-2.5.md"
BASE_ENTRY = "L001 | 2026-09-21 | 通用/占位 | 现象 | 写法A → 效果 | — | 结论 | 未试 | 来源\n"


def run(cmd):
    return subprocess.run([sys.executable, *map(str, cmd)], text=True, capture_output=True)


with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    lf = d / "lessons.md"
    lf.write_text("# 临时经验库\n\n" + BASE_ENTRY, encoding="utf-8")
    common = ["--phenomenon", "现象", "--a", "写法A → 效果", "--conclusion", "结论",
              "--confidence", "未试", "--source", "来源 2026-09-21"]
    LESSON_CASES = [
        ("log_lesson 合规前缀：写入成功", [LOG, "--file", lf, "--topic", "景别与画外/画外人物", *common], 0, "L002"),
        ("log_lesson 无前缀：拒绝、不写入", [LOG, "--file", lf, "--topic", "画外人物", *common], 1, "没有分类前缀"),
        ("log_lesson 分类不在 12 个里：拒绝、不写入", [LOG, "--file", lf, "--topic", "打斗场面/接触", *common], 1, "不在 12 个分类里"),
    ]
    for name, cmd, want_code, needle in LESSON_CASES:
        before = lf.read_text(encoding="utf-8")
        p = run(cmd)
        why = []
        if p.returncode != want_code:
            why.append(f"退出码 {p.returncode}（期望 {want_code}）")
        if needle not in (p.stdout + p.stderr):
            why.append(f"输出里没有“{needle}”")
        after = lf.read_text(encoding="utf-8")
        if want_code == 0 and after == before:
            why.append("合规条目没写进文件")
        if want_code != 0 and after != before:
            why.append("不合规却动了文件")
        fails += 0 if not why else 1
        print(("PASS" if not why else "FAIL"), f"| {name} |", "；".join(why) or "ok")

    # merge_lessons：来源里有无前缀条目 → 整次拒绝，目标文件不动
    src = d / "src.md"
    src.write_text("# 来源\n\n" + BASE_ENTRY
                   + "L003 | 2026-09-21 | 没前缀的主题 | 现象 | 写法A → 效果 | — | 结论 | 未试 | 来源\n",
                   encoding="utf-8")
    before = lf.read_text(encoding="utf-8")
    p = run([MERGE, "--from", src, "--into", lf])
    why = []
    if p.returncode != 1:
        why.append(f"退出码 {p.returncode}（期望 1）")
    if "L003" not in p.stderr or "没有分类前缀" not in p.stderr:
        why.append("stderr 没有列出违规编号与原因")
    if lf.read_text(encoding="utf-8") != before:
        why.append("拒绝合并却动了目标文件")
    fails += 0 if not why else 1
    print(("PASS" if not why else "FAIL"), "| merge_lessons 来源含无前缀条目：拒绝合并 |", "；".join(why) or "ok")

    # merge_lessons：来源条目全部合规 → 正常合并
    src2 = d / "src2.md"
    src2.write_text("# 来源\n\n" + BASE_ENTRY
                    + "L003 | 2026-09-21 | 操作命令/延长 | 现象 | 写法A → 效果 | — | 结论 | 已试 | 来源\n",
                    encoding="utf-8")
    p = run([MERGE, "--from", src2, "--into", lf])
    ok = p.returncode == 0 and "L003" in lf.read_text(encoding="utf-8")
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), "| merge_lessons 来源全部合规：正常合并 |", (p.stdout or p.stderr).strip()[:80])

    # lint_lessons：编号断档要报出来
    bad = d / "bad.md"
    bad.write_text("# 临时\n\n" + BASE_ENTRY
                   + "L005 | 2026-09-21 | 通用/占位 | 现象 | 写法A → 效果 | — | 结论 | 未试 | 来源\n",
                   encoding="utf-8")
    p = run([LINT, "--file", bad])
    ok = p.returncode == 1 and "编号不连续" in p.stderr
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), "| lint_lessons 编号断档：拦下 |", "ok" if ok else p.stderr.strip()[:120])

# lint_lessons：当前经验库必须干净（前缀合法 + 编号连续）
p = run([LINT, "--file", LESSONS])
ok = p.returncode == 0
fails += 0 if ok else 1
print(("PASS" if ok else "FAIL"), "| lint_lessons 当前经验库通过 |", (p.stdout or p.stderr).strip()[:160])

# ---- 案例库体检：可复用点必须落到经验编号或标成样板 ----
LINTC = ROOT / "scripts" / "lint_cases.py"
CASES_MD = ROOT / "references" / "cases" / "my-cases.md"


def case_md(bullets, rel="L001"):
    return ("# 临时案例库\n\n## 索引\n\n"
            "| 编号 | 日期 | 任务类型 | 时长 | 素材形态 | 题材关键词 | 什么时候选它 | 成片 | 可复用点 |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
            "| M001 | 2026-09-22 | 图生单镜 | 5s | 图1 | 测试 | 测试时选它 | a.mp4 | 无 |\n\n"
            "## 条目\n\n### M001 ｜ 2026-09-22 ｜ 图生单镜 ｜ 5 秒\n\n"
            "素材：@图片1 = 测试\n成片文件名：a.mp4\n我的评价：好\n"
            f"关联经验：{rel}\n\n可复用点：\n{bullets}\n\n"
            "提示词原文（需要抄句式时再读）：\n\n```text\n主体：测试。\n```\n")


CASE_LINT_CASES = [
    ("lint_cases 一条知识一条样板：通过", case_md("- 每镜几句、先写什么后写什么（样板）\n- 「那句句式」 → L001"), 0, "通过"),
    ("lint_cases 可复用点没编号也没标样板：拦下", case_md("- 「那句句式」写得真好"), 1, "既没有"),
    ("lint_cases 引用经验库里没有的编号：拦下", case_md("- 「那句句式」 → L999"), 1, "不存在"),
    ("lint_cases 关联经验为空：拦下", case_md("- 「那句句式」 → L001", rel=""), 1, "关联经验"),
]
with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    lf = d / "lessons.md"
    lf.write_text("# 临时经验库\n\n" + BASE_ENTRY, encoding="utf-8")
    for i, (name, body, want_code, needle) in enumerate(CASE_LINT_CASES):
        cf = d / f"cases{i}.md"
        cf.write_text(body, encoding="utf-8")
        p = run([LINTC, "--file", cf, "--lessons", lf])
        why = []
        if p.returncode != want_code:
            why.append(f"退出码 {p.returncode}（期望 {want_code}）")
        if needle not in (p.stdout + p.stderr):
            why.append(f"输出里没有“{needle}”")
        fails += 0 if not why else 1
        print(("PASS" if not why else "FAIL"), f"| {name} |", "；".join(why) or "ok")

# lint_cases：当前案例库必须干净（每条可复用点有编号或标样板，编号真的存在，索引对得上）
p = run([LINTC, "--file", CASES_MD, "--lessons", LESSONS])
ok = p.returncode == 0
fails += 0 if ok else 1
print(("PASS" if ok else "FAIL"), "| lint_cases 当前案例库通过 |", (p.stdout or p.stderr).strip()[:160])

TOTAL = (len(CASES) + len(WARN_CASES) + len(NO_WARN_CASES) + 2 + len(SUMMARY_CASES)
         + len(ASK_DETAIL_CASES) + 2 + len(REPORT_CASES)
         + len(LESSON_CASES) + 4 + len(CASE_LINT_CASES) + 1)
print(f"\n{TOTAL - fails}/{TOTAL} 通过")
sys.exit(1 if fails else 0)
