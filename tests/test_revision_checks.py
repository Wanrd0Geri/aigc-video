#!/usr/bin/env python3
"""修订格式与丢句检查回归：python3 tests/test_revision_checks.py。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "tests" / "check_cases"
CHECKER = ROOT / "scripts" / "check_prompt.py"
BASE = (CASES / "control_valid.txt").read_text(encoding="utf-8")
CLOSING = "全片不添加BGM，不添加字幕。"


class RevisionChecks(unittest.TestCase):
    def check(self, prompt, baseline=BASE, extra=()):
        with tempfile.TemporaryDirectory() as tmp:
            p, b, report, combined = (Path(tmp) / name for name in ("prompt.txt", "base.txt", "report.json", "combined.txt"))
            p.write_text(prompt, encoding="utf-8")
            b.write_text(baseline, encoding="utf-8")
            run = subprocess.run([sys.executable, str(CHECKER), "--prompt", str(p),
                                  "--baseline", str(b), "--report", str(report),
                                  "--save-checked", str(combined), "--total", "12", *extra],
                                 capture_output=True, text=True)
            out = json.loads(run.stdout)
            self.assertEqual(run.returncode, 0 if out["ok"] else 1, run.stderr)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["ready"], out["ok"])
            return out, combined.read_text(encoding="utf-8")

    def loss(self, out):
        return [w for w in out["warnings"] if "在新稿里消失" in w]

    def test_inherited_four_rejects_tail_constraint(self):
        out, _ = self.check(BASE.replace(CLOSING, "不出现第二个人。\n" + CLOSING))
        self.assertFalse(out["ok"])
        self.assertTrue(any("末尾只留固定句" in e for e in out["errors"]))
        self.assertEqual((out["format"], out["effective_format"]), ("继承", "四段"))

    def test_inherited_four_warns_inline_negative(self):
        out, _ = self.check((CASES / "inline_negative.txt").read_text(encoding="utf-8"))
        self.assertTrue(out["ok"])
        self.assertTrue(any(w.startswith("否定句：不出现第二个白猿") for w in out["warnings"]))

    def test_inherited_four_rejects_empty_section(self):
        out, _ = self.check(BASE.replace("一位穿灰衣的成年人。", ""))
        self.assertFalse(out["ok"])
        self.assertIn("段落内容为空：主体", out["errors"])

    def test_inherited_four_honors_locked_inline_negative(self):
        prompt = (CASES / "inline_negative.txt").read_text(encoding="utf-8")
        out, _ = self.check(prompt, extra=("--lock", "不出现第二个白猿。"))
        self.assertTrue(out["ok"])
        self.assertFalse(any(w.startswith("否定句：") for w in out["warnings"]))

    def test_inherited_four_validates_named_negative(self):
        out, _ = self.check(BASE, extra=("--negative-exception", "不出现不存在的猫。"))
        self.assertFalse(out["ok"])
        self.assertTrue(any("点名的句子在稿里找不到" in e for e in out["errors"]))

    def test_old_five_format_and_closing_preserved(self):
        base = (CASES / "five_section_old.txt").read_text(encoding="utf-8")
        prompt = (CASES / "five_section_revised.txt").read_text(encoding="utf-8")
        out, _ = self.check(prompt, base)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(out["effective_format"], "五段")

    def test_old_six_format_and_closing_preserved(self):
        base = (CASES / "six_section_new.txt").read_text(encoding="utf-8")
        prompt = (CASES / "six_section_revised.txt").read_text(encoding="utf-8")
        out, _ = self.check(prompt, base)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(out["effective_format"], "六段")

    def test_old_four_keeps_original_closing(self):
        base = (CASES / "inherit_old_source.txt").read_text(encoding="utf-8")
        out, _ = self.check(base, base)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(out["effective_format"], "四段")

    def test_unknown_legacy_shell_still_inherits(self):
        base = BASE.replace("主体：", "人物：").replace("场景：", "地点：")
        out, _ = self.check(base, base)
        self.assertTrue(out["ok"], out["errors"])
        self.assertEqual(out["effective_format"], "继承")

    def test_partial_combines_and_checks_four_format(self):
        prompt = "镜头2（6-12秒）：人物抬手拉开窗，镜头缓缓推近窗沿。"
        out, combined = self.check(prompt, extra=("--partial",))
        self.assertTrue(out["ok"], out["errors"])
        self.assertIn("镜头1（0-6秒）", combined)
        self.assertIn(prompt, combined)
        self.assertTrue(combined.endswith(CLOSING))

    def test_partial_inline_negative_is_not_discarded_as_tail(self):
        prompt = "镜头1（0-6秒）：人物向窗前走去，镜头缓缓推近。\n不出现第二个人。"
        out, combined = self.check(prompt, extra=("--partial", "--negative-exception", "不出现第二个人。"))
        self.assertTrue(out["ok"], out["errors"])
        self.assertIn("不出现第二个人。\n镜头2", combined)

    def test_partial_last_shot_still_rejects_tail_constraint(self):
        prompt = "镜头2（6-12秒）：镜头缓缓推近人物。\n不出现第二个人。"
        out, _ = self.check(prompt, extra=("--partial",))
        self.assertFalse(out["ok"])
        self.assertTrue(any("末尾只留固定句" in e for e in out["errors"]))

    def test_distinct_object_deleted_next_to_similar_retained_sentence(self):
        extra = "镜头缓慢推近人物的正脸。镜头缓慢推近人物的双手。"
        base = BASE.replace("衣摆轻晃。", "衣摆轻晃。" + extra)
        out, _ = self.check(base.replace("镜头缓慢推近人物的双手。", ""), base)
        self.assertTrue(out["ok"])
        self.assertEqual(len(self.loss(out)), 1)
        self.assertIn("镜头缓慢推近人物的双手", self.loss(out)[0])

    def test_other_shot_cannot_cover_deleted_sentence(self):
        base = BASE.replace("衣摆轻晃。", "衣摆轻晃。镜头缓慢推近人物的正脸。")
        prompt = base.replace("镜头缓慢推近人物的正脸。", "").replace(
            "窗边的轻纱缓缓飘动。", "窗边的轻纱缓缓飘动。镜头缓慢推近人物的正脸。")
        out, _ = self.check(prompt, base)
        self.assertIn("镜头缓慢推近人物的正脸", self.loss(out)[0])

    def test_small_rewording_within_shot_is_not_reported_as_loss(self):
        base = BASE.replace("衣摆轻晃。", "衣摆轻晃。镜头缓慢推近人物的正脸。")
        out, _ = self.check(base.replace("缓慢推近", "缓缓推近"), base)
        self.assertTrue(out["ok"])
        self.assertFalse(self.loss(out))

    def test_partial_loss_uses_only_replaced_shot(self):
        base = BASE.replace("衣摆轻晃。", "衣摆轻晃。镜头缓慢推近人物的正脸。镜头缓慢推近人物的双手。")
        prompt = "镜头1（0-6秒）：人物从门口走到窗前，衣摆轻晃。镜头缓慢推近人物的正脸。"
        out, _ = self.check(prompt, base, ("--partial",))
        self.assertTrue(out["ok"])
        self.assertEqual(len(self.loss(out)), 1)
        self.assertIn("父稿有 1 句", self.loss(out)[0])
        self.assertIn("双手", self.loss(out)[0])


if __name__ == "__main__":
    unittest.main()
