"""Outcome fallback must resolve report paths within the selected report directory."""
import datetime
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent


class RuleStatsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name) / 'current-project'
        self.d.mkdir()
        self.report = self.d / 'same.json'
        self.report.write_text(json.dumps({'kind': 'light', 'created_at': time.time(),
                                         'delivered_sha256': 'a' * 64}), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def stats(self, report):
        (self.d / 'outcomes.jsonl').write_text(json.dumps({'verdict': '采用', 'report': report}) + '\n', encoding='utf-8')
        before = {p.name: p.read_bytes() for p in self.d.iterdir()}
        p = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts/rule_stats.py'),
                            '--dir', str(self.d), '--today', datetime.date.today().isoformat()],
                           capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.d.iterdir()})
        return p.stdout

    def test_foreign_paths_do_not_match_same_name(self):
        for report in ('../other-project/same.json', str(self.d.parent / 'other-project/same.json')):
            with self.subTest(report=report):
                self.assertIn('有成片结果的 0 份，占 0%', self.stats(report))

    def test_local_paths_still_match(self):
        for report in ('same.json', './same.json', str(self.report)):
            with self.subTest(report=report):
                self.assertIn('有成片结果的 1 份，占 100%', self.stats(report))
