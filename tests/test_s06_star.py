import json
import unittest
from datetime import timedelta

import test_s04 as prior
from medplatform import s04_store
from medplatform import s06_star
from medplatform.s04_model import Completion
from medplatform.documents import stamp
from medplatform.s04_state import CASE_VERSION
from medplatform.web import create_app


class StarTests(unittest.TestCase):
    def setUp(self):
        self.base = prior.S04Tests()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.h = self.base.s
        self.configure()

    def configure(self, **settings):
        config = self.h.settings.model_copy(update=settings)
        app = create_app(config, clock=self.h.clock)
        self.h.app = app
        self.h.a = self.h.login('demo-patient-a', app=app)
        self.base.admin = self.h.login('demo-admin', app=app)
        self.base.b = app.state.s04
        self.service = app.state.s04
        status = self.base.api('GET', '/config/status', client=self.base.admin)
        version = next(x['version'] for x in status['version_refs'] if x['kind'] == 'model_config')
        self.base.api('PUT', '/config/model-profile', {'profile_id': 'mock-star', 'expected_config_version': version,
                                                    'confirmed': True}, client=self.base.admin)

    def generation(self, session):
        with self.h.db.connection(readonly=True) as conn:
            row = conn.execute('SELECT g.generation_id FROM b_generations g JOIN b_messages m ON m.message_id=g.user_message_id WHERE m.session_id=? ORDER BY g.rowid DESC LIMIT 1',
                               (session['session_id'],)).fetchone()
            _, gen = s04_store.generation(conn, row[0])
            checkpoint = s06_star.load(conn, row[0])
            assistants = conn.execute('SELECT COUNT(*) FROM b_messages WHERE session_id=? AND source_message_id IS NOT NULL',
                                      (session['session_id'],)).fetchone()[0]
        return gen, checkpoint, assistants

    def test_star_all_stages_share_budget_and_compatible_business_output(self):
        status = self.base.api('GET', '/config/status', client=self.base.admin)
        self.assertEqual(next(item['reason'] for item in status['capabilities'] if item['code'] == 'dialogue'), '本地 mock star')
        session = self.base.create()
        result = self.base.send(session, '我担心副作用，只想倾诉。')
        gen, state, count = self.generation(session)
        self.assertEqual(count, 1)
        self.assertEqual((gen['requested_pipeline'], gen['actual_pipeline']), ('star', 'star'))
        self.assertEqual([x['stage'] for x in gen['calls']], ['state', 'topic', 'strategy', 'candidate', 'candidate', 'select'])
        self.assertEqual(gen['budget']['used_network_attempts'], 0)
        self.assertEqual(state['next_stage'], 6)
        self.assertEqual(len(state['candidates']), 2)
        self.assertEqual(result['business_output']['difficulty_cues'][0]['evidence'], '担心副作用')
        self.assertNotIn('reasoning', json.dumps(state))

    def test_one_candidate_and_original_single_pass_remain_available(self):
        self.configure(STAR_MAX_CANDIDATES=1)
        result = self.base.send(self.base.create(), '一步就好，给个办法。')
        self.assertEqual(len(result['generation']['calls']), 5)
        status = self.base.api('GET', '/config/status', client=self.base.admin)
        version = next(x['version'] for x in status['version_refs'] if x['kind'] == 'model_config')
        self.base.api('PUT', '/config/model-profile', {'profile_id': 'mock-single-pass', 'expected_config_version': version,
                                                    'confirmed': True}, client=self.base.admin)
        result = self.base.send(self.base.create())
        self.assertEqual(result['generation']['actual_pipeline'], 'single_pass')
        self.assertEqual(len(result['generation']['calls']), 1)
        status = self.base.api('GET', '/config/status', client=self.base.admin)
        self.assertEqual(next(item['reason'] for item in status['capabilities'] if item['code'] == 'dialogue'), '本地 mock single_pass')

    def test_budget_exhaustion_does_not_publish_or_reset_on_retry(self):
        self.configure(STAR_MAX_ATTEMPTS=2)
        session = self.base.create()
        self.base.send(session, expected=502)
        gen, state, count = self.generation(session)
        self.assertEqual((len(gen['calls']), count, gen['error_code']), (2, 0, 'GENERATION_BUDGET_EXCEEDED'))
        self.base.api('POST', '/messages/'+gen['user_message_id']+'/generation-retries',
                      {'generation_id':gen['generation_id'], 'expected_turn_count':1}, expected=409)
        self.assertEqual(self.generation(session)[0]['calls'], gen['calls'])

    def test_mid_failure_resumes_exact_checkpoint_with_remaining_budget(self):
        session = self.base.create()
        self.base.trigger('star_mid_failure', session=session)
        self.base.send(session, expected=502)
        gen, state, count = self.generation(session)
        self.assertEqual((len(gen['calls']), state['next_stage'], count), (3, 2, 0))
        result = self.base.api('POST', '/messages/'+gen['user_message_id']+'/generation-retries',
                               {'generation_id':gen['generation_id'], 'expected_turn_count':1})
        self.assertEqual(result['generation']['generation_id'], gen['generation_id'])
        self.assertEqual(len(result['generation']['calls']), 7)
        self.assertEqual(self.generation(session)[2], 1)

    def test_explicit_fallback_stays_same_mode_and_remaining_budget(self):
        self.configure(STAR_ALLOW_SINGLE_PASS_FALLBACK=True)
        session = self.base.create()
        self.base.trigger('star_mid_failure', session=session)
        result = self.base.send(session)
        gen = result['generation']
        self.assertEqual((gen['requested_pipeline'], gen['actual_pipeline'], gen['fallback_reason']),
                         ('star', 'single_pass', 'STAR_STEP_FAILED'))
        self.assertEqual((len(gen['calls']), gen['mode']), (4, 'mock'))

    def test_unknown_step_never_falls_back_or_retries(self):
        self.configure(STAR_ALLOW_SINGLE_PASS_FALLBACK=True)
        session = self.base.create()
        self.base.trigger('llm_timeout', session=session)
        self.base.send(session, expected=502)
        gen, state, count = self.generation(session)
        self.assertEqual((gen['status'], len(gen['calls']), count), ('outcome_unknown', 1, 0))
        self.base.api('POST', '/messages/'+gen['user_message_id']+'/generation-retries',
                      {'generation_id':gen['generation_id'], 'expected_turn_count':1}, expected=409)

    def test_unknown_generation_cannot_be_erased_by_case_reset(self):
        session = self.base.create()
        self.base.trigger('llm_timeout', session=session)
        self.base.send(session, expected=502)
        self.base.api('POST', '/cases/'+prior.CASE_A+'/reset',
                      {'case_template_version':CASE_VERSION,'confirmed':True},client=self.base.admin,expected=409)
        self.assertEqual(self.generation(session)[0]['status'],'outcome_unknown')

    def test_selection_outside_candidate_set_cannot_publish(self):
        original = self.service.dialogue.adapter.complete
        def adapter(messages, **options):
            if any('"stage":"selection"' in x['content'] for x in messages):
                return Completion('{"selected_candidate":99}')
            return original(messages, **options)
        self.service.dialogue.adapter.complete = adapter
        session = self.base.create()
        self.base.send(session, expected=502)
        gen, state, count = self.generation(session)
        self.assertEqual((gen['error_code'], count), ('STAR_STEP_OUTPUT_INVALID', 0))

    def test_close_between_stages_cancels_without_publication(self):
        original = self.service.dialogue.adapter.complete
        def adapter(messages, **options):
            result = original(messages, **options)
            if any('"stage":"topic"' in x['content'] for x in messages):
                with self.h.db.transaction() as conn:
                    current = s04_store.session(conn, session['session_id'])
                    self.service.state.close_session(conn, current, {'expected_revision':current['meta']['revision'], 'reason':None})
            return result
        self.service.dialogue.adapter.complete = adapter
        session = self.base.create()
        self.base.send(session, expected=409)
        gen, _, count = self.generation(session)
        self.assertEqual((gen['status'], count), ('cancelled', 0))

    def test_plan_replacement_between_steps_invalidates_candidate_context(self):
        plan = self.h.confirm(effective_from=stamp(self.h.clock()))
        original = self.service.dialogue.adapter.complete
        def adapter(messages, **options):
            result = original(messages, **options)
            if any('"stage":"candidate_2"' in x['content'] for x in messages):
                self.h.time[0] += timedelta(seconds=1)
                self.h.confirm(existing_plan_id=plan['plan_id'], expected_plan_version=1, effective_from=stamp(self.h.clock()))
            return result
        self.service.dialogue.adapter.complete = adapter
        session = self.base.create()
        self.base.send(session, expected=502)
        gen, _, count = self.generation(session)
        self.assertEqual((gen['error_code'], count), ('GENERATION_CONTEXT_CHANGED', 0))

    def test_real_transport_retries_consume_shared_budget(self):
        adapter = self.service.dialogue.adapter
        original = adapter.complete
        calls = []
        def complete(messages, **options):
            calls.append(messages)
            return Completion(None, 'PROVIDER_RATE_LIMITED', transient=True) if len(calls) <= 2 else original(messages, **options)
        adapter.mode = 'real'  # Injected offline transport; no real network/API.
        adapter.complete = complete
        result = self.base.send(self.base.create())
        self.assertEqual((len(calls), result['generation']['budget']['used_network_attempts']), (8, 8))

    def test_case_reset_explicitly_cleans_only_child_checkpoints(self):
        session = self.base.create()
        self.base.send(session)
        self.base.api('POST', '/cases/'+prior.CASE_A+'/reset', {'case_template_version':CASE_VERSION, 'confirmed':True}, client=self.base.admin)
        with self.h.db.connection(readonly=True) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM b_star_checkpoints').fetchone()[0], 0)

    def test_readiness_and_emotional_cues_have_separate_original_evidence(self):
        result = self.base.send(self.base.create(), '我担心副作用，但准备试试整理问题。')
        out = result['business_output']
        self.assertEqual(out['change_readiness']['state'], 'preparing')
        self.assertEqual(out['change_readiness']['evidence'], '准备试试')
        self.assertEqual(out['difficulty_cues'][0]['evidence'], '担心副作用')
        refusal = self.base.send(self.base.create(), '不想继续，不需要建议。')
        self.assertEqual(refusal['business_output']['support_focus'], 'closing')
        self.assertEqual(refusal['business_output']['difficulty_cues'], [])
