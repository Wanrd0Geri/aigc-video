#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_prompt.py 回归：python3 tests/run_check_tests.py  （全部通过退出 0）"""
import hashlib, json, pathlib, re, subprocess, sys, tempfile
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
              ("bg_activity_wordlist.txt", [], "「发抖」——「它神情惊恐，浑身发抖」"),
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
              ("subject_action.txt", [], "衣物、头发、持物的可见结果写进镜内那一拍，每拍一处"),
              # v24 审查修复：只写曝光、“一成不变”“大半圈”都不算有意纯黑
              ("void_exposure_only.txt", [], "绝对化的空或黑：「纯黑」"),
              ("void_not_range.txt", [], "绝对化的空或黑：「纯黑」")]
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
                 # v23 审查修复：单独的“没有出画”、画面里的位置“始终在画面中央”不算总括；晃眼、掠食是外形，伤口持续渗血是伤势
                 ("guarantee_phrasing.txt", [], "没有出画」"),
                 ("guarantee_phrasing.txt", [], "画面中央"),
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
                 # 画面里的位置（始终位于画面中央）不算总括
                 ("guarantee_phrasing.txt", [], "位于画面中央"),
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
                 ("tried_negative_exception.txt", ["--negative-exception", "开始的一秒画面是纯黑，看不到任何轮廓、光点或亮边；暗部不做任何补光"], "否定句")]
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
    ("已试否定例外点名后在 checked 行里记数", "tried_negative_exception.txt",
     ["--negative-exception", "开始的一秒画面是纯黑，看不到任何轮廓、光点或亮边；暗部不做任何补光"], "checked", "已试否定例外 2 句已点名"),
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
        p = subprocess.run([sys.executable, str(S), "--prompt", str(pf), *extra], text=True, capture_output=True)
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
                 ("M002", ["--format", "六段"], "绝对化的空或黑"), ("M003", ["--format", "六段"], "绝对化的空或黑")]
with tempfile.TemporaryDirectory() as tmp:
    for cid, extra, key in SUCCESS_EXTRA:
        m = re.search(r"^### " + cid + r"\b.*?提示词原文[^\n]*\n\s*```text\n(.*?)\n```", cases_text, re.S | re.M)
        pf = pathlib.Path(tmp) / f"{cid}.txt"
        pf.write_text((m.group(1) if m else "") + "\n", encoding="utf-8")
        p = subprocess.run([sys.executable, str(S), "--prompt", str(pf), *extra], text=True, capture_output=True)
        hit = [w for w in json.loads(p.stdout)["warnings"] if key in w] if m else ["找不到提示词原文"]
        ok = not hit; fails += 0 if ok else 1
        print(("PASS" if ok else "FAIL"), f"| 成功案例 {cid} 不报“{key}” |", hit[:1] or "ok")

# ---- v23 审查修复：input_sha256 是整份输入的哈希（v16 起曾被分句循环变量覆盖，不同的稿算出同一个值） ----
shas = {}
for f in ("lantern_trial_s.txt", "lantern_trial_v22.txt"):
    p = subprocess.run([sys.executable, str(S), "--prompt", str(C / f), "--total", "6"], text=True, capture_output=True)
    shas[f] = json.loads(p.stdout)["input_sha256"]
want = hashlib.sha256((C / "lantern_trial_s.txt").read_text(encoding="utf-8").encode("utf-8")).hexdigest()
ok = len(set(shas.values())) == 2 and shas["lantern_trial_s.txt"] == want
fails += 0 if ok else 1
print(("PASS" if ok else "FAIL"), "| 两份不同的稿 input_sha256 不同，且等于整份输入的哈希 |", "ok" if ok else shas)

TOTAL = (len(CASES) + len(WARN_CASES) + len(NO_WARN_CASES) + 2 + len(SUMMARY_CASES)
         + len(ASK_DETAIL_CASES) + 2 + len(REPORT_CASES)
         + len(LESSON_CASES) + 4 + len(CASE_LINT_CASES) + 1
         + 4 + len(SUCCESS_EXTRA) + 1)
print(f"\n{TOTAL - fails}/{TOTAL} 通过")
sys.exit(1 if fails else 0)
