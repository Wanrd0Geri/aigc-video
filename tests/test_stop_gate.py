#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hooks/stop_gate.py 回归：覆盖只读审查的 16 个探针语义（c01–c09、n01–n07）、v7 的本轮绑定、
代码块契约、纯文本操作命令、交付行一致性，以及 v12 的三层判定（本轮报告 / 钩子代跑完整稿 / 局部与操作命令打回）。
只用构造的 transcript 与报告，不代表真实宿主行为。"""
import hashlib, json, os, subprocess, sys, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "stop_gate.py"
# 四段新壳：主体 / 场景 / 风格 / 情节，固定句是整份提示词的最后一行，不设结尾标题
PROMPT = "主体：一只黑色哑光陶杯。\n场景：陶杯直立在灰色桌面上，杯子和桌面全程静止。\n风格：写实产品摄影。\n情节：\n生成一段6秒的单镜产品视频。\n镜头1（0-6秒）：摄影机沿直线平稳缓推，杯子逐渐放大。\n全片不添加BGM，不添加字幕。"
# 必要否定句写在镜内（v13.1：末尾只有固定句那一行）
PROMPT_WITH_INLINE_NEG = PROMPT.replace("杯子逐渐放大。", "杯子逐渐放大。不出现第二只陶杯。")
# 五段旧壳（结尾标题 + 旧固定句）：钩子代跑时应当按 --format 五段 推断
FIVE_SECTION = PROMPT.replace("全片不添加BGM，不添加字幕。", "结尾：不添加字幕，不添加背景音乐。")
PARTIAL = "镜头2（4-8秒）：固定胸口以上近景，青年说：“银杭到了。”。"
EDIT_CMD = "编辑@视频1，将青年的衣服替换为黑色外套，保留原动作、时长和摄影。"
# 会被 check_prompt 查出错误的完整稿（固定句不在最后一行）：用来测"钩子代跑不通过"的分支
BROKEN = PROMPT + "\n画面最后在杯口停住。"
REQ = "b" * 64


def digest(t):
    return hashlib.sha256("\n".join(t.splitlines()).encode()).hexdigest()


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts))


class StopGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.d = Path(self.tmp.name)
        self.gate = self.d / "gate"; self.gate.mkdir()
        self.now = time.time()
        self.user_time = self.now - 60          # 本轮用户消息在一分钟前
        self.fresh = self.now - 30              # 本轮之后生成的报告
        self.stale = self.now - 600             # 上一轮（用户消息之前）的报告

    def tearDown(self):
        self.tmp.cleanup()

    def report(self, body, req=REQ, name="r.json", created=None, session=None):
        h = digest(body)
        rep = {"ready": True, "checked_sha256": h, "delivered_sha256": h, "requirements_sha256": req,
               "created_at": self.fresh if created is None else created, "session_id": session}
        (self.gate / name).write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        return h

    def light(self, body, name="l.json", created=None, session=None, ready=True):
        """轻量路径的 check_prompt --report 报告。"""
        h = digest(body)
        rep = {"kind": "light", "ready": ready, "checked_sha256": h, "delivered_sha256": h,
               "task": "生成", "format": "四段", "partial": False, "errors": [], "warnings": [],
               "labels": [], "locks": 0, "baseline_sha256": None,
               "created_at": self.fresh if created is None else created, "session_id": session}
        (self.gate / name).write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
        return h

    def run_hook(self, text, active=False, codex=False, transcript=True, user=True, session=None, user_stamp=True, extra_rows=None):
        payload = {"stop_hook_active": active}
        if session:
            payload["session_id"] = session
        rows = []
        if user:
            row = {"message": {"role": "user", "content": "把陶杯视频写出来。"}}
            if user_stamp:
                row["timestamp"] = iso(self.user_time)
            rows.append(row)
        rows.extend(extra_rows or [])
        rows.append({"message": {"role": "assistant", "content": [{"type": "text", "text": text}]}})
        if codex:
            payload.update({"turn_id": "t1", "last_assistant_message": text, "transcript_path": None})
        elif transcript:
            t = self.d / "tr.jsonl"
            t.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
            payload["transcript_path"] = str(t)
        else:
            payload["transcript_path"] = str(self.d / "missing.jsonl")
        p = subprocess.run([sys.executable, "-B", str(HOOK)], input=json.dumps(payload, ensure_ascii=False), text=True,
                           capture_output=True, env={**os.environ, "AIGC_GATE_DIR": str(self.gate)})
        return p.returncode, p.stdout, p.stderr

    def block(self, body, lang="text"):
        return "```" + lang + "\n" + body + "\n```\n"

    def receipt(self, h, req):
        return f"交付校验通过（正文 {h[:8]}｜需求 {req[:8]}）"

    def check_line(self, h):
        return f"check_prompt 通过（1 镜｜0-6 连续｜素材集合未核对｜镜内否定提醒 1 句｜待裁定提醒 1 条｜sha {h[:8]}）"

    def assertAllowWithNote(self, res, needle):
        self.assertEqual(res[0], 0, res[2])
        self.assertIn(needle, json.loads(res[1])["systemMessage"])

    def assertAllow(self, res):
        self.assertEqual(res[0], 0)
        if res[1].strip():
            self.assertNotIn("systemMessage", json.loads(res[1]))

    def assertBlock(self, res):
        self.assertEqual(res[0], 2)

    # ---- 审查探针 c01–c09 ----
    def test_c01_valid_passes(self):
        h = self.report(PROMPT)
        self.assertAllow(self.run_hook(self.block(PROMPT) + self.receipt(h, REQ)))

    def test_c02_changed_body_blocked(self):
        # 改过稿旧报告对不上：完整稿现在会被钩子代跑，所以这里用局部镜头保持"哈希对不上就拦"的语义
        h = self.report(PARTIAL)
        changed = PARTIAL.replace("银杭到了。", "杭州到了。")
        code, _, err = self.run_hook(self.block(changed) + self.receipt(h, REQ))
        self.assertEqual(code, 2); self.assertIn("没有本轮", err)

    def test_c03_wrong_requirement_receipt_blocked(self):
        h = self.report(PROMPT)
        code, _, err = self.run_hook(self.block(PROMPT) + self.receipt(h, "0" * 64))
        self.assertEqual(code, 2); self.assertIn("交付行与放行报告不一致", err)

    def test_c04_prompt_only_passes(self):
        self.report(PROMPT)
        self.assertAllow(self.run_hook(self.block(PROMPT)))

    def test_c05_partial_unchecked_blocked(self):
        self.assertBlock(self.run_hook(self.block(PARTIAL)))

    def test_c05b_partial_checked_passes(self):
        self.report(PARTIAL)
        self.assertAllow(self.run_hook(self.block(PARTIAL)))

    def test_c06_no_prompt_passes(self):
        self.assertAllow(self.run_hook("这一轮只核对修改范围，没有交付提示词。"))

    def test_c07_second_stop_invalid_warn_allows(self):
        code, out, _ = self.run_hook(self.block(BROKEN), active=True)
        self.assertEqual(code, 0); self.assertIn("未通过放行验收", json.loads(out)["systemMessage"])

    def test_c08_second_stop_invalid_codex_warn_allows(self):
        code, out, _ = self.run_hook(self.block(BROKEN), active=True, codex=True)
        self.assertEqual(code, 0); self.assertIn("未通过放行验收", json.loads(out)["systemMessage"])

    def test_c09_unreadable_transcript_blocked_once(self):
        code, _, err = self.run_hook(PROMPT, transcript=False)
        self.assertEqual(code, 2); self.assertIn("读不到", err)

    # ---- 审查探针 n01–n07 ----
    def test_n01_mixed_fenced_and_plain_blocked(self):
        h = self.report(PROMPT)
        changed = BROKEN.replace("全程静止", "向右快速滑动")
        code, _, err = self.run_hook(self.block(PROMPT) + self.receipt(h, REQ) + "\n另一个版本：\n" + changed)
        self.assertEqual(code, 2); self.assertIn("钩子代跑", err)

    def test_n02_plain_edit_command_blocked(self):
        self.assertBlock(self.run_hook(EDIT_CMD))

    def test_n02b_plain_edit_command_with_report_passes(self):
        self.report(EDIT_CMD)
        self.assertAllow(self.run_hook(EDIT_CMD))

    def test_n03_wrong_body_hash_receipt_blocked(self):
        self.report(PROMPT)
        code, _, err = self.run_hook(self.block(PROMPT) + self.receipt("0" * 64, REQ))
        self.assertEqual(code, 2); self.assertIn("交付行与放行报告不一致", err)

    def test_n04_old_report_before_this_turn_blocked(self):
        self.report(PROMPT, created=self.stale)
        code, _, err = self.run_hook(self.block(PROMPT))
        self.assertEqual(code, 2); self.assertIn("早于本轮用户消息", err)

    def test_n04b_report_after_user_message_passes(self):
        self.report(PROMPT, created=self.fresh)
        self.assertAllow(self.run_hook(self.block(PROMPT)))

    def test_n05_quote_block_not_inspected(self):
        text = "只分析下面这份旧稿的问题，不是本轮成品：\n" + self.block(PROMPT, "quote") + "\n诊断：时长与新要求不同。"
        self.assertAllow(self.run_hook(text))

    def test_n06_draft_block_not_inspected(self):
        text = "以下仅是概念草案，暂不作为最终视频提示词：\n" + self.block("镜头1：青年沿门廊向前走，摄影机侧向跟随。", "draft")
        self.assertAllow(self.run_hook(text))

    def test_n07_plain_body_with_receipt_passes(self):
        h = self.report(PROMPT)
        self.assertAllow(self.run_hook(PROMPT + "\n" + self.receipt(h, REQ)))

    # ---- 其余契约与边界 ----
    def test_json_and_bash_blocks_not_inspected(self):
        self.assertAllow(self.run_hook(self.block(PROMPT, "json") + self.block(PROMPT, "bash")))

    def test_unlabelled_block_is_inspected(self):
        self.assertBlock(self.run_hook(self.block(BROKEN, "")))

    def test_prompt_labelled_block_is_inspected(self):
        self.assertBlock(self.run_hook(self.block(BROKEN, "prompt")))

    def test_header_outside_block_is_free_text(self):
        self.report(PROMPT)
        head = "锁定：6 秒、单镜、陶杯\n待你定：这镜是否固定？我建议保持缓推。\n升级：原 = 平推 → 升 = 缓推收尾停稳\n\n"
        self.assertAllow(self.run_hook(head + self.block(PROMPT) + "例外：镜 1 未加额外道具，因为 6 秒装不下。"))

    def test_missing_closing_still_recognized(self):
        self.assertBlock(self.run_hook(self.block(PROMPT.replace("全片不添加BGM，不添加字幕。", ""))))

    def test_plain_full_draft_recognized(self):
        self.assertBlock(self.run_hook(BROKEN))

    def test_plain_chat_passes(self):
        self.assertAllow(self.run_hook("这个镜头的光向还需要核对。"))

    def test_two_prompts_one_report_blocked(self):
        h = self.report(PROMPT)
        changed = PROMPT.replace("全程静止", "向右快速滑动")
        self.assertBlock(self.run_hook(self.block(PROMPT) + self.receipt(h, REQ) + "\n" + self.block(changed)))

    def test_receipt_without_any_prompt_blocked(self):
        self.assertBlock(self.run_hook("这轮没有贴提示词。\n" + self.receipt("a" * 64, REQ)))

    def test_session_mismatch_blocked(self):
        self.report(PROMPT, session="session-A")
        code, _, err = self.run_hook(self.block(PROMPT), session="session-B")
        self.assertEqual(code, 2); self.assertIn("另一个会话", err)

    def test_same_session_passes(self):
        self.report(PROMPT, session="session-A")
        self.assertAllow(self.run_hook(self.block(PROMPT), session="session-A"))

    def test_report_without_session_id_still_passes(self):
        self.report(PROMPT, session=None)
        self.assertAllow(self.run_hook(self.block(PROMPT), session="session-A"))

    def test_user_message_without_timestamp_uses_transcript_mtime(self):
        self.report(PROMPT, created=self.stale)
        code, _, err = self.run_hook(self.block(PROMPT), user_stamp=False)
        self.assertEqual(code, 2); self.assertIn("早于本轮用户消息", err)

    def test_no_user_message_falls_back_to_day_window(self):
        self.report(PROMPT, created=self.stale)
        self.assertAllow(self.run_hook(self.block(PROMPT), user=False))

    def test_codex_without_transcript_warns_weak_binding(self):
        self.report(PROMPT)
        code, out, _ = self.run_hook(self.block(PROMPT), codex=True)
        self.assertEqual(code, 0); self.assertIn("本轮绑定较弱", json.loads(out)["systemMessage"])

    def test_codex_mode_block_is_json(self):
        code, out, _ = self.run_hook(self.block(BROKEN), codex=True)
        self.assertEqual(code, 0); self.assertEqual(json.loads(out)["decision"], "block")

    def test_stale_or_not_ready_report_ignored(self):
        h = digest(BROKEN)
        (self.gate / "r.json").write_text(json.dumps({"ready": False, "checked_sha256": h, "delivered_sha256": h,
                                                      "created_at": self.fresh}), encoding="utf-8")
        self.assertBlock(self.run_hook(self.block(BROKEN)))

    def test_report_older_than_a_day_ignored(self):
        self.report(BROKEN, created=self.now - 90000)
        self.assertBlock(self.run_hook(self.block(BROKEN), user=False))

    # ---- v12：三层判定（本轮报告 / 钩子代跑完整稿 / 局部与操作命令打回）----
    def test_v141_tool_result_row_after_report_is_not_user_message(self):
        # 真实 transcript：作者跑 check_prompt 后的 tool_result 行也是 role=user，时间晚于报告；不能把它当本轮用户消息
        self.light(PROMPT)
        late = {"timestamp": iso(self.now - 10), "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}}
        code, out, err = self.run_hook("```text\n" + PROMPT + "\n```\n" + self.check_line(PROMPT), extra_rows=[late])
        self.assertEqual(code, 0, err)
        self.assertNotIn("代跑", out)

    def test_v141_hook_feedback_row_is_not_user_message(self):
        self.light(PROMPT)
        fb = {"timestamp": iso(self.now - 10), "message": {"role": "user", "content": "Stop hook feedback:\naigc-video 放行钩子：第 1 份提示词……"}}
        code, out, err = self.run_hook("```text\n" + PROMPT + "\n```\n" + self.check_line(PROMPT), extra_rows=[fb])
        self.assertEqual(code, 0, err)

    def test_v141_real_user_message_after_report_still_stale(self):
        self.light(PROMPT)
        newer = {"timestamp": iso(self.now - 10), "message": {"role": "user", "content": [{"type": "text", "text": "再改一下第二镜"}]}}
        code, out, err = self.run_hook("```text\n" + PROMPT + "\n```\n", extra_rows=[newer])
        self.assertEqual(code, 2)
        self.assertIn("早于本轮用户消息", err)

    def test_v12_plain_reply_without_transcript_is_silent(self):
        code, out, err = self.run_hook("好的，明白了。", codex=True)
        self.assertEqual(code, 0, err)
        self.assertNotIn("绑定较弱", out)

    def test_v12_check_line_inside_json_fence_is_ignored(self):
        text = "```text\n" + PROMPT + "\n```\n\n```json\n{\"summary\": \"check_prompt 通过（1 镜｜sha 00000000）\"}\n```\n"
        code, out, err = self.run_hook(text)
        self.assertEqual(code, 0, err)
        self.assertIn("代跑", out)

    def test_v12_light_report_matches_allows(self):
        """轻量路径的 light 报告一样算本轮报告，放行且不带代跑提示。"""
        self.light(PROMPT)
        self.assertAllow(self.run_hook(self.block(PROMPT)))

    def test_v12_light_report_before_this_turn_blocked(self):
        """light 报告早于本轮用户消息：旧稿冒充本轮，拦下，不给代跑兜底。"""
        self.light(PROMPT, created=self.stale)
        code, _, err = self.run_hook(self.block(PROMPT))
        self.assertEqual(code, 2); self.assertIn("早于本轮用户消息", err)

    def test_v12_light_report_not_ready_falls_back_to_self_run(self):
        """light 报告 ready=false（作者跑出了错误）：报告不算数，回落到钩子代跑。"""
        self.light(PROMPT, ready=False)
        self.assertAllowWithNote(self.run_hook(self.block(PROMPT)), "代跑")

    def test_v12_no_report_valid_full_draft_self_run_allows(self):
        """没有任何报告 + 合法五段完整稿：钩子代跑通过，放行但带"作者没自己跑检查"的提示。"""
        code, out, err = self.run_hook(self.block(PROMPT))
        self.assertEqual(code, 0, err)
        msg = json.loads(out)["systemMessage"]
        self.assertIn("代跑", msg); self.assertIn("作者本轮没有自己跑检查", msg)

    def test_v12_no_report_broken_full_draft_blocked_with_errors(self):
        """没有报告 + 缺固定句的完整稿：代跑查出错误，阻止并列出错误原文。"""
        code, _, err = self.run_hook(self.block(BROKEN))
        self.assertEqual(code, 2)
        self.assertIn("固定句不在正文最后一行", err); self.assertIn("--report", err)

    def test_v12_no_report_partial_blocked_asks_baseline(self):
        """没有报告 + 局部镜头：钩子没有父稿，代跑没有意义，提示带 --baseline 自己跑。"""
        code, _, err = self.run_hook(self.block(PARTIAL))
        self.assertEqual(code, 2)
        self.assertIn("--baseline", err); self.assertIn("--partial", err)

    def test_v12_no_report_edit_command_blocked(self):
        """没有报告 + 纯文本操作命令：同样按第 3 层打回。"""
        code, _, err = self.run_hook(EDIT_CMD)
        self.assertEqual(code, 2); self.assertIn("--baseline", err)

    def test_v12_check_line_without_matching_report_blocked(self):
        """机械检查行的短哈希对不上任何本轮 light 报告：手写检查行，拦下。"""
        self.light(PROMPT)
        code, _, err = self.run_hook(self.block(PROMPT) + self.check_line("0" * 64))
        self.assertEqual(code, 2); self.assertIn("不要手写检查行", err)

    def test_v12_check_line_matching_light_report_allows(self):
        """机械检查行照抄自真实报告：放行。"""
        h = self.light(PROMPT)
        self.assertAllow(self.run_hook(self.block(PROMPT) + self.check_line(h)))

    def test_v12_check_line_on_self_run_draft_blocked(self):
        """代跑通过的稿没有报告，这时写检查行一定是手写的，拦下。"""
        code, _, err = self.run_hook(self.block(PROMPT) + self.check_line("a" * 64))
        self.assertEqual(code, 2); self.assertIn("不要手写检查行", err)

    def test_v12_self_run_failure_under_stop_hook_active_allows_with_note(self):
        """已经拦过一次、代跑仍失败：放行不死锁，但把失败写进 systemMessage。"""
        code, out, _ = self.run_hook(self.block(BROKEN), active=True)
        self.assertEqual(code, 0)
        self.assertIn("未通过放行验收", json.loads(out)["systemMessage"])

    def test_v12_self_run_failure_codex_mode_is_json_block(self):
        """Codex 模式下代跑失败：用 JSON decision=block 阻止，退出码仍是 0。"""
        code, out, _ = self.run_hook(self.block(BROKEN), codex=True)
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertEqual(d["decision"], "block"); self.assertIn("固定句不在正文最后一行", d["reason"])

    def test_v12_self_run_six_section_draft_allows(self):
        """六段旧壳完整稿：钩子按概述段推断成六段来代跑，不被外壳规则误伤。"""
        six = FIVE_SECTION.replace("场景：", "概述：生成一段6秒的单镜产品视频。\n场景：").replace(
            "情节：\n生成一段6秒的单镜产品视频。\n", "情节：\n")
        self.assertAllowWithNote(self.run_hook(self.block(six)), "代跑")

    def test_v13_self_run_five_section_draft_allows(self):
        """五段旧壳完整稿：钩子按结尾段推断成五段来代跑，旧固定句不被新口径误伤。"""
        self.assertAllowWithNote(self.run_hook(self.block(FIVE_SECTION)), "代跑")

    def test_v13_self_run_four_section_with_inline_negative_allows(self):
        """四段新壳 + 镜内否定句（末尾只有固定句）：代跑通过。"""
        self.assertAllowWithNote(self.run_hook(self.block(PROMPT_WITH_INLINE_NEG)), "代跑")

    def test_v131_self_run_four_section_tail_negative_blocked(self):
        """四段新壳把否定句写在固定句上面一行：代跑打回。"""
        tail = PROMPT.replace("全片不添加BGM，不添加字幕。", "不出现第二只陶杯。\n全片不添加BGM，不添加字幕。")
        code, _, err = self.run_hook(self.block(tail))
        self.assertEqual(code, 2); self.assertIn("末尾只留固定句", err)

    def test_v13_closing_not_last_line_blocked(self):
        """固定句不是最后一行的四段稿：代跑打回。"""
        code, _, err = self.run_hook(self.block(PROMPT + "\n杯口的高光停住。"))
        self.assertEqual(code, 2); self.assertIn("固定句不在正文最后一行", err)


if __name__ == "__main__":
    unittest.main(verbosity=1)
