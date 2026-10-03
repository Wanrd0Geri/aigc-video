#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_prompt.py 回归：python3 tests/run_check_tests.py  （全部通过退出 0）"""
import hashlib, json, os, pathlib, re, shutil, subprocess, sys, tempfile
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
    ("密度：正好 0.5 秒一拍（2 秒 4 拍）不提醒，通过", "dense_two_per_second.txt", ["--total", "12"], 0),
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
    # ---- v21 ----
    ("关键动作（松手）紧挨整幅遮挡（糊住）：只提醒", "key_action_occluded.txt", ["--total", "12"], 0),
    ("关键动作与整幅遮挡各带第N秒、相差 3 秒：通过", "key_action_staggered.txt", ["--total", "12"], 0),
    ("遮挡词前有否定（不占满画面）：通过", "key_action_negated.txt", ["--total", "12"], 0),
    ("发力过程写法（先转肩、再转胯、引到最后）：只提醒", "force_process.txt", ["--total", "12"], 0),
    ("发力只写结果（越转越快、袖子被甩平）：通过", "force_result.txt", ["--total", "12"], 0),
    ("情节段用 a-b秒 标题：命令区能识别，通过", "four_section_seconds_heads.txt", ["--total", "12"], 0),
    ("近景里的尺度名词（织纹）：只提醒", "micro_scale_in_near.txt", ["--total", "12"], 0),
    # ---- v22 讲戏口吻：镜内标签与镜内画质词（都只提醒）----
    ("镜内标签（摄影：/动作：/第二拍/镜头运动：/【构图】/第9秒：）与镜内画质词：只提醒", "shot_labels.txt", ["--total", "12"], 0),
    ("像标签但不是（焦点分两段走：/第4秒，/半拍/台词里的第一拍/旁白：/起幅是/落幅停在）：通过", "shot_labels_lookalike.txt", ["--total", "12"], 0),
    ("官方案例式镜内标签（动作/表情：/情感解析：/表情：）：只提醒", "shot_labels_official.txt", ["--total", "12"], 0),
    ("像标签但不是（鼓点的第一拍/第三拍下去）：通过", "shot_labels_beat_lookalike.txt", ["--total", "12"], 0),
    ("灯笼怪 v21 试稿与讲戏口吻重写稿：通过", "lantern_style_draft.txt", ["--total", "6", "--labels", "图1,图2", "--baseline", str(C / "lantern_v21_trial.txt")], 0),
    # ---- v23 主体段只写是谁、长什么样、有几个；总括保证句（都只提醒）----
    ("主体段写了持物状态、表演、随动与贴镜掠过：只提醒", "subject_action.txt", ["--total", "12", "--labels", "图1"], 0),
    ("主体段只写是谁、长什么样、有几个（绑定、静态外形、数量锁、身份锁、唯一光源）：通过", "subject_clean.txt", ["--total", "12", "--labels", "图1,图2,音频1"], 0),
    ("总括保证句（不断开的连续镜头 / 任何时刻 / 始终留在画面 / 整段里始终）：只提醒", "guarantee_lock.txt", ["--total", "12"], 0),
    ("灯笼怪两份试写稿（主体段写进情节、连续镜头锁）：只提醒", "lantern_trial_s.txt", ["--total", "6", "--labels", "图1,图2"], 0),
    ("灯笼怪两份试写稿（主体段写进情节、连续镜头锁）：只提醒", "lantern_trial_v22.txt", ["--total", "6", "--labels", "图1,图2"], 0),
    # v23 审查修复：强档补常见说法；主体段词表的误报与漏报
    ("总括保证句的其他说法（持续出现在镜头中、始终在画面里、从不离开画面、都不出画）：只提醒", "guarantee_phrasing.txt", ["--total", "12", "--labels", "图1"], 0),
    ("主体段词表：晃眼、掠食、伤口持续渗血不报，手持长剑照报：只提醒", "subject_wordlist.txt", ["--total", "12", "--labels", "图1"], 0),
    # v23 审查后同日修正：镜内“始终在画内”只有点名部位或切线才算取景；场景段的角色活动
    ("镜内取景约束（全镜里灯笼怪始终留在画内照报，头部和双肩始终留在画内不报）：只提醒", "guarantee_scope.txt", ["--total", "12", "--labels", "图1"], 0),
    ("场景段写了冤魂飞过、路人走过（雨、风、鸟群、落叶不报）：只提醒", "scene_activity.txt", ["--total", "12", "--labels", "图1"], 0),
    # v23 第二次复查修正：取景豁免只给镜头正文普通句；风格段的角色活动；总览句强档与宽档并一条；背景活动词表；外形状态与身份句
    ("主体段与总览句的站位保证（两人的左右位置全程不变）：只提醒", "guarantee_subject_position.txt", ["--total", "12", "--labels", "图1,图2"], 0),
    ("主体段的取景保证（全身 / 头部和双肩始终留在画面）：只提醒", "guarantee_subject_lantern.txt", ["--total", "12", "--labels", "图1"], 0),
    ("风格段写了冤魂飞过、贴镜掠过：只提醒", "style_activity.txt", ["--total", "12", "--labels", "图1"], 0),
    ("总览句的强档与“；”后分句并一条、场景段强档并入角色活动：只提醒", "guarantee_overview_merge.txt", ["--total", "12", "--labels", "图1"], 0),
    ("背景活动词表（盘旋、穿过、飘过、涌动、发抖、来来往往、赶路、鬼影）：只提醒", "bg_activity_wordlist.txt", ["--total", "12", "--labels", "图1"], 0),
    ("外形状态与身份句（一直湿透、始终是同一颗、同一主体）：通过", "guarantee_exempt_states.txt", ["--total", "12", "--labels", "图1"], 0),
    # ---- v24（2026-09-23 用户“按建议”）：密度按“不到 0.5 秒一拍”才提醒；有意的纯黑写明时长、范围或曝光依据不报；全局段材质词不扫 ----
    ("密度：正好 0.5 秒一拍（3 秒 6 拍，时码带小数）不提醒，通过", "dense_exact_half_second.txt", ["--total", "12"], 0),
    ("密度：1 秒里超过 2 拍（3 秒 7 拍）只提醒", "dense_over_two_per_second.txt", ["--total", "12"], 0),
    ("有意的纯黑（开始的一秒、画面九成、按灯笼的光曝光）：通过且不提醒", "void_intentional.txt", ["--total", "12"], 0),
    ("纯黑只有镜头标题的时码：只提醒", "void_heading_only.txt", ["--total", "12"], 0),
    ("纯黑只带“第8秒”时间点，另有“什么都没有”：只提醒", "void_time_point.txt", ["--total", "12"], 0),
    ("“上半身沉进纯黑里”（上半身不算范围）：只提醒", "void_body_half.txt", ["--total", "12"], 0),
    ("主体、场景、风格段的材质词（织纹、毛孔、纤维）不扫：通过", "micro_scale_in_global.txt", ["--total", "12"], 0),
    # ---- v24 审查修复：已试否定例外可点名；“先”“同时”不另算一拍；只写曝光不算有意纯黑；“不采用图中的纯黑背景”不扫；哪只手握棍不算总括 ----
    ("已试否定例外（句中否定）整句点名：通过", "tried_negative_exception.txt", ["--total", "12", "--negative-exception", "开始的一秒画面是纯黑，看不到任何轮廓、光点或亮边；暗部不做任何补光"], 0),
    ("已试否定例外只点名片段：拦下", "tried_negative_exception.txt", ["--total", "12", "--negative-exception", "看不到任何轮廓"], 1),
    ("密度：“先……接着……”与“同时”写的正好 0.5 秒一拍：通过", "dense_xian_tongshi.txt", ["--total", "12"], 0),
    ("纯黑只写按哪处光曝光：只提醒", "void_exposure_only.txt", ["--total", "12"], 0),
    ("纯黑同句只有“一成不变”“大半圈”：只提醒", "void_not_range.txt", ["--total", "12"], 0),
    ("主体段“不采用图中的纯黑背景”+ 镜内有意纯黑：通过", "void_ref_bg_excluded.txt", ["--total", "12", "--labels", "图1"], 0),
    ("主体段“白猿全程用右手握棍”（E1 身份事实）：通过", "prop_hand_in_subject.txt", ["--total", "12"], 0),
    ("样例：打斗 12 秒", "../sample-combat-12s.txt", ["--total", "12", "--labels", "图片1,图片2,图片3"], 0),
    ("样例：对话 12 秒", "../sample-dialogue-12s.txt", ["--total", "12", "--labels", "图片1,图片2"], 0),
    # ---- v25（2026-09-23）一、错误级误报 ----
    ("A10 普通说法不算引用（挂上一轮满月 / 宛如上好的 / 不要像木偶 / 镜内第二句的再次）：通过", "ref_wording_lookalike.txt", ["--total", "12"], 0),
    ("A10 漏报的引用性措辞（这次不要 / 和之前一样 / 承接着）：拦下", "ref_wording_missed.txt", ["--total", "12"], 1),
    ("A10 镜头第一句的“再次”：只提醒", "ref_again_first_sentence.txt", ["--total", "12"], 0),
    ("A19 末镜最后一行“不远处的灯笼……”：通过", "tail_line_buyuanchu.txt", ["--total", "12"], 0),
    ("A19 末镜最后一行“无数冤魂……”：通过", "tail_line_wushu.txt", ["--total", "12"], 0),
    ("A19 固定句上一行“严禁……”：拦下", "tail_line_yanjin.txt", ["--total", "12"], 1),
    # ---- v25 二、讲戏口吻生效（新提醒都只提醒，不拦）----
    ("A1 灯笼怪 v23 试写（24 句 / 6 秒，正好 0.5 秒一拍）：通过", "lantern_v23_trial.txt", ["--task", "生成", "--total", "6", "--labels", "图1,图2"], 0),
    ("A1 句数估拍（2 秒 10 句）：只提醒", "dense_sentences.txt", ["--total", "12"], 0),
    ("A2 弱词后跟运镜术语、前面没写镜头：只提醒", "weak_motion_no_prefix.txt", ["--total", "12"], 0),
    ("A2 人物与面部描写里的微微 / 轻微（推开门、拉紧背带、嘴角轻微下拉、眉头轻微下压、肩膀微微下降）：通过", "weak_motion_person.txt", ["--total", "12"], 0),
    ("A2 面部描写后面紧跟的“镜头微微推近”：只提醒", "weak_motion_camera_after_face.txt", ["--total", "12"], 0),
    ("A3 成文主规则第 2 条正例（占满画面下半 + 离开它的手）：通过", "key_event_rule2_example.txt", ["--total", "12"], 0),
    ("A3 新关键动作词（离开它的手 / 冲向镜头）紧挨整幅遮挡：只提醒", "key_action_new_words.txt", ["--total", "12"], 0),
    ("A4 站位保证全稿扫、始终在画面中央照报：只提醒", "guarantee_position_scan.txt", ["--total", "12"], 0),
    ("A5 道具归属、亮着熄着、场景段环境句不算总括：通过", "guarantee_exempt_more.txt", ["--total", "12"], 0),
    ("A6 紧跟标题的否定句与严禁 / 请勿 / 别：只提醒", "negative_after_heading.txt", ["--total", "12"], 0),
    ("A7 命令区的参考视频与首帧句不算总览句：通过", "command_zone_reference.txt", ["--total", "12", "--labels", "图1,图2,图3,视频1"], 0),
    ("A8 尺度名词按句取最近的景别：只提醒", "micro_scale_per_sentence.txt", ["--total", "12"], 0),
    ("A9 重心单独不报、与转肩转胯连写才报；传到 / 蓄力：只提醒", "force_chain_mechanism.txt", ["--total", "12"], 0),
    ("A13 取景写成能装下什么：只提醒", "framing_fit_words.txt", ["--total", "12"], 0),
    ("A14 远处与贴镜之间有推近：通过", "far_near_transition.txt", ["--total", "12"], 0),
    ("A15 主体段的情绪词与动作单字：只提醒", "subject_emotion_action.txt", ["--total", "12", "--labels", "图1"], 0),
    ("A16 风格段的随动、表演与放慢后恢复：只提醒", "style_follow_perf.txt", ["--total", "12"], 0),
    ("A16 风格段的跟随感、稳定器般、呼吸感的手持：通过", "style_camera_character.txt", ["--total", "12"], 0),
    ("A17 图片N / 视频片段N 与同段两次绑定：只提醒", "asset_long_form.txt", ["--total", "12"], 0),
    ("A17 “用于……；不采用……”不算两次绑定：通过", "asset_bind_skip.txt", ["--total", "12", "--labels", "图1"], 0),
    ("A18 各段画质词与解释词：只提醒", "quality_words_sections.txt", ["--total", "12"], 0),
    ("A18 风格段末尾的画质尾巴：通过且不提醒", "quality_style_tail.txt", ["--total", "12"], 0),
    ("A18 风格段只有画质词：只提醒", "quality_style_only.txt", ["--total", "12"], 0),
    ("B1 只有人物动作、没有摄影运动：只提醒", "camera_person_actions.txt", ["--total", "12"], 0),
    ("B5 --asks 有效要求里的空词（震撼）：通过且不提醒", "asks_empty_word_draft.txt", ["--total", "12", "--asks", str(C / "asks_empty_word.txt")], 0),
    ("--task 推断：延续视频N → 延长，通过", "extend_yanxu.txt", ["--total", "5", "--labels", "视频1"], 0),
    ("延长必填词认“延续视频N”：显式 --task 延长，通过", "extend_yanxu.txt", ["--task", "延长", "--total", "5", "--labels", "视频1"], 0),
    ("--task 推断：移除视频1 → 编辑，通过", "edit_remove.txt", ["--labels", "视频1,图1"], 0),
    ("--task 推断：没给 --task 的延长稿按延长检查，通过", "extend_ok.txt", ["--total", "5", "--labels", "视频1"], 0),
    ("--task 推断：a-b秒 标题 + 风格段视频1 + 镜内“雨势增加”仍是生成，通过", "rain_increase_seconds_heads.txt", ["--total", "8", "--labels", "视频1"], 0),
    ("--task 编辑但命令区没有动词：拦下（报错列出移除）", "rain_increase_seconds_heads.txt", ["--task", "编辑", "--labels", "视频1"], 1),
    ("A6 旧壳结尾段计数认“严禁 / 请勿”：5 条拦下", "five_section_yanjin.txt", ["--format", "五段", "--total", "12"], 1),
    # ---- 压缩审校（2026-09-24，writing-rules 成文主规则第 5 条）：复读、虚词、密度三条提醒都只提醒，不拦 ----
    ("压缩审校·密度：镜1 305 字 / 3 秒超过参考线 90：只提醒", "density_over_line.txt", ["--total", "12"], 0),
    ("压缩审校·密度：去掉台词后 208 字 / 3 秒（连台词约 98 字 / 秒）：通过", "density_under_line.txt", ["--total", "12"], 0),
    ("压缩审校·复读：镜内“她的影子长长地拖在石阶上”写了两次：只提醒", "repeat_phrase.txt", ["--total", "12"], 0),
    ("压缩审校·复读：主体段外貌短语、场景地点名、画框切线、画面坐标、运镜、台词、素材短名在镜内重复：通过", "repeat_phrase_exempt_subject.txt", ["--total", "12"], 0),
    ("压缩审校·复读改稿：父稿只写一次、新稿写成两次：只提醒", "repeat_phrase.txt", ["--baseline", str(C / "repeat_phrase_parent.txt"), "--total", "12"], 0),
    ("压缩审校·虚词：一镜 5 个（逐渐、缓缓、一路、随之、此时）：只提醒", "filler_words_over.txt", ["--total", "12"], 0),
    ("压缩审校·虚词：时序词、慢慢、急速、不断、开始的一秒与 3 个以内的虚词：通过", "filler_words_ok.txt", ["--total", "12"], 0),
    # ---- v35 表演排队（writing-rules 成文主规则第 8 条）：只提醒，不拦 ----
    ("v35 表演排队（说完……才抬头、才开口、放下杯子之后才去开门）：只提醒", "perf_queue_report.txt", ["--total", "12"], 0),
    ("v35 交叠短语、摄影机顺序、台词里的说完、单独的然后 / 随后 / 接着：通过且不提醒", "perf_queue_overlap_ok.txt", ["--total", "12"], 0),
    # ---- 2026-10-01 五条提醒（蛟龙雷暴、曲伯牌坊复盘；都只提醒，不拦）----
    ("角度词前的削弱词（机位在胸口高度微微仰起、稍微俯拍）：只提醒", "weak_angle.txt", ["--total", "12"], 0),
    ("表演句与没带削弱词的角度（嘴角微微上扬、头微微仰起、微微俯下身、略高于、稍作停顿、稍后俯拍）：通过", "weak_angle_ok.txt", ["--total", "12"], 0),
    ("朝向只写方位词（看向右前方、脸朝画面左侧）：只提醒", "orient_dir_only.txt", ["--total", "12"], 0),
    ("朝向带部位判据、没有左右、右手是部位、镜头转向、单独的视线句：通过", "orient_dir_parts.txt", ["--total", "12"], 0),
    ("朝向写人物自身方位（望着自己的右前方，曲伯原句）：只提醒", "orient_dir_self.txt", ["--total", "6"], 0),
    ("跟拍没有位移证据（贴在他身后、跟拍、一起往巷子深处跑）：只提醒", "follow_no_evidence.txt", ["--total", "12"], 0),
    ("跟拍有门框一个个从画框两侧退出去；不再跟拍、跟随感、目光跟住：通过", "follow_with_evidence.txt", ["--total", "12"], 0),
    ("高速镜里写位置和大小稳住 / 大小和位置始终不变（v37 起报反模式 AP01）：只提醒", "hold_frame_speed.txt", ["--total", "12"], 0),
    ("对话与横移镜里的位置和大小不变（没有速度词，不报 AP01）：通过", "hold_frame_slow.txt", ["--total", "12"], 0),
    ("尺度比喻用具体实物（有房子那么大、碗口大小的、像山一样高；v37 起报反模式 AP03）：只提醒", "scale_simile_object.txt", ["--total", "12"], 0),
    ("尺度比喻用主体部位（比它的头还大、和蛇身一样粗、拳头大小的、像它的尾巴一样长）与不同大小的（不报 AP03）：通过", "scale_simile_self.txt", ["--total", "12"], 0),
    ("露出它往上盘的长身体、看到它的全身：只提醒", "framing_show_body.txt", ["--total", "12"], 0),
    ("L145 原句：露出它螺旋着往天上盘的长身体（“露出”后隔 9 个字）：只提醒", "framing_show_l145.txt", ["--total", "12"], 0),
    ("露出它的后颈和一排背刺、看到它的头：通过", "framing_show_ok.txt", ["--total", "12"], 0),
    # ---- v37 反模式表（references/antipatterns.md）与三个降噪开关：都只提醒，不拦 ----
    ("反模式 AP01 速度镜报、同一句在慢镜不报；AP06 速度镜里的慢慢：只提醒", "ap_speed_hold.txt", ["--total", "12"], 0),
    ("反模式 AP02 露出它的全身、AP03 场景段的房子比喻、AP04 龙卷风柱：只提醒", "ap_any_rows.txt", ["--total", "12"], 0),
    ("反模式 AP01 单写“大小不变”照报，机位的位置固定不报：只提醒", "ap_speed_size.txt", ["--total", "12"], 0),
    ("白模稿默认模式：命令区对应句报总览句，AP05 不扫", "ap_baimo.txt", ["--total", "12", "--labels", "图1,视频1"], 0),
    ("白模稿 --mode 白模：总览句不报，AP05 报", "ap_baimo.txt", ["--total", "12", "--labels", "图1,视频1", "--mode", "白模"], 0),
    ("白模稿标题带秒数、写焦段：--mode 白模 报 AP07、AP08（候选），只提醒", "ap_baimo_lens.txt", ["--total", "12", "--labels", "图1,视频1", "--mode", "白模"], 0),
    ("白模稿环境形体对应竹子、山路，正文写第几秒：--mode 白模 报 AP05、AP07，只提醒", "ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模"], 0),
    ("速度镜里“保持在画面中央”：报 AP01，只提醒", "ap_speed_center.txt", ["--total", "12"], 0),
    ("远处到“擦着镜头”中间没有逼近：只提醒", "far_near_rub.txt", ["--total", "12"], 0),
    ("速度镜钉在画面中心报 AP01，留在正中但一点点变小的不报：只提醒", "ap_speed_center_resize.txt", ["--total", "12"], 0),
    ("背景层句里的远处不算主体位置（M010 镜1 原样）：只提醒", "far_near_bg_layer.txt", ["--total", "12"], 0),
    ("--rewrite-authorized 不关要求清单：缺落点照样拦", "revise_dropped_two.txt",
     ["--baseline", str(C / "revise_parent.txt"), "--total", "12", "--rewrite-authorized", "--asks", str(C / "asks_lost_overlap.txt")], 1),
    ("--adjudicated 裁定清单找不到：参数错误", "ap_speed_hold.txt", ["--total", "12", "--adjudicated", str(C / "不存在的裁定清单.txt")], 2),
    # ---- v40：无时码稿 --shot-seconds 逐镜算字数密度（屋脊打戏 L161）----
    ("白模稿 --shot-seconds 个数和镜数不符：拦下", "ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模", "--shot-seconds", "0.7"], 1),
    ("白模稿 --shot-seconds 写了非数字：参数错误", "ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模", "--shot-seconds", "0.7,快"], 2),
    ("白模稿 --shot-seconds 两镜短秒数：通过但提醒密度", "ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模", "--shot-seconds", "0.1,0.1"], 0),
]
fails = 0
for name, f, args, want in CASES:
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / f), *args], text=True, encoding="utf-8", errors="replace", capture_output=True)
    try:
        d = json.loads(p.stdout)
    except Exception:
        d = {"errors": [p.stderr.strip()[:200]]}
    ok = p.returncode == want
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {name} | exit {p.returncode} (期望 {want}) | errors={d.get('errors', [])[:2]}")
# 弱运镜与密度提醒必须真的出现在 warnings 里
WARN_CASES = [("weak_motion.txt", [], "弱措辞"), ("dense_beats.txt", [], "节拍"),
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
              ("explain_words.txt", [], "空词：仿佛"),
              # v21：关键动作紧挨整幅遮挡、发力过程写法（同句机制词并入）、机制词新文案、近景不算特写
              ("key_action_occluded.txt", [], "关键动作「松手」和整幅遮挡「糊住」"),
              ("force_process.txt", [], "发力过程写法：「先转肩」"),
              ("force_process.txt", [], "同句机制词「惯性」"),
              ("mechanism_words.txt", [], "改写看得见的结果"),
              ("micro_scale_in_near.txt", [], "尺度名词「织纹」出现在非特写镜头里"),
              # v22：镜内标签逐镜列出、镜内画质词
              ("shot_labels.txt", [], "镜1 镜内标签「摄影：」「动作：」「第二拍」「镜头运动：」"),
              ("shot_labels.txt", [], "镜2 镜内标签「【构图】」「第9秒：」"),
              ("shot_labels.txt", [], "画质词「电影感」"),
              # v22 审查修复：官方案例的复合标签与新增标签词
              ("shot_labels_official.txt", [], "镜1 镜内标签「动作/表情：」「情感解析：」"),
              ("shot_labels_official.txt", [], "镜2 镜内标签「表情：」"),
              # v23：主体段逐句列出动作 / 随动 / 持物状态 / 调度；总括保证句（强档全稿、宽档主体段与镜内总览句）
              ("subject_action.txt", [], "主体段这句写了动作、随动、持物状态或调度：「倒提」——「图1用于"),
              ("subject_action.txt", [], "「牙不停地磕」——「那颗人头"),
              ("subject_action.txt", [], "「随动作」「甩开」「慢半拍」「落回」"),
              ("subject_action.txt", [], "「掠过」「前景」「镜头」"),
              ("guarantee_lock.txt", [], "总括保证句：「不断开的连续镜头」「任何时刻」「至少有一部分」"),
              ("guarantee_lock.txt", [], "总括保证句：「始终留在画面」——「他始终留在画面中央」"),
              ("guarantee_lock.txt", [], "镜1 总括保证句：「始终」——「整段里"),
              ("guarantee_headerless.txt", [], "总括保证句：「始终」——「天空里始终有"),
              ("lantern_v21_trial.txt", [], "（同句总括词「始终」并入本条"),
              ("lantern_v21_trial.txt", ["--baseline", str(C / "lantern_v21_trial.txt")], "这句父稿原有"),
              # v23：用户指出“主体的时候把一部分情节里的东西也写进去了”的两份试写稿，应报的句子逐条报出
              ("lantern_trial_s.txt", ["--total", "6"], "总括保证句：「任何时刻」「至少有一部分」——「全片是一个连续镜头"),
              ("lantern_trial_s.txt", ["--total", "6"], "「倒提」——「图1用于灯笼怪的外形"),
              ("lantern_trial_s.txt", ["--total", "6"], "「抓着」「倒提」「随它的动作」「晃」——「那颗人头被它抓着长发"),
              ("lantern_trial_s.txt", ["--total", "6"], "「飞着」「掠过」「前景」——「背景和前景飞着的冤魂"),
              ("lantern_trial_s.txt", ["--total", "6"], "镜1 总括保证句：「始终」——「整段里，画面深处始终有"),
              # v23 审查修复：镜内总览句延到句号，“；”接着的分句一并列出
              ("lantern_trial_s.txt", ["--total", "6"], "「焦点始终留在灯笼怪和那颗人头上」"),
              ("lantern_trial_v22.txt", ["--total", "6"], "总括保证句：「不断开的连续镜头」「任何时刻」「至少有一部分」"),
              ("lantern_trial_v22.txt", ["--total", "6"], "「揪着」「倒提」——「图1用于灯笼怪的外形"),
              ("lantern_trial_v22.txt", ["--total", "6"], "「牙不停地磕」——「那颗人头带着诡异的笑"),
              ("lantern_trial_v22.txt", ["--total", "6"], "「随动作」「甩开」「慢半拍」「落回」——「长袍被雨淋透"),
              ("lantern_trial_v22.txt", ["--total", "6"], "「飞着」——「身后的雨夜里始终飞着"),
              ("lantern_trial_v22.txt", ["--total", "6"], "「掠过」「前景」「镜头」——「前景偶尔有一只贴着镜头"),
              # v23 审查修复：强档补常见说法（含用户原话“持续出来在镜头中”和换了说法的 L087 锁）
              ("guarantee_phrasing.txt", [], "总括保证句：「持续出现在镜头」——「灯笼怪持续出现在镜头中」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「始终在画面里」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「全程都在画面里」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「从头到尾没有离开画面」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「都不出画」——「整段里灯笼怪都不出画」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「从不离开画面」——「全片是一个连续镜头"),
              # v23 审查修复：主体段“手持长剑”是持物，不走镜头性格豁免
              ("subject_wordlist.txt", [], "「手持」——「他全程手持长剑」（同句总括词「全程」并入本条"),
              # v23 审查后同日修正：持物提醒说明可裁定（全片不换手的道具归属可以留在主体段）
              ("subject_wordlist.txt", [], "持物可裁定：这件道具若全片不换手"),
              # 用户原话“持续出来在镜头中”
              ("guarantee_phrasing.txt", [], "总括保证句：「持续出来在镜头」——「灯笼怪是持续出来在镜头中的」"),
              # 镜内“全镜 / 本镜”不再豁免：不点名部位或切线的“始终留在画内 / 全程都在画内 / 从不离开画面”照报
              ("guarantee_scope.txt", [], "总括保证句：「始终留在画内」——「全镜里灯笼怪始终留在画内」"),
              ("guarantee_scope.txt", [], "总括保证句：「全程都在画内」「从不离开画面」——「本镜它全程都在画内"),
              # 场景段的角色活动（冤魂飞过、路人走过）提醒写进情节
              ("scene_activity.txt", [], "场景段这句写了角色活动：「冤魂」「飞过」「掠过」——「背景里始终有"),
              ("scene_activity.txt", [], "（同句总括词「始终」并入本条"),
              ("scene_activity.txt", [], "场景段这句写了角色活动：「路人」「走过」"),
              # v23 第二次复查修正：取景豁免只给镜头正文里的普通句，主体段与“整段里”总览句照报（成文主规则第 7 条的官方冲突例）
              ("guarantee_subject_position.txt", ["--labels", "图1,图2"], "总括保证句：「全程」——「两人的左右位置全程不变」"),
              ("guarantee_subject_position.txt", ["--labels", "图1,图2"], "总括保证句：「全程」——「苏云与罗大娘的左右位置全程保持不变」"),
              ("guarantee_subject_position.txt", ["--labels", "图1,图2"], "镜1 总括保证句：「全程」——「整段里两人的左右位置全程不变」"),
              ("guarantee_subject_lantern.txt", [], "总括保证句：「始终留在画面」——「灯笼怪的全身始终留在画面里」"),
              ("guarantee_subject_lantern.txt", [], "总括保证句：「始终留在画内」——「灯笼怪的头部和双肩始终留在画内」"),
              # 风格段的角色活动（同一类背景活动换到第三处）
              ("style_activity.txt", [], "风格段这句写了角色活动：「冤魂」「飞过」「掠过」——「背景里始终有"),
              ("style_activity.txt", [], "风格段只写画面质感与镜头性格"),
              ("style_activity.txt", [], "（同句总括词「始终」并入本条"),
              # 总览句里强档与宽档并成一条，“；”后的分句一并列出；场景段同句的强档并入角色活动提醒
              ("guarantee_overview_merge.txt", [], "镜1 总括保证句：「始终在画面里」「始终」——「整段里灯笼怪始终在画面里」（用“；”接着的分句同属这段总览，一并处理：「焦点始终留在灯笼上」"),
              ("guarantee_overview_merge.txt", [], "场景段这句写了角色活动：「冤魂」「飞过」——「冤魂始终在画面里朝左飞过」（同句总括词「始终在画面里」「始终」并入本条"),
              # 总括提醒里区分主体与背景群体：主体写进每一拍的画框，背景群体每镜第一次出现时写一次
              ("guarantee_headerless.txt", [], "背景群体按成文主规则第 3 条在每一镜第一次出现时写一次"),
              # 背景活动词表：主体段与场景段共用
              ("bg_activity_wordlist.txt", [], "「盘旋」——「冤魂在它身后盘旋」"),
              ("bg_activity_wordlist.txt", [], "「穿过」——「冤魂从它身后穿过」"),
              ("bg_activity_wordlist.txt", [], "「飘过」——「冤魂一群群朝左边飘过去」"),
              ("bg_activity_wordlist.txt", [], "「涌动」——「人群在街上涌动」"),
              # v25（A15）：情绪词进主体段词表，“神情惊恐”同句一并列出
              ("bg_activity_wordlist.txt", [], "「发抖」「惊恐」——「它神情惊恐，浑身发抖」"),
              ("bg_activity_wordlist.txt", [], "场景段这句写了角色活动：「冤魂」「飘过」"),
              ("bg_activity_wordlist.txt", [], "场景段这句写了角色活动：「路人」「来来往往」"),
              ("bg_activity_wordlist.txt", [], "场景段这句写了角色活动：「村民」「赶路」"),
              ("bg_activity_wordlist.txt", [], "场景段这句写了角色活动：「鬼影」「掠过」"),
              # 强档补说法；部位只是修饰（捧着的人头、腰间的人头）不算取景豁免
              ("guarantee_phrasing.txt", [], "总括保证句：「一刻也没有离开画面」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「不会离开画面」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「始终处于画面之中」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「始终保留在画面」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「始终位于画面内」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「始终留在画内」——「那颗被它双手捧着的人头始终留在画内」"),
              ("guarantee_phrasing.txt", [], "总括保证句：「一直在画面里」——「它腰间的人头一直在画面里」"),
              # v25（A4）：“始终在画面中央 / 始终位于画面中央”没有规则依据的豁免，整个物件始终在画内、没给切线，照报
              ("guarantee_phrasing.txt", [], "总括保证句：「始终在画面中央」「始终位于画面中央」——「快速后拉到膝盖以上"),
              # v24：密度提醒按新口径（不到 0.5 秒一拍，1 秒里超过 2 个互不相连的动作才算太密）
              ("dense_over_two_per_second.txt", [], "镜1 约 7 个动作节拍挤在 3 秒里（平均不到 0.5 秒一拍"),
              ("dense_beats.txt", [], "1 秒里超过 2 个互不相连的不同动作才算太密"),
              # v24：纯黑没写时长、范围或曝光依据仍报（标题时码、“第N秒”、“上半身”都不算），提醒里给出有意纯黑的写法；压死的黑、什么都没有、再没有第三样照报
              ("void_heading_only.txt", [], "绝对化的空或黑：「纯黑」"),
              ("void_heading_only.txt", [], "有意的纯黑在同一句写明持续多久或占多大范围"),
              ("void_time_point.txt", [], "绝对化的空或黑：「纯黑」"),
              ("void_time_point.txt", [], "绝对化的空或黑：「什么都没有」"),
              ("void_body_half.txt", [], "绝对化的空或黑：「纯黑」"),
              ("absolute_void.txt", [], "绝对化的空或黑：「再没有第三样」"),
              # v24：主体段随动提醒说明镜内每拍可写一处衣物、头发或持物的可见结果
              ("subject_action.txt", [], "衣物、头发、持物的可见结果写进镜内那一拍，每拍最多一处"),
              # v24 审查修复：只写曝光、“一成不变”“大半圈”都不算有意纯黑
              ("void_exposure_only.txt", [], "绝对化的空或黑：「纯黑」"),
              ("void_not_range.txt", [], "绝对化的空或黑：「纯黑」"),
              # ---- v25 一、A10：镜头第一句的“再次”仍提醒 ----
              ("ref_again_first_sentence.txt", [], "可能的引用性措辞：再次"),
              # ---- v25 二、讲戏口吻生效 ----
              # A1：讲戏口吻按句数估拍（2 秒 10 句 → 5 拍）
              ("dense_sentences.txt", [], "镜1 约 5 个动作节拍挤在 2 秒里"),
              # A2：弱词后 0–4 字跟运镜术语，不要求前面写镜头
              ("weak_motion_no_prefix.txt", [], "镜1 运镜用了弱措辞"),
              ("weak_motion_no_prefix.txt", [], "镜2 运镜用了弱措辞"),
              ("../sample-dialogue-12s.txt", [], "镜1 运镜用了弱措辞"),
              ("weak_motion_camera_after_face.txt", [], "镜1 运镜用了弱措辞"),
              # A3：新关键动作词；没带部位限定的“占满画面”仍算整幅遮挡
              ("key_action_new_words.txt", [], "镜1 关键动作「离开它的手」和整幅遮挡「糊住」"),
              ("key_action_new_words.txt", [], "镜2 关键动作「冲向镜头」和整幅遮挡「整幅被」"),
              ("key_action_new_words.txt", [], "镜3 关键动作「松手」和整幅遮挡「占满画面」"),
              # A4：站位保证全稿扫（场景段、风格段、镜内普通句），始终在画面中央照报
              ("guarantee_position_scan.txt", [], "总括保证句：「左右位置全程不变」——「两人的左右位置全程不变」；站位保证"),
              ("guarantee_position_scan.txt", [], "总括保证句：「站位始终不变」——「两人的站位始终不变」"),
              ("guarantee_position_scan.txt", [], "镜1 总括保证句：「相对位置一直保持不变」——「苏云与罗大娘的相对位置一直保持不变」"),
              ("guarantee_position_scan.txt", [], "总括保证句：「始终在画面中央」——「灯笼始终在画面中央」"),
              # A6：紧跟段落标题 / 镜头标题的第一句、严禁 / 请勿 / 别
              ("negative_after_heading.txt", [], "否定句：不要任何声音"),
              ("negative_after_heading.txt", [], "否定句：不出现第二个人"),
              ("negative_after_heading.txt", [], "否定句：严禁出现文字水印"),
              ("negative_after_heading.txt", [], "否定句：请勿让窗外出现路人"),
              ("negative_after_heading.txt", [], "否定句：别让轻纱挡住他的脸"),
              ("negative_after_heading.txt", [], "writing-rules 附录第 62 条"),
              # A8：按句取最近的景别或画框切线；“近景（不是特写）”不豁免
              ("micro_scale_per_sentence.txt", [], "镜1 尺度名词「织纹」"),
              ("micro_scale_per_sentence.txt", [], "镜2 尺度名词「抽丝」"),
              # A9：重心与转肩转胯连写才报；力 / 劲……传到任意部位、蓄力
              ("force_chain_mechanism.txt", [], "镜2 发力过程写法：「转肩」「转胯」「重心移到」"),
              ("force_chain_mechanism.txt", [], "机制词：「传到」"),
              ("force_chain_mechanism.txt", [], "机制词：「蓄力」"),
              # A13：取景写成能装下什么（L101 原稿 lantern_trial_s 也报）
              ("framing_fit_words.txt", [], "镜1 取景写成了“能装下什么”：「拉到能看见」"),
              ("framing_fit_words.txt", [], "镜2 取景写成了“能装下什么”：「刚够装下」"),
              ("lantern_trial_s.txt", ["--total", "6"], "镜1 取景写成了“能装下什么”：「刚够装下」"),
              # A15：主体段的情绪词与动作单字
              ("subject_emotion_action.txt", ["--labels", "图1"], "「拔」「愤怒」「冷笑」——「他满脸愤怒，冷笑着拔出长刀」"),
              ("subject_emotion_action.txt", ["--labels", "图1"], "情绪不写主体段"),
              # A16：风格段的随动、表演、放慢后恢复；风格段写“衣料随步伐摆动”的旧夹具在现行规则下就该报
              ("style_follow_perf.txt", [], "风格段里有时序或具体运镜/动作：「随步伐」「摆动」「表演」「克制」「眼神」「后恢复」"),
              ("control_valid.txt", [], "风格段里有时序或具体运镜/动作：「随步伐」「摆动」"),
              ("../sample-dialogue-12s.txt", [], "风格段里有时序或具体运镜/动作：「随呼吸」「微动」「表演」「克制」「眼神」"),
              ("../sample-combat-12s.txt", [], "风格段里有时序或具体运镜/动作：「后恢复」"),
              # A17：图片N / 视频片段N；同一段里同一素材绑定两次
              ("asset_long_form.txt", [], "新稿素材统一写 图N / 视频N / 音频N：「图片1」「视频片段2」"),
              ("asset_long_form.txt", [], "素材 图1 在主体段绑定了 2 次"),
              # A18：主体段、场景段、镜内的画质词；风格段画质词不在最后一句；解释词补“为了表现”；风格段只有画质词
              ("quality_words_sections.txt", [], "主体段里有画质词「8K」「高清」"),
              ("quality_words_sections.txt", [], "场景段里有画质词「电影级」"),
              ("quality_words_sections.txt", [], "风格段的画质词「电影感」不在最后一句"),
              ("quality_words_sections.txt", [], "镜1 镜头正文里有画质词「精美」"),
              ("quality_words_sections.txt", [], "空词：为了表现"),
              ("quality_style_only.txt", [], "风格段只有画质词"),
              # A20：镜头标题的非整数秒
              ("dense_exact_half_second.txt", [], "镜头标题的秒数不是整数：「0-1.1秒」「1.1-4.1秒」「4.1-12秒」"),
              # B1：只认摄影运动术语（对话样例镜 2、镜 3 只有表演，没有运镜）
              ("camera_person_actions.txt", [], "镜1 未识别到摄影运动；本用户默认每镜有可见运镜，固定须有用户要求或保护来源"),
              ("../sample-dialogue-12s.txt", [], "镜2 未识别到摄影运动"),
              ("../sample-dialogue-12s.txt", [], "镜3 未识别到摄影运动"),
              # B2：正文里有素材引用而没给 --labels 才提醒；B5 对照：没给 --asks 时“震撼”照报空词
              ("at_refs_in_new_draft.txt", [], "没有给 --labels，素材集合未核对"),
              ("asks_empty_word_draft.txt", [], "空词：震撼"),
              # ---- 压缩审校（2026-09-24，成文主规则第 5 条）：三条提醒的原文 ----
              ("density_over_line.txt", ["--density-line", "90"], "镜1 每秒 102 字，超过参考线 90（暂定，待 A/B 实测）；看看有没有复述或模型自己会补的东西（成文主规则第 5 条）"),
              ("repeat_phrase.txt", [], "复读提醒：「她的影子长长地拖在石阶上」在情节里出现 2 次，第二次起可能是复述，留不留你定；落幅、焦点落点、每镜自足的句子照留（成文主规则第 5 条）"),
              ("repeat_phrase.txt", ["--baseline", str(C / "repeat_phrase_parent.txt")], "复读提醒：「她的影子长长地拖在石阶上」在情节里出现 2 次"),
              ("filler_words_over.txt", [], "镜1 虚词 5 个（逐渐、缓缓、一路、随之、此时），顺序和时间已清楚的可删，逐渐、缓缓改成具体变化或速度而不是删（成文主规则第 5 条）"),
              # 灯笼怪 v23 试写（notes 原稿副本）：镜1 806 字 / 6 秒；落幅把“一个挑着暖光的小身影”又写了一遍
              ("lantern_v23_trial.txt", ["--total", "6", "--density-line", "90"], "镜1 每秒 134 字，超过参考线 90"),
              ("lantern_v23_trial.txt", ["--total", "6"], "复读提醒：「一个挑着暖光的小身影」在情节里出现 2 次"),
              ("lantern_trial_v22.txt", ["--total", "6", "--density-line", "90"], "镜1 每秒 120 字，超过参考线 90"),
              ("lantern_trial_s.txt", ["--total", "6"], "镜1 虚词 4 个（一路×3、继续）"),
              # v31：没有终点的程度词（L098）、串行运镜句数
              ("open_degree.txt", ["--total", "6"], "程度词没有终点"),
              ("serial_camera.txt", ["--total", "6"], "串行运镜 7 句挤在 6 秒里"),
              # v35 表演排队：正例应报（一镜合并一条，逐处列出）；物理依赖（放下杯子之后才去开门）也报——合法误报，裁定保留
              ("perf_queue_report.txt", [], "镜1 可能的表演排队：「说完“…”，苏云才抬头」「他停顿一下，才开口」；按成文主规则第 8 条"),
              ("perf_queue_report.txt", [], "镜2 可能的表演排队：「他放下杯子之后才去开门」；"),
              ("perf_queue_report.txt", [], "感知、身体条件或观看目的确需先后时可保留（逐条裁定）"),
              # “推到胸口之后才移焦”没有显式摄影主体、也不是纯摄影动词对：保留警告交 AI 裁定
              ("perf_queue_camera_subject.txt", [], "镜1 可能的表演排队：「推到胸口之后才移焦」；"),
              # 混合语境：每镜只报人物排队那一处（摘录后紧跟“；”，说明没有别的摘录）
              ("perf_queue_mixed.txt", [], "镜1 可能的表演排队：「苏云推门之后才抬头」；"),
              ("perf_queue_mixed.txt", [], "镜2 可能的表演排队：「说完才回应」；"),
              ("perf_queue_mixed.txt", [], "镜3 可能的表演排队：「说完才转身」；"),
              ("perf_queue_mixed.txt", [], "镜4 可能的表演排队：「他又说完才回应」；"),
              ("perf_queue_mixed.txt", [], "镜5 可能的表演排队：「苏云推门之后才抬头」；"),
              # 样例对话稿镜头3 的“说完嘴角向下一沉”是应报提醒（D2 baseline 预记，不算误报）
              ("../sample-dialogue-12s.txt", [], "镜3 可能的表演排队：「“…”说完嘴角向下一沉」"),
              # 2026-10-01 五条提醒：正例的原文
              ("weak_angle.txt", [], "镜1 角度词前加了削弱词：「微微仰起」"),
              ("weak_angle.txt", [], "镜2 角度词前加了削弱词：「稍微俯拍」"),
              ("weak_angle.txt", [], "（writing-rules 成文主规则第 6 条、L050）"),
              ("orient_dir_only.txt", [], "镜1 朝向只写了方位词：「看向右前方」"),
              ("orient_face_toward.txt", [], "镜1 朝向只写了方位词：「朝向画面右侧」"),   # 回放补：埋雷稿原句的写法
              ("orient_face_toward.txt", [], "镜2 朝向只写了方位词：「面向画面左侧」"),   # v38 动词表加「面向」
              ("orient_face_eye.txt", [], "镜1 朝向只写了方位词：「朝向画面右侧」"),   # 埋雷稿原句：一只暗红的眼睛盯着上方，只有部位字、没有可见写法
              ("orient_face_eye.txt", [], "镜2 朝向只写了方位词：「转向画面左侧」"),   # “转眼间”的眼不是部位判据
              ("density_under_line.txt", [], "镜1 朝向只写了方位词：「看向画面左侧」"),   # 嘴角、额头是表情与细节，不是朝向判据，照报
              ("ap_baimo_lens.txt", ["--labels", "图1,视频1", "--mode", "白模"], "反模式 AP07（候选，未试（模式约定，L153））：「镜头1（0-6秒）」「镜头2（6-12秒）」"),
              ("ap_baimo_lens.txt", ["--labels", "图1,视频1", "--mode", "白模"], "反模式 AP08（候选，未试（模式约定，L153））：「24mm」「超广角」"),
              ("ap_baimo_lens.txt", ["--labels", "图1,视频1", "--mode", "白模"], "反模式 AP09（候选，未试（模式约定，L153））：命令区没有「严格保持」「切点前后状态一致」「角色一致性」任一句"),   # 命令区没有严格保持 / 切点前后状态一致 / 角色一致性
              ("ap_speed_center_resize.txt", [], "镜2 反模式 AP01（两条以上 L047、L144）：「钉在画面中心」"),
              ("lantern_trial_s.txt", ["--total", "6"], "同一镜里既有远处位置又有贴镜动作"),   # “甩到身后最远处”不在背景层句里，照报
              ("ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模"], "反模式 AP05（两条以上 L152）：「方块对应竹子」「圆盘对应山」"),   # 环境词表补竹、草、房、墙、桥、山、路
              ("ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模"], "反模式 AP07（候选，未试（模式约定，L153））：「第2秒」"),   # 标题不带秒数，正文的第几秒也抓
              ("ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模", "--shot-seconds", "0.1,0.1"], "白模短镜只写一件事的可见结果"),   # v40 无时码稿给每镜秒数后逐镜算密度
              ("ap_speed_center.txt", [], "镜1 反模式 AP01（两条以上 L047、L144）：「保持在画面中央」"),
              ("far_near_rub.txt", [], "「尽头」在前、「擦着镜头」在后"),
              ("orient_dir_only.txt", [], "镜2 朝向只写了方位词：「脸朝画面左侧」"),
              ("orient_dir_only.txt", [], "（writing-rules 决策 D09、L059）"),
              ("orient_dir_self.txt", [], "镜1 朝向只写了方位词：「望着自己的右前方」"),
              ("follow_no_evidence.txt", [], "镜1 跟拍没有位移证据：「贴在他身后」「跟拍」「一起往巷子深处跑」"),
              ("follow_no_evidence.txt", [], "（writing-rules 决策 D01、D04，L044、L143）"),
              # v37：④⑤ 并进反模式表 AP01、AP03（同一批夹具，改核对表驱动的文案；AP03 场合是任何，一稿报一条、不带镜号）
              ("hold_frame_speed.txt", [], "镜1 反模式 AP01（两条以上 L047、L144）：「位置和大小稳住」"),
              ("hold_frame_speed.txt", [], "镜2 反模式 AP01（两条以上 L047、L144）：「大小和位置始终不变」"),
              ("hold_frame_speed.txt", [], "；恒定约束把主体钉在原地，只剩背景在动；改成：写主体在画框里反复越界、镜头追回"),
              ("scale_simile_object.txt", [], "反模式 AP03（候选，单次 L154）：「有房子那么大」"),
              ("scale_simile_object.txt", [], "碗口大小的」「像山一样高」"),
              ("scale_simile_object.txt", [], "；比喻的喻体被画成实物（房子）；改成：用画内参照比大小：比它的头还大"),
              ("framing_show_body.txt", [], "镜1 取景写成了“能装下什么”：「露出它往上盘的长身体」"),
              ("framing_show_body.txt", [], "镜2 取景写成了“能装下什么”：「看到它的全身」"),
              ("framing_show_l145.txt", [], "镜1 取景写成了“能装下什么”：「露出它螺旋着往天上盘的长身体」"),   # L145 引的原句，“露出”后隔 9 个字
              ("framing_show_l145.txt", [], "同样会把机位拉远（L145）"),
              ("framing_show_body.txt", [], "（writing-rules 决策 D07、L101）；露出 / 看到 + 全身、长身体同样会把机位拉远（L145）"),
              # ---- v37 反模式表：逐镜的行带镜号、放在这一镜最后，全稿级的不带镜号；单次 / 未试标「候选」；AP02 沿用老文案、末尾标编号 ----
              ("ap_speed_hold.txt", [], "镜1 反模式 AP01（两条以上 L047、L144）：「位置和大小稳住」；恒定约束把主体钉在原地，只剩背景在动；改成："),
              ("ap_speed_hold.txt", [], "镜3 反模式 AP06（候选，单次 L150）：「慢慢」"),
              ("ap_speed_size.txt", [], "镜1 反模式 AP01（两条以上 L047、L144）：「大小不变」"),   # 蛟龙 helix 稿原句，v36 的④报过
              ("ap_any_rows.txt", [], "反模式 AP03（候选，单次 L154）：「有房子那么大」；比喻的喻体被画成实物（房子）"),
              ("ap_any_rows.txt", [], "反模式 AP04（候选，单次 L154）：「龙卷风柱」"),
              ("ap_any_rows.txt", [], "镜1 取景写成了“能装下什么”：「露出它的全身」"),
              ("ap_any_rows.txt", [], "同样会把机位拉远（L145）；反模式 AP02（两条以上 L145、L045）"),
              ("framing_fit_words.txt", [], "（writing-rules 决策 D07、L101）；反模式 AP02（两条以上 L145、L045）"),
              ("ap_baimo.txt", ["--labels", "图1,视频1"], "情节段开头有总览句：「灰色方块对应漂浮的碎石"),
              ("ap_baimo.txt", ["--labels", "图1,视频1", "--mode", "白模"], "反模式 AP05（两条以上 L152）：「方块对应漂浮的碎石」「圆柱对应龙卷」"),
              ("hold_frame_speed.txt", ["--adjudicated", str(C / "adjudicated_shot.txt")], "镜1 反模式 AP01"),   # 行首带镜号只删那一镜
              # 显式 --mode 默认：朝向方位词、跟拍位移证据、摄影运动三条照报（--mode 白模 的反例在 NO_WARN_CASES）
              ("orient_dir_only.txt", ["--mode", "默认"], "镜1 朝向只写了方位词：「看向右前方」"),
              ("follow_no_evidence.txt", ["--mode", "默认"], "镜1 跟拍没有位移证据"),
              ("camera_person_actions.txt", ["--mode", "默认"], "镜1 未识别到摄影运动")]
