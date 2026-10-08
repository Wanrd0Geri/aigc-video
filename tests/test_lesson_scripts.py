#!/usr/bin/env python3
"""经验库脚本行为回归：python3 tests/test_lesson_scripts.py。
review_lessons 连 archive 一起查与数文件名来源、log_lesson 加锁与原子替换、merge_lessons 冲突退出码。
只对临时目录里的文件跑，不碰真实经验库与案例库。"""
from pathlib import Path
import importlib.util
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

try: import fcntl
except ImportError: fcntl = None

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
REVIEW = SCRIPTS / "review_lessons.py"
LOG = SCRIPTS / "log_lesson.py"
MERGE = SCRIPTS / "merge_lessons.py"
BUILD = SCRIPTS / "build_lessons_index.py"
LINT = SCRIPTS / "lint_lessons.py"
HEAD = "# 测试经验库\n\n## 七、诊断新增\n\n"
LOG_ARGS = ("--topic", "摄影/测试", "--phenomenon", "现象", "--a", "写法A",
            "--conclusion", "单次观察：测试", "--confidence", "已试", "--source", "x.mp4")


def row(lid, date="2026-09-01", topic="摄影/测试", conclusion="单次观察：测试", confidence="已试", source="a.mp4"):
    """九字段经验条目。"""
    return f"{lid} | {date} | {topic} | 现象 | 写法A | — | {conclusion} | {confidence} | {source}"


def cmd(script, *args):
    return [sys.executable, "-X", "utf8", str(script), *map(str, args)]


def run(script, *args):
    return subprocess.run(cmd(script, *args), capture_output=True, text=True, encoding="utf-8")


def section(out, start, end):
    """清单里从 start 开头的标题行到 end 开头的标题行之间的文字（找不到 end 就到末尾）。"""
    lines = out.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith(start))
    j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith(end)), len(lines))
    return "\n".join(lines[i:j])


def lesson_rows(path):
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith("L")]


