"""Public fabricated Auto acceptance contracts; no provider or research fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import unittest
import uuid
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / 'scripts/deploy_smoke')):
    if p not in sys.path:
        sys.path.insert(0, p)
import run_auto_acceptance as auto

SID = '11111111-2222-4333-8444-555555555555'
MODEL = 'gpt-6-astra[1m]'
HASH = 'a' * 64


def events(root):
    return [
        {'type': 'system', 'subtype': 'init', 'session_id': SID,
         'model': MODEL, 'permissionMode': 'auto', 'claude_code_version': '2.1.281'},
        {'type': 'assistant', 'session_id': SID, 'message': {'model': 'gpt-6-astra', 'content': [
            {'type': 'tool_use', 'id': 'tool_digest', 'name': 'Bash', 'input': {'command': auto.digest_command(root)}}]}},
        {'type': 'user', 'session_id': SID, 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 'tool_digest', 'content': f'SHA2-256({root}/CLAUDE.md)= {HASH}\n'}]}},
        {'type': 'assistant', 'session_id': SID, 'message': {'model': 'gpt-6-astra', 'content': [{'type': 'text', 'text': 'Digest completed.'}]}},
        {'type': 'result', 'subtype': 'success', 'session_id': SID, 'is_error': False, 'num_turns': 3, 'permission_denials': []},
    ]


def wire(rows):
    return ('\n'.join(json.dumps(row) for row in rows) + '\n').encode()


def native(bodies=None):
    # Hand-authored public values with the verified 2.1.281 six-event framing.
    # No runtime/test imports of research artifacts or private captured content.
    bodies = bodies if bodies is not None else [
        '[auto-mode] new action being classified: tool=Bash actionChars=1 id=tool_digest',
        '[Stall] classifier_request_started reqId=req_one tool=Bash model=gpt-5.6-sol[1m] stage=xml_s1 promptTokensEst=[REDACTED]',
        '[Stall] classifier_request_finished reqId=req_one tool=Bash stage=xml_s1 outcome=ok durationMs=1',
        'Slow permission decision: 1ms for Bash (mode=auto, behavior=allow)',
        '[Stall] tool_dispatch_start tool=Bash toolUseId=tool_digest permissionDecisionMs=1',
        '[Stall] tool_dispatch_end tool=Bash toolUseId=tool_digest outcome=ok durationMs=1',
    ]
    return ''.join(f'2000-01-01T00:00:00.000Z [{"DEBUG" if body.startswith("[auto-mode]") else "INFO"}] {body}\n' for body in bodies).encode()


# Public fabricated identifiers/paths/endpoints; fixed prose is the supported
# 2.1.281 operational template, not copied session content or a research import.
NOTICE_CONTENT = (
    "We're changing auto mode to no longer charge for classifier requests in Claude Code. "
    "However, this session isn't eligible because your requests go through gateway.example.invalid:4242, "
    "which isn't compatible with this update. Nothing breaks: auto mode keeps working, "
    "and its classifier requests are billed as before. To fix it and access the new version "
    "of auto mode, ask your gateway to implement: https://example.invalid/optional-gateway-feature")
ANCILLARY_NATIVE = [
    ('auxiliary_lock_contention', 'NON-FATAL: Lock acquisition failed for /fabricated/cache/tool.lock '
     '(expected in multi-process scenarios): Lock already held by another process'),
    ('optional_telemetry_file_missing', "$.fs.read (telemetry): /fabricated/telemetry/state.json failed: "
     "ENOENT: no such file or directory, open '/fabricated/telemetry/state.json'"),
    ('metrics_opt_out_check_unavailable', '[Anthropic telemetry] Failed to check metrics opt-out status: '
     'Auth error: no credential usable for the metrics opt-out check'),
]


def informational():
    return {'type':'system','subtype':'informational','content':NOTICE_CONTENT,'isMeta':False,
            'level':'warning','timestamp':'2000-01-01T00:00:00.000Z',
            'uuid':'66666666-7777-4888-8999-000000000000','session_id':SID}


def error_line(body):
    return f'2000-01-01T00:00:00.000Z [ERROR] {body}\n'.encode()


class AutoParserTests(unittest.TestCase):
    def setUp(self):
        self.meta = {k: True for k in ('natural_completion', 'child_reaped', 'capture_drained', 'capture_intact')}
        self.meta.update(exit_code=0, stop_reason=None)

    def judge(self, rows=None, debug=None, meta=None):
        return auto.adjudicate(wire(events(ROOT) if rows is None else rows), native() if debug is None else debug,
                               self.meta if meta is None else meta, auto.ActionLedger(ROOT), MODEL, HASH)[0]

    def test_full_chain_is_only_zero_exit(self):
        report = self.judge()
        self.assertEqual(report['status'], 'CLASSIFIER_ALLOW_PASS', report)
        self.assertEqual(report['classifier_selected_model'], 'gpt-5.6-sol[1m]')
        self.assertIsNone(report['classifier_provider_response_model'])
        self.assertEqual(auto.exit_code(report['status']), 0)
        for status in auto.FAILURES:
            self.assertEqual(auto.exit_code(status), 1)
        for status in ('INCONCLUSIVE', 'ACTION_NOT_REACHED', 'FAST_PATH_ACTION_SUCCESS', 'PREFLIGHT_ONLY', 'CONSENT_NOT_GRANTED'):
            self.assertEqual(auto.exit_code(status), 2)

    def test_known_informational_warning_is_visible_not_eligibility_proof(self):
        rows = events(ROOT)
        notice = informational()
        rows.insert(1,notice)
        report = self.judge(rows)
        self.assertEqual(report['status'],'CLASSIFIER_ALLOW_PASS',report)
        self.assertEqual(report['diagnostics'],[{'source':'structured','severity':'warning',
            'category':'auto_billing_update_ineligible_continues',
            'sha256':hashlib.sha256(NOTICE_CONTENT.encode()).hexdigest()}])
        self.assertNotIn(NOTICE_CONTENT,json.dumps(report))
        self.assertNotIn('gateway.example.invalid',json.dumps(report))
        self.assertNotIn(notice['uuid'],json.dumps(report))
        # These remain inference-transaction checks, never free-billing eligibility.
        self.assertIsNone(report['provider_calls_total'])
        self.assertNotIn('billing_eligible',report)

    def test_three_exact_native_diagnostics_are_ancillary_not_transport(self):
        for category,body in ANCILLARY_NATIVE:
            for debug in (error_line(body)+native(),native()+error_line(body)):
                with self.subTest(category=category):
                    report = self.judge(debug=debug)
                    self.assertEqual(report['status'],'CLASSIFIER_ALLOW_PASS',report)
                    self.assertEqual(report['diagnostics'],[{'source':'native','severity':'ERROR',
                        'category':category,'sha256':hashlib.sha256(body.encode()).hexdigest()}])
                    self.assertNotIn(body,json.dumps(report))
                    self.assertNotIn('/fabricated',json.dumps(report))

    def test_unknown_native_error_is_inconclusive_not_claimed_transport(self):
        for body in ('Synthetic telemetry exporter unavailable',
                     'FATAL: Lock acquisition failed for /fabricated/required.lock: another process',
                     "$.fs.read (action): /fabricated/input failed: ENOENT: no such file or directory, open '/fabricated/input'",
                     '[Anthropic telemetry] classifier backend unavailable',
                     ANCILLARY_NATIVE[0][1]+' toolUseId=tool_digest',
                     ANCILLARY_NATIVE[1][1]+' reqId=req_one',
                     ANCILLARY_NATIVE[2][1]+'; inference authentication failed'):
            with self.subTest(body=body):
                report = self.judge(debug=native()+error_line(body))
                self.assertEqual((report['status'],report['reason']),('INCONCLUSIVE','unknown_native_error'))
                self.assertEqual(auto.exit_code(report['status']),2)
                self.assertNotIn(body,json.dumps(report))
        report = self.judge(debug=native()+error_line('unknown warning').replace(b'[ERROR]',b'[WARN]'))
        self.assertEqual((report['status'],report['reason']),('INCONCLUSIVE','unknown_native_warning'))

    def test_ancillary_never_masks_admission_policy_classifier_or_hook_failure(self):
        warnings = b''.join(error_line(body) for _,body in ANCILLARY_NATIVE)
        for body,status in [('verifyAutoModeGateAccess: canEnterAuto=false','ADMISSION_REJECTED'),
                            ('Auto mode classifier unavailable, denying action','POLICY_DENIED'),
                            ('Auto mode classifier (XML) error: backend unavailable','TRANSPORT_PARSER_FAILURE'),
                            ('inference authentication_error','TRANSPORT_PARSER_FAILURE'),
                            ('inference invalid_api_key','TRANSPORT_PARSER_FAILURE')]:
            report = self.judge(debug=warnings+native()+error_line(body))
            self.assertEqual(report['status'],status,report)
            self.assertNotEqual(auto.exit_code(report['status']),0)
        rows = events(ROOT)
        rows.insert(1,{'type':'system','subtype':'hook_response','outcome':'error','exit_code':1,
                       'content':ANCILLARY_NATIVE[2][1]})
        self.assertEqual(self.judge(rows,warnings+native())['status'],'TRANSPORT_PARSER_FAILURE')

    def test_informational_schema_is_exact_and_duplicates_block(self):
        mutations = [('level',value) for value in ([],{},True,None,'info','error','WARN')]
        mutations += [('isMeta',value) for value in (True,0,None,'false')]
        mutations += [('content',value) for value in ([],{},None,42)]
        mutations += [('timestamp',value) for value in (None,42,'2000-02-30T00:00:00.000Z',
                      '2000-01-01T25:00:00.000Z','2000-01-01T00:00:00Z','2000-01-01T00:00:00.000+00:00')]
        mutations += [(key,value) for key in ('uuid','session_id') for value in (
            None,[],42,'not-a-uuid','00000000-0000-1000-8000-000000000001',
            'AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE')]
        mutations += [('uuid',SID),('session_id','77777777-8888-4999-8000-111111111111'),
                      ('subtype','unknown_system_notice'),('extra','ignored?')]
        for key,value in mutations:
            notice = informational()
            notice[key] = value
            rows = events(ROOT)
            rows.insert(1,notice)
            with self.subTest(key=key,value=value):
                self.assertNotEqual(self.judge(rows)['status'],'CLASSIFIER_ALLOW_PASS')
        for key in informational():
            notice = informational()
            del notice[key]
            rows = events(ROOT)
            rows.insert(1,notice)
            self.assertNotEqual(self.judge(rows)['status'],'CLASSIFIER_ALLOW_PASS')
        rows = events(ROOT)
        rows[1:1] = [informational(),informational()]
        self.assertEqual(self.judge(rows)['status'],'INCONCLUSIVE')
        rows = events(ROOT)
        rows.insert(0,informational())
        self.assertEqual(self.judge(rows)['status'],'INCONCLUSIVE')
        raw = wire([informational()]).replace(b'"level": "warning"',b'"level":"warning","level":"error"')
        report,_ = auto.adjudicate(wire(events(ROOT)[:1])+raw+wire(events(ROOT)[1:]),native(),self.meta,
                                  auto.ActionLedger(ROOT),MODEL,HASH)
        self.assertEqual(report['status'],'INCONCLUSIVE')

    def test_informational_unknown_or_contradictory_content_blocks(self):
        contents = ['Synthetic diagnostic notice.', '\ud800', 'Auto mode classifier unavailable.',
                    NOTICE_CONTENT.replace('keeps working','stops working'),
                    NOTICE_CONTENT+' Auto mode classifier unavailable.',
                    NOTICE_CONTENT.replace('Nothing breaks:','Admission denied:'),
                    NOTICE_CONTENT.replace('billed as before','now unavailable'),
                    NOTICE_CONTENT.replace('gateway.example.invalid:4242','gateway says classifier denied'),
                    NOTICE_CONTENT.replace('https://example.invalid/optional-gateway-feature','unsupported endpoint prose')]
        for content in contents:
            rows = events(ROOT)
            notice = informational()
            notice['content'] = content
            rows.insert(1,notice)
            self.assertEqual(self.judge(rows)['status'],'INCONCLUSIVE')

    def test_all_ancillary_notices_do_not_upgrade_interrupted_capture(self):
        rows = events(ROOT)
        rows.insert(1,informational())
        debug = native()+b''.join(error_line(body) for _,body in ANCILLARY_NATIVE)
        meta = dict(self.meta,natural_completion=False,exit_code=143,stop_reason='unsupported_system_event')
        report = self.judge(rows,debug,meta)
        self.assertEqual((report['status'],auto.exit_code(report['status'])),('INCONCLUSIVE',2))
        self.assertEqual(report['reason'],'interrupted_or_incomplete_capture')
        self.assertEqual(len(report['diagnostics']),4)

    def test_ancillary_warning_does_not_change_final_confirmation_contract(self):
        base = events(ROOT)
        question = auto.confirmation_questions(ROOT)[0]
        for text,permitted in [(question,True),('Proceed?',False),(question+' Also change settings.',False)]:
            rows = [base[0],informational(),base[3],base[-1]]
            rows[2]['message']['content'] = [{'type':'text','text':text}]
            report,stream = auto.adjudicate(wire(rows),error_line(ANCILLARY_NATIVE[0][1]),self.meta,
                                           auto.ActionLedger(ROOT),MODEL,HASH)
            self.assertEqual(report['status'],'ACTION_NOT_REACHED',report)
            self.assertEqual(auto.continuation_prompt(stream,True) is not None,permitted)
            self.assertIsNone(auto.continuation_prompt(stream,False))

    def test_success_rejects_native_only_read_skill_before_or_after_digest(self):
        for tool in ('Read','Skill'):
            start = f'[Stall] tool_dispatch_start tool={tool} toolUseId=unreported permissionDecisionMs=1'
            end = f'[Stall] tool_dispatch_end tool={tool} toolUseId=unreported outcome=ok durationMs=1'
            for extra in (native([start,end]),native([start]),native([end]),
                          native([start,end.replace('outcome=ok','outcome=error')])):
                for debug in (extra+native(),native()+extra):
                    with self.subTest(tool=tool,debug_hash=hashlib.sha256(debug).hexdigest()):
                        report = self.judge(debug=debug)
                        self.assertEqual((report['status'],auto.exit_code(report['status'])),('INCONCLUSIVE',2))
                        self.assertEqual(report['reason'],'native_structured_tool_disagreement')

    def test_success_accepts_fully_owned_mandatory_activity_and_digest(self):
        for tool,payload in [('Read',{'file_path':str(ROOT/'CLAUDE.md')}),
                             ('Skill',{'skill':'daaf-orchestrator'}),
                             ('Bash',{'command':f'wc -l {ROOT}/CLAUDE.md'})]:
            base = events(ROOT)
            call = copy.deepcopy(base[1])
            call['message']['content'] = [{'type':'tool_use','id':'required_tool','name':tool,'input':payload}]
            reply = copy.deepcopy(base[2])
            reply['message']['content'] = [{'type':'tool_result','tool_use_id':'required_tool','content':'public fixture'}]
            rows = base[:1]+[call,reply]+base[1:]
            before = native().replace(b'tool_digest',b'required_tool').replace(b'req_one',b'req_required').replace(b'tool=Bash',('tool='+tool).encode()).replace(b'for Bash ',('for '+tool+' ').encode())
            for prefix in (before,b''.join(before.splitlines(keepends=True)[-2:])):
                report = self.judge(rows,prefix+native())
                self.assertEqual(report['status'],'CLASSIFIER_ALLOW_PASS',report)
                self.assertEqual(report['classifier_selected_model'],'gpt-5.6-sol[1m]')
                self.assertTrue(report['digest_success'])
            if tool == 'Bash':
                fast = native(['Skipping auto mode classifier for Bash: configured rule'])
                prefix = b''.join(before.splitlines(keepends=True)[-2:])
                self.assertEqual(self.judge(rows,fast+prefix+native())['status'],'CLASSIFIER_ALLOW_PASS')
            # All extra tools are structured/allowed, but native completeness and
            # success are still mandatory. The digest's success cannot mask them.
            for bad in (b''.join(before.splitlines(keepends=True)[:-1]),
                        before.replace(b'outcome=ok',b'outcome=error'),
                        native(['ordinary debug'])):
                report = self.judge(rows,bad+native())
                self.assertEqual((report['status'],auto.exit_code(report['status'])),('INCONCLUSIVE',2))

    def test_fastpath_marker_without_owned_dispatch_is_inconclusive(self):
        report = self.judge(debug=native(['Skipping auto mode classifier for Bash: configured rule']))
        self.assertEqual(report['status'],'INCONCLUSIVE')
        self.assertEqual(auto.exit_code(report['status']),2)

    def test_observed_native_six_event_contract(self):
        parsed = auto.native_events(native())
        self.assertEqual([kind for kind, fields in parsed],
            ['classification','start','finish','allow','dispatch_start','dispatch_end'])
        self.assertEqual(parsed[0][1]['toolUseId'],'tool_digest')
        self.assertEqual(parsed[1][1]['promptTokensEst'],'[REDACTED]')
        self.assertEqual(parsed[2][1]['durationMs'],'1')
        self.assertEqual(parsed[3][1],{'tool':'Bash','mode':'auto','behavior':'allow'})
        self.assertEqual(parsed[4][1]['permissionDecisionMs'],'1')
        report = self.judge()
        self.assertEqual((report['status'],auto.exit_code(report['status'])),('CLASSIFIER_ALLOW_PASS',0))
        self.assertTrue(report['digest_success'])
        self.assertTrue(report['normal_parser_acceptance_via_client_decision'])
        self.assertFalse(report['raw_classifier_xml_independently_available'])
        self.assertIsNone(report['classifier_request_route'])

    def test_observed_metadata_grammar_is_closed(self):
        mutations = [
            (b'actionChars=1',b'actionChars=1junk'),
            (b'actionChars=1',b'actionChars=1.5'),
            (b'actionChars=1',b'actionChars=-1'),
            (b'actionChars=1',b'actionChars=1 actionChars=2'),
            (b'id=tool_digest',b'id=other note=tool_digest'),
            (b'reqId=req_one',b'reqId=req_one reqId=req_two'),
            (b'permissionDecisionMs=1',b'permissionDecisionMs=1 permissionDecisionMs=2'),
            (b'permissionDecisionMs=1',b'permissionDecisionMs=1ms'),
            (b'durationMs=1',b'durationMs=NaN'),
            (b'durationMs=1',b'durationMs=1 outcome=error'),
            (b'behavior=allow)',b'behavior=allow, behavior=deny)'),
            (b'mode=auto,',b'mode=auto, mode=bypassPermissions,'),
            (b'1ms for Bash',b'1ms for Read'),
            (b'Slow permission decision:',b'Unknown permission decision:'),
            (b'tool=Bash actionChars=1 id=tool_digest',b'Bash tool_digest'),
            (b'Slow permission decision: 1ms for Bash (mode=auto, behavior=allow)',
             b'[Permission] Decision tool=Bash mode=auto behavior=allow'),
            (b' promptTokensEst=[REDACTED]',b''),
            (b' permissionDecisionMs=1',b' permissionDecisionMs=1 unknown=ok'),
        ]
        mutations += [(b'promptTokensEst=[REDACTED]',b'promptTokensEst='+value)
            for value in (b'[redacted]',b'[Redacted]',b'<REDACTED>',b'(REDACTED)',b'1',
                          b'"[REDACTED]"',b'[REDACTED]suffix',b'[REDACTED] promptTokensEst=1')]
        for old,new in mutations:
            with self.subTest(old=old,new=new):
                debug = native().replace(old,new)
                self.assertNotEqual(debug,native())
                self.assertEqual(self.judge(debug=debug)['status'],'INCONCLUSIVE')
        for old in (b'actionChars=1',b'durationMs=1',b'permissionDecisionMs=1'):
            self.assertEqual(self.judge(debug=native().replace(old,old.split(b'=')[0]+b'=0'))['status'],
                             'CLASSIFIER_ALLOW_PASS')

    def test_action_free_full_observed_classification_frames(self):
        for name,payload in [('Read',{'file_path':str(ROOT/'CLAUDE.md')}),
                             ('Skill',{'skill':'daaf-orchestrator'}),
                             ('Bash',{'command':f'wc -l {ROOT}/CLAUDE.md'})]:
            rows = events(ROOT)
            rows[1]['message']['content'] = [{'type':'tool_use','id':'public_tool', 'name':name,'input':payload}]
            rows[2]['message']['content'] = [{'type':'tool_result','tool_use_id':'public_tool','content':'public fixture'}]
            rows[3]['message']['content'] = [{'type':'text','text':auto.confirmation_questions(ROOT)[0]}]
            debug = native().replace(b'tool_digest',b'public_tool').replace(b'tool=Bash',('tool='+name).encode()).replace(b'for Bash ',('for '+name+' ').encode())
            report,stream = auto.adjudicate(wire(rows),debug,self.meta,auto.ActionLedger(ROOT),MODEL,HASH)
            self.assertEqual(report['status'],'ACTION_NOT_REACHED',report)
            self.assertIsNotNone(auto.continuation_prompt(stream,True))
            for bad in (debug.replace(b'toolUseId=public_tool',b'toolUseId=other'),debug[:-1],
                        b''.join(debug.splitlines(keepends=True)[:-1])):
                report,_ = auto.adjudicate(wire(rows),bad,self.meta,auto.ActionLedger(ROOT),MODEL,HASH)
                self.assertEqual(report['status'],'INCONCLUSIVE')

    def test_failed_or_unknown_hook_response_cannot_pass(self):
        for outcome, code, expected in [('success',0,'CLASSIFIER_ALLOW_PASS'),
                ('error',1,'TRANSPORT_PARSER_FAILURE'), ('success',1,'TRANSPORT_PARSER_FAILURE'),
                ('cancelled',0,'TRANSPORT_PARSER_FAILURE'), ('success',None,'INCONCLUSIVE'),
                (None,0,'INCONCLUSIVE'), ('success',False,'INCONCLUSIVE')]:
            rows = events(ROOT)
            rows.insert(1,{'type':'system','subtype':'hook_response','outcome':outcome,'exit_code':code})
            report = self.judge(rows)
            self.assertEqual(report['status'],expected)
            if expected != 'CLASSIFIER_ALLOW_PASS':
                self.assertNotEqual(auto.exit_code(report['status']),0)

    def test_structured_permission_denial_status_and_exit(self):
        rows = events(ROOT)
        rows[-1]['permission_denials'] = [{'tool_name':'Bash', 'tool_use_id':'tool_digest',
                                           'tool_input':{'command':auto.digest_command(ROOT)}}]
        report = self.judge(rows)
        self.assertEqual((report['status'], auto.exit_code(report['status'])), ('POLICY_DENIED', 1))
        for value in (None, {}, 'denied', [{}], [None], [{'tool_name':'Bash','tool_use_id':[], 'tool_input':{}}]):
            rows[-1]['permission_denials'] = value
            report = self.judge(rows)
            self.assertEqual((report['status'], auto.exit_code(report['status'])), ('INCONCLUSIVE', 2))
        del rows[-1]['permission_denials']
        self.assertEqual(self.judge(rows)['status'], 'INCONCLUSIVE')

    def test_final_completion_all_blocks_no_stale_text(self):
        base = events(ROOT)
        question = auto.confirmation_questions(ROOT)[0]
        for blocks in ([{'type':'text','text':'I will change settings.'}, {'type':'text','text':question}],
                       [{'type':'text','text':question}, {'type':'text','text':question}]):
            rows = [base[0], copy.deepcopy(base[3]), base[-1]]
            rows[1]['message']['content'] = blocks
            parsed = auto.parse_stdout(wire(rows), auto.ActionLedger(ROOT), MODEL, HASH)
            self.assertIsNone(auto.continuation_prompt(parsed, True))
        first = copy.deepcopy(base[3])
        first['message'].update(id='completion_one', content=[{'type':'text','text':question}])
        final = copy.deepcopy(base[3])
        final['message'].update(id='completion_two', content=[{'type':'thinking','thinking':'public fixture'}])
        parsed = auto.parse_stdout(wire([base[0], first, final, base[-1]]), auto.ActionLedger(ROOT), MODEL, HASH)
        self.assertIsNone(auto.continuation_prompt(parsed, True))
        # Multiple stream records from ONE completion cannot discard earlier scope.
        first['message']['content'] = [{'type':'text','text':'I will change settings.'}]
        final['message'].update(id='completion_one', content=[{'type':'text','text':question}])
        parsed = auto.parse_stdout(wire([base[0], first, final, base[-1]]), auto.ActionLedger(ROOT), MODEL, HASH)
        self.assertIsNone(auto.continuation_prompt(parsed, True))
        parsed = auto.parse_stdout(wire([base[0], final, base[-1]]), auto.ActionLedger(ROOT), MODEL, HASH)
        self.assertIsNotNone(auto.continuation_prompt(parsed, True))
        del first['message']['id']
        del final['message']['id']
        parsed = auto.parse_stdout(wire([base[0], first, final, base[-1]]), auto.ActionLedger(ROOT), MODEL, HASH)
        self.assertIsNone(auto.continuation_prompt(parsed, True))

    def test_native_full_tokens_wrong_fields_and_duplicate_values(self):
        for debug in (
            native().replace(b'reqId=req_one tool=Bash model',b'reqId=req_one.alpha tool=Bash model').replace(b'reqId=req_one tool=Bash stage',b'reqId=req_one.beta tool=Bash stage'),
            native().replace(b'toolUseId=tool_digest',b'toolUseId=other note=tool_digest'),
            native().replace(b'outcome=ok',b'outcome=ok outcome=error'),
            native().replace(b'outcome=ok',b'outcome=ok.suffix'),
            native().replace(b'tool=Bash',b'tool=Bash tool=Read'),
            native().replace(b'behavior=allow',b'behavior=allow behavior=deny'),
            native().replace(b'id=tool_digest',b'id=tool_digest_suffix'),
            native().replace(b'toolUseId=tool_digest',b'toolUseId=tool_digest.suffix'),
        ):
            self.assertNotEqual(debug,native(), 'mutation must change the wire fixture')
            self.assertEqual(self.judge(debug=debug)['status'],'INCONCLUSIVE')
        # Full dotted request identity is preserved, not truncated at a word boundary.
        self.assertEqual(self.judge(debug=native().replace(b'req_one',b'req_one.alpha'))['status'], 'CLASSIFIER_ALLOW_PASS')

    def test_action_free_native_requires_owned_complete_known_tools(self):
        base = events(ROOT)
        question = copy.deepcopy(base[3])
        question['message']['content'] = [{'type':'text','text':auto.confirmation_questions(ROOT)[0]}]
        rows = [base[0],question,base[-1]]
        for debug in (b'',native()[:-1],native(),native(['[Stall] tool_dispatch_start toolUseId=omitted tool=Bash']),
                      native(['[Stall] classifier_request_started reqId=req_one stage=xml_s1 model=gpt-5.6-sol tool=Bash'])):
            self.assertEqual(self.judge(rows,debug)['status'],'INCONCLUSIVE')
        for name,payload in [('Read',{'file_path':str(ROOT/'CLAUDE.md')}),
                             ('Skill',{'skill':'daaf-orchestrator'}),
                             ('Bash',{'command':f'wc -l {ROOT}/CLAUDE.md'})]:
            call = copy.deepcopy(base[1])
            call['message']['content'] = [{'type':'tool_use','id':'public_read','name':name,'input':payload}]
            reply = copy.deepcopy(base[2])
            reply['message']['content'] = [{'type':'tool_result','tool_use_id':'public_read','content':'public fixture'}]
            complete_rows = [base[0],call,reply,question,base[-1]]
            debug = native([f'[Stall] tool_dispatch_start tool={name} toolUseId=public_read permissionDecisionMs=1',
                            f'[Stall] tool_dispatch_end tool={name} toolUseId=public_read outcome=ok durationMs=1'])
            self.assertEqual(self.judge(complete_rows,debug)['status'],'ACTION_NOT_REACHED')
            self.assertEqual(self.judge(complete_rows,debug.splitlines(keepends=True)[0])['status'],'INCONCLUSIVE')
            self.assertEqual(self.judge(complete_rows,native(['ordinary debug']))['status'],'INCONCLUSIVE')

    def test_missing_reordered_wrong_and_overlapping_native_never_pass(self):
        lines = native().splitlines(keepends=True)
        variants = [b''.join(lines[:i] + lines[i+1:]) for i in range(len(lines))]
        variants += [b''.join(reversed(lines)), native().replace(b'req_one tool=Bash stage', b'req_two tool=Bash stage'),
                     native().replace(b'toolUseId=tool_digest', b'toolUseId=other'),
                     lines[0] + lines[0] + b''.join(lines[1:]),
                     native().replace(b'outcome=ok', b'outcome=error'), native()[:-1],
                     native() + b'unsupported unprefixed line\n']
        for value in variants:
            with self.subTest(value_hash=hashlib.sha256(value).hexdigest()):
                self.assertNotEqual(self.judge(debug=value)['status'], 'CLASSIFIER_ALLOW_PASS')

    def test_wrong_hash_session_version_denial_and_duplicate_results(self):
        base = events(ROOT)
        mutations = []
        for index, key, value in [(0, 'claude_code_version', '2.1.999'), (0, 'permissionMode', 'bypassPermissions'),
                                  (2, 'session_id', str(uuid.uuid4())), (4, 'permission_denials', [{}])]:
            rows = copy.deepcopy(base)
            rows[index][key] = value
            mutations.append(rows)
        wrong = copy.deepcopy(base)
        wrong[2]['message']['content'][0]['content'] = HASH
        mutations.append(wrong)
        mutations.extend([base[:-1], base[1:], base[:2]+[base[1]]+base[2:], base+[base[-1]]])
        for index, rows in enumerate(mutations):
            report = self.judge(rows)
            if index == 7:  # identical same-ID tool event is intentionally deduplicated
                self.assertEqual(report['status'], 'CLASSIFIER_ALLOW_PASS')
            else:
                self.assertNotEqual(report['status'], 'CLASSIFIER_ALLOW_PASS')

    def test_strict_jsonl_and_capture(self):
        for raw in (wire(events(ROOT)) + b'bad\n', wire(events(ROOT))[:-1], b'{"type":"system","type":"result"}\n', b'[]\n'):
            with self.assertRaises(auto.EvidenceError):
                auto.parse_stdout(raw, auto.ActionLedger(ROOT), MODEL, HASH)
        for key in self.meta:
            value = dict(self.meta)
            value[key] = False if key != 'exit_code' else 1
            if key == 'stop_reason':
                value[key] = 'deadline'
            self.assertNotEqual(self.judge(meta=value)['status'], 'CLASSIFIER_ALLOW_PASS')

    def test_malformed_field_types_are_inconclusive_not_exceptions(self):
        for index, key, value in ((0, 'type', []), (0, 'subtype', {}), (1, 'session_id', [])):
            rows = events(ROOT)
            rows[index][key] = value
            self.assertEqual(self.judge(rows)['status'], 'INCONCLUSIVE')
        for index, key, value in ((1, 'name', []), (1, 'input', []), (2, 'tool_use_id', []),
                                  (2, 'content', [{'type':'text','text':1}]), (2, 'type', {})):
            rows = events(ROOT)
            rows[index]['message']['content'][0][key] = value
            self.assertEqual(self.judge(rows)['status'], 'INCONCLUSIVE')
        with self.assertRaises(auto.EvidenceError):
            auto.ActionLedger(ROOT).observe({'id':'id1','name':'Skill','input':{'skill':[]}})

    def test_competing_brackets_missing_session_and_conflicting_id(self):
        lines = native().splitlines(keepends=True)
        overlap = native(['[auto-mode] new action being classified: tool=Bash actionChars=1 id=other_action'])
        self.assertNotEqual(self.judge(debug=b''.join(lines[:2])+overlap+b''.join(lines[2:]))['status'], 'CLASSIFIER_ALLOW_PASS')
        rows = events(ROOT)
        del rows[1]['session_id']
        self.assertNotEqual(self.judge(rows)['status'], 'CLASSIFIER_ALLOW_PASS')
        rows = events(ROOT)
        extra = copy.deepcopy(rows[1])
        extra['message']['content'][0]['input']['command'] += ' /other.md'
        rows.insert(2, extra)
        self.assertNotEqual(self.judge(rows)['status'], 'CLASSIFIER_ALLOW_PASS')
        with self.assertRaises(auto.EvidenceError):
            auto.decode_event(b'{"value":NaN}')

    def test_explicit_fastpath_denial_and_admission_are_not_pass(self):
        for body, expected in [('Skipping auto mode classifier for Bash: configured rule', 'FAST_PATH_ACTION_SUCCESS'),
                               ('Auto mode classifier blocked action: denied', 'POLICY_DENIED'),
                               ('verifyAutoModeGateAccess: canEnterAuto=false', 'ADMISSION_REJECTED'),
                               ('Auto mode classifier (XML) error: parse', 'TRANSPORT_PARSER_FAILURE')]:
            debug = native([body])
            if expected == 'FAST_PATH_ACTION_SUCCESS':
                debug += b''.join(native().splitlines(keepends=True)[-2:])
            report = self.judge(debug=debug)
            self.assertEqual(report['status'], expected)
        self.assertEqual(self.judge(debug=native(['ordinary debug']))['status'], 'INCONCLUSIVE')


class AutoLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.root = ROOT / 'scripts/scratch' / ('auto_tests_' + uuid.uuid4().hex)
        self.root.mkdir(parents=True, mode=0o700)
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / 'CLAUDE.md').write_text('public fabricated instruction\n')

    def args(self, **changes):
        import argparse
        fields = dict(model=MODEL, report_dir=str(self.root/'run'), yes=True,
                      retain_private_capture=True, allow_bounded_continuations=True, preflight_only=False)
        fields.update(changes)
        return argparse.Namespace(**fields)

    def fake_preflight(self):
        from route_detection import resolve_main_model
        return (resolve_main_model({'DAAF_PROVIDER_SHIM':'openai','SHIM_BACKEND_MODE':'chatgpt',
                                    'ANTHROPIC_BASE_URL':'http://127.0.0.1:4141'}, explicit_model=MODEL),
                hashlib.sha256((self.root/'CLAUDE.md').read_bytes()).hexdigest(), {'checks':{'ready':True}})

    def test_normal_flags_no_extra_grants_or_benchmark(self):
        args = auto.normal_argv('claude', self.root/'debug.log', 'public prompt', MODEL, SID)
        self.assertIn('auto', args)
        self.assertEqual(args[args.index('--resume')+1], SID)
        self.assertEqual(args[args.index('--max-turns')+1], '6')
        for word in ('bypassPermissions', '--dangerously-skip-permissions', '--allowedTools', '--settings', '--session-id'):
            self.assertNotIn(word, args)
        plain = auto.normal_argv('claude', self.root/'debug.log', 'public prompt')
        self.assertNotIn('--model', plain)

    def test_unmapped_default_alias_is_compatible_but_never_launches(self):
        # 2026-10-12: the shipped settings.json sets ANTHROPIC_DEFAULT_MODEL=opus.
        # Unmapped, the alias is family-compatible on the native route but has no
        # exact model ID to check the initialized model against, so the dedicated
        # runner stays preflight_unresolved instead of launching a paid child.
        from route_detection import resolve_main_model
        resolution = resolve_main_model({'ANTHROPIC_DEFAULT_MODEL': 'opus'})
        self.assertEqual((resolution.compatibility, resolution.resolved_model), ('compatible', ''))
        child = mock.Mock(side_effect=AssertionError('no exact model ID to verify'))
        digest = hashlib.sha256((self.root/'CLAUDE.md').read_bytes()).hexdigest()
        with mock.patch.object(auto, 'preflight', return_value=(resolution, digest, {'checks': {'ready': True}})):
            report, _ = auto.run_acceptance(self.args(model=None), {}, self.root, child)
        self.assertEqual((report['status'], report['reason'], report['children_launched']),
                         ('INCONCLUSIVE', 'preflight_unresolved', 0))
        child.assert_not_called()
        # An explicit default ID does carry the exact identity to verify.
        explicit = resolve_main_model({'ANTHROPIC_DEFAULT_MODEL': 'claude-opus-4-8'})
        self.assertEqual((explicit.compatibility, explicit.resolved_model), ('compatible', 'claude-opus-4-8'))

    def test_live_capture_and_continuation_are_separate_consents(self):
        for flag in ('yes', 'retain_private_capture', 'preflight_only'):
            args = self.args(report_dir=str(self.root/flag), **{flag: flag == 'preflight_only'})
            child = mock.Mock(side_effect=AssertionError('no live child authorized'))
            with mock.patch.object(auto, 'preflight', return_value=self.fake_preflight()):
                report, _ = auto.run_acceptance(args, {}, self.root, child)
            self.assertEqual(report['children_launched'], 0)
            self.assertNotEqual(auto.exit_code(report['status']), 0)
            child.assert_not_called()

    def test_three_owned_session_invocations_max_and_truthful_confirmation(self):
        calls = []
        def capture(argv, out, env, stream, pointers):
            calls.append(argv)
            rows = events(self.root)
            identifier = f'public_read_{len(calls)}'
            rows[1]['message']['content'] = [{'type':'tool_use','id':identifier,'name':'Read',
                'input':{'file_path':str(self.root/'CLAUDE.md')}}]
            rows[2]['message']['content'] = [{'type':'tool_result','tool_use_id':identifier,'content':'public fixture'}]
            rows[3]['message']['content'][0]['text'] = auto.confirmation_questions(self.root)[len(calls) % 2]
            rows.insert(1,informational())
            auto.private_write(out/'stdout.jsonl', wire(rows))
            auto.private_write(out/'stderr.log', b'')
            auto.private_write(out/'native-debug.log', native([
                f'[Stall] tool_dispatch_start tool=Read toolUseId={identifier} permissionDecisionMs=1',
                f'[Stall] tool_dispatch_end tool=Read toolUseId={identifier} outcome=ok durationMs=1']))
            return dict(natural_completion=True, child_reaped=True, capture_drained=True, capture_intact=True, exit_code=0, stop_reason=None)
        with mock.patch.object(auto, 'preflight', return_value=self.fake_preflight()):
            report, _ = auto.run_acceptance(self.args(), {}, self.root, capture)
        self.assertEqual(len(calls), 3)
        self.assertEqual(report['reason'], 'continuation_budget_exhausted')
        self.assertEqual(len(report['diagnostics']),3)
        self.assertTrue(all(item['category']=='auto_billing_update_ineligible_continues' for item in report['diagnostics']))
        for argv in calls[1:]:
            self.assertEqual(argv[argv.index('--resume')+1], SID)
            self.assertIn('operator explicitly delegated', argv[-1])
        with self.assertRaises(FileExistsError):
            auto.run_acceptance(self.args(), {}, self.root, capture)
        self.assertEqual(len(calls), 3)

    def test_generic_or_new_scope_question_is_not_confirmed(self):
        stream = auto.StreamEvidence(auto.ActionLedger(self.root), MODEL, HASH)
        stream.result = {'subtype':'success'}
        for text in ('Proceed?', 'Yes?', 'Confirm changing settings?', auto.confirmation_questions(self.root)[0]+' Also edit permissions.'):
            stream.assistant_text = text
            self.assertIsNone(auto.continuation_prompt(stream, True))
        stream.assistant_text = auto.confirmation_questions(self.root)[0]
        self.assertIsNone(auto.continuation_prompt(stream, False))
        self.assertIsNotNone(auto.continuation_prompt(stream, True))
        stream.ledger.digest_id = 'attempted'
        self.assertIsNone(auto.continuation_prompt(stream, True))

    def test_native_disagreement_or_truncation_never_launches_resume(self):
        for index, debug in enumerate((native(), b'', native()[:-1],
                native(['[Stall] tool_dispatch_start toolUseId=omitted tool=Bash']))):
            calls=[]
            def capture(argv,out,env,stream,pointers):
                calls.append(argv)
                base=events(self.root)
                rows=[base[0],base[3],base[-1]]
                rows[1]['message']['content']=[{'type':'text','text':auto.confirmation_questions(self.root)[0]}]
                auto.private_write(out/'stdout.jsonl',wire(rows))
                auto.private_write(out/'stderr.log',b'')
                auto.private_write(out/'native-debug.log',debug)
                return dict(natural_completion=True,child_reaped=True,capture_drained=True,capture_intact=True,exit_code=0,stop_reason=None)
            with mock.patch.object(auto,'preflight',return_value=self.fake_preflight()):
                report,_=auto.run_acceptance(self.args(report_dir=str(self.root/f'mismatch_{index}')),{},self.root,capture)
            self.assertEqual(len(calls),1)
            self.assertEqual(report['status'],'INCONCLUSIVE')

    def test_interrupted_attempt_never_launches_resume(self):
        count = []
        def capture(argv, out, env, stream, pointers):
            count.append(1)
            stream.ledger.observe(events(self.root)[1]['message']['content'][0])
            auto.private_write(out/'stdout.jsonl', wire(events(self.root)[:2]))
            auto.private_write(out/'stderr.log', b'')
            auto.private_write(out/'native-debug.log', native())
            return dict(natural_completion=False, child_reaped=True, capture_drained=True, capture_intact=True, exit_code=-15, stop_reason='deadline')
        with mock.patch.object(auto, 'preflight', return_value=self.fake_preflight()):
            report, _ = auto.run_acceptance(self.args(), {}, self.root, capture)
        self.assertEqual(len(count), 1)
        self.assertTrue(report['digest_attempted'])
        self.assertEqual(report['status'], 'INCONCLUSIVE')

    def test_offline_capture_monitor_recognizes_only_exact_notice(self):
        for index,content in enumerate((NOTICE_CONTENT,'Synthetic unknown warning.')):
            rows = events(self.root)
            notice = informational()
            notice['content'] = content
            rows.insert(1,notice)
            out = self.root/f'notice_monitor_{index}'
            out.mkdir(mode=0o700)
            stream = auto.StreamEvidence(auto.ActionLedger(self.root),MODEL,HASH)
            meta = auto.capture_child(['/usr/bin/printf','%s',wire(rows).decode()],out,{},stream,timeout=2)
            self.assertEqual(meta['stop_reason'],None if index == 0 else 'unknown_system_notice')
            self.assertEqual(meta['natural_completion'],index == 0)
            self.assertTrue(meta['child_reaped'])
            self.assertTrue(meta['capture_drained'])
            self.assertEqual(len(stream.diagnostics),1)

    def test_real_offline_process_capture_and_timeout_cleanup(self):
        import stat
        for label, argv, timeout in [('natural', ['/usr/bin/printf', '%s', wire(events(self.root)).decode()], 2),
                                     ('timeout', ['/usr/bin/sleep', '5'], 0.05)]:
            out = self.root/label
            out.mkdir(mode=0o700)
            stream = auto.StreamEvidence(auto.ActionLedger(self.root), MODEL, HASH)
            meta = auto.capture_child(argv, out, {}, stream, timeout=timeout)
            self.assertTrue(meta['child_reaped'], meta)
            self.assertTrue(meta['capture_drained'], meta)
            self.assertLess(meta['elapsed_seconds'], 6)
            self.assertEqual(meta['stop_reason'], None if label == 'natural' else 'deadline')
            self.assertEqual(stat.S_IMODE((out/'stdout.jsonl').stat().st_mode), 0o600)
            manifest = auto.write_manifest(out)
            self.assertIn('exit.json', manifest)

    @unittest.skipUnless(sys.platform == 'linux', 'Linux process-group/subreaper fixture')
    def test_descendant_pipeholder_is_killed_drained_and_reaped(self):
        import ctypes
        import os
        import signal
        import time
        # Adopt the fabricated orphan so the test can reap it even if PID1 cannot.
        libc = ctypes.CDLL(None, use_errno=True)
        previous = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(previous), 0, 0, 0), 0)  # GET_CHILD_SUBREAPER
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)  # SET_CHILD_SUBREAPER
        pidfile = self.root/'descendant_pid.txt'
        fixture = self.root/'pipeholder.py'
        fixture.write_text('import subprocess, sys\nfrom pathlib import Path\n'
            'child=subprocess.Popen(["/usr/bin/sleep","30"])\n'
            'Path('+repr(str(pidfile))+').write_text(str(child.pid))\n')
        pid = None
        reaped = False
        try:
            out = self.root/'descendant'
            out.mkdir(mode=0o700)
            meta = auto.capture_child([sys.executable,'-B',str(fixture)],out,{},
                auto.StreamEvidence(auto.ActionLedger(self.root),MODEL,HASH),timeout=0.3)
            pid = int(pidfile.read_text())
            self.assertEqual(meta['stop_reason'],'deadline')
            self.assertTrue(meta['child_reaped'])
            self.assertTrue(meta['capture_drained'], 'parent-only termination leaves descendant pipes open')
            self.assertLess(meta['elapsed_seconds'], 6)
            deadline = time.monotonic()+1
            while time.monotonic() < deadline:
                found,_ = os.waitpid(pid,os.WNOHANG)
                if found == pid:
                    reaped = True
                    break
                time.sleep(0.01)
            self.assertTrue(reaped, 'descendant survived group cleanup')
            with self.assertRaises(ProcessLookupError):
                os.kill(pid,0)
        finally:
            if pid is None and pidfile.exists():
                pid = int(pidfile.read_text())
            if pid and not reaped:
                try:
                    os.kill(pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
                deadline = time.monotonic()+1
                while time.monotonic() < deadline:
                    try:
                        if os.waitpid(pid,os.WNOHANG)[0] == pid:
                            break
                    except ChildProcessError:
                        break
                    time.sleep(0.01)
            libc.prctl(36,previous.value,0,0,0)

    def test_no_inherited_file_cap_and_owned_native_overflow(self):
        large = self.root/'existing_audit.log'
        with large.open('wb') as handle:
            handle.truncate(auto.CAPTURE_LIMIT+1)
        fixture = self.root/'append.py'
        fixture.write_text('from pathlib import Path\nwith Path('+repr(str(large))+').open("ab") as f:\n    f.write(b"x")\n')
        out = self.root/'append'
        out.mkdir(mode=0o700)
        meta = auto.capture_child([sys.executable,'-B',str(fixture)],out,{},
            auto.StreamEvidence(auto.ActionLedger(self.root),MODEL,HASH))
        self.assertEqual(meta['exit_code'],0)
        self.assertTrue(meta['natural_completion'])
        self.assertEqual(large.stat().st_size,auto.CAPTURE_LIMIT+2)
        out = self.root/'native_overflow'
        out.mkdir(mode=0o700)
        fixture = self.root/'overflow.py'
        fixture.write_text('from pathlib import Path\nPath('+repr(str(out/'native-debug.log'))+').write_bytes(b"x"*65536)\n')
        with mock.patch.object(auto,'CAPTURE_LIMIT',4096):
            meta = auto.capture_child([sys.executable,'-B',str(fixture)],out,{},
                auto.StreamEvidence(auto.ActionLedger(self.root),MODEL,HASH))
        self.assertFalse(meta['capture_intact'])
        self.assertEqual(meta['stop_reason'],'native_capture_limit')
        self.assertLessEqual((out/'native-debug.log').stat().st_size,4096)
        self.assertTrue(meta['child_reaped'])
        self.assertTrue(meta['capture_drained'])

    def test_spawn_exception_is_preserved_and_does_not_pass(self):
        out = self.root/'spawn_failure'
        out.mkdir(mode=0o700)
        with mock.patch.object(auto.subprocess, 'Popen', side_effect=OSError('fabricated')):
            meta = auto.capture_child(['unused'], out, {}, auto.StreamEvidence(auto.ActionLedger(self.root), MODEL, HASH))
        self.assertEqual(meta['stop_reason'], 'supervisor_exception')
        self.assertFalse(meta['capture_intact'])
        self.assertTrue((out/'exit.json').exists())
        self.assertTrue((out/'launch_claim.json').exists())

    def test_final_drain_and_capture_failure_remain_nonpassing(self):
        out = self.root/'late_drain'
        out.mkdir(mode=0o700)
        monitor = auto.StreamEvidence(auto.ActionLedger(self.root), MODEL, HASH)
        # Reproducible early parser stop with more saved bytes arriving during cleanup.
        raw = b'not-json\n' + wire(events(self.root))
        meta = auto.capture_child(['/usr/bin/printf', '%s', raw.decode()], out, {}, monitor)
        self.assertTrue(meta['child_reaped'])
        self.assertEqual(meta['stop_reason'], 'malformed_jsonl')
        saved = auto.read_capture(out/'stdout.jsonl')
        self.assertTrue(saved.startswith(b'not-json\n'))
        report, _ = auto.adjudicate(saved, native(), meta, auto.ActionLedger(self.root), MODEL, HASH)
        self.assertNotEqual(report['status'], 'CLASSIFIER_ALLOW_PASS')

    def test_stream_limit_and_monitor_exception_cleanup(self):
        out = self.root/'limit'
        out.mkdir(mode=0o700)
        with mock.patch.object(auto, 'CAPTURE_LIMIT', 256):
            meta = auto.capture_child(['/usr/bin/printf', '%s', 'x'*4096], out, {},
                                      auto.StreamEvidence(auto.ActionLedger(self.root), MODEL, HASH))
        self.assertTrue(meta['child_reaped'])
        self.assertFalse(meta['capture_intact'])
        self.assertLessEqual((out/'stdout.jsonl').stat().st_size, 256)
        out = self.root/'observer_exception'
        out.mkdir(mode=0o700)
        observer = auto.StreamEvidence(auto.ActionLedger(self.root), MODEL, HASH)
        with mock.patch.object(observer, 'observe', side_effect=RuntimeError('fabricated')):
            meta = auto.capture_child(['/usr/bin/printf', '%s', wire(events(self.root)).decode()], out, {}, observer)
        self.assertTrue(meta['child_reaped'])
        self.assertFalse(meta['capture_intact'])
        self.assertEqual(meta['stop_reason'], 'supervisor_exception')

    def test_preflight_rejects_inherited_non_normal_flags_and_nondev(self):
        from route_detection import resolve_main_model
        resolution = resolve_main_model({'ANTHROPIC_MODEL':'claude-opus-4-8'})
        for key in ('DAAF_BENCHMARK_RUN', 'CLAUDE_CODE_BYPASS_PERMISSIONS', 'CLAUDE_CODE_USE_BEDROCK'):
            with mock.patch.object(auto, 'collect_main_model', return_value=(resolution, {})), mock.patch.object(auto.shutil, 'which', return_value='/public/tool'):
                _, _, result = auto.preflight({'DAAF_DEV':'1', key:'1'}, self.root, None)
            self.assertFalse(all(result['checks'].values()))
        with mock.patch.object(auto, 'collect_main_model', return_value=(resolution, {})):
            _, _, result = auto.preflight({}, self.root, None)
        self.assertFalse(result['checks']['development_image'])

    def test_preflight_effective_settings_route_health_and_context(self):
        # Real bounded settings reader/resolver; only HTTP/executable discovery mocked.
        config = self.root/'user'
        config.mkdir()
        project = self.root/'.claude'
        project.mkdir()
        path = project/'settings.json'
        ambient = {'DAAF_DEV':'1','CLAUDE_CONFIG_DIR':str(config)}
        shim = {'DAAF_PROVIDER_SHIM':'openai','SHIM_BACKEND_MODE':'chatgpt',
                'ANTHROPIC_BASE_URL':'http://127.0.0.1:4141','ANTHROPIC_MODEL':MODEL}
        path.write_text(json.dumps({'env':shim}))
        with mock.patch.object(auto.shutil,'which',return_value='/public/tool'), mock.patch.object(auto,'_read_local_health',side_effect=OSError('offline')) as health:
            resolution,_,pre = auto.preflight(ambient,self.root,None)
            self.assertEqual(resolution.compatibility,'compatible')
            self.assertEqual(pre['route'],'chatgpt-subscription')
            self.assertFalse(pre['checks']['health_ready'])
            self.assertEqual(health.call_count,1)
            child = mock.Mock(side_effect=AssertionError('failed health cannot launch'))
            report,_ = auto.run_acceptance(self.args(model=None),ambient,self.root,child)
            self.assertEqual(report['children_launched'],0)
            child.assert_not_called()
        for backend in ('chatgpt','openai'):
            path.write_text(json.dumps({'env':dict(shim,SHIM_BACKEND_MODE=backend)}))
            with mock.patch.object(auto.shutil,'which',return_value='/public/tool'), mock.patch.object(auto,'_read_local_health',return_value={'service':auto.EXPECTED_SHIM_SERVICE,'status':'ok','backend_mode':backend}):
                resolution,_,pre = auto.preflight(dict(ambient,**dict(shim,SHIM_BACKEND_MODE='openai' if backend=='chatgpt' else 'chatgpt')),self.root,None)
                self.assertTrue(pre['checks']['health_ready'])
                self.assertEqual(resolution.expected_backend,backend)
                self.assertNotIn('http://',json.dumps(pre))
        # The reverse overlay is native, so never query an unrelated ambient shim.
        path.write_text(json.dumps({'env':{'DAAF_PROVIDER_SHIM':'','SHIM_BACKEND_MODE':'',
            'ANTHROPIC_BASE_URL':'','ANTHROPIC_MODEL':'claude-opus-4-8'}}))
        with mock.patch.object(auto.shutil,'which',return_value='/public/tool'), mock.patch.object(auto,'_read_local_health',side_effect=AssertionError('wrong backend')) as health:
            resolution,_,pre = auto.preflight(dict(ambient,**shim),self.root,None)
            self.assertEqual(pre['route'],'anthropic-subscription')
            self.assertEqual(resolution.compatibility,'compatible')
            health.assert_not_called()
        for flag in ('DAAF_BENCHMARK_RUN','CLAUDE_CODE_BYPASS_PERMISSIONS','CLAUDE_CODE_DANGEROUSLY_SKIP_PERMISSIONS'):
            path.write_text(json.dumps({'env':{'ANTHROPIC_MODEL':'claude-opus-4-8',flag:'1'}}))
            with mock.patch.object(auto.shutil,'which',return_value='/public/tool'):
                resolution,_,pre = auto.preflight(ambient,self.root,None)
            self.assertEqual(resolution.compatibility,'compatible')
            self.assertFalse(pre['checks']['no_benchmark_or_bypass'])

    def test_safe_report_does_not_publish_captured_prompts_or_session_id(self):
        def capture(argv, out, env, stream, pointers):
            rows = events(self.root)
            digest = hashlib.sha256((self.root/'CLAUDE.md').read_bytes()).hexdigest()
            rows[2]['message']['content'][0]['content'] = f'SHA2-256({self.root}/CLAUDE.md)= {digest}'
            rows[3]['message']['content'][0]['text'] = 'PRIVATE_PROMPT_SENTINEL'
            rows.insert(1,informational())
            auto.private_write(out/'stdout.jsonl', wire(rows))
            auto.private_write(out/'stderr.log', b'')
            auto.private_write(out/'native-debug.log', native()+b''.join(error_line(body) for _,body in ANCILLARY_NATIVE))
            return dict(natural_completion=True, child_reaped=True, capture_drained=True, capture_intact=True, exit_code=0, stop_reason=None)
        with mock.patch.object(auto, 'preflight', return_value=self.fake_preflight()):
            report, out = auto.run_acceptance(self.args(), {'ANTHROPIC_AUTH_TOKEN':'DO_NOT_REPORT_SENTINEL'}, self.root, capture)
        self.assertEqual(report['status'], 'CLASSIFIER_ALLOW_PASS', report)
        self.assertFalse(report['as_configured_certification'])
        for name in ('report.json', 'report.md'):
            rendered = (out/name).read_text()
            for private in ('PRIVATE_PROMPT_SENTINEL', 'DO_NOT_REPORT_SENTINEL', SID,
                            NOTICE_CONTENT, '/fabricated/', 'gateway.example.invalid',
                            *[body for _,body in ANCILLARY_NATIVE]):
                self.assertNotIn(private, rendered)
            for category in ['auto_billing_update_ineligible_continues',*[category for category,_ in ANCILLARY_NATIVE]]:
                self.assertIn(category,rendered)

    def test_pointer_ownership_and_private_exclusive_paths(self):
        owned = self.root/'native-debug.log'
        owned.write_text('public fixture')
        prior, new, foreign = [self.root/name for name in ('prior', 'new', 'foreign')]
        prior.symlink_to(owned)
        before = auto.pointer_snapshot([prior, new, foreign])
        try:
            new.symlink_to(owned)
            foreign.symlink_to(self.root/'other.log')
            self.assertEqual(auto.cleanup_pointers(before, owned), 1)
            self.assertTrue(prior.is_symlink())
            self.assertTrue(foreign.is_symlink())
        finally:
            for path in (prior, new, foreign):
                if path.is_symlink():
                    path.unlink()
        path = self.root/'exclusive.json'
        auto.private_write(path, {'public':True})
        with self.assertRaises(FileExistsError):
            auto.private_write(path, {})
        with self.assertRaises(auto.EvidenceError):
            auto.make_run_dir('/outside-repository/auto', self.root)


class AutoMonitorTests(unittest.TestCase):
    def test_mandatory_reads_and_skills(self):
        for skill in auto.MANDATORY_SKILLS:
            auto.ActionLedger(ROOT).observe({'id': 'id1', 'name': 'Skill', 'input': {'skill': skill}})
        for name, payload in [('Read', {'file_path': str(ROOT/'CLAUDE.md')}),
                              ('Bash', {'command': f'wc -l {ROOT}/CLAUDE.md'})]:
            auto.ActionLedger(ROOT).observe({'id': 'id1', 'name': name, 'input': payload})

    def test_reject_mutation_private_paths_extra_arguments_and_unknowns(self):
        cases = [('Write', {}), ('Read', {'file_path': str(ROOT/'.env')}),
                 ('Read', {'file_path': str(ROOT/'research/private.md')}),
                 ('Read', {'file_path': str(ROOT/'agent_reference/../CLAUDE.md')}),
                 ('Skill', {'skill': 'unknown'}), ('Skill', {'skill': 'skill-authoring', 'args': 'change settings'})]
        for suffix in ('; pwd', ' > result.txt', ' /other/file', ' && pwd'):
            cases.append(('Bash', {'command': auto.digest_command(ROOT)+suffix}))
        for key in ('dangerouslyDisableSandbox', 'run_in_background', 'unknown'):
            cases.append(('Bash', {'command': auto.digest_command(ROOT), key: True}))
        for name, payload in cases:
            with self.subTest(name=name, keys=list(payload)):
                with self.assertRaises(auto.EvidenceError):
                    auto.ActionLedger(ROOT).observe({'id':'id1', 'name':name, 'input':payload})

    def test_id_dedup_conflict_and_no_second_digest(self):
        ledger = auto.ActionLedger(ROOT)
        block = events(ROOT)[1]['message']['content'][0]
        self.assertTrue(ledger.observe(block))
        self.assertFalse(ledger.observe(block))
        with self.assertRaisesRegex(auto.EvidenceError, 'conflicting_tool_id'):
            ledger.observe(dict(block, input={'command':'pwd'}))
        with self.assertRaisesRegex(auto.EvidenceError, 'second_digest_action'):
            ledger.observe(dict(block, id='second'))