for f, extra, key in WARN_CASES:
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / f), "--total", "12", *extra], text=True, encoding="utf-8", errors="replace", capture_output=True)
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
                 ("control_valid.txt", [], "空词："),
                 # v21：已错开或遮挡被否定的不报；只写结果的不报；并入发力过程后机制词不单独报；
                 # 锁定文字里的重心类不报；干净稿不误伤；机制词新文案不再举“肩膀滞后”；a-b秒 标题不算总览句；
                 # key_action_negated 里另有“不会糊住”，覆盖遮挡词前两字的否定窗口
                 ("key_action_staggered.txt", [], "整幅遮挡"),
                 ("key_action_negated.txt", [], "整幅遮挡"),
                 ("force_result.txt", [], "发力过程"),
                 ("force_process.txt", [], "机制词：「惯性」"),
                 ("force_process.txt", ["--lock", "重心压在后脚上"], "「重心压在」"),
                 ("control_valid.txt", [], "整幅遮挡"),
                 ("control_valid.txt", [], "发力过程"),
                 ("mechanism_words.txt", [], "肩膀滞后"),
                 ("four_section_seconds_heads.txt", [], "总览句"),
                 # v21 修复：--asks 有效要求里的机制词（用户原话）不报
                 ("mechanism_words.txt", ["--asks", str(C / "asks_mech.txt")], "机制词：「惯性」"),
                 # v22：像标签但不是的写法、风格段的画质尾巴、父稿里原样存在的标签、镜头标题本身、灯笼怪两稿都不报
                 ("shot_labels_lookalike.txt", [], "镜内标签"),
                 ("shot_labels_lookalike.txt", [], "画质词"),
                 ("shot_labels.txt", ["--baseline", str(C / "shot_labels.txt")], "镜内标签"),
                 ("control_valid.txt", [], "镜内标签"),
                 ("four_section_seconds_heads.txt", [], "镜内标签"),
                 ("lantern_v21_trial.txt", [], "镜内标签"),
                 ("lantern_style_draft.txt", [], "镜内标签"),
                 # v22 审查修复：“第N拍”只在句首并紧跟冒号、逗号或句末才算（音乐卡点、拍打次数不报）
                 ("shot_labels_beat_lookalike.txt", [], "镜内标签"),
                 # v23：绑定句、静态外形（挑着 / 斜披 / 一直咧到）、不采用分句、数量锁、身份锁、唯一光源、场景天气、
                 # 风格段全程手持、一镜到底、点名部位的镜内取景约束（头部和双肩始终留在画内）都不报；素材绑定句里的“机位”不算调度；锁定文字不报；局部替换不报父稿主体段
                 ("subject_clean.txt", [], "主体段这句"),
                 ("subject_clean.txt", [], "总括保证句"),
                 ("subject_action.txt", ["--lock", "上下牙不停地磕"], "牙不停地磕"),
                 ("extend_ok.txt", [], "主体段这句"),
                 ("guarantee_lock.txt", [], "全程手持"),
                 ("guarantee_lock.txt", [], "全片只有他"),
                 ("guarantee_headerless.txt", [], "地平线始终"),
                 ("guarantee_headerless.txt", [], "全程手持摄影"),
                 # v23 审查后同日修正：“手持”后面没有道具名词时是镜头性格（手持近距离镜头），不算持物也不算总括
                 ("guarantee_headerless.txt", [], "手持近距离镜头"),
                 ("control_valid.txt", [], "主体段这句"),
                 ("control_valid.txt", [], "总括保证句"),
                 ("../sample-dialogue-12s.txt", [], "主体段这句"),
                 ("partial_subject_shot2.txt", ["--baseline", str(C / "subject_action.txt"), "--partial"], "主体段这句"),
                 # v23：两份试写稿里的数量锁、静态外形、唯一光源、风格段镜头性格不报
                 ("lantern_trial_s.txt", ["--total", "6"], "画面里只有一个实体的灯笼怪"),
                 ("lantern_trial_s.txt", ["--total", "6"], "全身被雨淋透"),
                 ("lantern_trial_s.txt", ["--total", "6"], "全程保持这一种风格"),
                 ("lantern_trial_v22.txt", ["--total", "6"], "全片只有一个挑着亮灯笼"),
                 ("lantern_trial_v22.txt", ["--total", "6"], "灯笼是唯一的暖光源"),
                 ("lantern_trial_v22.txt", ["--total", "6"], "灯笼里点着火"),
                 # v23 审查修复：单独的“没有出画”不算总括；晃眼、掠食是外形，伤口持续渗血是伤势（“始终在画面中央”v25 起照报，见 WARN_CASES）
                 ("guarantee_phrasing.txt", [], "没有出画」"),
                 ("subject_wordlist.txt", [], "晃眼"),
                 ("subject_wordlist.txt", [], "掠食"),
                 ("subject_wordlist.txt", [], "渗血"),
                 # v23 审查后同日修正：写明“全片不换手”的道具归属是身份层面的事实，不报；点名部位或切线的镜内取景约束不报
                 ("subject_wordlist.txt", [], "短刀"),
                 ("guarantee_scope.txt", [], "「快速后拉到膝盖以上"),
                 ("guarantee_scope.txt", [], "大小和位置"),
                 ("guarantee_scope.txt", [], "切在它的膝盖"),
                 # 场景段的天气与环境反应、鸟群、落叶、“不采用图中人群”不报；镜内的冤魂活动不走场景段提醒
                 ("scene_activity.txt", [], "雨丝"),
                 ("scene_activity.txt", [], "破幡"),
                 ("scene_activity.txt", [], "鸟"),
                 ("scene_activity.txt", [], "落叶"),
                 ("scene_activity.txt", [], "不采用图中人群"),
                 ("scene_activity.txt", [], "主体段这句"),
                 ("subject_clean.txt", [], "场景段这句"),
                 # v23 第二次复查修正：镜头正文里的跟拍取景（大小和位置始终不变、头部和双肩始终留在画内）仍不报
                 ("guarantee_subject_position.txt", ["--labels", "图1,图2"], "大小和位置"),
                 ("guarantee_subject_lantern.txt", [], "「快速后拉到膝盖以上"),
                 # 风格段的镜头性格（全程手持）不报；干净稿不报风格段角色活动
                 ("style_activity.txt", [], "全程手持"),
                 ("style_activity.txt", [], "主体段这句"),
                 ("style_clean.txt", [], "风格段这句"),
                 ("subject_clean.txt", [], "风格段这句"),
                 ("lantern_trial_v22.txt", ["--total", "6"], "风格段这句"),
                 # 总览句“；”后的分句不再单独成条；场景段同句不再另报一条总括
                 ("guarantee_overview_merge.txt", [], "——「焦点始终留在灯笼上」"),
                 ("guarantee_overview_merge.txt", [], "总括保证句：「始终在画面里」——「冤魂始终在画面里"),
                 # 麻绳穿过腰间是外形，盔甲经过雨水冲刷是表面状态
                 ("bg_activity_wordlist.txt", [], "麻绳穿过"),
                 ("bg_activity_wordlist.txt", [], "盔甲经过"),
                 # 参考图看不出的外形状态（一直湿透）与身份句（始终是同一颗、同一主体始终是同一个连续对象）不算总括
                 ("guarantee_exempt_states.txt", [], "总括保证句"),
                 ("guarantee_exempt_states.txt", [], "主体段这句"),
                 # v24：正好 0.5 秒一拍不报密度；有意的纯黑不报；“压死的黑”的提醒不带有意纯黑的写法；全局段材质词不扫；随动提醒不再说“交给模型”
                 ("dense_two_per_second.txt", [], "节拍"),
                 ("dense_exact_half_second.txt", [], "节拍"),
                 ("void_intentional.txt", [], "绝对化的空或黑"),
                 ("absolute_void.txt", [], "有意的纯黑"),
                 ("micro_scale_in_global.txt", [], "尺度名词"),
                 ("subject_action.txt", [], "否则交给模型"),
                 # v24 审查修复：“先”“同时”不另算一拍；“不采用图中的纯黑背景”不扫；全程用右手握棍不算总括也不算主体段动作
                 ("dense_xian_tongshi.txt", [], "节拍"),
                 ("void_ref_bg_excluded.txt", ["--labels", "图1"], "绝对化的空或黑"),
                 ("prop_hand_in_subject.txt", [], "总括保证句"),
                 ("prop_hand_in_subject.txt", [], "主体段这句"),
                 ("tried_negative_exception.txt", ["--negative-exception", "开始的一秒画面是纯黑，看不到任何轮廓、光点或亮边；暗部不做任何补光"], "否定句"),
                 # ---- v25 一、A10：镜内第二句以后的“再次”指同一镜前面的动作，不报 ----
                 ("ref_wording_lookalike.txt", [], "再次"),
                 # ---- v25 二、讲戏口吻生效 ----
                 # A1：4 句 / 2 秒 = 2 拍不报；灯笼怪 v23 试写与讲戏口吻重写稿都是 24 句 / 6 秒，正好 0.5 秒一拍不报
                 ("dense_sentences.txt", [], "镜2 约"),
                 ("lantern_v23_trial.txt", ["--total", "6"], "节拍"),
                 ("lantern_style_draft.txt", ["--total", "6"], "节拍"),
                 # A2：人物与面部描写里的微微 / 轻微（嘴角轻微下拉、眉头轻微下压，writing-rules 第 1 道门正例）不算弱运镜；有横移、慢推就算有摄影运动
                 ("weak_motion_person.txt", [], "弱措辞"),
                 ("weak_motion_person.txt", [], "未识别到摄影运动"),
                 # A3：关键主体自己占满画面下半 / 右下一块不算整幅遮挡（成文主规则第 2 条正例、灯笼怪两稿）
                 ("key_event_rule2_example.txt", [], "整幅遮挡"),
                 ("lantern_trial_v22.txt", ["--total", "6"], "整幅遮挡"),
                 ("lantern_v23_trial.txt", ["--total", "6"], "整幅遮挡"),
                 # A4：跟拍取景（它在画面里的大小和位置始终不变）不算站位保证；道具停在画面哪里不按站位报
                 ("guarantee_position_scan.txt", [], "——「近景跟拍罗大娘"),
                 ("guarantee_position_scan.txt", [], "「位置一直保持」"),
                 # A5：全程右手握着铁棒、属于、拿在手里、亮着 / 熄着 / 是湿的；场景段的雨丝、灯光
                 ("guarantee_exempt_more.txt", [], "总括保证句"),
                 ("guarantee_exempt_more.txt", [], "主体段这句"),
                 # A6：“别墅”不是劝阻；点名后的静音句不再提醒
                 ("negative_after_heading.txt", [], "别墅"),
                 ("negative_after_heading.txt", ["--negative-exception", "不要任何声音。"], "否定句：不要任何声音"),
                 # A7：命令区的参考视频与首帧句不算总览句；没有“情节：”标题的稿不报总览句
                 ("command_zone_reference.txt", ["--labels", "图1,图2,图3,视频1"], "总览句"),
                 ("guarantee_headerless.txt", [], "总览句"),
                 # A8：“近景，推近到大特写”之后的织纹按大特写算
                 ("micro_scale_per_sentence.txt", [], "镜3 尺度名词"),
                 # A9：单独一句“重心移到左脚”不报
                 ("force_chain_mechanism.txt", [], "镜1 发力过程"),
                 # A14：远处与贴镜之间有推近；灯笼怪 v21 试稿（贴镜在前、远处在后，中间还有拉远）不再误报
                 ("far_near_transition.txt", [], "既有远处位置又有贴镜动作"),
                 ("lantern_v21_trial.txt", [], "既有远处位置又有贴镜动作"),
                 # A15：明晃晃、挺拔是外形
                 ("subject_emotion_action.txt", ["--labels", "图1"], "明晃晃"),
                 ("subject_emotion_action.txt", ["--labels", "图1"], "挺拔"),
                 # A16：跟随感、稳定器般、呼吸感的手持、画面边缘随呼吸浮动是镜头性格
                 ("style_camera_character.txt", [], "风格段里有时序"),
                 # A17：“用于……；不采用……”不算两次绑定；不写图片N的稿不报
                 ("asset_bind_skip.txt", ["--labels", "图1"], "绑定了"),
                 ("no_at_refs.txt", ["--labels", "图1,图2,音频1"], "统一写"),
                 # A18：风格段末尾的画质尾巴不报，也不算“只有画质词”
                 ("quality_style_tail.txt", [], "画质词"),
                 # B1：推近、后撤都是摄影运动；编辑命令的摄影按原视频不报
                 ("../sample-dialogue-12s.txt", [], "镜1 未识别到摄影运动"),
                 ("../sample-combat-12s.txt", [], "镜2 未识别到摄影运动"),
                 ("edit_remove.txt", ["--labels", "视频1,图1"], "未识别到摄影运动"),
                 # B2：正文里没有素材引用时不提醒 --labels
                 ("control_valid.txt", [], "没有给 --labels"),
                 # B5：--asks 有效要求里的空词不报
                 ("asks_empty_word_draft.txt", ["--asks", str(C / "asks_empty_word.txt")], "空词：震撼"),
                 # ---- 压缩审校（2026-09-24）：台词不算字数；豁免的重复；时序词与速度词；改稿时父稿原样的部分；锁定文字 ----
                 ("density_under_line.txt", [], "参考线"),
                 ("repeat_phrase_exempt_subject.txt", [], "复读提醒"),
                 ("repeat_phrase.txt", [], "画框下缘切在"),
                 ("filler_words_ok.txt", [], "虚词"),
                 ("lantern_v23_trial.txt", ["--total", "6"], "超过参考线"),   # 默认参考线 200：v23 的 134 字/秒不报
                 ("repeat_phrase.txt", ["--baseline", str(C / "repeat_phrase.txt")], "复读提醒"),
                 ("density_over_line.txt", ["--baseline", str(C / "density_over_line.txt")], "参考线"),
                 ("filler_words_over.txt", ["--baseline", str(C / "filler_words_over.txt")], "虚词"),
                 ("filler_words_over.txt", ["--lock", "他从画面右下方逐渐走进画面，镜头缓缓后拉"], "虚词"),
                 # 旧夹具里的同形不同事：“画框下缘切在灯笼后方…/切在它的小腿”“朝画面左上方”“贴着 / 擦着镜头从画面…”
                 # “镜头跟着大幅度”“在画面左上方 ×3”“它下方的雪面”都是切线、坐标或各拍自己的运镜，不报复读
                 ("lantern_trial_v22.txt", ["--total", "6"], "复读提醒"),
                 ("lantern_v21_trial.txt", [], "复读提醒"),
                 ("lantern_trial_s.txt", ["--total", "6"], "复读提醒"),
                 ("../sample-combat-12s.txt", [], "复读提醒"),
                 ("control_valid.txt", [], "复读提醒"),
                 ("control_valid.txt", [], "参考线"),
                 ("control_valid.txt", [], "虚词"),
                 # v31：程度词后面有终点不报；三句运镜不到镜长一半不报，宾语位置的“镜头”不算主语
                 ("open_degree_with_end.txt", ["--total", "6"], "程度词没有终点"),
                 ("serial_camera_ok.txt", ["--total", "6"], "串行运镜"),
                 # v35 表演排队：没等她说完 / 话音未落 / 说到一半 / 镜头推到胸口之后才移焦 / 后拉之后才移焦 / 不等他做完、
                 # 台词里的“你说完了吗”、单独的然后 / 随后 / 接着都不报；锁定文字不报；样例打斗稿、对话稿镜1–2 不报
                 ("perf_queue_overlap_ok.txt", [], "表演排队"),
                 ("perf_queue_report.txt", ["--lock", "他放下杯子之后才去开门"], "镜2 可能的表演排队"),
                 ("../sample-combat-12s.txt", [], "表演排队"),
                 ("../sample-dialogue-12s.txt", [], "镜1 可能的表演排队"),
                 ("../sample-dialogue-12s.txt", [], "镜2 可能的表演排队"),
                 ("control_valid.txt", [], "表演排队"),
                 # 2026-10-01 五条提醒：反例不报。表演句（嘴角微微上扬、头微微仰起、微微俯下身）、略高于、稍作停顿、稍后；
                 # 带部位判据的朝向、没有左右的望向、右手、镜头转向；跟拍有位移证据、不再跟拍、跟随感、目光跟住；编辑命令的“跟随原有动作”；
                 # 没有速度词的位置和大小不变；总括保证句的跟拍取景豁免保留不动；主体部位做参照的尺度与不同大小的；
                 # 能看见全身已按 FRAMING_FIT_RE 报过、不重复列也不加 L145
                 ("weak_angle_ok.txt", [], "角度词前加了削弱词"),
                 ("weak_motion_person.txt", [], "角度词前加了削弱词"),
                 ("orient_dir_parts.txt", [], "朝向只写了方位词"),
                 ("follow_with_evidence.txt", [], "跟拍没有位移证据"),
                 ("follow_no_evidence.txt", [], "镜2 跟拍没有位移证据"),
                 ("hold_frame_speed.txt", [], "跟拍没有位移证据"),
                 ("edit_ok.txt", ["--task", "编辑", "--labels", "视频1,图片1"], "跟拍没有位移证据"),
                 ("hold_frame_slow.txt", [], "反模式 AP01"),
                 ("hold_frame_slow.txt", [], "总括保证句"),
                 ("hold_frame_speed.txt", [], "总括保证句"),
                 ("guarantee_position_scan.txt", [], "反模式 AP01"),
                 ("scale_simile_self.txt", [], "反模式 AP03"),
                 ("framing_show_ok.txt", [], "取景写成了"),
                 ("framing_fit_words.txt", [], "（L145）"),
                 # ---- v37 反模式表与降噪开关的反例 ----
                 ("ap_speed_hold.txt", [], "镜2 反模式 AP01"),          # 同一句写在没有速度词的慢推镜里不报
                 ("ap_speed_hold.txt", [], "镜1 反模式 AP06"),
                 ("ap_speed_hold.txt", [], "镜2 反模式 AP06"),          # “慢推”不是慢慢 / 缓缓 / 缓慢，这一镜也不是速度镜
                 ("ap_speed_size.txt", [], "镜2 反模式 AP01"),          # 机位的位置固定说的是相机
                 ("ap_any_rows.txt", [], "反模式 AP05"),                # 白模的行只在 --mode 白模 时扫
                 ("ap_any_rows.txt", [], "「比它的头还大」"),            # 画内参照比大小，不报 AP03
                 ("ap_any_rows.txt", ["--asks", str(C / "asks_ap_tornado.txt")], "反模式 AP04"),   # 命中词是有效要求的关键词
                 ("ap_any_rows.txt", ["--lock", "四周悬着几块有房子那么大的岩石。"], "反模式 AP03"),   # 锁定文字不扫
                 ("ap_baimo.txt", ["--labels", "图1,视频1"], "反模式 AP05"),
                 ("ap_baimo.txt", ["--labels", "图1,视频1", "--mode", "白模"], "总览句"),
                 ("ap_baimo.txt", ["--labels", "图1,视频1", "--mode", "白模"], "图1中蛟龙的头部"),   # 对应图N 的角色映射不报 AP05
                 ("revise_dropped_two.txt", ["--baseline", str(C / "revise_parent.txt"), "--rewrite-authorized"], "在新稿里消失"),
                 ("revise_padded.txt", ["--baseline", str(C / "revise_parent.txt"), "--rewrite-authorized"], "新稿比父稿长"),
                 ("ap_speed_hold.txt", ["--adjudicated", str(C / "adjudicated_ap.txt")], "反模式 AP01"),
                 ("hold_frame_speed.txt", ["--adjudicated", str(C / "adjudicated_shot.txt")], "镜2 反模式 AP01"),
                 # --mode 白模：朝向和运镜由视频1给，朝向方位词、跟拍位移证据、摄影运动三条不报（默认模式照报，见 WARN_CASES）
                 ("orient_dir_only.txt", ["--mode", "白模"], "朝向只写了方位词"),
                 ("follow_no_evidence.txt", ["--mode", "白模"], "跟拍没有位移证据"),
                 ("camera_person_actions.txt", ["--mode", "白模"], "未识别到摄影运动"),   # 命令区没有“白模”二字也不报
                 ("orient_face_toward_parts.txt", [], "朝向只写了方位词"),   # 同一句写了露出的部位（右耳、后脑）就不报
                 ("orient_part_visible.txt", [], "朝向只写了方位词"),   # 附录第 33 条、L059 的三种原句写法：鼻尖和下巴指向、后脑留在、右耳露出后半只
                 ("camera_person_actions.txt", [], "朝向只写了方位词"),   # “抬眼看向画面右上方”是视线
                 ("repeat_phrase_exempt_subject.txt", [], "朝向只写了方位词"),   # “抬眼看向画面右侧外”是视线
                 ("repeat_phrase.txt", [], "朝向只写了方位词"),   # “夕阳把她的侧脸勾出一道亮边”：受光面印证朝向（L059、决策 D11）
                 ("ap_baimo_lens.txt", ["--labels", "图1,视频1"], "反模式 AP07"),   # 白模的行只在 --mode 白模 时扫
                 ("ap_baimo_lens.txt", ["--labels", "图1,视频1"], "反模式 AP08"),
                 ("ap_baimo_lens.txt", ["--labels", "图1,视频1"], "反模式 AP09"),   # 默认模式不报
                 ("ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模"], "反模式 AP09"),   # 命令区写了严格保持……角色一致性全程保持
                 ("ap_speed_center_resize.txt", [], "镜1 反模式 AP01"),   # 留在画面正中，后面跟着“一点点变小”：大小在变，不是恒定约束（M007 那种）
                 ("far_near_bg_layer.txt", [], "远处位置又有贴镜动作"),   # “背景是远处……”是层次，碎块擦着镜头是另一样东西（M010 原句）
                 ("ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模"], "人形对应图1"),   # 对应图N 的角色映射照旧不报
                 ("ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模", "--shot-seconds", "6,6"], "超过参考线"),   # v40 秒数够长不报密度
                 ("ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1", "--mode", "白模"], "超过参考线"),   # 没给 --shot-seconds 的无时码稿照旧不算密度
                 ("ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1"], "反模式 AP05"),   # 默认模式不扫白模的行
                 ("ap_baimo_env.txt", ["--untimed", "--labels", "图1,视频1"], "反模式 AP07"),
                 ("ap_speed_center.txt", [], "镜2 反模式 AP01")]   # “留在画面正中”在慢推镜里，不是速度镜
