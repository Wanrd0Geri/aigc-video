#!/usr/bin/env python3
"""codex_stop_adapter.py：只做格式转换，不改 stop_gate 的判断。"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks"


def load_adapter():
    spec = importlib.util.spec_from_file_location("codex_stop_adapter_under_test", HOOKS / "codex_stop_adapter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodexAdapterTest(unittest.TestCase):
    def setUp(self):
        self.adapter = load_adapter()

    def write_rows(self, rows):
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8")
        with handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.addCleanup(Path(handle.name).unlink)
        return handle.name

    def test_shared_hook_is_the_sibling_file(self):
        self.assertEqual(self.adapter.SHARED_HOOK, HOOKS / "stop_gate.py")
        self.assertIs(self.adapter.shared.read_transcript, self.adapter.read_transcript)

    def test_codex_message_rows_get_a_message_field(self):
        path = self.write_rows([
            {"type": "response_item", "payload": {"type": "message", "role": "user",
                                                  "content": [{"type": "input_text", "text": "写一条"}]}},
            {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                                                  "content": [{"type": "output_text", "text": "好的"}]}},
        ])
        rows = self.adapter.read_transcript(path)
        self.assertEqual([row["message"]["role"] for row in rows], ["user", "assistant"])
        self.assertEqual(rows[0]["message"]["content"], [{"type": "text", "text": "写一条"}])
        self.assertEqual(rows[1]["message"]["content"], [{"type": "text", "text": "好的"}])

    def test_other_rows_pass_through_unchanged(self):
        claude_row = {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "x"}]}}
        tool_row = {"type": "response_item", "payload": {"type": "function_call", "name": "shell"}}
        rows = self.adapter.read_transcript(self.write_rows([claude_row, tool_row]))
        self.assertEqual(rows, [claude_row, tool_row])

    def test_missing_transcript_stays_none(self):
        self.assertIsNone(self.adapter.read_transcript(None))


if __name__ == "__main__":
    unittest.main()
