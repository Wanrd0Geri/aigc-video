#!/usr/bin/env python3
"""v47 脚本回归：python3 tests/test_v47_scripts.py。
log_lesson 认缩写的多条来源；check_prompt 把项目内报告记进报告目录索引、log_outcome 按 8 位 sha 找得到；
extract_frames 的运动量（定住、重演候选）。只在临时目录里跑，不碰真实经验库和 ~/.aigc-video-gate。"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
CASES = ROOT / "tests" / "check_cases"
HEAD = "# 测试经验库\n\n## 七、诊断新增\n\n"


def run(script, *args, env=None):
    return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / script), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", env=env)


class LogLessonSources(unittest.TestCase):
    def log(self, source, conclusion="测试结论"):
        with tempfile.TemporaryDirectory() as tmp:
            lib = Path(tmp) / "lessons.md"
            lib.write_text(HEAD, encoding="utf-8")
            p = run("log_lesson.py", "--topic", "摄影/测试", "--phenomenon", "现象", "--a", "写法A",
                    "--conclusion", conclusion, "--confidence", "已试", "--source", source, "--file", lib)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stderr

    def test_abbreviated_multi_sources_not_single(self):
        for src in ("某片 镜头_v09/v10/v11/v12_*.mp4", "镜头_v06/v07 对 v09–v12 *.mp4", "镜头_v07.mp4 对 v11、v12",
                    "镜头_v17.mp4 对 v16"):
            self.assertNotIn("来源只有一条成片", self.log(src), src)

    def test_single_source_still_reminds(self):
        for src in ("某片 镜头_v03.mp4 2026-10-15", "镜头_v3-final.mp4", "镜头_对比图.mp4", "镜头_v3-20261015.mp4",
                    "针对v3.mp4", "背对v3.mp4", "镜头_v3 对 v20261015.mp4"):
            self.assertIn("来源只有一条成片", self.log(src), src)


class ReportCopy(unittest.TestCase):
    def run_check(self, gate, rep):
        env = {**os.environ, "AIGC_GATE_DIR": str(gate)}
        p = run("check_prompt.py", "--prompt", CASES / "control_valid.txt", "--total", "12", "--report", rep, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return env

    def test_project_report_copied_into_gate_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate, proj = Path(tmp) / "gate", Path(tmp) / "proj"
            proj.mkdir()
            rep = proj / "检查报告.json"
            env = self.run_check(gate, rep)
            original = json.loads(rep.read_text(encoding="utf-8"))
            copies = list(gate.glob("*.json"))
            self.assertEqual(len(copies), 1)
            copy = json.loads(copies[0].read_text(encoding="utf-8"))
            self.assertEqual(copy["copied_from"], str(rep.resolve()))
            self.assertEqual({k: v for k, v in copy.items() if k != "copied_from"}, original)
            sha8 = original["delivered_sha256"][:8]
            # 门禁、统计、记成片结果都只扫报告目录：副本让三处都看得到
            q = run("log_outcome.py", "--sha", sha8, "--video", "x.mp4", "--verdict", "采用", env=env)
            self.assertEqual(q.returncode, 0, q.stderr)
            row = json.loads((gate / "outcomes.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(row["sha"], sha8)
            r = run("rule_stats.py", "--dir", gate, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_report_inside_gate_dir_not_copied(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = Path(tmp) / "gate"
            self.run_check(gate, gate / "r.json")
            self.assertEqual([p.name for p in gate.glob("*.json")], ["r.json"])


class Motion(unittest.TestCase):
    def setUp(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("没有 numpy")
        import extract_frames
        self.ef = extract_frames

    def frames(self, values):
        import numpy as np
        return np.stack([np.full((9, 16), v, dtype=np.uint8) for v in values])

    def test_still_hold_and_repeat(self):
        # 24 fps：前 1 秒在变，接着 1.5 秒定住，最后 1 秒把前 1 秒重演一遍
        ramp = [i * 8 for i in range(24)]
        vals = ramp + [ramp[-1]] * 36 + ramp
        diffs, segs, holds, repeats = self.ef.motion_analyze(self.frames(vals), 24.0, 12)
        self.assertEqual(len(segs), 7)          # 83 个帧对，最后一段不足 12
        self.assertTrue(all(s["still"] for s in segs[2:4]))
        self.assertEqual([(round(h["t0"], 2), h["segs"]) for h in holds], [(1.0, 2)])
        self.assertTrue(repeats, "重演段应被报出")
        self.assertLess(repeats[0]["a"][0], 1.0)
        self.assertGreater(repeats[0]["b"][0], 2.0)

    def test_steady_motion_no_hold_no_repeat(self):
        vals = [(i * 7) % 250 for i in range(48)]
        _d, segs, holds, repeats = self.ef.motion_analyze(self.frames(vals), 24.0, 12)
        self.assertFalse(any(s["still"] for s in segs))
        self.assertEqual(holds, [])

    def test_motion_errors_do_not_escape(self):
        from unittest.mock import patch
        logs = []
        for exc in (PermissionError("写不进"), OSError("ffprobe 起不来"), ValueError("坏数据")):
            with patch.object(self.ef, "motion_report", side_effect=exc):
                self.ef.motion_step("ffmpeg", "ffprobe", "x.mp4", Path("."), lambda n: None, logs.append)
        self.assertEqual(len(logs), 3)
        self.assertTrue(all(x.startswith("运动量: 失败") for x in logs))

    def test_extract_frames_writes_motion_files(self):
        ff = self.ef.find_tool("ffmpeg")
        if not ff or not self.ef.find_tool("ffprobe"):
            self.skipTest("没有 ffmpeg")
        with tempfile.TemporaryDirectory() as tmp:
            v, out = Path(tmp) / "t.mp4", Path(tmp) / "f"
            r = subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x90:rate=24",
                                "-pix_fmt", "yuv420p", str(v)], capture_output=True)
            self.assertEqual(r.returncode, 0)
            p = run("extract_frames.py", v, out)
            self.assertIn(p.returncode, (0, 3), p.stderr)
            self.assertIn("运动量", (out / "motion.txt").read_text(encoding="utf-8"))
            names = (out / ".aigc-frames.manifest").read_text(encoding="utf-8").split()
            self.assertIn("motion.txt", names)
            self.assertIn("motion.json", names)
            p2 = run("extract_frames.py", v, out)             # 重跑能清掉自己上一次的 motion 文件
            self.assertIn(p2.returncode, (0, 3), p2.stderr)


if __name__ == "__main__":
    unittest.main()