for f, extra, key in NO_WARN_CASES:
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / f), "--total", "12", *extra], text=True, encoding="utf-8", errors="replace", capture_output=True)
    d = json.loads(p.stdout); hit = [w for w in d["warnings"] if key in w]; ok = not hit; fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {f} 不触发“{key}”提醒 |", hit[:1] or "ok")

# ---- 四段稿的否定提醒：镜内一条给一条提醒；--negative-exception 点名后不再提醒 ----
for args, want_n, label in [([], 1, "镜内否定：提醒 1 条"),
                            (["--negative-exception", "不出现第二个白猿。"], 0, "点名后：提醒 0 条")]:
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / "inline_negative.txt"), "--total", "12", *args],
                       text=True, encoding="utf-8", errors="replace", capture_output=True)
    d = json.loads(p.stdout)
    hits = [w for w in d["warnings"] if w.startswith("否定句：")]
    ok = p.returncode == 0 and len(hits) == want_n
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {label} | exit {p.returncode} | {hits}")
# summary 里四段用"否定句提醒 N 句"，旧壳仍用"自写否定计数 N 条"；一行里不放全角括号（钩子正则按「）」截断）
SUMMARY_CASES = [("inline_negative.txt", ["--total", "12"], "否定句提醒 1 句"),
                 ("control_valid.txt", ["--total", "12"], "否定句提醒 0 句"),
                 ("five_section_four_negatives.txt", ["--format", "五段", "--total", "12"], "自写否定计数 4 条"),
                 # v17 A：要求清单进 summary
                 ("asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_ok.txt")], "要求清单 2 条有效全部有落点"),
                 ("asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_withdrawn.txt")], "要求清单 2 条有效全部有落点"),
                 ("asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_missing.txt")], "要求清单 3 条有效，1 条没有落点"),
                 ("asks_draft.txt", ["--total", "12", "--asks", str(C / "asks_bad_format.txt")], "要求清单格式错误"),
                 # v25 B2：没给 --labels 时，正文里没有素材引用写“无素材引用”，有引用才写“素材集合未核对”
                 ("control_valid.txt", ["--total", "12"], "无素材引用"),
                 ("at_refs_in_new_draft.txt", ["--total", "12"], "素材集合未核对"),
                 # v37 --adjudicated：“已裁定 M 条”跟在“待裁定提醒 N 条”后面、sha 前面
                 ("ap_speed_hold.txt", ["--total", "12", "--adjudicated", str(C / "adjudicated_ap.txt")], "待裁定提醒 2 条｜已裁定 1 条｜sha ")]
