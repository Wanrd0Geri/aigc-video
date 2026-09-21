#!/usr/bin/env python3
"""Validate delivery evidence against the actual prompt; never infer semantic quality from regex.

python3 scripts/verify_delivery.py --prompt prompt.txt --requirements requirements.json
    --review review.json [--baseline parent.txt] [--partial]
    [--independent-review independent.json] [--report result.json] [--output delivered.txt] [--response response.md]

--response 在放行时生成可直接粘贴给用户的成品：代码块 + 交付行；交付时只粘贴这个文件，不手工拼。
--response-mode prompt-only 只生成代码块不带交付行（用户说"只要提示词"时用）；放行钩子按正文哈希核对，不依赖那行字。
报告里的 created_at（本次运行时间）与 session_id（环境变量 AIGC_SESSION_ID，没有则 null）供 Stop 钩子做本轮绑定：
报告早于本轮用户消息、或属于别的会话时不算本轮验收，必须为当前要求重跑。

Schema and workflow: references/review/quality-gate.md. Exit 0 ready, 1 not ready, 2 invalid input.
The checker is executed here, not accepted from a supplied 'pass' receipt. Human/model review
content is checked for completeness and text binding, not certified as semantically correct.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time

DOMAINS = ['intent_assets', 'composition_camera', 'action_performance',
           'timing_continuity', 'materials_light_vfx', 'sound_delivery']


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def evaluate(args):
    req_text = Path(args.requirements).read_text(encoding='utf-8')
    req = json.loads(req_text)
    rev = read_json(args.review)
    raw = Path(args.prompt).read_text(encoding='utf-8')
    parent = Path(args.baseline).read_text(encoding='utf-8') if args.baseline else ''
    errors = []
    if args.output_scope == 'affected' and not args.partial:
        raise ValueError('output-scope affected 只用于已有父稿的 partial 修订')
    request = req['request']
    if not isinstance(request, str) or not request.strip():
        raise ValueError('requirements.request 必须保存原始用户请求')
    if req.get('task') not in ['生成', '编辑', '延长', '衔接']:
        raise ValueError('requirements.task 必须明确指定命令性质')
    labels = req['labels']
    locks = req.get('exact_locks', [])
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels) or len(labels) != len(set(labels)):
        raise ValueError('labels 必须是无重复数组，无素材明确写 []')
    if not isinstance(locks, list) or not all(isinstance(x, str) and x.strip() for x in locks):
        raise ValueError('exact_locks 必须是非空文字数组')
    source = request + '\n' + parent
    for lock in locks:
        if lock not in source:
            errors.append('逐字锁缺少原请求或父稿依据：' + lock[:60])
    # The user's standing preference permits narrow homophone substitutions, not paraphrase.
    pronunciation = req.get('pronunciation', [])
    if not isinstance(pronunciation, list):
        raise ValueError('pronunciation 必须为数组，无替换可省略或写 []')
    effective_locks = list(locks)
    seen_original = set()
    for entry in pronunciation:
        original, spoken = entry.get('original', ''), entry.get('spoken', '')
        if not original or original not in source or original not in locks or original in seen_original:
            errors.append('发音映射原台词缺少来源、逐字锁或重复')
        seen_original.add(original)
        if req.get('pronunciation_policy', 'homophone_allowed') == 'exact_only':
            errors.append('当前任务锁定字形，不允许同音替换')
        pairs = entry.get('replacements', [])
        built = list(original)
        used = set()
        if not pairs or not entry.get('reason', '').strip():
            errors.append('发音映射缺少替换明细或语境理由')
        for pair in pairs:
            idx, old, new = pair.get('index'), pair.get('from', ''), pair.get('to', '')
            if (type(idx) is not int or idx < 0 or idx >= len(original) or idx in used
                    or len(old) != 1 or len(new) != 1 or original[idx] != old or old == new
                    or not re.fullmatch(r'[\u3400-\u9fff]', old) or not re.fullmatch(r'[\u3400-\u9fff]', new)):
                errors.append('发音替换必须是有准确位置的单个汉字，不能改标点或漏记改字')
                continue
            used.add(idx)
            reading = pair.get('source_pinyin', '')
            if not re.fullmatch(r'[a-zv]+[1-5]', reading) or pair.get('target_pinyin') != reading:
                errors.append('发音替换的原字语境读音与替换字读音必须同音同调')
            built[idx] = new
        if ''.join(built) != spoken or spoken == original:
            errors.append('发音文本包含未记录改写，或没有实际替换')
        # Keep original locks in the immutable requirements; checker receives only the approved mapped form.
        effective_locks = [spoken if x == original else x for x in effective_locks]
    if req.get('pronunciation_policy', 'homophone_allowed') not in ['homophone_allowed', 'exact_only']:
        errors.append('未知 pronunciation_policy')
    if not isinstance(req.get('complex'), bool) or not req.get('complexity_reason', '').strip():
        raise ValueError('必须判定 complex 并写 complexity_reason，不能默认省略独立复核')
    requirements = req['requirements']
    if not isinstance(requirements, list) or not requirements:
        raise ValueError('必须先从原请求建立 requirements')
    ids = [x['id'] for x in requirements]
    if len(set(ids)) != len(ids):
        raise ValueError('需求编号重复')
    for r in requirements:
        if not r.get('source', '').strip() or r['source'] not in source or not r.get('text', '').strip():
            errors.append(f"需求 {r['id']} 缺少可定位的原文依据")

    cmd = [sys.executable, str(Path(__file__).with_name('check_prompt.py')), '--prompt', args.prompt, '--task', req['task']]
    if labels:
        cmd += ['--labels', ','.join(labels)]
    if req.get('total') is not None:
        cmd += ['--total', str(req['total'])]
    if req.get('untimed'):
        cmd += ['--untimed']
    if req.get('format'):
        cmd += ['--format', req['format']]
    for lock in effective_locks:
        cmd += ['--lock', lock]
    neg_exc = req.get('negative_exception', [])
    if not isinstance(neg_exc, list) or not all(isinstance(x, dict) and x.get('sentence', '').strip() and x.get('reason', '').strip() for x in neg_exc):
        raise ValueError('negative_exception 必须是 [{"sentence": "结尾里的那句否定", "reason": "防什么、为什么没有正向写法"}] 数组，无例外写 [] 或省略')
    sentences = [x['sentence'].strip().rstrip('。；;') for x in neg_exc]
    if len(set(sentences)) != len(sentences):
        errors.append('negative_exception 有重复句子；每条例外必须对应一条不同的独立否定条款')
    for x in neg_exc:
        if len(x['reason'].strip()) < 8 or x['reason'].strip() in ['质量需要', '需要', '必要']:
            errors.append('negative_exception 的 reason 不能是“质量需要”这类空话，要写防什么、为什么没有等价正向写法（脚本只能查长度与空话，必要性仍由专业审查判断）')
    if neg_exc:
        cmd += ['--negative-exception', '；'.join(dict.fromkeys(sentences))]
    if args.baseline:
        cmd += ['--baseline', args.baseline]
    if args.partial:
        cmd += ['--partial']
    if req.get('unchanged'):
        cmd += ['--unchanged', ','.join(str(x) for x in req['unchanged'])]
    # Import only the deterministic synthesis helper to bind review quotes to the same full text.
    sys.dont_write_bytecode = True
    import check_prompt
    if args.partial:
        synth_errors = []
        full = '\n'.join(check_prompt.synthesize(parent.splitlines(), raw.splitlines(), synth_errors, req.get('unchanged', [])))
        errors.extend(synth_errors)
    else:
        full = '\n'.join(raw.splitlines())
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        mechanical = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise ValueError('检查器没有返回 JSON：' + p.stderr[:200])
    if p.returncode != 0 or not mechanical.get('ok'):
        errors.extend(mechanical.get('errors', ['机械检查未完成']))
    prompt_hash, req_hash = digest(full), digest(req_text)
    if mechanical.get('checked_sha256') != prompt_hash:
        errors.append('机械检查正文与语义审查正文不一致')
    # 素材集合按 check_prompt 的归一键比对：需求里写 图片1 还是 图1 都对得上（键一律是 图N / 视频N / 音频N）
    if set(mechanical.get('stats', {}).get('labels_used', [])) != {check_prompt.norm_label(x) for x in labels}:
        errors.append('实际素材集合与需求不一致（含明确无素材的情况）')
    if rev.get('prompt_sha256') != prompt_hash or rev.get('requirements_sha256') != req_hash:
        errors.append('审查记录对应的正文或需求版本已过期')
    if rev.get('baseline_sha256') != (digest(parent) if args.baseline else None):
        errors.append('审查记录的父稿版本不一致')
    if not rev.get('author', '').strip() or not rev.get('reviewer', '').strip():
        errors.append('缺少作者与审查者标识；标识须与实际执行记录相符')

    def rows_by_id(rows, expected, label):
        got = [x.get('id') for x in rows]
        if len(got) != len(set(got)) or set(got) != set(expected):
            errors.append(label + ' 有漏项、重复或额外编号')
        return rows

    def evidence(row, allow_na=False):
        status = row.get('status')
        if status == 'na' and allow_na:
            if not row.get('reason', '').strip() or not row.get('source', '').strip() or row['source'] not in source:
                errors.append(f"{row.get('id')} 不适用缺少原请求/父稿依据")
        elif status == 'pass':
            if not row.get('quote', '').strip() or row['quote'] not in full or not row.get('reason', '').strip():
                errors.append(f"{row.get('id')} 通过缺少最终正文原句或判断依据")
        else:
            errors.append(f"{row.get('id')} 尚未通过：{status}")

    for row in rows_by_id(rev.get('coverage', []), ids, '需求覆盖'):
        evidence(row)
    for row in rows_by_id(rev.get('checks', []), DOMAINS, '六个专业检查域'):
        evidence(row, allow_na=True)
    # Per-shot evidence makes the standing camera preference explicit on every delivery.
    heads = check_prompt.parse_heads(full.splitlines())
    blocks = check_prompt.shot_blocks(full.splitlines(), heads)
    shot_texts = ['\n'.join(body) for _head, body, _tail in blocks] or [full]
    camera_rows = rows_by_id(rev.get('camera', []), list(range(1, len(shot_texts) + 1)), '逐镜摄影')
    for row in camera_rows:
        idx = row.get('id')
        if type(idx) is not int or not 1 <= idx <= len(shot_texts):
            errors.append('摄影编号必须是完整稿的顺序序号，从1开始')
            continue
        body = shot_texts[idx - 1]
        quote, mode = row.get('quote', ''), row.get('mode')
        if not quote.strip() or quote not in body or not row.get('reason', '').strip():
            errors.append(f'摄影 {idx} 缺少本镜原句或实际判断')
        if mode == 'moving':
            effect = row.get('effect_quote', '')
            if not effect.strip() or effect not in body:
                errors.append(f'摄影 {idx} 缺少本镜可见幅度或画面变化原句')
        elif mode in ['fixed', 'preserved']:
            authority = row.get('source', '')
            if not authority.strip() or authority not in source:
                errors.append(f'摄影 {idx} 固定或继承缺少用户要求/父稿依据')
            if mode == 'preserved' and not args.baseline and req['task'] != '编辑':
                errors.append(f'摄影 {idx} 继承模式仅用于实际父稿修订或保持源视频摄影的编辑')
        elif mode == 'fixed_by_design':
            errors.append(f'摄影 {idx} 不允许作者自行固定（fixed_by_design 已撤销）；认为固定更合适时先向用户提出，用户确认后用 fixed 并在 source 引用用户确认的原话')
        else:
            errors.append(f'摄影 {idx} 模式必须为 moving/fixed/preserved')
    if pronunciation:
        speech = rev.get('pronunciation_review', {})
        if (speech.get('status') != 'pass' or speech.get('entries_checked') != len(pronunciation)
                or not speech.get('reason', '').strip() or speech.get('unresolved') != []):
            errors.append('同音替换缺少实际语境、读音、说话人及非发音字段核对')
        for entry in pronunciation:
            if entry.get('spoken', '') not in full:
                errors.append('最终稿没有本版发音文本')
    assets = req.get('assets', [])
    if {x.get('label') for x in assets} != set(labels) or len(assets) != len(labels):
        errors.append('每份实际素材必须有读取记录及职责，无素材时 assets=[]')
    for asset in assets:
        if asset.get('status') != 'read' or not asset.get('evidence', '').strip() or not asset.get('role', '').strip():
            errors.append(f"素材 {asset.get('label')} 未完成读取/职责核对")

    warnings = mechanical.get('warnings', [])
    decisions = rev.get('warnings', [])
    if sorted(x.get('message', '') for x in decisions) != sorted(warnings):
        errors.append('当前机械警告没有逐条裁定，或裁定属于旧版本')
    for row in decisions:
        if row.get('decision') not in ['false_positive', 'accepted_constraint'] or not row.get('reason', '').strip():
            errors.append('警告仍未解决；修复后重新运行，不能只标已修复')
        quote = row.get('quote', '')
        if not quote.strip() or (quote not in full and quote not in source):
            errors.append('警告裁定缺少最终正文或原请求依据')
    if rev.get('unresolved') != []:
        errors.append('unresolved 必须明确为 []，有未解决问题不能放行')
    independent = None
    if args.independent_review:
        independent = read_json(args.independent_review)
    if req['complex'] and independent is None:
        errors.append('复杂任务缺少独立复核；保留候选，不能宣称已验收')
    if independent is not None:
        if (independent.get('prompt_sha256') != prompt_hash or independent.get('requirements_sha256') != req_hash
                or independent.get('status') != 'pass' or independent.get('unresolved') != []
                or not independent.get('reviewer', '').strip() or independent['reviewer'] == rev.get('author')
                or not independent.get('reason', '').strip()
                or not independent.get('quote', '').strip() or independent['quote'] not in full):
            errors.append('独立复核缺少本版依据、未通过或审查者与作者相同')
        # 复核必须来自作者之外的新上下文：记录是哪个子代理 / 会话，且它没有读过作者的审查结论。
        ctx = independent.get('context', {})
        if (not isinstance(ctx, dict) or ctx.get('kind') not in ['subagent', 'new_session', 'other_person']
                or not ctx.get('id', '').strip() or ctx.get('saw_author_review') is not False):
            errors.append('独立复核必须记录 context：{kind: subagent|new_session|other_person, id: 可定位的会话或代理标识, saw_author_review: false}；同一上下文换名不算独立')
    exported = False
    output_text = '\n'.join(raw.splitlines()) if args.output_scope == 'affected' else full
    if not errors and args.output:
        target = Path(args.output)
        if target.exists() and target.read_text(encoding='utf-8') != output_text:
            errors.append('导出路径已有不同正文；请使用本次运行的新路径，防止覆盖版本')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(output_text, encoding='utf-8')
            exported = True
    summary_line = ('交付校验通过' if not errors else '交付未放行') + f'（正文 {prompt_hash[:8]}｜需求 {req_hash[:8]}）'
    response_written = False
    if exported and args.response:
        rp = Path(args.response)
        if rp.exists() and rp.read_text(encoding='utf-8') != '':
            errors.append('response 路径已有内容；请使用本次运行的新路径')
        else:
            rp.parent.mkdir(parents=True, exist_ok=True)
            block = '```text\n' + output_text.rstrip('\n') + '\n```\n'
            rp.write_text(block + ('' if args.response_mode == 'prompt-only' else summary_line + '\n'), encoding='utf-8')
            response_written = True
    return {'ready': not errors, 'mechanical': mechanical, 'quality_evidence': 'complete' if not errors else 'incomplete',
            'response_written': response_written,
            'errors': list(dict.fromkeys(errors)), 'checked_sha256': prompt_hash, 'requirements_sha256': req_hash,
            'output_written': exported, 'output_scope': args.output_scope, 'delivered_sha256': digest(output_text) if exported else None, 'summary': ('交付校验通过' if not errors else '交付未放行') + f'（正文 {prompt_hash[:8]}｜需求 {req_hash[:8]}）',
            'limits': '核对实际运行、证据完整性和版本绑定；语义判断仍由真实审查负责，不证明成片效果或作者身份。'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['prompt', 'requirements', 'review']:
        ap.add_argument('--' + name, required=True)
    for name in ['baseline', 'independent-review', 'report', 'output', 'response']:
        ap.add_argument('--' + name)
    ap.add_argument('--partial', action='store_true')
    ap.add_argument('--output-scope', choices=['complete', 'affected'], default='complete', help='局部修订可仅导出已在完整父稿中验收的受影响镜头')
    ap.add_argument('--response-mode', choices=['with-receipt', 'prompt-only'], default='with-receipt', help='用户只要提示词时用 prompt-only：成品不带交付行，钩子仍按正文哈希核对')
    args = ap.parse_args()
    try:
        result = evaluate(args)
        code = 0 if result['ready'] else 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        result = {'ready': False, 'errors': [str(e)], 'output_written': False, 'summary': '交付未放行（输入或记录无效）'}
        code = 2
    # 本轮绑定：放行钩子用 created_at 判断报告是不是在本轮用户消息之后生成的，用 session_id 判断是不是同一个会话。
    result['created_at'] = time.time()
    result['session_id'] = os.environ.get('AIGC_SESSION_ID') or None
    data = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(data + '\n', encoding='utf-8')
    print(data)
    sys.exit(code)


if __name__ == '__main__':
    main()