class LessonScripts(unittest.TestCase):
    # 1. 整理清单第一节：主库查不到的编号连 archive 一起查
    def test_review_hot_lesson_found_in_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            lib, arch, cases = d / "lessons.md", d / "archive.md", d / "cases.md"
            lib.write_text(HEAD + row("L001") + "\n", encoding="utf-8")
            arch.write_text("# 归档\n\n## 已升级为规则\n\n"
                            + row("L002", topic="摄影/归档测试", conclusion="结论【已升级为规则：writing-rules.md 第 1 条】")
                            + "\n", encoding="utf-8")
            cases.write_text("# 案例\n\n## M001｜案例一\n\n关联经验：L002\n\n## M002｜案例二\n\n关联经验：L002\n",
                             encoding="utf-8")
            p = run(REVIEW, "--file", lib, "--cases", cases, "--archive", arch, "--today", "2026-09-27")
            self.assertEqual(p.returncode, 0, p.stderr)
            sec = section(p.stdout, "## 一、", "## 二、")
            self.assertTrue(any(ln.startswith("| L002 |") for ln in sec.splitlines()), sec)
            self.assertIn("archive：已升级为规则", sec)
            self.assertNotIn("经验库里没有这条", sec)

    # 2. 整理清单第六节：来源里数到两个成片文件名就算有第二个来源
    def test_review_second_source_counts_file_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            lib, cases = d / "lessons.md", d / "cases.md"
            lib.write_text(HEAD + row("L001", date="2026-08-01", source="a.mp4; b.mp4") + "\n"
                           + row("L002", date="2026-08-01", topic="摄影/另一条", source="c.mp4") + "\n",
                           encoding="utf-8")
            cases.write_text("# 案例\n", encoding="utf-8")
            p = run(REVIEW, "--file", lib, "--cases", cases, "--today", "2026-09-27")
            self.assertEqual(p.returncode, 0, p.stderr)
            sec = section(p.stdout, "## 六、", "## 七、")
            self.assertIn("| L002 |", sec)
            self.assertNotIn("| L001 |", sec)

    def test_review_hot_evidence_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib, cases = Path(tmp) / "lessons.md", Path(tmp) / "cases.md"
            records = [row("L001", source="a.mp4，待核对"),
                       row("L002", conclusion="修法已被否定", source="a.mp4；b.mov"),
                       row("L003", source="用户实测"),
                       row("L004", source="视频节点 1；视频节点 2"),
                       row("L005", conclusion="修法待验", source="a.mp4，待核对"),
                       row("L006").replace("写法A", "没试过"),
                       row("L007").replace(" | — | ", " | 未试 | ")]
            lib.write_text(HEAD + "\n".join(records) + "\n", encoding="utf-8")
            refs = "、".join(f"L{n:03d}" for n in range(1, 8))
            cases.write_text(f"## M001｜案例一\n关联经验：{refs}\n\n## M002｜案例二\n关联经验：{refs}\n", encoding="utf-8")
            p = run(REVIEW, "--file", lib, "--cases", cases)
            self.assertEqual(p.returncode, 0, p.stderr)
            sec = section(p.stdout, "## 一、", "## 二、")
            self.assertIn("| 证据状态 |", sec)
            expected = {"L001": "来源待核对、单来源", "L002": "修法待验、多来源",
                        "L003": "多来源", "L004": "多来源", "L005": "来源待核对、修法待验、单来源",
                        "L006": "修法待验、单来源", "L007": "修法待验、单来源"}
            for lid, state in expected.items():
                with self.subTest(lid=lid):
                    line = next(ln for ln in sec.splitlines() if ln.startswith(f"| {lid} |"))
                    self.assertEqual(line.split(" | ")[4], state)

    # 3. 并发写入：5 个进程同时写，编号不撞、条目不丢、没有临时文件残留
    def test_log_concurrent_writes_get_distinct_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            lib = d / "lessons.md"
            lib.write_text(row("L001") + "\n", encoding="utf-8")
            procs = [subprocess.Popen(cmd(LOG, *LOG_ARGS, "--file", lib), stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True, encoding="utf-8") for _ in range(5)]
            outs = []
            for p in procs:
                out, err = p.communicate(timeout=30)
                self.assertEqual(p.returncode, 0, err)
                outs.append(out.strip())
            self.assertEqual(sorted(outs), ["L002", "L003", "L004", "L005", "L006"])
            self.assertEqual(len(lesson_rows(lib)), 6)
            self.assertEqual(list(d.glob("*.tmp.*")), [])

    # 4. 锁生效：锁被占着时 log_lesson.py 等着，释放后写入成功
    @unittest.skipIf(fcntl is None, "本平台无 fcntl，不测锁")
    def test_log_waits_for_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            lib = d / "lessons.md"
            lib.write_text(row("L001") + "\n", encoding="utf-8")
            with open(d / ".lessons.md.lock", "a+") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                p = subprocess.Popen(cmd(LOG, *LOG_ARGS, "--file", lib), stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, encoding="utf-8")
                try:
                    time.sleep(0.5)
                    waiting = p.poll() is None
                finally:
                    fcntl.flock(lk, fcntl.LOCK_UN)
            try:
                out, err = p.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.communicate()
                self.fail("释放锁后 10 秒内没有写完")
            self.assertTrue(waiting, "锁被占着时 log_lesson.py 已经退出，没有等锁")
            self.assertEqual(p.returncode, 0, err)
            self.assertEqual(out.strip(), "L002")
            self.assertTrue(any(ln.startswith("L002 | ") for ln in lesson_rows(lib)))

    # 5. 合并退出码：有同编号不同内容退出 3（dry-run 不写，正式合并照常写新增、冲突保留目标），无冲突退出 0
    def test_merge_conflict_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            src, dst = d / "src.md", d / "dst.md"
            target = HEAD + row("L001", conclusion="单次观察：目标的写法") + "\n"
            dst.write_text(target, encoding="utf-8")
            src.write_text(HEAD + row("L001", conclusion="单次观察：来源改写过") + "\n"
                           + row("L002", topic="摄影/新条目") + "\n", encoding="utf-8")

            p = run(MERGE, "--from", src, "--into", dst, "--dry-run")
            self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
            self.assertIn("冲突 1 条", p.stdout)
            self.assertIn("dry-run：未写入", p.stdout)
            self.assertNotIn("build_lessons_index.py", p.stderr)
            self.assertEqual(dst.read_text(encoding="utf-8"), target)

            p = run(MERGE, "--from", src, "--into", dst)
            self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
            self.assertIn("本次写入 1 条", p.stdout)
            self.assertIn("build_lessons_index.py", p.stderr)
            self.assertIn(str(dst), p.stderr)
            self.assertFalse((d / "index.md").exists())
            rows = {ln.split(" | ")[0]: ln.split(" | ") for ln in lesson_rows(dst)}
            self.assertEqual(rows["L002"][7], "未试（合并待审）")
            self.assertEqual(rows["L002"][8], "a.mp4（原标：已试）")
            self.assertEqual(rows["L001"][6], "单次观察：目标的写法")
            self.assertEqual(list(d.glob("*.tmp.*")), [])

            dst.write_text(target, encoding="utf-8")
            src.write_text(target + row("L002", topic="摄影/新条目") + "\n", encoding="utf-8")
            p = run(MERGE, "--from", src, "--into", dst)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("相同 1 条", p.stdout)
            self.assertIn("冲突 0 条", p.stdout)
            self.assertIn("本次写入 1 条", p.stdout)


    def test_supplement_appends_without_changing_other_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp) / "lessons.md"
            original = HEAD + row("L001") + "\n" + row("L002", source="other.mp4") + "\n"
            lib.write_text(original, encoding="utf-8")
            p = run(LOG, "--file", lib, "--supplement", "L001", "--source", "new.mp4",
                    "--conclusion-append", "补充观察", "--date", "2026-09-27")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout.strip(), "L001")
            self.assertIn("build_lessons_index.py", p.stderr)
            self.assertIn(str(lib), p.stderr)
            expected = original.replace("单次观察：测试 | 已试 | a.mp4",
                                        "单次观察：测试【补充 2026-09-27：补充观察】 | 已试 | a.mp4；new.mp4")
            self.assertEqual(lib.read_text(encoding="utf-8"), expected)
            p = run(LOG, "--file", lib, "--supplement", "L001", "--source", "third.mov")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(lib.read_text(encoding="utf-8"), expected.replace("a.mp4；new.mp4", "a.mp4；new.mp4；third.mov"))
            self.assertEqual(list(Path(tmp).glob("*.tmp.*")), [])

    def test_supplement_rejects_missing_archived_and_new_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib, arch = Path(tmp) / "lessons.md", Path(tmp) / "archive.md"
            original = HEAD + row("L001") + "\n"
            archived = row("L002") + "\n"
            lib.write_text(original, encoding="utf-8")
            arch.write_text(archived, encoding="utf-8")
            for args in [("--supplement", "L003", "--source", "new.mp4"),
                         ("--supplement", "L002", "--source", "new.mp4"),
                         ("--supplement", "L001"),
                         ("--supplement", "L001", "--source", "new.mp4", "--topic", "摄影/测试")]:
                with self.subTest(args=args):
                    p = run(LOG, "--file", lib, *args)
                    self.assertEqual(p.returncode, 2, p.stderr)
                    self.assertNotIn("build_lessons_index.py", p.stderr)
                    self.assertEqual(lib.read_text(encoding="utf-8"), original)
                    self.assertEqual(arch.read_text(encoding="utf-8"), archived)


    def test_log_ids_expand_past_999_and_lint_stays_continuous(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib, arch = Path(tmp) / "lessons.md", Path(tmp) / "archive.md"
            lib.write_text(HEAD + row("L998") + "\n" + row("L999") + "\n", encoding="utf-8")
            # 从 L001 起连续的规则不变：早期编号在归档，主库只留边界两条。
            archived = "\n".join(row(f"L{n:03d}") for n in range(1, 998)) + "\n"
            arch.write_text(archived, encoding="utf-8")
            for expected in ("L1000", "L1001"):
                p = run(LOG, *LOG_ARGS, "--file", lib)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout.strip(), expected)
            self.assertEqual([ln.split(" | ")[0] for ln in lesson_rows(lib)],
                             ["L998", "L999", "L1000", "L1001"])
            built = run(BUILD, "--file", lib)
            self.assertEqual(built.returncode, 0, built.stderr)
            p = run(SCRIPTS / "lint_lessons.py", "--file", lib)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("经验库 4 条（archive 另有 997 条，编号合集连续）", p.stdout)
            p = run(LOG, "--file", lib, "--supplement", "L1000", "--source", "four-digit.mov")
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout.strip(), "L1000")
            self.assertEqual(arch.read_text(encoding="utf-8"), archived)
            lib.write_text("\n".join(ln for ln in lib.read_text(encoding="utf-8").splitlines()
                                     if not ln.startswith("L1000 | ")) + "\n", encoding="utf-8")
            built = run(BUILD, "--file", lib)
            self.assertEqual(built.returncode, 0, built.stderr)
            p = run(SCRIPTS / "lint_lessons.py", "--file", lib)
            self.assertEqual(p.returncode, 1, p.stderr)
            self.assertIn("这里应当是 L1000", p.stderr)


class LessonsIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lib = self.root / "主库.md"
        self.index = self.root / "index.md"
        self.lib.write_text(HEAD + row("L001") + "\n", encoding="utf-8")

    def build(self, *args):
        p = run(BUILD, "--file", self.lib, *args)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def module(self):
        self.assertTrue(BUILD.is_file(), "索引生成器尚未实现")
        spec = importlib.util.spec_from_file_location("lessons_index_under_test", BUILD)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob("*") if p.is_file()}

    # Wrong columns, normalization, sorting or archive leakage must break this projection.
    def test_four_columns_preserve_original_order_unicode_and_confidence(self):
        source = (HEAD + row("L1000", topic="摄影/裸|竖线", conclusion="反例：甲→乙【撤回】；a|b",
                             confidence="未试（合并待审）") + "\n" + row("L003") + "\n页尾说明\n")
        self.lib.write_text(source, encoding="utf-8")
        archive = self.root / "archive.md"
        archive.write_text(row("L002") + "\n", encoding="utf-8")
        before = self.snapshot()
        self.build()
        actual = self.index.read_text(encoding="utf-8")
        self.assertIn("编号 | 分类/主题 | 结论 | 置信度\n---|---|---|---\n", actual)
        self.assertEqual([x for x in actual.splitlines() if x.startswith("L")], [
            "L1000 | 摄影/裸|竖线 | 反例：甲→乙【撤回】；a|b | 未试（合并待审）",
            "L003 | 摄影/测试 | 单次观察：测试 | 已试"])
        self.assertNotIn("\r", actual)
        for name, state in before.items(): self.assertEqual(self.snapshot()[name], state)

    def test_empty_library_generates_checkable_header(self):
        self.lib.write_text("# 空库\n说明文字\n", encoding="utf-8")
        self.build()
        self.assertFalse(lesson_rows(self.index))
        self.build("--check")

    def test_deterministic_generation_and_read_only_check(self):
        self.build()
        first = self.index.read_bytes()
        self.build()
        self.assertEqual(first, self.index.read_bytes())
        before = self.snapshot()
        self.build("--check")
        self.assertEqual(before, self.snapshot())

    def test_check_missing_does_not_create_directory(self):
        missing = self.root / "missing" / "nested" / "index.md"
        before = self.snapshot()
        p = run(BUILD, "--file", self.lib, "--index", missing, "--check")
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("索引", p.stderr)
        self.assertFalse(missing.parent.exists())
        self.assertEqual(before, self.snapshot())

    def test_invalid_source_never_overwrites_existing_index(self):
        self.index.write_bytes(b"previous index\n")
        for source in [row("L001") + "\n" + row("L001"), row("L002") + " | extra",
                       "L003 | only two", row("L004").replace("L004 |", "L004|", 1)]:
            with self.subTest(source=source):
                self.lib.write_text(source, encoding="utf-8")
                before = self.snapshot()
                p = run(BUILD, "--file", self.lib)
                self.assertEqual(p.returncode, 1, p.stderr)
                self.assertIn("L00", p.stderr)
                self.assertEqual(before, self.snapshot())

    def test_missing_extra_duplicate_reordered_and_changed_cells_fail_check(self):
        self.lib.write_text(HEAD + row("L001") + "\n" + row("L002") + "\n", encoding="utf-8")
        self.build()
        original = self.index.read_text(encoding="utf-8")
        line1 = "L001 | 摄影/测试 | 单次观察：测试 | 已试"
        line2 = "L002 | 摄影/测试 | 单次观察：测试 | 已试"
        variants = {
            "missing": original.replace(line1+"\n", ""),
            "extra": original + "L003 | 摄影/测试 | 结论 | 未试\n",
            "duplicate": original + line1 + "\n",
            "reordered": original.replace(line1+"\n"+line2, line2+"\n"+line1),
            "topic": original.replace("摄影/测试", "摄影/不同", 1),
            "conclusion": original.replace("单次观察：测试", "单次观察：不同", 1),
            "confidence": original.replace("| 已试", "| 未试（合并待审）", 1),
            "empty": "", "header": original.replace("置信度", "不应更改"),
        }
        for name, text in variants.items():
            with self.subTest(name=name):
                self.index.write_text(text, encoding="utf-8")
                before = self.snapshot()
                p = run(BUILD, "--file", self.lib, "--check")
                self.assertEqual(p.returncode, 1, p.stderr)
                self.assertIn("索引", p.stderr)
                self.assertEqual(before, self.snapshot())

    def test_empty_identifier_row_is_rejected_without_replacing_index(self):
        self.lib.write_text(HEAD + row("L001") + "\n" + row(""), encoding="utf-8")
        self.index.write_bytes(b"old index\n")
        before = self.snapshot()
        p = run(BUILD, "--file", self.lib)
        self.assertEqual(p.returncode, 1, p.stdout+p.stderr)
        self.assertIn("编号为空", p.stderr)
        self.assertEqual(before, self.snapshot())

    def test_custom_output_and_lint_require_the_same_index(self):
        dest = self.root / "另一个目录" / "custom.md"
        self.build("--index", dest)
        self.assertTrue(dest.is_file())
        self.assertFalse(self.index.exists())
        p = run(LINT, "--file", self.lib, "--index", dest)
        self.assertEqual(p.returncode, 0, p.stderr)
        before = self.snapshot()
        dest.write_text(dest.read_text(encoding="utf-8").replace("| 已试", "| 未试"), encoding="utf-8")
        changed = self.snapshot()
        p = run(LINT, "--file", self.lib, "--index", dest)
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("索引", p.stderr)
        self.assertEqual(changed, self.snapshot())
        self.assertEqual(before[self.lib.name], self.snapshot()[self.lib.name])

    def test_lint_fails_missing_index_without_repair(self):
        before = self.snapshot()
        p = run(LINT, "--file", self.lib)
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("索引", p.stderr)
        self.assertEqual(before, self.snapshot())

    def test_lint_pure_function_signature_is_preserved(self):
        spec = importlib.util.spec_from_file_location("lint_under_test", LINT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.lint(row("L002"), row("L001")), (1, []))

    def test_output_cannot_overwrite_source_or_archive(self):
        arch = self.root / "archive.md"
        arch.write_text(row("L002"), encoding="utf-8")
        for dest in [self.lib, arch]:
            with self.subTest(dest=dest):
                before = self.snapshot()
                p = run(BUILD, "--file", self.lib, "--index", dest)
                self.assertEqual(p.returncode, 1, p.stderr)
                self.assertEqual(before, self.snapshot())

    def test_source_mutation_during_generation_prevents_publication(self):
        module = self.module()
        self.index.write_bytes(b"old index\n")
        original_fsync = module.os.fsync
        def source_changed(fd):
            original_fsync(fd)
            self.lib.write_text(HEAD + row("L001", confidence="未试"), encoding="utf-8")
        # A real concurrent write at the temp-file flush boundary, with real file IO.
        with patch.object(module.os, "fsync", side_effect=source_changed):
            with self.assertRaisesRegex(ValueError, "主库.*变化"):
                module.build_index(self.lib, self.index)
        self.assertEqual(self.index.read_bytes(), b"old index\n")
        self.assertEqual({x.name for x in self.root.iterdir()}, {self.lib.name, self.index.name})

    def test_failed_atomic_replace_keeps_old_index_and_cleans_temp(self):
        module = self.module()
        self.index.write_bytes(b"old index\n")
        before = self.snapshot()
        with patch.object(module.os, "replace", side_effect=OSError("模拟发布失败")):
            with self.assertRaisesRegex(OSError, "模拟发布失败"):
                module.build_index(self.lib, self.index)
        self.assertEqual(before, self.snapshot())

    def test_log_append_reminds_without_rebuilding_or_changing_stdout(self):
        self.build()
        before = self.index.read_bytes()
        p = run(LOG, *LOG_ARGS, "--file", self.lib)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, "L002\n")
        self.assertIn("build_lessons_index.py", p.stderr)
        self.assertIn(str(self.lib), p.stderr)
        self.assertEqual(before, self.index.read_bytes())
        self.assertEqual(run(LINT, "--file", self.lib).returncode, 1)
        self.build()
        self.assertEqual(run(LINT, "--file", self.lib).returncode, 0)

    def test_merge_zero_conflict_only_dry_run_and_rejection_do_not_remind(self):
        src = self.root / "from.md"
        for label, source, args, exit_code in [
            ("zero", row("L001"), (), 0),
            ("conflict_only", row("L001", conclusion="另一条"), (), 3),
            ("dry_run", row("L002"), ("--dry-run",), 0),
            ("rejected", row("L002", topic="无分类"), (), 1),
        ]:
            with self.subTest(label=label):
                src.write_text(HEAD + source + "\n", encoding="utf-8")
                before = self.snapshot()
                p = run(MERGE, "--from", src, "--into", self.lib, *args)
                self.assertEqual(p.returncode, exit_code, p.stdout+p.stderr)
                self.assertNotIn("build_lessons_index.py", p.stderr)
                self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