for f, args, needle in SUMMARY_CASES:
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / f), *args], text=True, encoding="utf-8", errors="replace", capture_output=True)
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
    ("已试否定例外点名后在 checked 行里记数", "tried_negative_exception.txt",
     ["--negative-exception", "开始的一秒画面是纯黑，看不到任何轮廓、光点或亮边；暗部不做任何补光"], "checked", "已试否定例外 2 句已点名"),
    ("消失的句子已被 A 的错误覆盖：不重复报", "revise_dropped_two.txt",
     ["--baseline", str(C / "revise_parent.txt"), "--asks", str(C / "asks_lost_overlap.txt")], "warnings",
     "父稿有 1 句在新稿里消失：「后景虚化成一片柔光」"),
]
for name, f, args, field, needle in ASK_DETAIL_CASES:
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / f), "--total", "12", *args], text=True, encoding="utf-8", errors="replace", capture_output=True)
    d = json.loads(p.stdout); hit = [x for x in d[field] if needle in x]; ok = bool(hit); fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {name} |", hit[:1] or d[field])

# ---- v25：错误原文、checked 行与 summary 的细节（参数不自动加 --total）----
DETAIL_CASES = [
    ("A10 漏报补上：这次不要", "ref_wording_missed.txt", ["--total", "12"], "errors", "引用性措辞：这次不要"),
    ("A10 漏报补上：和之前一样", "ref_wording_missed.txt", ["--total", "12"], "errors", "引用性措辞：和之前一样"),
    ("A10 漏报补上：承接着", "ref_wording_missed.txt", ["--total", "12"], "errors", "引用性措辞：承接着"),
    ("A19 固定句上一行“严禁……”报末尾只留固定句", "tail_line_yanjin.txt", ["--total", "12"], "errors", "末尾只留固定句"),
    ("A1 checked 里逐镜列出句数与估算拍数（v23 试写 24 句 → 12 拍）", "lantern_v23_trial.txt", ["--total", "6", "--labels", "图1,图2"],
     "checked", "镜1 动作密度：24 句、时序词 2 个，估算 12 拍，6 秒，平均 0.50 秒一拍"),
    ("--task 推断写进 checked：延长", "extend_yanxu.txt", ["--total", "5", "--labels", "视频1"], "checked",
     "没给 --task，按情节段开头的命令区推断为「延长」；建议显式传 --task"),
    ("--task 推断写进 checked：编辑", "edit_remove.txt", ["--labels", "视频1,图1"], "checked", "推断为「编辑」"),
    ("--task 推断写进 checked：a-b秒 标题 + 雨势增加仍是生成", "rain_increase_seconds_heads.txt", ["--total", "8", "--labels", "视频1"],
     "checked", "推断为「生成」"),
    ("延长缺必填词的报错列出“延续视频N”", "extend_five_missing_command.txt", ["--task", "延长", "--total", "5", "--labels", "视频1"],
     "errors", "向后延长 / 向前延长 / 续写 / 延续视频N"),
    ("编辑缺必填词的报错列出“移除”", "rain_increase_seconds_heads.txt", ["--task", "编辑", "--labels", "视频1"],
     "errors", "编辑 / 替换 / 删除 / 增加 / 移除 / 修改"),
    ("A6 旧壳结尾段计数认严禁 / 请勿（5 条）", "five_section_yanjin.txt", ["--format", "五段", "--total", "12"], "errors", "结尾段否定句 5 条"),
    ("B2 没有素材引用时 checked 写明素材集合为空", "control_valid.txt", ["--total", "12"], "checked", "正文里没有 图N / 视频N / 音频N 引用"),
    ("压缩审校·checked 逐镜列出字数密度（v23 试写 806 字 / 6 秒，去掉镜头标题）", "lantern_v23_trial.txt",
     ["--total", "6", "--labels", "图1,图2", "--density-line", "90"], "checked", "镜1 字数密度：806 字，6 秒，每秒 134 字（参考线 90，暂定）"),
    ("压缩审校·台词不算字数（镜1 去掉台词 208 字 / 3 秒）", "density_under_line.txt", ["--total", "12"], "checked",
     "镜1 字数密度：208 字，3 秒，每秒 69 字"),
    ("压缩审校·没有复读时 checked 写明", "repeat_phrase_exempt_subject.txt", ["--total", "12"], "checked", "情节里没有 6 字以上的复读短语"),
    # ---- v37 反模式表与三个降噪开关：checked、errors、adjudicated 字段 ----
    ("反模式表加载结果写进 checked", "control_valid.txt", ["--total", "12"], "checked", "反模式表已加载："),
    ("--mode 白模 在 checked 里写明", "ap_baimo.txt", ["--total", "12", "--labels", "图1,视频1", "--mode", "白模"], "checked", "白模模式：命令区总览句不报"),
    ("--mode 白模 关掉的另外三条也在 checked 里写明", "camera_person_actions.txt", ["--total", "12", "--mode", "白模"], "checked",
     "白模模式：朝向方位词、跟拍位移证据、摄影运动三条不报"),
    ("--rewrite-authorized 在 checked 里写明", "revise_dropped_two.txt", ["--baseline", str(C / "revise_parent.txt"), "--total", "12", "--rewrite-authorized"],
     "checked", "已按授权重写关闭父稿句消失提醒；要求清单仍核对"),
    ("--rewrite-authorized 时要求清单照旧核对：缺落点的错误照报", "revise_dropped_two.txt",
     ["--baseline", str(C / "revise_parent.txt"), "--total", "12", "--rewrite-authorized", "--asks", str(C / "asks_lost_overlap.txt")],
     "errors", "要求 R4「镜头缓缓推近到胸口高度」在正文里没有落点"),
    ("--adjudicated：JSON 的 adjudicated 列出删掉的原文", "ap_speed_hold.txt", ["--total", "12", "--adjudicated", str(C / "adjudicated_ap.txt")],
     "adjudicated", "镜1 反模式 AP01（两条以上 L047、L144）：「位置和大小稳住」"),
    ("--adjudicated：checked 记清单行数、删掉条数和这次没对上的行", "ap_speed_hold.txt", ["--total", "12", "--adjudicated", str(C / "adjudicated_ap.txt")],
     "checked", "裁定清单 2 行，删掉已裁定提醒 1 条；这些行这次没对上提醒：「风格段里有时序」"),
]
for name, f, args, field, needle in DETAIL_CASES:
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / f), *args], text=True, encoding="utf-8", errors="replace", capture_output=True)
    d = json.loads(p.stdout); v = d[field]
    hit = ([v] if needle in v else []) if isinstance(v, str) else [x for x in v if needle in x]
    ok = bool(hit); fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {name} |", hit[:1] or v)

