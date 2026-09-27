#!/usr/bin/env python3
"""经验库脚本行为回归：python3 tests/test_lesson_scripts.py。
review_lessons 连 archive 一起查与数文件名来源、log_lesson 加锁与原子替换、merge_lessons 冲突退出码。
只对临时目录里的文件跑，不碰真实经验库与案例库。"""
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

try: import fcntl
except ImportError: fcntl = None

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
REVIEW = SCRIPTS / "review_lessons.py"
LOG = SCRIPTS / "log_lesson.py"
MERGE = SCRIPTS / "merge_lessons.py"
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
            self.assertEqual(dst.read_text(encoding="utf-8"), target)

            p = run(MERGE, "--from", src, "--into", dst)
            self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
            self.assertIn("本次写入 1 条", p.stdout)
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


if __name__ == "__main__":
    unittest.main()
