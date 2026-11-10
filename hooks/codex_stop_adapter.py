#!/usr/bin/env python3
"""Codex 专用入口：把 Codex 的会话记录转成 stop_gate.py 读得懂的格式，再交给它判断。

只做格式转换；识别提示词、对报告、机械检查和重试都在同目录的 stop_gate.py 里。
"""
import importlib.util
from pathlib import Path


SHARED_HOOK = Path(__file__).resolve().parent / "stop_gate.py"
_spec = importlib.util.spec_from_file_location("aigc_video_shared_stop_gate", SHARED_HOOK)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load shared video hook: {SHARED_HOOK}")
shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shared)
_shared_read_transcript = shared.read_transcript


def read_transcript(path):
    rows = _shared_read_transcript(path)
    if rows is None:
        return None
    normalized = []
    for row in rows:
        payload = row.get("payload") if isinstance(row, dict) else None
        if not (isinstance(row, dict) and row.get("type") == "response_item"
                and isinstance(payload, dict) and payload.get("type") == "message"):
            normalized.append(row)
            continue
        message = dict(payload)
        content = message.get("content")
        if isinstance(content, list):
            message["content"] = [
                {**item, "type": {"input_text": "text", "output_text": "text",
                                  "input_image": "image"}.get(item.get("type"), item.get("type"))}
                if isinstance(item, dict) else item
                for item in content
            ]
        normalized.append({**row, "message": message})
    return normalized


shared.read_transcript = read_transcript


if __name__ == "__main__":
    raise SystemExit(shared.main())