# ---- v25：infer_task_from_text（check_prompt 没给 --task 与 hooks/stop_gate.py 代跑共用）----
sys.path.insert(0, str(ROOT / "scripts"))
sys.dont_write_bytecode = True
import check_prompt as CP
SHELL = "主体：一位穿灰衣的成年人。\n场景：室内走廊。\n风格：{style}\n情节：\n{zone}镜头1（0-5秒）：{shot}\n全片不添加BGM，不添加字幕。"
INFER_CASES = [
    ("向后延长视频1 → 延长", SHELL.format(style="写实。", zone="向后延长视频1，新增 5 秒。\n", shot="镜头慢推，他停下。"), "延长"),
    ("延续视频2 → 延长", SHELL.format(style="写实。", zone="延续视频2，新增 5 秒。\n", shot="镜头慢推，他停下。"), "延长"),
    ("风格段的“延续视频1的画风”不算命令 → 生成", SHELL.format(style="延续视频1的画风。", zone="", shot="镜头慢推，他停下。"), "生成"),
    ("编辑视频1 → 编辑", SHELL.format(style="写实。", zone="编辑视频1，把上衣替换为图1中的服装。\n", shot="只换上衣。"), "编辑"),
    ("把视频1中的路人删除 → 编辑", SHELL.format(style="写实。", zone="把视频1中的路人删除。\n", shot="街面留空。"), "编辑"),
    ("参考视频1的运镜，光亮逐渐增加 → 生成", SHELL.format(style="写实。", zone="参考视频1的运镜，光亮逐渐增加。\n", shot="镜头慢推。"), "生成"),
    ("无缝衔接 → 衔接", SHELL.format(style="写实。", zone="将视频1和视频2无缝衔接起来，不修改视频1和视频2。\n", shot="镜头慢推。"), "衔接"),
    ("a-b秒 标题 + 镜内雨势增加 → 生成", (C / "rain_increase_seconds_heads.txt").read_text(encoding="utf-8"), "生成"),
]
for name, text, want in INFER_CASES:
    got = CP.infer_task_from_text(text)
    ok = got == want; fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| infer_task_from_text：{name} |", got)

