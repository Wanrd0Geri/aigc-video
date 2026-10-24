#!/usr/bin/env python3
"""v48 三项提醒与完整稿字数回归；只读夹具，报告写入临时目录。"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts/check_prompt.py"
BASE = (ROOT / "tests/check_cases/control_valid.txt").read_text(encoding="utf-8")
PARENT_HINT = "要求清单缺父稿："
ORIGIN_HINT = "新稿比起点版累计增长："
TAKE_HINT = "一镜到底却有多个镜头标题："


def chars(text):
    return len(re.sub(r"\s", "", text))


def sized_prompt(size):
    padding = "石" * (size - chars(BASE))
    assert size >= chars(BASE)
    return BASE.replace("室内走廊", "室内走廊" + padding)


class V48Checks(unittest.TestCase):
    def check(self, prompt=BASE, *, baseline=None, origin=None, asks=None,
              adjudicated=None, extra=(), expected_exit=None):
        with tempfile.TemporaryDirectory(prefix="aigc-v48-") as tmp:
            folder = Path(tmp)
            args = [sys.executable, "-X", "utf8", str(CHECKER), "--task", "生成"]
            for flag, value in (("prompt", prompt), ("baseline", baseline),
                                ("origin", origin), ("asks", asks), ("adjudicated", adjudicated)):
                if value is not None:
                    path = folder / (flag + ".txt")
                    path.write_text(value, encoding="utf-8", newline="\n")
                    args += ["--" + flag, str(path)]
            report = folder / "report.json"
            run = subprocess.run([*args, "--report", str(report), *extra], capture_output=True,
                                 text=True, encoding="utf-8",
                                 env={**os.environ, "AIGC_GATE_DIR": str(folder / "gate")})
            out = json.loads(run.stdout)
            self.assertEqual(run.returncode, expected_exit if expected_exit is not None
                             else (0 if out["ok"] else 1), run.stderr)
            if report.exists():
                saved = json.loads(report.read_text(encoding="utf-8"))
                self.assertEqual(saved["warnings"], out["warnings"])
                self.assertEqual(saved.get("length_comparison"), out.get("length_comparison"))
            return out

    def has_hint(self, out, prefix, field="warnings"):
        return any(w.startswith(prefix) for w in out[field])

    def test_asks_missing_parent_warns_without_error(self):
        out = self.check(asks="R1 | 10:00 | 保留走廊 | 走廊 | 有效\n")
        self.assertTrue(out["ok"], out["errors"])
        self.assertTrue(self.has_hint(out, PARENT_HINT))

    def test_asks_parent_comment_satisfies_header(self):
        out = self.check(asks="# 父稿 v2 = base.txt\nR1 | 10:00 | 保留走廊 | 走廊 | 有效\n")
        self.assertFalse(self.has_hint(out, PARENT_HINT))
        self.assertEqual(out["asks_checked"], 1)

    def test_no_asks_has_no_parent_hint(self):
        self.assertFalse(self.has_hint(self.check(), PARENT_HINT))

    def test_parent_hint_adjudication_keeps_missing_requirement_error(self):
        out = self.check(asks="R1 | 10:00 | 保留红伞 | 红伞 | 有效\n", adjudicated="要求清单缺父稿\n")
        self.assertFalse(out["ok"])
        self.assertTrue(any("没有落点" in e for e in out["errors"]))
        self.assertFalse(self.has_hint(out, PARENT_HINT))
        self.assertTrue(self.has_hint(out, PARENT_HINT, "adjudicated"))

    def test_origin_detects_cumulative_growth_with_small_parent_step(self):
        out = self.check(sized_prompt(270), baseline=sized_prompt(250), origin=sized_prompt(200))
        self.assertTrue(self.has_hint(out, ORIGIN_HINT))
        self.assertFalse(self.has_hint(out, "新稿比父稿长"))
        metric = out["length_comparison"]
        self.assertEqual((metric["current_chars"], metric["baseline_delta"],
                          metric["origin_delta_percent"]), (270, 20, 35.0))

    def test_origin_threshold_is_strictly_more_than_thirty_percent(self):
        for size, expected in ((259, False), (260, False), (261, True)):
            with self.subTest(size=size):
                out = self.check(sized_prompt(size), origin=sized_prompt(200))
                self.assertEqual(self.has_hint(out, ORIGIN_HINT), expected)

    def test_rewrite_reports_counts_and_keeps_asks_check(self):
        out = self.check(sized_prompt(300), baseline=sized_prompt(210), origin=sized_prompt(200),
                         asks="R1 | 10:00 | 保留红伞 | 红伞 | 有效\n", extra=("--rewrite-authorized",))
        self.assertFalse(self.has_hint(out, ORIGIN_HINT))
        self.assertFalse(self.has_hint(out, "新稿比父稿长"))
        self.assertEqual(out["length_comparison"]["baseline_delta"], 90)
        self.assertEqual(out["length_comparison"]["origin_delta_percent"], 50.0)
        self.assertTrue(any("比父稿 +90 字；比起点版 +50.0%" in c for c in out["checked"]))
        self.assertTrue(any("没有落点" in e for e in out["errors"]))

    def test_origin_is_optional_and_shrink_is_counted(self):
        out = self.check(sized_prompt(200), baseline=sized_prompt(220))
        self.assertFalse(self.has_hint(out, ORIGIN_HINT))
        self.assertEqual(out["length_comparison"]["baseline_delta"], -20)
        self.assertNotIn("origin_chars", out["length_comparison"])
        out = self.check(sized_prompt(200), origin=sized_prompt(250))
        self.assertEqual(out["length_comparison"]["origin_delta_percent"], -20.0)

    def test_origin_and_baseline_ignore_whitespace(self):
        out = self.check(sized_prompt(260), baseline="\n\t" + sized_prompt(260),
                         origin="\n " + sized_prompt(200).replace("：", "：\t "))
        self.assertEqual(out["length_comparison"]["baseline_delta"], 0)
        self.assertEqual(out["length_comparison"]["origin_delta_percent"], 30.0)
        self.assertFalse(self.has_hint(out, ORIGIN_HINT))

    def test_origin_comment_does_not_implicitly_read_path(self):
        out = self.check(asks="# 父稿 v2 = parent.txt\n# 起点 v1 = missing.txt\n")
        self.assertTrue(out["ok"], out["errors"])
        self.assertNotIn("length_comparison", out)

    def test_empty_or_missing_origin_is_input_error(self):
        out = self.check(origin=" \n\t", expected_exit=2)
        self.assertIn("去空白后为空", out["errors"][0])
        with tempfile.TemporaryDirectory() as tmp:
            out = self.check(extra=("--origin", str(Path(tmp) / "absent.txt")), expected_exit=2)
        self.assertIn("起点稿找不到", out["errors"][0])

    def test_partial_length_uses_synthesized_full_prompt(self):
        replacement = "镜头2（6-12秒）：人物停下并抬手，窗边的轻纱缓缓飘动。" + "石" * 100
        out = self.check(replacement, baseline=BASE, origin=BASE, extra=("--partial",))
        self.assertEqual(out["length_comparison"]["current_chars"], chars(BASE) + 100)
        self.assertEqual(out["length_comparison"]["baseline_delta"], 100)
        self.assertTrue(self.has_hint(out, ORIGIN_HINT))

    def test_origin_warning_can_be_adjudicated_with_current_sha(self):
        prompt = sized_prompt(300)
        first = self.check(prompt, origin=sized_prompt(200))
        sha = first["delivered_sha256"][:8]
        out = self.check(prompt, origin=sized_prompt(200),
                         adjudicated=f"新稿比起点版累计增长 @{sha}\n")
        self.assertFalse(self.has_hint(out, ORIGIN_HINT))
        self.assertTrue(self.has_hint(out, ORIGIN_HINT, "adjudicated"))

    def test_origin_stale_adjudication_keeps_warning(self):
        out = self.check(sized_prompt(300), origin=sized_prompt(200),
                         adjudicated="新稿比起点版累计增长 @00000000\n")
        self.assertTrue(self.has_hint(out, ORIGIN_HINT))
        self.assertTrue(any("失效裁定 1 条" in c for c in out["checked"]))

    def test_one_take_in_style_or_plot_warns_for_multiple_headers(self):
        for prompt in (BASE.replace("写实，", "一镜到底，写实，"),
                       BASE.replace("人物从门口", "一镜到底，人物从门口")):
            with self.subTest(prompt=prompt):
                out = self.check(prompt)
                self.assertTrue(self.has_hint(out, TAKE_HINT))
                self.assertTrue(out["ok"], out["errors"])

    def test_one_take_single_header_and_ordinary_multishot_do_not_warn(self):
        one = BASE.replace("写实，", "一镜到底，写实，").replace("镜头1（0-6秒）", "镜头1（0-12秒）")
        one = one.replace("镜头2（6-12秒）：", "第6秒起，")
        for prompt in (BASE, one):
            self.assertFalse(self.has_hint(self.check(prompt), TAKE_HINT))

    def test_one_take_dialogue_unrelated_section_and_negated_claim_do_not_warn(self):
        for prompt in (BASE.replace("人物停下并抬手", '人物说道：“一镜到底。”人物停下并抬手'),
                       BASE.replace("成年人。", "成年人。一镜到底。"),
                       BASE.replace("写实，", "不采用一镜到底，写实，")):
            with self.subTest(prompt=prompt):
                self.assertFalse(self.has_hint(self.check(prompt), TAKE_HINT))

    def test_one_take_warning_can_be_adjudicated(self):
        out = self.check(BASE.replace("写实，", "一镜到底，写实，"),
                         adjudicated="一镜到底却有多个镜头标题\n")
        self.assertFalse(self.has_hint(out, TAKE_HINT))
        self.assertTrue(self.has_hint(out, TAKE_HINT, "adjudicated"))

    def test_one_take_whitebox_untimed_does_not_require_seconds(self):
        prompt = BASE.replace("写实，", "一镜到底，写实，")
        prompt = prompt.replace("镜头1（0-6秒）", "镜头1").replace("镜头2（6-12秒）：", "随后，")
        out = self.check(prompt, extra=("--mode", "白模", "--untimed", "--shot-seconds", "12"))
        self.assertFalse(self.has_hint(out, TAKE_HINT))
        self.assertTrue(out["ok"], out["errors"])


if __name__ == "__main__":
    unittest.main()
