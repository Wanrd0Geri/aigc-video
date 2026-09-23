"""Deterministic tests only; synthetic review records do NOT establish semantic quality."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
BASE = (ROOT/'tests/check_cases/control_valid.txt').read_text().replace('衣摆轻晃。', '衣摆轻晃。摄影机向右缓移，门框向左错开。').replace('轻纱缓缓飘动。', '轻纱缓缓飘动。摄影机缓推，人脸逐渐放大。')


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


AUTO = object()   # gate() 默认按当前审查记录自动补一份绑定本版哈希的独立复核；传 None 表示不给


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.prompt = self.d/'prompt.txt'; self.prompt.write_text(BASE)

    def tearDown(self):
        self.tmp.cleanup()

    def checker(self, text=BASE, args=()):
        self.prompt.write_text(text)
        p = subprocess.run([sys.executable, str(ROOT/'scripts/check_prompt.py'), '--prompt', str(self.prompt), *args], capture_output=True, text=True)
        return p.returncode, json.loads(p.stdout)

    def setup_gate(self, text=BASE, check_args=()):
        self.prompt.write_text(text)
        # 全套路径恒为 complex=true（由严格审 / 审核节点触发，要求独立复核）
        self.req = {'request':'12秒两镜行走，没有参考素材。', 'task':'生成', 'labels':[], 'assets':[], 'total':12,
                    'exact_locks':[], 'requirements':[{'id':'R1','source':'两镜行走','text':'两个镜头行走'}],
                    'complex':True,'complexity_reason':'用户要求严格审；单人行走，供机械测试的固定样本'}
        self.req_path = self.d/'requirements.json'
        self.req_path.write_text(json.dumps(self.req, ensure_ascii=False))
        code, check = self.checker(text, ['--total','12', *check_args])
        quote = '人物从门口走到窗前，衣摆轻晃。'
        self.review = {'author':'unit-author','reviewer':'unit-author','prompt_sha256':check['checked_sha256'],
                       'requirements_sha256':sha(self.req_path.read_text()), 'baseline_sha256':None,
                       'coverage':[{'id':'R1','status':'pass','quote':quote,'reason':'仅为验证引用绑定的合成测试记录'}],
                       'checks':[{'id':k,'status':'pass','quote':quote,'reason':'仅测试字段完整性，不是审美判断'} for k in ['intent_assets','composition_camera','action_performance','timing_continuity','materials_light_vfx','sound_delivery']],
                       'camera':[{'id':1,'mode':'moving','quote':'摄影机向右缓移','effect_quote':'门框向左错开','reason':'本测试正文中的摄影与视差'}, {'id':2,'mode':'moving','quote':'摄影机缓推','effect_quote':'人脸逐渐放大','reason':'本测试正文中的摄影与尺度变化'}],
                       'warnings':[{'message':w,'decision':'false_positive','quote':'没有参考素材','reason':'该单元样本明确无素材，集合为空'} for w in check['warnings']], 'unresolved':[]}

    def auto_independent(self):
        """绑定当前审查记录哈希的独立复核（新上下文、没看过作者结论）；只为机械测试，不代表真实复核。"""
        return {'prompt_sha256':self.review['prompt_sha256'],'requirements_sha256':self.review['requirements_sha256'],
                'reviewer':'unit-independent-reviewer','status':'pass','unresolved':[],
                'quote':'人物从门口走到窗前，衣摆轻晃。','reason':'单元测试：独立复核绑定本版正文与需求',
                'context':{'kind':'subagent','id':'unit-subagent-auto','saw_author_review':False}}

    def gate(self, independent=AUTO, extra=()):
        self.req_path.write_text(json.dumps(self.req,ensure_ascii=False))
        if independent is AUTO:
            independent = self.auto_independent()
        path = self.d/'review.json'; path.write_text(json.dumps(self.review,ensure_ascii=False))
        cmd=[sys.executable,str(ROOT/'scripts/verify_delivery.py'),'--prompt',str(self.prompt),'--requirements',str(self.req_path),'--review',str(path),'--output',str(self.d/'delivered.txt')]
        if independent is not None:
            f=self.d/'independent.json';f.write_text(json.dumps(independent,ensure_ascii=False));cmd+=['--independent-review',str(f)]
        cmd += list(extra)
        p=subprocess.run(cmd,capture_output=True,text=True)
        return p.returncode,json.loads(p.stdout)

    def test_multiple_partial_middle_tail_rejected(self):
        parent=self.d/'parent.txt';parent.write_text(BASE)
        for tail in ['结尾：\nvoice.m4a\n','全片不添加BGM，不添加字幕。\n']:
            body='镜头1（0-6秒）：人物走到窗前。\n'+tail+'镜头2（6-12秒）：人物停下，轻纱飘动。\n'
            self.assertEqual(self.checker(body,['--baseline',str(parent),'--partial','--total','12'])[0],1)

    def test_new_generation_lock_pass_and_fail(self):
        text=BASE.replace('并抬手','并抬手说：“I am ready.”')
        self.assertEqual(self.checker(text,['--lock','I am ready.','--total','12'])[0],0)
        self.assertEqual(self.checker(text.replace('I am ready.','Iamready.'),['--lock','I am ready.','--total','12'])[0],1)

    def test_old_shell_locked_five_negatives(self):
        # 五段旧壳：结尾段仍走 4 条否定预算，用户逐字锁的否定不占预算
        text=(ROOT/'tests/check_cases/five_section_five_negatives.txt').read_text()
        lock='\n'.join(text.splitlines()[-5:]).strip()
        self.assertEqual(self.checker(text,['--format','五段','--lock',lock,'--total','12'])[0],0)
        self.assertEqual(self.checker(text,['--format','五段','--total','12'])[0],1)

    def test_four_section_tail_must_hold_only_closing(self):
        # 四段新壳（v13.1）：末尾只留固定句，末尾的否定句即便被 --lock 锁住也拦
        tail=BASE.replace('全片不添加BGM，不添加字幕。','不出现第二个人。\n全片不添加BGM，不添加字幕。')
        code,d=self.checker(tail,['--lock','不出现第二个人。','--total','12'])
        self.assertEqual(code,1); self.assertTrue(any('末尾只留固定句' in e for e in d['errors']))
        # 同一句写进镜内：通过，只留一条提醒
        inline=BASE.replace('门框向左错开。','门框向左错开。不出现第二个人。')
        code,d=self.checker(inline,['--total','12'])
        self.assertEqual(code,0,d['errors'])
        self.assertEqual(len([w for w in d['warnings'] if w.startswith('否定句：')]),1)

    def test_empty_shot_and_section_rejected(self):
        for text in [BASE.replace('一位穿灰衣的成年人。',''), BASE.replace('人物从门口走到窗前，衣摆轻晃。摄影机向右缓移，门框向左错开。','')]:
            self.assertEqual(self.checker(text,['--total','12'])[0],1)

    def test_summary_never_calls_missing_label_matched(self):
        code,d=self.checker(BASE,['--labels','图片1','--total','12'])
        self.assertEqual(code,1); self.assertIn('素材 图片1 不匹配',d['summary'])
        self.assertNotIn('素材 图片1 匹配',d['summary'])

    def test_inherit_requires_baseline(self):
        self.assertEqual(self.checker(BASE,['--format','继承'])[0],2)

    def test_gate_ready_exports_checked_body(self):
        self.setup_gate();code,d=self.gate()
        self.assertEqual(code,0,d);self.assertTrue(d['ready'])
        self.assertEqual((self.d/'delivered.txt').read_text(),'\n'.join(BASE.splitlines()))

    def test_report_records_round_binding_fields(self):
        """报告必须带 created_at 与 session_id：Stop 钩子靠它们判断这份放行是不是本轮、本会话的。"""
        self.setup_gate()
        report = self.d/'report.json'
        import os as _os
        before = _os.environ.get('AIGC_SESSION_ID')
        _os.environ['AIGC_SESSION_ID'] = 'unit-session'
        try:
            code, d = self.gate(extra=['--report', str(report)])
        finally:
            if before is None:
                _os.environ.pop('AIGC_SESSION_ID', None)
            else:
                _os.environ['AIGC_SESSION_ID'] = before
        self.assertEqual(code, 0, d)
        saved = json.loads(report.read_text())
        for key in ('created_at', 'session_id'):
            self.assertIn(key, d); self.assertIn(key, saved)
        self.assertIsInstance(saved['created_at'], float)
        self.assertEqual(saved['session_id'], 'unit-session')

    def test_gate_missing_domain_blocks_export(self):
        self.setup_gate();self.review['checks'].pop()
        code,d=self.gate();self.assertEqual(code,1,d);self.assertFalse((self.d/'delivered.txt').exists())

    def test_gate_missing_warning_blocks(self):
        self.setup_gate();self.review['warnings']=[]
        self.assertEqual(self.gate()[0],1)

    def test_gate_old_prompt_hash_blocks(self):
        self.setup_gate();self.prompt.write_text(BASE.replace('抬手','抬起右手'))
        self.assertEqual(self.gate()[0],1)

    def test_gate_old_requirements_hash_blocks(self):
        self.setup_gate();self.req['request']+='另一个版本。'
        self.assertEqual(self.gate()[0],1)

    def test_gate_missing_coverage_blocks(self):
        self.setup_gate();self.review['coverage']=[]
        self.assertEqual(self.gate()[0],1)

    def test_gate_unresolved_or_failed_review_blocks(self):
        for mutate in ['unresolved','fail']:
            self.setup_gate()
            if mutate=='unresolved':self.review['unresolved']=['镜头关系未定']
            else:self.review['checks'][1]['status']='fail'
            self.assertEqual(self.gate()[0],1)

    def test_gate_invented_evidence_blocks(self):
        self.setup_gate();self.review['checks'][1]['quote']='最终稿没有写的内容'
        self.assertEqual(self.gate()[0],1)

    def test_gate_na_needs_actual_source(self):
        self.setup_gate();self.review['checks'][1]={'id':'composition_camera','status':'na','source':'因为想省时间','reason':'不检查'}
        self.assertEqual(self.gate()[0],1)

    def test_gate_complex_requires_separate_record_binding(self):
        self.setup_gate();self.req['complex']=True
        self.req_path.write_text(json.dumps(self.req,ensure_ascii=False));self.review['requirements_sha256']=sha(self.req_path.read_text())
        self.assertEqual(self.gate(None)[0],1)  # 全套路径不给独立复核：不放行
        independent={'prompt_sha256':self.review['prompt_sha256'],'requirements_sha256':self.review['requirements_sha256'],
                     'reviewer':'unit-author','status':'pass','unresolved':[],'quote':self.review['coverage'][0]['quote'],'reason':'单元测试绑定'}
        self.assertEqual(self.gate(independent)[0],1)
        independent['reviewer']='unit-other-reviewer'
        self.assertEqual(self.gate(independent)[0],1)  # 没有 context：同一上下文换名不算独立
        independent['context']={'kind':'subagent','id':'unit-subagent-1','saw_author_review':True}
        self.assertEqual(self.gate(independent)[0],1)  # 看过作者结论也不算独立
        independent['context']={'kind':'subagent','id':'unit-subagent-1','saw_author_review':False}
        self.assertEqual(self.gate(independent)[0],0)
        # 核验修复那一轮的可选建议：suggestions 不进 unresolved，脚本不认识这个字段也不该拦
        independent['suggestions']=[{'point':'镜1 第二句','suggestion':'可以再给一个落点','reason':'可读性'}]
        self.assertEqual(self.gate(independent)[0],0)

    def test_camera_fixed_by_design_is_rejected(self):
        self.setup_gate(BASE.replace('摄影机向右缓移，门框向左错开。','摄影机固定在门框正前方。'))
        self.review['camera'][0]={'id':1,'mode':'fixed_by_design','quote':'摄影机固定在门框正前方','reason':'单元测试：对白近景口型同步，固定更稳','notice':'待你定：镜 1 我按专业理由固定了'}
        code,res=self.gate(); self.assertEqual(code,1); self.assertTrue(any('已撤销' in e for e in res['errors']))

    def test_negative_exception_duplicates_and_fragments_rejected(self):
        text=BASE.replace('门框向左错开。','门框向左错开。不出现水印。不出现现代物品。不出现重复人物。不出现多余道具。不出现反光。')
        for sentences in (['不出现水印。','不出现水印。'],['水','印']):
            self.setup_gate(text)
            self.req['negative_exception']=[{'sentence':s,'reason':'单元测试：该句防具体对象，无等价正向写法'} for s in sentences]
            self.refresh_requirement_hash()
            code,c=self.checker(text,['--total','12','--negative-exception','；'.join(sentences)])
            self.review['warnings']=[{'message':w,'decision':'accepted_constraint','quote':'没有参考素材','reason':'单元测试记录'} for w in c['warnings']]
            self.assertEqual(self.gate()[0],1)
        self.setup_gate(text)
        self.req['negative_exception']=[{'sentence':'不出现水印。','reason':'防平台水印，无正向写法'},{'sentence':'不出现反光。','reason':'防桌面镜面反光抢主体，无正向写法'}]
        self.refresh_requirement_hash()
        code,c=self.checker(text,['--total','12','--negative-exception','不出现水印。；不出现反光。'])
        self.review['warnings']=[{'message':w,'decision':'accepted_constraint','quote':'没有参考素材','reason':'单元测试记录'} for w in c['warnings']]
        self.assertEqual(self.gate()[0],0)

    def test_response_prompt_only_mode(self):
        self.setup_gate()
        code,res=self.gate(extra=['--response',str(self.d/'r.md'),'--response-mode','prompt-only'])
        self.assertEqual(code,0); body=(self.d/'r.md').read_text()
        self.assertTrue(body.startswith('```text\n') and '交付校验通过' not in body)

    def test_negative_exception_must_be_sentence_list(self):
        self.setup_gate()
        self.req['negative_exception']='质量需要'
        self.assertEqual(self.gate()[0],2)
        self.req['negative_exception']=[{'sentence':'不出现第二个人。','reason':'质量需要'}]
        self.refresh_requirement_hash(); code,res=self.gate(); self.assertEqual(code,1); self.assertTrue(any('空话' in e for e in res['errors']))

    def test_response_file_is_written_on_ready(self):
        self.setup_gate()
        code,res=self.gate(extra=['--response',str(self.d/'response.md')])
        self.assertEqual(code,0); self.assertTrue(res['response_written'])
        body=(self.d/'response.md').read_text()
        self.assertTrue(body.startswith('```text\n') and '交付校验通过（正文 ' in body)

    def test_gate_missing_asset_blocks(self):
        self.setup_gate();self.req['labels']=['图片1'];self.req['assets']=[{'label':'图片1','status':'missing','role':'人物','evidence':'未附图'}]
        self.req_path.write_text(json.dumps(self.req,ensure_ascii=False));self.review['requirements_sha256']=sha(self.req_path.read_text())
        self.assertEqual(self.gate()[0],1)

    def test_gate_lock_must_have_source(self):
        self.setup_gate();self.req['exact_locks']=['一位穿灰衣的成年人。']
        self.req_path.write_text(json.dumps(self.req,ensure_ascii=False));self.review['requirements_sha256']=sha(self.req_path.read_text())
        self.assertEqual(self.gate()[0],1)

    def test_gate_refuses_overwriting_another_version(self):
        self.setup_gate();target=self.d/'delivered.txt';target.write_text('old version')
        self.assertEqual(self.gate()[0],1);self.assertEqual(target.read_text(),'old version')


    def test_partial_export_checks_full_but_delivers_affected(self):
        self.setup_gate()
        parent=self.d/'parent.txt';parent.write_text(BASE)
        self.review['baseline_sha256']=sha(BASE)
        partial=(ROOT/'tests/check_cases/partial_shot2.txt').read_text().replace('轻纱缓缓飘动。','轻纱缓缓飘动。摄影机缓推，人脸逐渐放大。')
        self.prompt.write_text(partial)
        # Bind synthetic evidence to the actual reconstructed draft.
        code,c=self.checker(partial,['--baseline',str(parent),'--partial','--total','12'])
        self.review['prompt_sha256']=c['checked_sha256']
        self.review['warnings']=[{'message':w,'decision':'false_positive','quote':'没有参考素材','reason':'测试明确无素材'} for w in c['warnings']]
        code,d=self.gate(extra=['--baseline',str(parent),'--partial','--output-scope','affected'])
        self.assertEqual(code,0,d)
        delivered=(self.d/'delivered.txt').read_text()
        self.assertEqual(delivered,'\n'.join(partial.splitlines()))
        self.assertEqual(d['delivered_sha256'],sha(delivered))
        self.assertNotEqual(d['checked_sha256'],d['delivered_sha256'])

    def test_affected_without_partial_rejected(self):
        self.setup_gate();self.assertEqual(self.gate(extra=['--output-scope','affected'])[0],2)

    def refresh_requirement_hash(self):
        self.req_path.write_text(json.dumps(self.req,ensure_ascii=False))
        self.review['requirements_sha256']=sha(self.req_path.read_text())

    def setup_speech(self):
        text=BASE.replace('人物停下并抬手', '人物说：“银杭开门了。”后停下并抬手')
        self.setup_gate(text)
        self.req['request']+='台词“银行开门了。”允许银行的行按hang2作同音替换。'
        self.req['exact_locks']=['银行开门了。']
        self.req['pronunciation']=[{'original':'银行开门了。','spoken':'银杭开门了。','reason':'银行的行和杭均读hang2',
            'replacements':[{'index':1,'from':'行','to':'杭','source_pinyin':'hang2','target_pinyin':'hang2'}]}]
        self.review['pronunciation_review']={'status':'pass','entries_checked':1,'reason':'本测试记录原字与替代字同音同调，其他字符保持','unresolved':[]}
        self.refresh_requirement_hash()

    def test_camera_missing_record_blocks(self):
        self.setup_gate();self.review.pop('camera');self.assertEqual(self.gate()[0],1)

    def test_camera_missing_shot_blocks(self):
        self.setup_gate();self.review['camera'].pop();self.assertEqual(self.gate()[0],1)

    def test_camera_effect_from_other_shot_blocks(self):
        self.setup_gate();self.review['camera'][0]['effect_quote']='人脸逐渐放大';self.assertEqual(self.gate()[0],1)

    def test_camera_fixed_without_source_blocks(self):
        self.setup_gate();self.review['camera'][0]['mode']='fixed';self.assertEqual(self.gate()[0],1)

    def test_camera_preserved_invalid_new_generation_blocks(self):
        self.setup_gate();self.review['camera'][0].update(mode='preserved',source='两镜行走');self.assertEqual(self.gate()[0],1)

    def test_camera_explicit_fixed_can_export(self):
        self.setup_gate(BASE.replace('摄影机向右缓移，门框向左错开。','摄影机全程固定。'))
        self.req['request']+='镜头1摄影机全程固定。';self.refresh_requirement_hash()
        self.review['camera'][0]={'id':1,'mode':'fixed','quote':'摄影机全程固定。','source':'镜头1摄影机全程固定。','reason':'用户明确锁定本镜固定'}
        self.assertEqual(self.gate()[0],0)

    def test_homophone_exports_spoken_and_keeps_source_lock(self):
        self.setup_speech();code,data=self.gate();self.assertEqual(code,0,data)
        self.assertIn('银杭开门了。',(self.d/'delivered.txt').read_text())
        self.assertEqual(json.loads(self.req_path.read_text())['exact_locks'],['银行开门了。'])

    def test_homophone_wrong_tone_blocks(self):
        self.setup_speech();self.req['pronunciation'][0]['replacements'][0]['target_pinyin']='hang4';self.refresh_requirement_hash();self.assertEqual(self.gate()[0],1)

    def test_homophone_unrecorded_paraphrase_blocks(self):
        self.setup_speech();self.req['pronunciation'][0]['spoken']='银杭已经开门了。';self.refresh_requirement_hash();self.assertEqual(self.gate()[0],1)

    def test_homophone_punctuation_rewrite_blocks(self):
        self.setup_speech();e=self.req['pronunciation'][0];e['spoken']='银杭开门了！';e['replacements'].append({'index':5,'from':'。','to':'！','source_pinyin':'a1','target_pinyin':'a1'});self.refresh_requirement_hash();self.assertEqual(self.gate()[0],1)

    def test_homophone_explicit_exact_only_blocks(self):
        self.setup_speech();self.req['pronunciation_policy']='exact_only';self.refresh_requirement_hash();self.assertEqual(self.gate()[0],1)

    def test_homophone_missing_semantic_review_blocks(self):
        self.setup_speech();self.review.pop('pronunciation_review');self.assertEqual(self.gate()[0],1)

    def test_homophone_wrong_index_blocks(self):
        self.setup_speech();self.req['pronunciation'][0]['replacements'][0]['index']=2;self.refresh_requirement_hash();self.assertEqual(self.gate()[0],1)

    def test_homophone_does_not_rewrite_other_field_lock(self):
        self.setup_speech()
        self.req['request']+='画面牌子保留文字“银行开门了。”。'
        self.req['exact_locks'].append('牌子写着“银行开门了。”')
        self.req['request']+='牌子写着“银行开门了。”'
        body=self.prompt.read_text().replace('场景：', '场景：牌子写着“银杭开门了。”')
        self.prompt.write_text(body)
        self.review['prompt_sha256']=sha('\n'.join(body.splitlines()))
        self.refresh_requirement_hash()
        code,result=self.gate()
        self.assertEqual(code,1,result)
        self.assertTrue(any('锁定文字' in error for error in result['errors']))

    # ---- v25 D6：全套路径 complex 恒为 true，缺省或 false 报错不放行 ----
    def test_d6_complex_false_or_missing_blocks(self):
        for mutate in ('false', 'missing'):
            self.setup_gate()
            if mutate == 'false':
                self.req['complex'] = False
            else:
                self.req.pop('complex')
            self.refresh_requirement_hash()
            code, res = self.gate()
            self.assertEqual(code, 1, res)
            self.assertTrue(any('全套路径 complex 必须为 true（需独立复核）' in e for e in res['errors']), res['errors'])
            self.assertFalse((self.d/'delivered.txt').exists())

    def test_d6_complexity_reason_still_required(self):
        self.setup_gate(); self.req['complexity_reason'] = ''
        self.refresh_requirement_hash()
        self.assertEqual(self.gate()[0], 2)

    # ---- v25 D5：requirements.asks 转给 check_prompt --asks ----
    def write_asks(self, name, rows):
        f = self.d/name
        f.write_text('\n'.join(rows) + '\n', encoding='utf-8')
        return f

    def test_d5_asks_forwarded_blocks_missing_landing(self):
        self.setup_gate()
        self.write_asks('asks.txt', ['R1 | 03:12 | 两镜行走 | 走到窗前 | 有效',
                                     'R2 | 03:20 | 窗外要有一只猫 | 猫 | 有效'])
        self.req['asks'] = 'asks.txt'   # 相对路径：当前目录找不到时按 requirements.json 所在目录找
        self.refresh_requirement_hash()
        code, res = self.gate()
        self.assertEqual(code, 1, res)
        self.assertTrue(any('要求 R2' in e and '没有落点' in e for e in res['errors']), res['errors'])
        self.assertEqual(res['mechanical'].get('asks_checked'), 2)

    def test_d5_asks_forwarded_passes_when_landed(self):
        self.setup_gate()
        asks = self.write_asks('asks.txt', ['R1 | 03:12 | 两镜行走 | 走到窗前 | 有效'])
        self.req['asks'] = str(asks)
        self.refresh_requirement_hash()
        code, res = self.gate()
        self.assertEqual(code, 0, res)
        self.assertEqual(res['mechanical'].get('asks_checked'), 1)
        self.assertIn('要求清单 1 条有效全部有落点', res['mechanical']['summary'])

    def test_d5_asks_missing_file_blocks(self):
        self.setup_gate(); self.req['asks'] = 'no-such-asks.txt'
        self.refresh_requirement_hash()
        code, res = self.gate()
        self.assertEqual(code, 1, res)
        self.assertTrue(any('requirements.asks 指定的要求清单找不到' in e for e in res['errors']), res['errors'])

    def test_d5_asks_null_is_single_round(self):
        self.setup_gate(); self.req['asks'] = None
        self.refresh_requirement_hash()
        code, res = self.gate()
        self.assertEqual(code, 0, res)
        self.assertIsNone(res['mechanical'].get('asks_checked'))

    # ---- v25 D8：requirements.format（缺省：有父稿按继承、无父稿按四段）----
    def test_d8_format_defaults_to_four_without_parent(self):
        five = (ROOT/'tests/check_cases/five_section_old.txt').read_text()
        self.setup_gate(five, ['--format', '五段'])
        code, res = self.gate()
        self.assertEqual(code, 1, res)
        self.assertEqual(res['mechanical'].get('effective_format'), '四段')

    def test_d8_format_explicit_old_shell_passes(self):
        five = (ROOT/'tests/check_cases/five_section_old.txt').read_text().replace(
            '衣摆轻晃。', '衣摆轻晃。摄影机向右缓移，门框向左错开。').replace('轻纱缓缓飘动。', '轻纱缓缓飘动。摄影机缓推，人脸逐渐放大。')
        self.setup_gate(five, ['--format', '五段'])
        self.req['format'] = '五段'; self.refresh_requirement_hash()
        code, res = self.gate()
        self.assertEqual(code, 0, res)
        self.assertEqual(res['mechanical'].get('effective_format'), '五段')

    def test_d8_format_inherit_requires_parent(self):
        self.setup_gate(); self.req['format'] = '继承'; self.refresh_requirement_hash()
        self.assertEqual(self.gate()[0], 2)

    def test_d8_format_unknown_value_rejected(self):
        self.setup_gate(); self.req['format'] = '七段'; self.refresh_requirement_hash()
        self.assertEqual(self.gate()[0], 2)

    # ---- v25 D7：四段父稿 + 局部镜头里的镜内否定句：合成时按父稿外壳切，不当成结尾丢掉 ----
    def test_d7_partial_inline_negative_under_four_section_parent(self):
        self.setup_gate()
        parent = self.d/'parent.txt'; parent.write_text(BASE)
        partial = '镜头1（0-6秒）：人物从门口走到窗前，衣摆轻晃。摄影机向右缓移，门框向左错开。\n不出现第二个人。'
        self.prompt.write_text(partial)
        self.req['negative_exception'] = [{'sentence': '不出现第二个人。', 'reason': '单元测试：防群演闯入，镜内没有等价正向写法'}]
        self.refresh_requirement_hash()
        self.review['baseline_sha256'] = sha(BASE)
        code, c = self.checker(partial, ['--baseline', str(parent), '--partial', '--total', '12',
                                         '--negative-exception', '不出现第二个人。'])
        self.assertEqual(code, 0, c['errors'])
        self.review['prompt_sha256'] = c['checked_sha256']
        self.review['warnings'] = [{'message': w, 'decision': 'false_positive', 'quote': '没有参考素材', 'reason': '测试明确无素材'} for w in c['warnings']]
        self.prompt.write_text(partial)
        code, res = self.gate(extra=['--baseline', str(parent), '--partial'])
        self.assertEqual(code, 0, res)
        self.assertFalse(any('局部镜头' in e for e in res['errors']))


if __name__=='__main__':
    unittest.main(verbosity=2)