# ---- v35 表演排队：逐命中按 span 包含裁定（报告模式与豁免模板在同一份剥完台词的字符串上算；writing-rules 成文主规则第 8 条）----
# (名称, 镜头正文（先按 check_prompt 剥台词）, 期望要报的命中 [(起, 止, 原文)], 期望豁免的命中或 None 不核对)
QUEUE_SPAN_CASES = [
    ("正例：说完……才抬头两处都报", "罗大娘说完，苏云才抬头", [(3, 5, "说完"), (8, 11, "才抬头")], []),
    ("反例1：没等她说完他就开口（等她说完与其中说完都在模板里）", "没等她说完他就开口", [], [(1, 5, "等她说完"), (3, 5, "说完")]),
    ("反例1：话音未落本身不触发", "话音未落他抬头", [], []),
    ("反例1：说到一半本身不触发", "他说到一半停住", [], []),
    ("反例1：话还没说完", "话还没说完，他就转身", [], [(3, 5, "说完")]),
    ("反例2：镜头推到胸口之后才移焦（显式主语 + 终点）", "镜头推到胸口之后才移焦", [], [(6, 9, "之后才")]),
    ("反例2：后拉之后才移焦（两侧都是摄影术语，主语可省）", "后拉之后才移焦", [], [(2, 5, "之后才")]),
    ("反例2：推到胸口之后才移焦无显式摄影主体，保留警告", "推到胸口之后才移焦", [(4, 7, "之后才")], []),
    ("反例2：不等他做完就开口", "不等他做完就开口", [], [(1, 5, "等他做完")]),
    ("反例3：台词引号里的说完不算", CP.strip_dialogue("他低声说：“你说完了吗？”"), [], []),
    ("混合：摄影之后才豁免，人物推门之后才抬头照报", "镜头推到胸口之后才移焦，苏云推门之后才抬头",
     [(16, 19, "之后才"), (18, 21, "才抬头")], [(6, 9, "之后才")]),
    ("混合：逗号换成空格仍只报人物命中", "镜头推到胸口之后才移焦 苏云推门之后才抬头",
     [(16, 19, "之后才"), (18, 21, "才抬头")], [(6, 9, "之后才")]),
    ("混合：话音未落他抬头；说完才回应只报第二处", "话音未落他抬头；说完才回应", [(8, 10, "说完"), (10, 13, "才回应")], []),
    ("混合：没等她说完，他就开口；说完才转身只报末次", "没等她说完，他就开口；说完才转身",
     [(11, 13, "说完"), (13, 16, "才转身")], [(1, 5, "等她说完"), (3, 5, "说完")]),
    ("同一小句：只豁免第一次说完，后半真排队照报（豁免模板到最近第一次结束词即止）", "没等她说完他又说完才回应",
     [(7, 9, "说完"), (9, 12, "才回应")], [(1, 5, "等她说完"), (3, 5, "说完")]),
    ("报告模式“等…结束词”也到第一次结束词即止", "等她说完他又说完才回应",
     [(0, 4, "等她说完"), (2, 4, "说完"), (6, 8, "说完"), (8, 11, "才回应")], []),
    ("物理依赖：放下杯子之后才去开门照报（合法误报，裁定保留）", "放下杯子之后才去开门", [(4, 7, "之后才")], []),
    ("人物推门之后才抬头照报", "推门之后才抬头", [(2, 5, "之后才"), (4, 7, "才抬头")], []),
    ("人物拉住手之后才回应照报（裸“拉”不算摄影）", "拉住手之后才回应", [(3, 6, "之后才"), (5, 8, "才回应")], []),
    ("人物摇头之后才开口照报（裸“摇”不算摄影）", "摇头之后才开口", [(2, 5, "之后才"), (4, 7, "才开口")], []),
    ("然后 / 随后 / 接着单独出现不报", "然后他抬头，随后转身，接着开口", [], []),
    ("然后才照报", "然后才抬头", [(0, 3, "然后才"), (2, 5, "才抬头")], []),
    ("话音刚落照报", "话音刚落，她抬头", [(0, 4, "话音刚落")], []),
]
for name, text, want, want_ex in QUEUE_SPAN_CASES:
    got, got_ex, _spans = CP.perf_queue_scan(text)
    ok = got == want and (want_ex is None or got_ex == want_ex); fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| 表演排队 span：{name} |", got, got_ex)

# ---- v25 A20：正文超过 15000 字符报错误；15000 以内不报 ----
with tempfile.TemporaryDirectory() as tmp:
    base = (C / "control_valid.txt").read_text(encoding="utf-8").rstrip("\n")
    pad = "人物从门口走到窗前，衣摆轻晃，镜头慢推。"
    for label, n, want_err in [("超过 15000 字符：报错", (15000 - len(base)) // len(pad) + 1, True),
                               ("不到 15000 字符：不报长度", (15000 - len(base)) // len(pad), False)]:
        body = base.replace("人物从门口走到窗前，衣摆轻晃。", "人物从门口走到窗前，衣摆轻晃。" + pad * n, 1)
        pf = pathlib.Path(tmp) / f"long{n}.txt"
        pf.write_text(body, encoding="utf-8")
        p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(pf), "--total", "12"], text=True, encoding="utf-8", errors="replace", capture_output=True)
        d = json.loads(p.stdout)
        has = any("超过即梦提示词上限 15000 字符" in e for e in d["errors"])
        ok = has == want_err and (p.returncode == 1) == want_err and (len(body) > 15000) == want_err
        fails += 0 if ok else 1
        print(("PASS" if ok else "FAIL"), f"| A20 {label}（实际 {len(body)} 字符）|", d["errors"][:1])

# ---- 压缩审校：复读每份稿最多报 5 条（7 组不同的重复只报前 5 组，按出现先后）----
with tempfile.TemporaryDirectory() as tmp:
    reps7 = ["老人把烟袋锅磕在门槛上", "黄狗叼着一只破草鞋跑过", "晾衣绳上的蓝布衫鼓起来", "井台边的木桶晃了两下",
             "屋檐下的风铃叮当作响", "墙头的南瓜藤垂到窗前", "灶台上的铁锅冒着白气"]
    shot = "，".join(reps7) + "。镜头慢推，" + "，".join(reps7) + "。"
    draft = ("主体：\n一位穿灰衣的老人。\n场景：\n午后的农家小院。\n风格：\n写实，暖黄阳光。\n情节：\n"
             f"镜头1（0-12秒）：{shot}\n全片不添加BGM，不添加字幕。\n")
    pf = pathlib.Path(tmp) / "reps7.txt"
    pf.write_text(draft, encoding="utf-8")
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(pf), "--total", "12"], text=True, encoding="utf-8", errors="replace", capture_output=True)
    d = json.loads(p.stdout)
    got = [w for w in d["warnings"] if w.startswith("复读提醒")]
    ok = p.returncode == 0 and len(got) == 5 and all(f"「{r}」" in g for r, g in zip(reps7, got))
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), "| 压缩审校·复读每份稿最多报 5 条（7 组重复按出现先后列前 5 组）|", len(got), got[:1])

# --report 里记 asks_checked（没给 --asks 时是 null）
with tempfile.TemporaryDirectory() as tmp:
    for args, want in [(["--asks", str(C / "asks_ok.txt")], 2), ([], None)]:
        rp = pathlib.Path(tmp) / f"asks{want}.json"
        subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / "asks_draft.txt"), "--total", "12",
                        "--report", str(rp), *args], text=True, encoding="utf-8", errors="replace", capture_output=True)
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
        p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / f), *args, "--report", str(rp)],
                           text=True, encoding="utf-8", errors="replace", capture_output=True)
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
    return subprocess.run([sys.executable, "-X", "utf8", *map(str, cmd)], text=True, encoding="utf-8", errors="replace", capture_output=True)


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

# ---- v31：archive.md 出口——取号看合集、体检查合集与重复、案例引用归档编号、写入提醒、整理清单第五第六节 ----
REVIEW = ROOT / "scripts" / "review_lessons.py"
ARCHIVE_CASES = []
with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    lf, af = d / "lessons.md", d / "archive.md"
    ROW = "L{n:03d} | {date} | 通用/占位{n} | 现象 | 写法A → 效果 | — | {concl} | 未试 | {src}\n"
    lf.write_text("# 临时经验库\n\n## 七、诊断新增\n<!-- 整理于 2026-09-01 L001 -->\n" + ROW.format(n=1, date="2026-09-01", concl="结论", src="来源"), encoding="utf-8")
    af.write_text("# 归档\n\n## 已升级为规则\n\n" + ROW.format(n=2, date="2026-09-02", concl="结论【已升级为规则：writing-rules.md 第 1 条】", src="来源"), encoding="utf-8")
    common = ["--phenomenon", "现象", "--conclusion", "结论", "--confidence", "未试"]
    p = run([LINT, "--file", lf])
    ARCHIVE_CASES.append(("lint_lessons 主库 L001 + archive L002：合集连续，通过", p.returncode == 0 and "archive 另有 1 条" in p.stdout, (p.stdout + p.stderr)[:100]))
    p = run([LOG, "--file", lf, "--topic", "通用/取号", "--a", "写法A → 效果", "--source", "a.mp4 与 b.mp4 对照", *common])
    ARCHIVE_CASES.append(("log_lesson 取号跨 archive：L003 而不是 L002", p.stdout.strip() == "L003", p.stdout.strip() + p.stderr[:60]))
    p = run([LOG, "--file", lf, "--topic", "通用/超长", "--a", "写" * 90, "--source", "a.mp4 与 b.mp4 对照", *common])
    ARCHIVE_CASES.append(("log_lesson 写法A 90 字：写入但提醒超过 80 字", p.returncode == 0 and "超过 80 字" in p.stderr, p.stderr[:80]))
    p = run([LOG, "--file", lf, "--topic", "通用/单条", "--a", "写法A → 效果", "--source", "jimeng-2026-09-25-1641.mp4", *common])
    ARCHIVE_CASES.append(("log_lesson 来源只有一条成片、没标单次观察：提醒", p.returncode == 0 and "单次观察" in p.stderr, p.stderr[:80]))
    # 标记 L001 之后已有 L003–L005 三条，手工补 L006–L011 六条，再写一条 L012 正好第 10 条触发整理提醒
    for k in range(6, 12):
        lf.write_text(lf.read_text(encoding="utf-8") + ROW.format(n=k, date="2026-09-10", concl="结论", src="x.mp4 对照 y.mp4"), encoding="utf-8")
    p = run([LOG, "--file", lf, "--topic", "通用/第十条", "--a", "写法A → 效果", "--source", "x.mp4 对照 y.mp4", *common])
    ARCHIVE_CASES.append(("log_lesson 整理标记之后满 10 条：提醒该整理", p.returncode == 0 and "该跑「整理经验」" in p.stderr, p.stderr[:80]))
    cf = d / "cases.md"
    cf.write_text(case_md("- 「那句句式」 → L002", rel="L002"), encoding="utf-8")
    p = run([LINTC, "--file", cf, "--lessons", lf])
    ARCHIVE_CASES.append(("lint_cases 可复用点指向 archive 里的 L002：通过", p.returncode == 0, (p.stdout + p.stderr)[:80]))
    dup = d / "dup.md"
    dup.write_text("# 归档\n\n" + ROW.format(n=1, date="2026-09-01", concl="结论", src="来源"), encoding="utf-8")
    p = run([LINT, "--file", lf, "--archive", dup])
    ARCHIVE_CASES.append(("lint_lessons 同一编号主库和 archive 都有：拦下", p.returncode == 1 and "都有" in p.stderr, p.stderr[:80]))
    gap = d / "gap.md"
    gap.write_text("# 归档\n\n" + ROW.format(n=13, date="2026-09-01", concl="结论", src="来源"), encoding="utf-8")
    p = run([LINT, "--file", lf, "--archive", gap])
    ARCHIVE_CASES.append(("lint_lessons 合集断档（主库缺 L002、archive 只有 L013）：拦下", p.returncode == 1 and "编号不连续" in p.stderr, p.stderr[:80]))
    # review_lessons：第五节列漏搬的（主库里带【并入】）；第六节按 --today 列满 30 天的单次观察，有对照的不列
    lf2 = d / "l2.md"
    lf2.write_text("# 临时\n\n" + ROW.format(n=1, date="2026-09-01", concl="单次观察：结论", src="a.mp4")
                   + ROW.format(n=2, date="2026-09-01", concl="单次观察：结论", src="a.mp4 对照 b.mp4")
                   + ROW.format(n=3, date="2026-09-25", concl="单次观察：结论", src="c.mp4")
                   + ROW.format(n=4, date="2026-09-01", concl="结论【并入 L001】", src="d.mp4"), encoding="utf-8")
    out = run([REVIEW, "--file", lf2, "--cases", cf, "--archive", af, "--today", "2026-10-05"]).stdout
    six = out[out.index("## 六"):]
    ARCHIVE_CASES.append(("review_lessons 第六节：满 30 天的单次观察 L001 列出，有对照的 L002 和只有 10 天的 L003 不列",
                          "| L001 |" in six and "| L002 |" not in six and "| L003 |" not in six, six[:160]))
    five = out[out.index("## 五"):out.index("## 六")]
    ARCHIVE_CASES.append(("review_lessons 第五节：主库里带【并入】没搬走的 L004 列为漏搬，并报 archive 现有 1 条",
                          "L004" in five and "并入 L001" in five and "archive.md 现有 1 条" in five, five[-200:]))
for name, ok, detail in ARCHIVE_CASES:
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {name} |", "ok" if ok else detail)

# ---- v25 五：review_lessons 认三位编号的“见 Lxxx”，多个升级标记显示最后一个 ----
REVIEW = ROOT / "scripts" / "review_lessons.py"
REVIEW_CHECKS = [
    ("review_lessons：“见 L101”这种 L1xx 编号也列进第三节", "| L001 | 通用/占位 | L101 | 未试 |"),
    ("review_lessons：多个升级标记显示最后一个（规则位置更新）",
     "- L002 通用/两个标记 → 已拆到 writing-rules.md 第 53 条（2 个标记，显示最后一个：规则位置更新）"),
]
with tempfile.TemporaryDirectory() as tmp:
    d = pathlib.Path(tmp)
    lf = d / "lessons.md"
    lf.write_text("# 临时经验库\n\n"
                  "L001 | 2026-09-21 | 通用/占位 | 现象 | 写法A → 效果 | — | 结论，见 L101 | 未试 | 来源\n"
                  "L002 | 2026-09-21 | 通用/两个标记 | 现象 | 写法A → 效果 | — | 结论【已升级为规则：SKILL.md 九步⑥】"
                  "【规则位置更新：已拆到 writing-rules.md 第 53 条】 | 已试 | 来源\n", encoding="utf-8")
    cf = d / "cases.md"
    cf.write_text(case_md("- 「那句句式」 → L001"), encoding="utf-8")
    out = run([REVIEW, "--file", lf, "--cases", cf]).stdout
    for name, needle in REVIEW_CHECKS:
        ok = needle in out; fails += 0 if ok else 1
        print(("PASS" if ok else "FAIL"), f"| {name} |", "ok" if ok else out[-300:])

# ---- v25 五：install.sh 只从主线仓库的 main 分支安装；sync.sh 只在 main 分支上同步（临时 HOME 里跑，不碰真实的 skills 软链）----
def _bash():
    """Windows 上只用 Git Bash（C:\\Windows\\System32\\bash.exe 是 WSL，HOME 与路径都对不上）；找不到返回 None，守门测试记 SKIP。"""
    if sys.platform != "win32":
        return "bash"
    cands = [r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files (x86)\Git\bin\bash.exe"]
    g = shutil.which("git")
    if g:   # …\Git\cmd\git.exe 或 …\Git\bin\git.exe 或 …\Git\mingw64\bin\git.exe → …\Git\bin\bash.exe
        gp = pathlib.Path(g).resolve()
        cands += [str(up / "bin" / "bash.exe") for up in list(gp.parents)[:3]]
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def sh(script, home):
    return subprocess.run([_bash(), str(script)], text=True, encoding="utf-8", errors="replace", capture_output=True,
                          env={**os.environ, "HOME": str(home)})


SCRIPT_GUARD_CASES = []
GUARD_RUN = _bash() is not None
if not GUARD_RUN:
    print("SKIP | install.sh / sync.sh 守门（4 项）| Windows 上没找到 Git Bash（装 Git for Windows 后重跑）；不计入总数")
else:
    with tempfile.TemporaryDirectory() as tmp:
        home = pathlib.Path(tmp)
        repo = home / "Documents" / "Codex" / "aigc-video"
        (repo / "scripts").mkdir(parents=True)
        shutil.copy(ROOT / "install.sh", repo / "install.sh")
        shutil.copy(ROOT / "scripts" / "sync.sh", repo / "scripts" / "sync.sh")
        def git(*args):
            return subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", *args],
                                  text=True, encoding="utf-8", errors="replace", capture_output=True)
        git("init", "-q", "-b", "dev"); git("commit", "-q", "--allow-empty", "-m", "init")
        SCRIPT_GUARD_CASES = [
            ("install.sh 不在主线路径（dev 工作区）：拒绝执行", ROOT / "install.sh", 1, "只从主线仓库"),
            ("install.sh 在主线路径但分支是 dev：拒绝执行", repo / "install.sh", 1, "只在 main 分支上安装"),
            ("sync.sh 分支是 dev：拒绝执行", repo / "scripts" / "sync.sh", 1, "只在 main 分支上同步"),
        ]
        for name, script, want, needle in SCRIPT_GUARD_CASES:
            p = sh(script, home)
            linked = (home / ".claude" / "skills" / "aigc-video").exists() or (home / ".codex" / "skills" / "aigc-video").exists()
            commits = len(git("log", "--oneline").stdout.splitlines())
            ok = p.returncode == want and needle in p.stderr and not linked and commits == 1
            fails += 0 if ok else 1
            print(("PASS" if ok else "FAIL"), f"| {name} |", (p.stderr.strip().splitlines() or ["无输出"])[0][:80])
        git("switch", "-q", "-c", "main")
        p = sh(repo / "install.sh", home)
        link = home / ".claude" / "skills" / "aigc-video"
        if sys.platform == "win32":
            ok = p.returncode == 0 and link.exists()
        else:
            ok = p.returncode == 0 and link.is_symlink() and link.resolve() == repo.resolve()
        fails += 0 if ok else 1
        print(("PASS" if ok else "FAIL"), "| install.sh 在主线仓库的 main 分支：两个宿主都挂上软链 |", p.stdout.strip().splitlines()[:1] or p.stderr[:120])

# lint_cases：当前案例库必须干净（每条可复用点有编号或标样板，编号真的存在，索引对得上）
p = run([LINTC, "--file", CASES_MD, "--lessons", LESSONS])
ok = p.returncode == 0
fails += 0 if ok else 1
print(("PASS" if ok else "FAIL"), "| lint_cases 当前案例库通过 |", (p.stdout or p.stderr).strip()[:160])

# ---- 词库体检：带“理解度”列的五列词条表每行五列、理解度合规、可用句不含空词 / 解释词 / 画质词 / 引用性措辞 / 发力过程 ----
LINTX = ROOT / "scripts" / "lint_lexicon.py"
p = run([LINTX])
ok = p.returncode == 0
fails += 0 if ok else 1
_out = (p.stdout or p.stderr).strip().splitlines()
print(("PASS" if ok else "FAIL"), "| lint_lexicon 当前词库通过 |", (_out[-1] if _out else "")[:160])

# ---- v21：成功案例不误伤——M001–M004 的提示词原文不许报下面八类提醒 ----
# 旧外壳会报格式错误，不看退出码；只核对“整幅遮挡”“发力过程写法”“镜内标签”“画质词”“主体段这句”“场景段这句”
# “风格段这句”“总括保证句”八类提醒不出现。M001–M003 是六段旧稿，按 --format 六段跑；主体段、场景段与风格段提醒只对四段新稿启用，
# 因为按四段扫时 M002（「镜头」——“全程用右手握棍，他正脸对着镜头时……”）、M003（「握着」）会报主体段动作，
# 那是旧模板的写法，属预期。M004 是四段稿，按默认四段口径扫也不报。
SUCCESS_CASES = [("M001", ["--format", "六段"]), ("M002", ["--format", "六段"]),
                 ("M003", ["--format", "六段"]), ("M004", [])]
cases_text = CASES_MD.read_text(encoding="utf-8")
with tempfile.TemporaryDirectory() as tmp:
    for cid, extra in SUCCESS_CASES:
        m = re.search(r"^### " + cid + r"\b.*?提示词原文[^\n]*\n\s*```text\n(.*?)\n```", cases_text, re.S | re.M)
        if not m:
            fails += 1
            print("FAIL", f"| 成功案例 {cid} 不误伤 | my-cases.md 里找不到 {cid} 的提示词原文代码块")
            continue
        pf = pathlib.Path(tmp) / f"{cid}.txt"
        pf.write_text(m.group(1) + "\n", encoding="utf-8")
        p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(pf), *extra], text=True, encoding="utf-8", errors="replace", capture_output=True)
        try:
            ws = json.loads(p.stdout)["warnings"]
        except Exception:
            fails += 1
            print("FAIL", f"| 成功案例 {cid} 不误伤 | 输出不是 JSON：{p.stderr.strip()[:120]}")
            continue
        hit = [w for w in ws if "整幅遮挡" in w or "发力过程写法" in w or "镜内标签" in w or "画质词" in w
               or "主体段这句" in w or "场景段这句" in w or "风格段这句" in w or "总括保证句" in w]
        ok = not hit; fails += 0 if ok else 1
        print(("PASS" if ok else "FAIL"), f"| 成功案例 {cid} 不报“整幅遮挡”“发力过程写法”“镜内标签”“画质词”“主体段这句”“场景段这句”“风格段这句”“总括保证句” |", hit[:1] or "ok")

# v24：成功案例里 E8、E9 口径的直接出处——M001 的“开始的一秒画面是纯黑”“画面九成落在纯黑里”（L073、L074 已试）不报绝对化的空或黑；
# M003 镜1 按时序词粗估 7 秒 8 拍（“先”“同时”不另算；审查修复前算作 14 拍、正好 0.5 秒一拍），不报动作密度
SUCCESS_EXTRA = [("M001", ["--format", "六段"], "绝对化的空或黑"), ("M003", ["--format", "六段"], "节拍"),
                 # 审查修复：M002、M003 素材绑定句里的“不采用图中的纯黑背景”说的是参考图，不报
                 ("M002", ["--format", "六段"], "绝对化的空或黑"), ("M003", ["--format", "六段"], "绝对化的空或黑"),
                 # 压缩审校：M001（已试成功，镜1 约 59 字 / 秒）不报字数密度与虚词（“开始的一秒”不算虚词由 filler_words_ok 专门测）
                 ("M001", ["--format", "六段"], "参考线"), ("M001", ["--format", "六段"], "虚词")]
with tempfile.TemporaryDirectory() as tmp:
    for cid, extra, key in SUCCESS_EXTRA:
        m = re.search(r"^### " + cid + r"\b.*?提示词原文[^\n]*\n\s*```text\n(.*?)\n```", cases_text, re.S | re.M)
        pf = pathlib.Path(tmp) / f"{cid}.txt"
        pf.write_text((m.group(1) if m else "") + "\n", encoding="utf-8")
        p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(pf), *extra], text=True, encoding="utf-8", errors="replace", capture_output=True)
        hit = [w for w in json.loads(p.stdout)["warnings"] if key in w] if m else ["找不到提示词原文"]
        ok = not hit; fails += 0 if ok else 1
        print(("PASS" if ok else "FAIL"), f"| 成功案例 {cid} 不报“{key}” |", hit[:1] or "ok")

# v38 回放：成功案例 M001–M010 在默认模式下不报朝向提醒（M002“朝向画面左侧的那半边脸……被照亮”是受光面描述，M004“话尾回到看向画面左下方的视线”是视线，M003、M005 的“画面向右”不是“面向”）；本来就该报的案例这里一条没有，案例原文不改
ORIENT_SUCCESS = [f"M{n:03d}" for n in range(1, 11)]
with tempfile.TemporaryDirectory() as tmp:
    for cid in ORIENT_SUCCESS:
        m = re.search(r"^### " + cid + r"\b.*?提示词原文[^\n]*\n\s*```text\n(.*?)\n```", cases_text, re.S | re.M)
        pf = pathlib.Path(tmp) / f"{cid}.txt"
        pf.write_text((m.group(1) if m else "") + "\n", encoding="utf-8")
        p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(pf)], text=True, encoding="utf-8", errors="replace", capture_output=True)
        hit = [w for w in json.loads(p.stdout)["warnings"] if "朝向只写了方位词" in w] if m else ["找不到提示词原文"]
        ok = not hit; fails += 0 if ok else 1
        print(("PASS" if ok else "FAIL"), f"| 成功案例 {cid} 默认模式不报“朝向只写了方位词” |", hit[:1] or "ok")

# ---- v23 审查修复：input_sha256 是整份输入的哈希（v16 起曾被分句循环变量覆盖，不同的稿算出同一个值） ----
shas = {}
for f in ("lantern_trial_s.txt", "lantern_trial_v22.txt"):
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / f), "--total", "6"], text=True, encoding="utf-8", errors="replace", capture_output=True)
    shas[f] = json.loads(p.stdout)["input_sha256"]
want = hashlib.sha256((C / "lantern_trial_s.txt").read_text(encoding="utf-8").encode("utf-8")).hexdigest()
ok = len(set(shas.values())) == 2 and shas["lantern_trial_s.txt"] == want
fails += 0 if ok else 1
print(("PASS" if ok else "FAIL"), "| 两份不同的稿 input_sha256 不同，且等于整份输入的哈希 |", "ok" if ok else shas)

# ---- v37 反模式表（references/antipatterns.md）：表本身的体检、表写错或缺失时不崩、summary 与钩子检查行兼容 ----
AP_EXTRA = []
_tbl, _notes = CP.load_antipatterns()
_bad = [r["id"] for r in (_tbl or {}).get("rows", []) if not re.match(r"^(两条以上|单次|未试)\s*(?:（模式约定，)?L\d{3}", r["evidence"])]
AP_EXTRA.append(("反模式表读得出、没有写错的行；正则行的证据列以等级开头并带 L 编号（模式约定写「未试（模式约定，Lxxx）」）；代码索引行齐全",
                 bool(_tbl) and not _notes and not _bad and _tbl["index"] >= 7, f"notes={_notes} bad={_bad}"))
ESC = chr(92) + "|"     # Markdown 表格里转义过的竖线
with tempfile.TemporaryDirectory() as tmp:
    bad_table = pathlib.Path(tmp) / "bad.md"
    bad_table.write_text(
        "| 场合 | 扫哪段 | 判定词 |\n|---|---|---|\n| 速度镜 | 同镜内 | \x60冲" + ESC + "窜\x60 |\n\n"
        "| 编号 | 场合 | 触发 | 为什么 | 证据 | 改成 |\n|---|---|---|---|---|---|\n"
        "| AP90 | 镜内 | \x60测试词\x60 | 为什么 | 单次 L001 | 改成 |\n"
        "| AP91 | 镜内 | \x60(\x60 | 为什么 | 单次 L001 | 改成 |\n"
        "| AP92 | 全片 | \x60测试词\x60 | 为什么 | 单次 L001 | 改成 |\n"
        "| AP93 | 镜内 | \x60测试词\x60 | 为什么 | 单次 L001 |\n"
        "| AP94 | 速度镜 | \x60慢" + ESC + "缓\x60 | 为什么 | 大概 L001 | 改成 |\n"
        "| AP90 | 镜内 | \x60别的词\x60 | 为什么 | 单次 L001 | 改成 |\n"
        "| AP95 | 任何 | 实现：代码（某张词表） | 为什么 | 单次 L001 | 改成 |\n", encoding="utf-8")
    t2, n2 = CP.load_antipatterns(bad_table)
    ids = [r["id"] for r in (t2 or {}).get("rows", [])]
    ok = (ids == ["AP90", "AP94"] and t2["index"] == 1 and t2["gates"]["速度镜"].search("往上窜") is not None
          and t2["rows"][1]["candidate"] and t2["rows"][1]["rxs"][0].pattern == "慢|缓"
          and all(any(k in n for n in n2) for k in ("AP91", "AP92", "AP93", "AP94", "编号重复")))
    AP_EXTRA.append(("反模式表写错的行（正则编译不过、场合不对、列数不对、编号重复）逐行跳过并说明；证据等级不明按候选；表格里转义的竖线还原",
                     ok, f"ids={ids} notes={n2}"))
    empty = pathlib.Path(tmp) / "empty.md"
    empty.write_text("# 只有标题，没有表\n", encoding="utf-8")
    t3, n3 = CP.load_antipatterns(empty)
    t4, n4 = CP.load_antipatterns(pathlib.Path(tmp) / "不存在.md")
    ok = t3 is None and t4 is None and any("反模式表未加载" in n for n in n3) and any("反模式表未加载" in n for n in n4)
    AP_EXTRA.append(("反模式表一行都读不出、文件不存在：返回 None 并说明「反模式表未加载」", ok, f"{n3} {n4}"))
    # 把脚本单独拷到一个没有 references/ 的目录里跑：不崩、退出码照旧、checked 记「反模式表未加载」、不出反模式提醒
    (pathlib.Path(tmp) / "scripts").mkdir()
    lone = pathlib.Path(tmp) / "scripts" / "check_prompt.py"
    shutil.copy(S, lone)
    why = []
    for f, want in [("hold_frame_speed.txt", 0), ("duplicate_shot_id.txt", 1)]:
        p = subprocess.run([sys.executable, "-X", "utf8", str(lone), "--prompt", str(C / f), "--total", "12"],
                           text=True, encoding="utf-8", errors="replace", capture_output=True)
        try:
            d = json.loads(p.stdout)
        except Exception:
            why.append(f"{f} 输出不是 JSON：{p.stderr.strip()[-160:]}")
            continue
        if p.returncode != want:
            why.append(f"{f} 退出码 {p.returncode}（期望 {want}）")
        if not any("反模式表未加载" in c for c in d["checked"]):
            why.append(f"{f} checked 里没有「反模式表未加载」")
        if any("反模式" in w for w in d["warnings"]):
            why.append(f"{f} 表缺失时还出了反模式提醒")
    AP_EXTRA.append(("反模式表文件缺失：脚本不崩，退出码照旧，checked 记「反模式表未加载」", not why, "；".join(why) or "ok"))
    # 真表还没用到的三个场合（主体段、场景段、贴身近景）：在同一个临时目录里放一张小表，只扫该扫的那段
    (pathlib.Path(tmp) / "references").mkdir()
    (pathlib.Path(tmp) / "references" / "antipatterns.md").write_text(
        "| 场合 | 扫哪段 | 判定词 |\n|---|---|---|\n| 贴身近景 | 同镜内 | \x60近景" + ESC + "特写\x60 |\n\n"
        "| 编号 | 场合 | 触发 | 为什么 | 证据 | 改成 |\n|---|---|---|---|---|---|\n"
        "| AP90 | 主体段 | \x60灰衣" + ESC + "白衣\x60 | 测试 | 单次 L001 | 测试 |\n"
        "| AP91 | 场景段 | \x60侧窗" + ESC + "门后\x60 | 测试 | 两条以上 L001、L002 | 测试 |\n"
        "| AP92 | 贴身近景 | \x60抬手\x60 | 测试 | 未试 L001 | 测试 |\n", encoding="utf-8")
    scoped = pathlib.Path(tmp) / "scoped.txt"
    scoped.write_text("主体：\n一位穿灰衣的成年人。\n场景：\n室内走廊，侧窗透入柔光。\n风格：\n写实。\n情节：\n"
                      "镜头1（0-6秒）：全景，镜头慢推，人物抬手推开门，门后站着一个白衣人。\n"
                      "镜头2（6-12秒）：近景，镜头慢推，人物抬手，窗边的轻纱轻轻飘动。\n全片不添加BGM，不添加字幕。\n", encoding="utf-8")
    p = subprocess.run([sys.executable, "-X", "utf8", str(lone), "--prompt", str(scoped), "--total", "12"],
                       text=True, encoding="utf-8", errors="replace", capture_output=True)
    ws = json.loads(p.stdout)["warnings"]
    want = ["反模式 AP90（候选，单次 L001）：「灰衣」；", "反模式 AP91（两条以上 L001、L002）：「侧窗」；", "镜2 反模式 AP92（候选，未试 L001）：「抬手」；"]
    ok = (p.returncode == 0 and all(any(w.startswith(x) for w in ws) for x in want)
          and not any("镜1 反模式 AP92" in w or "「白衣」" in w or "「门后」" in w for w in ws))
    AP_EXTRA.append(("场合是主体段 / 场景段的行只扫那一段，贴身近景只扫有判定词的镜；两条以上的不标候选", ok, ws))
# summary 加了“已裁定 M 条”以后，hooks/stop_gate.py 的检查行正则照样取得到 sha；没删任何提醒时 summary 不出现“已裁定”
import importlib.util
_spec = importlib.util.spec_from_file_location("stop_gate_for_check_tests", ROOT / "hooks" / "stop_gate.py")
_sg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sg)
p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / "ap_speed_hold.txt"), "--total", "12",
                    "--adjudicated", str(C / "adjudicated_ap.txt")], text=True, encoding="utf-8", errors="replace", capture_output=True)
d = json.loads(p.stdout)
m = _sg.CHECK_LINE.search(d["summary"])
AP_EXTRA.append(("summary 带“已裁定 1 条”时 stop_gate 的检查行正则照样认出“通过”和 sha 短哈希",
                 bool(m) and m.group(1) == "通过" and m.group(3) == d["delivered_sha256"][:8], d["summary"]))
p = subprocess.run([sys.executable, "-X", "utf8", str(S), "--prompt", str(C / "ap_speed_hold.txt"), "--total", "12"],
                   text=True, encoding="utf-8", errors="replace", capture_output=True)
d = json.loads(p.stdout)
AP_EXTRA.append(("没给 --adjudicated 时 summary 不出现“已裁定”，JSON 的 adjudicated 是空列表",
                 "已裁定" not in d["summary"] and d.get("adjudicated") == [], d["summary"]))
for name, ok, detail in AP_EXTRA:
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {name} |", detail if not ok else "ok")

# ---- v38 度量回路：报告多存的六样、log_outcome 追加与找不到 sha 报错、rule_stats 在夹具目录上出表 ----
M_EXTRA = []
LOGO = ROOT / "scripts" / "log_outcome.py"
STATS = ROOT / "scripts" / "rule_stats.py"
RS = C / "rule_stats"            # rule_stats 的夹具目录：v38 报告两份、v37 报告一份、全套报告一份、outcomes.jsonl 两行
NEW_KEYS = ("antipatterns", "adjudicated_ids", "mode", "rewrite_authorized", "asks_file", "hint_types")


def _report_run(args, report):
    p = subprocess.run([sys.executable, "-X", "utf8", str(S), *map(str, args), "--report", str(report)],
                       text=True, encoding="utf-8", errors="replace", capture_output=True)
    return p, json.loads(pathlib.Path(report).read_text(encoding="utf-8")), json.loads(p.stdout)


def _logo(gate, *args):
    return run([LOGO, "--dir", gate, *args])


def _lines(f):
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()] if f.exists() else []


with tempfile.TemporaryDirectory() as tmp:
    gate = pathlib.Path(tmp) / "gate"
    # 1) 带 --adjudicated：AP01 被裁、AP06 待裁定；六样字段的形状与值，stdout 与报告一致，hint_types 合计 = 待裁定 + 已裁定
    p, rep, out = _report_run(["--prompt", C / "ap_speed_hold.txt", "--total", "12", "--adjudicated", C / "adjudicated_ap.txt"], gate / "r1.json")
    want_ap = [{"id": "AP01", "shot": 1, "hits": ["位置和大小稳住"], "evidence": "两条以上 L047、L144", "candidate": False, "adjudicated": True},
               {"id": "AP06", "shot": 3, "hits": ["慢慢"], "evidence": "单次 L150", "candidate": True, "adjudicated": False}]
    ok = (p.returncode == 0 and rep.get("antipatterns") == want_ap and rep.get("adjudicated_ids") == ["AP01"]
          and rep.get("mode") == "默认" and rep.get("rewrite_authorized") is False and rep.get("asks_file") is None
          and list(rep.get("hint_types") or {}) == list(CP.HINT_TYPES)
          and rep["hint_types"] == {**dict.fromkeys(CP.HINT_TYPES, 0), "复读": 1, "反模式": 2}
          and sum(rep["hint_types"].values()) == len(rep["warnings"]) + len(rep["adjudicated"])
          and all(out.get(k) == rep.get(k) for k in NEW_KEYS))
    M_EXTRA.append(("--report 多存六样：antipatterns 一条提醒一项、含已裁定的那条并标 adjudicated，adjudicated_ids、mode、rewrite_authorized、"
                    "asks_file、hint_types（全部提醒按类别计数）都在，stdout 同样有", ok, {k: rep.get(k) for k in NEW_KEYS}))
    # 2) 全稿级的反模式行镜号是 null，逐镜的（含 AP02 那条取景提醒）带镜号；没给 --adjudicated 时全标 false
    _p, rep2, _o = _report_run(["--prompt", C / "ap_any_rows.txt", "--total", "12"], pathlib.Path(tmp) / "r2.json")
    got = [(it["id"], it["shot"], it["candidate"], it["adjudicated"]) for it in rep2.get("antipatterns") or []]
    ok = (got == [("AP02", 1, False, False), ("AP03", None, True, False), ("AP04", None, True, False)]
          and rep2.get("adjudicated_ids") == [] and rep2["hint_types"]["反模式"] == 3)
    M_EXTRA.append(("antipatterns：全稿级的行 shot 是 null，逐镜的带镜号（AP02 那条取景提醒也记）；没给 --adjudicated 时 adjudicated 全是 false", ok, got))
    # 3) mode、rewrite_authorized、asks_file 照实记（有错误的稿也写报告）
    asks = C / "asks_lost_overlap.txt"
    p3, rep3, _o = _report_run(["--prompt", C / "revise_dropped_two.txt", "--baseline", C / "revise_parent.txt", "--total", "12",
                                "--mode", "白模", "--rewrite-authorized", "--asks", asks], pathlib.Path(tmp) / "r3.json")
    ok = (p3.returncode == 1 and rep3.get("mode") == "白模" and rep3.get("rewrite_authorized") is True
          and rep3.get("asks_file") == str(asks.resolve()))
    M_EXTRA.append(("mode = 白模、rewrite_authorized = true、asks_file 是要求清单的绝对路径；有错误时照样写进报告", ok,
                    {k: rep3.get(k) for k in ("mode", "rewrite_authorized", "asks_file")}))
    # 4) 提醒类别：七类各取一条真实文案（含旧壳结尾段否定句、AP02 句末编号；动作节拍与串行运镜归其它）
    samples = [("情节段开头有总览句：「灰色方块对应漂浮的碎石」；生成类新稿情节段直接从镜头标题开始", "总览句"),
               ("父稿有 2 句在新稿里消失：「镜头缓缓推近到胸口高度」；按 references/review/revise-rules.md 核对删改授权", "父稿句消失"),
               ("复读提醒：「它在画面里的位置和大小稳住」在情节里出现 2 次", "复读"),
               ("镜1 每秒 102 字，超过参考线 90（暂定，待 A/B 实测）", "密度"),
               ("否定句：不出现第二个白猿；确认是特殊情况且无正向写法", "否定句"),
               ("结尾段否定句 5 条，超过上限 4（固定句合算 1 条；操作类官方约束句不计）", "否定句"),
               ("镜1 取景写成了“能装下什么”：「露出它的全身」；取景写画框切在哪；反模式 AP02（两条以上 L145、L045）", "反模式"),
               ("反模式 AP03（候选，单次 L154）：「有房子那么大」；比喻的喻体被画成实物（房子）", "反模式"),
               ("镜1 约 8 个动作节拍挤在 3 秒里（平均不到 0.5 秒一拍", "其它"),
               ("镜1 串行运镜 4 句挤在 2 秒里", "其它"),
               ("新稿比父稿长 20%（100→120 字）", "其它")]
    bad = [(w[:16], CP.hint_type(w), t) for w, t in samples if CP.hint_type(w) != t]
    M_EXTRA.append(("hint_type 七类：总览句 / 父稿句消失 / 复读 / 密度（只算字数密度）/ 否定句（含旧壳结尾段）/ 反模式（含 AP02）/ 其它", not bad, bad))

    # 5) log_outcome：按 8 位 sha 找到报告，追加一行；字段齐，触发的编号含已裁定的，模式照报告
    sha8 = rep["delivered_sha256"][:8]
    outf = gate / "outcomes.jsonl"
    p = _logo(gate, "--sha", sha8, "--video", "视频节点 5 - 副本 (8).mp4", "--verdict", "采用", "--note", "用户：好了很多", "--lesson", "L144")
    rows = _lines(outf)
    r0 = rows[0] if rows else {}
    ok = (p.returncode == 0 and len(rows) == 1 and r0.get("sha") == sha8 and r0.get("report") == "r1.json"
          and r0.get("video") == "视频节点 5 - 副本 (8).mp4" and r0.get("verdict") == "采用" and r0.get("note") == "用户：好了很多"
          and r0.get("lesson") == "L144" and r0.get("antipatterns") == ["AP01", "AP06"] and r0.get("adjudicated_ids") == ["AP01"]
          and r0.get("mode") == "默认" and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", r0.get("time") or "")))
    M_EXTRA.append(("log_outcome 按 8 位 sha 找到报告，往 outcomes.jsonl 追加一行：时间、sha、报告、成片、评价、备注、经验编号、触发与裁定的反模式编号、模式",
                    ok, (p.stdout + p.stderr).strip()[:200] if not ok else "ok"))
    # 6) 直接给报告路径也行，再追加一行
    p = _logo(gate, "--sha", gate / "r1.json", "--video", "第二条.mp4", "--verdict", "否")
    rows = _lines(outf)
    ok = p.returncode == 0 and len(rows) == 2 and rows[1].get("verdict") == "否" and rows[1].get("antipatterns") == ["AP01", "AP06"]
    M_EXTRA.append(("log_outcome 的 --sha 给报告路径：同样追加一行", ok, (p.stdout + p.stderr).strip()[:200]))
    # 7) 找不到 sha：退出 1、说找不到、文件不动；评价不是三档之一：参数错误退出 2、文件不动
    before = outf.read_bytes()
    p = _logo(gate, "--sha", "0123abcd", "--video", "x.mp4", "--verdict", "采用")
    p2 = _logo(gate, "--sha", sha8, "--video", "x.mp4", "--verdict", "还行")
    ok = p.returncode == 1 and "找不到 sha 0123abcd" in p.stderr and p2.returncode == 2 and outf.read_bytes() == before
    M_EXTRA.append(("log_outcome 找不到 sha 报错退出 1、评价不是 采用 / 部分 / 否 退出 2，outcomes.jsonl 都不动", ok,
                    f"{p.returncode} {p.stderr.strip()[:120]} | {p2.returncode}"))
    # 8) v38 之前的报告（没有 antipatterns / mode）：编号从提醒原文里取，模式记 null
    shutil.copy(RS / "20260801-120000.json", gate / "old.json")
    p = _logo(gate, "--sha", "cccc3333", "--video", "旧稿.mp4", "--verdict", "部分")
    rows = _lines(outf)
    ok = p.returncode == 0 and len(rows) == 3 and rows[2].get("antipatterns") == ["AP01"] and rows[2].get("mode") is None
    M_EXTRA.append(("log_outcome 读 v38 之前的报告：反模式编号从提醒原文里取，模式记 null", ok, rows[2] if len(rows) > 2 else p.stderr.strip()[:160]))
    # 9) rule_stats 在这个临时目录上：两份报告、三行结果，AP01 触发 2 次、被裁 1 次，采用 / 部分 / 否各 1
    snap = {f.name: f.read_bytes() for f in gate.iterdir()}
    p = run([STATS, "--dir", gate, "--today", "2026-10-01"])
    ok = (p.returncode == 0 and "| AP01 | 正式 | 2 | 1 | 1 | 1 | 1 |" in p.stdout and "| AP06 | 候选 | 1 | 0 | 1 | 0 | 1 |" in p.stdout
          and {f.name: f.read_bytes() for f in gate.iterdir()} == snap)
    M_EXTRA.append(("rule_stats 读 check_prompt 报告与 log_outcome 写的结果出表，目录里的文件一个字节不动", ok, p.stdout[-400:] if not ok else "ok"))

# 10) rule_stats 在固定夹具目录上（--today 定死）：反模式、类别、最近 30 天三节的数都对；全套报告不计；只读
snap = {f.name: f.read_bytes() for f in RS.iterdir()}
p = run([STATS, "--dir", RS, "--today", "2026-10-01"])
_st = {r["id"]: ("候选" if r["candidate"] else "正式") for r in (CP.load_antipatterns()[0] or {}).get("rows", [])}
want = [f"| AP01 | {_st.get('AP01')} | 2 | 1 | 1 | 0 | 1 |", f"| AP06 | {_st.get('AP06')} | 1 | 0 | 1 | 0 | 0 |",
        "| 父稿句消失 | 1 | 0 | 0% |", "| 反模式 | 3 | 1 | 33% |", "| 合计 | 8 | 1 | 12% |",
        "check_prompt 报告 3 份（v38 之前的 1 份", "全套报告 1 份不计", "成片结果 2 条（outcomes.jsonl）：采用 1、部分 0、否 1",
        "## 三、最近 30 天（2026-09-02 到 2026-10-01）", "新增报告 2 份，涉及 2 份不同正文；有成片结果的 1 份，占 50%"]
miss = [x for x in want if x not in p.stdout]
ok = p.returncode == 0 and not miss and {f.name: f.read_bytes() for f in RS.iterdir()} == snap
M_EXTRA.append(("rule_stats 在夹具目录上出表：触发、被裁定、采用 / 否成片里触发、正式 / 候选；类别总数与裁定率；最近 30 天报告数与有成片结果的占比", ok,
                miss or p.stderr.strip()[:200]))
with tempfile.TemporaryDirectory() as tmp:
    gate9 = pathlib.Path(tmp)
    _p9, rep9, _o9 = _report_run(["--prompt", C / "ap_baimo_lens.txt", "--total", "12", "--labels", "图1,视频1", "--mode", "白模"], gate9 / "r9.json")
    ids9 = [it["id"] for it in rep9.get("antipatterns") or []]
    p9 = run([STATS, "--dir", gate9, "--today", "2026-10-01"])
    ok = ("AP09" in ids9 and rep9["hint_types"]["反模式"] == len(ids9) and "| AP09 | 候选 | 1 | 0 | 0 | 0 | 0 |" in p9.stdout)
    M_EXTRA.append(("AP09（白模命令区缺一致性句）提醒带编号：进报告的 antipatterns，rule_stats 按编号统计、标候选", ok, (ids9, p9.stdout[-300:]) if not ok else "ok"))
for name, ok, detail in M_EXTRA:
    fails += 0 if ok else 1
    print(("PASS" if ok else "FAIL"), f"| {name} |", detail if not ok else "ok")

TOTAL = (len(CASES) + len(WARN_CASES) + len(NO_WARN_CASES) + 2 + len(SUMMARY_CASES) + 1  # lint_lexicon 当前词库
         + len(ASK_DETAIL_CASES) + 2 + len(REPORT_CASES)
         + len(LESSON_CASES) + 4 + len(CASE_LINT_CASES) + 1
         + 4 + len(SUCCESS_EXTRA) + 1
         + len(ORIENT_SUCCESS)  # v38 回放：成功案例不报朝向提醒
         + len(DETAIL_CASES) + len(INFER_CASES) + len(QUEUE_SPAN_CASES) + 2
         + len(REVIEW_CHECKS) + (len(SCRIPT_GUARD_CASES) + 1 if GUARD_RUN else 0)
         + len(ARCHIVE_CASES)  # v31 archive 出口
         + len(AP_EXTRA)  # v37 反模式表体检、表缺失不崩、summary 与钩子兼容
         + len(M_EXTRA)  # v38 度量回路：报告新字段、log_outcome、rule_stats
         + 1)  # 压缩审校：复读每份稿最多报 5 条
print(f"\n{TOTAL - fails}/{TOTAL} 通过")
sys.exit(1 if fails else 0)
