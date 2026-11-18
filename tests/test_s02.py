import base64
import copy
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from medplatform.config import ROOT, Settings
from medplatform.database import Database
from medplatform.documents import all_docs, get, stamp
from medplatform.errors import AppError
from medplatform.migrations import migrate
from medplatform.protection import protect, unprotect
from medplatform.s02_api import ROUTES
from medplatform.s02_service import seed_demo
from medplatform.web import create_app

BASE='http://127.0.0.1:8000'
PA='demo-patient-a-self'
PB='demo-patient-b-self'


def key():
    return str(uuid.uuid4())


def unknown_answers():
    return {f'Q{i}':{'state':'unknown','value':None} for i in range(1,9)}


def defaults():
    return dict(enabled=False,channels=['in_app'],sound_enabled=False,vibration_enabled=False,routine_mode='regular',
                anchors=[],privacy_enabled=False,custom_text=None,privacy_windows=[],repeat_interval_minutes=None,
                max_repeats=0,snooze_minutes=None,notify_family=False)


class S02Tests(unittest.TestCase):
    def setUp(self):
        (ROOT/'test-output').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-output');self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)
        self.db=Database(self.path/'demo.sqlite3')
        migrate(self.db,initialize=True)
        self.time=[datetime(2026,11,16,10,tzinfo=timezone.utc)]
        self.clock=lambda:self.time[0]
        seed_demo(self.db,self.clock)
        self.settings=Settings(_env_file=None,APP_ENV='test',DATABASE_PATH=self.db.path)
        self.app=create_app(self.settings,clock=self.clock)
        self.clients=[]
        self.a=self.login('demo-patient-a');self.b=self.login('demo-patient-b');self.f=self.login('demo-family')

    def login(self, account, app=None, operation=None):
        c=TestClient(app or self.app,base_url=BASE,raise_server_exceptions=False)
        self.clients.append(c);self.addCleanup(c.close)
        r=c.post('/api/v1/auth/demo-session',json={'demo_account_id':account},headers={'Origin':BASE,'Idempotency-Key':operation or key()})
        self.assertEqual(r.status_code,201,r.text)
        c.csrf=r.json()['data']['csrf_token'];c.login_response=r
        return c

    def call(self, c, method, path, body=None, *, operation=None, expected=200, **kwargs):
        headers={'Origin':BASE,'X-CSRF-Token':c.csrf,'Idempotency-Key':operation or key()}
        r=c.request(method,'/api/v1'+path,json=body,headers=headers,**kwargs)
        self.assertEqual(r.status_code,expected,r.text)
        data=r.json();self.assertEqual(set(data),{'request_id','status','data','error'})
        self.assertEqual(data['request_id'],r.headers['X-Request-ID'])
        return data['data'] if expected<400 else data['error']

    def bind(self, scopes):
        code=self.call(self.a,'POST',f'/patients/{PA}/family-binding-codes',{},expected=201)
        binding=self.call(self.f,'POST','/family-bindings/redeem',{'binding_code':code['binding_code']},expected=201)
        grant=self.call(self.a,'PUT',f"/family-bindings/{binding['binding_id']}/grant",
                        {'expected_revision':0,'scopes':scopes,'valid_until':None,'confirmed':True})
        return binding,grant

    def response(self,c=None,patient=PA,answers=None):
        c=c or self.a
        result=self.call(c,'POST',f'/patients/{patient}/questionnaire-responses',{'questionnaire_version':'initial-v0.1'},expected=201)
        rid=result['response_id']
        if answers is not None:
            result=self.call(c,'PUT',f'/questionnaire-responses/{rid}/answers',{'expected_revision':1,'answers':answers})
        return result

    def submitted(self,answers=None):
        response=self.response(answers=answers or unknown_answers())
        return self.call(self.a,'POST',f"/questionnaire-responses/{response['response_id']}/submit",{'expected_revision':response['meta']['revision'],'confirmed':True})

    def medication(self):
        return self.call(self.a,'POST',f'/patients/{PA}/medications',{'name':'虚构药品资料（非医疗指令）'},expected=201)

    def draft(self, *, count=1, schedule=None, files=None):
        entries=[]
        for i in range(count):
            med=self.medication()
            entries.append(dict(draft_entry_id=key(),medication_id=med['medication_id'],dose_value='1.00',dose_unit='虚构单位',
                                start_date='2026-11-16',end_date=None,schedule=schedule or {'kind':'daily','times':['08:00','20:00'],'weekdays':[]},
                                meal_requirement=None,medical_notes='虚构资料，不用于服药',strict_timing=None,min_interval_minutes=None,source_file_ids=files or []))
        return self.call(self.a,'POST',f'/patients/{PA}/drafts',{'entries':entries,'source_file_ids':files or []},expected=201)

    def pending(self, draft=None):
        draft=draft or self.draft()
        return self.call(self.a,'POST',f"/drafts/{draft['draft_id']}/submit",{'expected_revision':draft['meta']['revision'],'content_revision':draft['content_revision']})

    def confirm(self,draft=None,**changes):
        draft=draft or self.pending()
        body=dict(draft_id=draft['draft_id'],draft_revision=draft['content_revision'],existing_plan_id=None,expected_plan_version=None,
                  effective_from=stamp(self.clock()+timedelta(hours=1)),confirmed=True)
        body.update(changes)
        return self.call(self.a,'POST',f'/patients/{PA}/plan-confirmations',body,expected=201)

    def upload(self, c=None,patient=PA,source=None,raw=b'%PDF-1.4\n% Fictional test only\n%%EOF\n',filename='fictional.pdf',operation=None):
        c=c or self.a
        return c.post(f'/api/v1/patients/{patient}/files',data={'source_event_id':source or key()},files={'file':(filename,raw,'application/pdf')},
                      headers={'Origin':BASE,'X-CSRF-Token':c.csrf,'Idempotency-Key':operation or key()})

    def test_login_restart_expiry_cookie_and_protected_receipts(self):
        r=self.a.login_response
        self.assertIn('HttpOnly',r.headers['set-cookie']);self.assertIn('SameSite=lax',r.headers['set-cookie']);self.assertIn('Path=/',r.headers['set-cookie'])
        token=self.a.cookies.get('session');csrf=self.a.csrf
        restarted=create_app(self.settings,clock=self.clock)
        c=TestClient(restarted,base_url=BASE);self.addCleanup(c.close);c.cookies.set('session',token)
        self.assertEqual(c.get('/api/v1/auth/me').status_code,200)
        raw=self.db.path.read_bytes();self.assertNotIn(token.encode(),raw);self.assertNotIn(csrf.encode(),raw)
        self.time[0]+=timedelta(hours=8)
        self.assertEqual(c.get('/api/v1/auth/me').status_code,401)

    def test_login_replay_logout_and_old_login_does_not_revive(self):
        operation=key();c=self.login('demo-admin',operation=operation);token=c.cookies.get('session')
        retry=self.login('demo-admin',operation=operation)
        self.assertEqual(token,retry.cookies.get('session'))
        logout_key=key();result=self.call(c,'POST','/auth/logout',{},operation=logout_key)
        self.assertEqual(result['outcome'],'logged_out');self.assertEqual(c.get('/api/v1/auth/me').status_code,401)
        c.cookies.set('session',token)
        again=self.call(c,'POST','/auth/logout',{},operation=logout_key)
        self.assertEqual(result,again)
        r=retry.post('/api/v1/auth/demo-session',json={'demo_account_id':'demo-admin'},headers={'Origin':BASE,'Idempotency-Key':operation})
        self.assertEqual(r.status_code,401)

    def test_binding_scope_revocation_and_account_both_roles(self):
        binding,grant=self.bind(['patient:read','medication:read'])
        patients=self.call(self.f,'GET','/patients')['items']
        self.assertEqual({p['relationship'] for p in patients},{'self','family'})
        self.call(self.f,'GET',f'/patients/{PA}')
        self.call(self.f,'GET',f'/patients/{PB}',expected=404)
        self.call(self.f,'GET',f'/patients/{PA}/files',expected=403)
        self.call(self.a,'POST',f"/grants/{grant['grant_id']}/revoke",{'expected_revision':1,'reason':'虚构撤销验收'})
        self.call(self.f,'GET',f'/patients/{PA}',expected=403)
        me=self.call(self.f,'GET','/auth/me')
        self.assertNotIn(PA,{p['patient']['patient_id'] for p in me['patients']})
        state=self.call(self.f,'GET',f'/patients/{PA}/family-bindings')['items']
        self.assertEqual(len(state),1)
        self.call(self.f,'POST',f"/family-bindings/{binding['binding_id']}/revoke",{'expected_revision':1,'reason':'退出关系'})
        self.call(self.f,'GET',f'/patients/{PA}',expected=404)

    def test_binding_sensitive_replay_consumed_and_expired(self):
        operation=key()
        code=self.call(self.a,'POST',f'/patients/{PA}/family-binding-codes',{},operation=operation,expected=201)
        same=self.call(self.a,'POST',f'/patients/{PA}/family-binding-codes',{},operation=operation,expected=201)
        self.assertEqual(code,same);self.assertNotIn(code['binding_code'].encode(),self.db.path.read_bytes())
        self.call(self.f,'POST','/family-bindings/redeem',{'binding_code':code['binding_code']},expected=201)
        self.call(self.a,'POST',f'/patients/{PA}/family-binding-codes',{},operation=operation,expected=409)
        self.call(self.b,'POST','/family-bindings/redeem',{'binding_code':code['binding_code']},expected=409)
        new=self.call(self.b,'POST',f'/patients/{PB}/family-binding-codes',{},expected=201)
        self.time[0]+=timedelta(minutes=5)
        self.call(self.f,'POST','/family-bindings/redeem',{'binding_code':new['binding_code']},expected=409)

    def test_grant_concurrency_expiration_and_no_privileged_delegation(self):
        binding,grant=self.bind(['patient:read'])
        self.call(self.f,'PUT',f"/family-bindings/{binding['binding_id']}/grant",{'expected_revision':1,'scopes':['plan:confirm'],'valid_until':None,'confirmed':True},expected=404)
        self.call(self.a,'PUT',f"/family-bindings/{binding['binding_id']}/grant",{'expected_revision':0,'scopes':[],'valid_until':None,'confirmed':True},expected=409)
        self.call(self.a,'PUT',f"/family-bindings/{binding['binding_id']}/grant",{'expected_revision':1,'scopes':['demo:manage'],'valid_until':None,'confirmed':True},expected=422)
        grant=self.call(self.a,'PUT',f"/family-bindings/{binding['binding_id']}/grant",{'expected_revision':1,'scopes':['patient:read'],'valid_until':stamp(self.clock()+timedelta(minutes=1)),'confirmed':True})
        self.time[0]+=timedelta(minutes=1)
        self.call(self.f,'GET',f'/patients/{PA}',expected=403)
        rows=self.call(self.a,'GET',f'/patients/{PA}/grants')['items'];self.assertEqual(rows[0]['status'],'expired')
        with self.db.connection(readonly=True) as c:
            self.assertEqual(get(c,'Grant',grant['grant_id'])['status'],'active')

    def test_current_patient_persists_and_stale_context_cannot_target_other(self):
        self.bind(['patient:read'])
        self.call(self.f,'PUT','/auth/current-patient',{'patient_id':PA})
        other=self.login('demo-family');self.assertEqual(other.login_response.json()['data']['current_patient_id'],PA)
        self.call(self.f,'PUT','/auth/current-patient',{'patient_id':PB},expected=403)
        self.call(self.f,'PATCH',f'/patients/{PA}',{'expected_revision':1,'display_name':'不应成功'},expected=403)

    def test_patient_patch_timezone_does_not_shift_plan(self):
        plan=self.confirm();before=self.call(self.a,'GET',f"/plans/{plan['plan_id']}/versions/1")
        self.call(self.a,'PATCH',f'/patients/{PA}',{'expected_revision':1,'timezone':'America/New_York'})
        after=self.call(self.a,'GET',f"/plans/{plan['plan_id']}/versions/1")
        self.assertEqual(before,after)
        self.call(self.a,'PATCH',f'/patients/{PA}',{'expected_revision':1,'display_name':'旧页'},expected=409)
        self.call(self.a,'PATCH',f'/patients/{PA}',{'expected_revision':2,'timezone':None},expected=422)

    def test_questionnaire_eight_themes_validation_and_submission(self):
        definition=self.call(self.a,'GET','/questionnaires/initial')
        self.assertEqual(len(definition['themes']),8)
        response=self.response();rid=response['response_id']
        self.call(self.a,'POST',f'/questionnaire-responses/{rid}/submit',{'expected_revision':1,'confirmed':True},expected=422)
        answers=unknown_answers();answers['Q2']={'state':'answered','value':{'selected':['none','busy'],'top_ranked':[],'other_text':None}}
        self.call(self.a,'PUT',f'/questionnaire-responses/{rid}/answers',{'expected_revision':1,'answers':answers},expected=422)
        answers['Q2']['value']['selected']=['busy'];answers['Q2']['value']['top_ranked']=['busy']
        answers['Q6']={'state':'answered','value':{'confidence_level':0}}
        self.call(self.a,'PUT',f'/questionnaire-responses/{rid}/answers',{'expected_revision':1,'answers':answers},expected=422)
        answers['Q6']['value']['confidence_level']=3
        saved=self.call(self.a,'PUT',f'/questionnaire-responses/{rid}/answers',{'expected_revision':1,'answers':answers})
        self.assertEqual(self.call(self.a,'GET',f'/questionnaire-responses/{rid}'),saved)
        done=self.call(self.a,'POST',f'/questionnaire-responses/{rid}/submit',{'expected_revision':2,'confirmed':True})
        self.assertEqual(done['status'],'submitted')
        self.call(self.a,'PUT',f'/questionnaire-responses/{rid}/answers',{'expected_revision':3,'answers':answers},expected=409)

    def test_assisted_response_no_family_profile_or_formal_plan(self):
        self.bind(['questionnaire:assist','questionnaire:read','profile:read','plan:confirm'])
        response=self.response(self.f,answers=unknown_answers())
        self.assertEqual(response['respondent_mode'],'family_assisted')
        self.assertTrue(all(a['answered_by']=='family_assisted' for a in response['answers'].values()))
        self.call(self.f,'POST',f'/patients/{PA}/profiles',{'response_id':response['response_id']},expected=403)
        self.call(self.f,'POST',f'/patients/{PA}/plan-confirmations',dict(draft_id='unknown',draft_revision=1,existing_plan_id=None,expected_plan_version=None,effective_from=stamp(self.clock()+timedelta(hours=1)),confirmed=True),expected=403)

    def test_profile_deferred_methods_reuse_and_history(self):
        answers=unknown_answers();answers['Q1']={'state':'answered','value':{'primary':'follows_plan','additional':[]}}
        submitted=self.submitted(answers)
        body={'response_id':submitted['response_id']}
        profile=self.call(self.a,'POST',f'/patients/{PA}/profiles',body,expected=201)
        again=self.call(self.a,'POST',f'/patients/{PA}/profiles',body,expected=201)
        self.assertEqual(profile['profile_id'],again['profile_id']);self.assertIsNone(profile['primary_type']);self.assertIsNone(profile['cas']['value'])
        self.assertEqual(profile['reported_behavior'],'follows_plan');self.assertIsNone(profile['assessment_method_version'])
        corrected=self.call(self.a,'POST',f'/patients/{PA}/questionnaire-responses',{'questionnaire_version':'initial-v0.1','supersedes_response_id':submitted['response_id']},expected=201)
        self.assertNotEqual(corrected['response_id'],submitted['response_id'])
        self.assertEqual(self.call(self.a,'GET',f"/profiles/{profile['profile_id']}"),profile)
        self.call(self.b,'GET',f"/profiles/{profile['profile_id']}",expected=404)

    def test_medication_partial_update_and_prescription_fields_forbidden(self):
        med=self.medication();mid=med['medication_id']
        med=self.call(self.a,'PATCH',f'/medications/{mid}',{'expected_revision':1,'notes':'虚构备注'})
        med=self.call(self.a,'PATCH',f'/medications/{mid}',{'expected_revision':2,'name':'资料拼写修正'})
        self.assertEqual(med['notes'],'虚构备注')
        med=self.call(self.a,'PATCH',f'/medications/{mid}',{'expected_revision':3,'notes':None})
        self.assertIsNone(med['notes'])
        self.call(self.a,'PATCH',f'/medications/{mid}',{'expected_revision':4,'dose_value':'2'},expected=422)

    def test_upload_dedup_content_integrity_and_revoked_access(self):
        source=key();r=self.upload(source=source);self.assertEqual(r.status_code,201,r.text);doc=r.json()['data']
        again=self.upload(source=source);self.assertEqual(again.json()['data']['file_id'],doc['file_id'])
        conflict=self.upload(source=source,raw=b'%PDF-1.4 different');self.assertEqual(conflict.status_code,409)
        content=self.call(self.a,'GET',f"/files/{doc['file_id']}/content")
        self.assertEqual(hashlib.sha256(base64.b64decode(content['content_base64'])).hexdigest(),doc['sha256'])
        self.call(self.b,'GET',f"/files/{doc['file_id']}",expected=404)
        binding,grant=self.bind(['files:read'])
        self.call(self.f,'GET',f"/files/{doc['file_id']}/content")
        self.call(self.a,'POST',f"/grants/{grant['grant_id']}/revoke",{'expected_revision':1,'reason':'撤销文件授权'})
        self.call(self.f,'GET',f"/files/{doc['file_id']}/content",expected=403)
        self.assertEqual(len(self.call(self.a,'GET',f'/patients/{PA}/files')['items']),1)

    def test_upload_type_size_failure_and_filename_cannot_escape(self):
        self.assertEqual(self.upload(raw=b'not pdf').status_code,415)
        self.assertEqual(self.upload(raw=b'%PDF-'+b'x'*10485760).status_code,413)
        r=self.upload(filename='../../outside.pdf');self.assertEqual(r.status_code,201,r.text)
        doc=r.json()['data'];self.assertTrue((self.app.state.s02.file_root/(doc['file_id']+'.blob')).is_file())
        self.assertFalse((self.path/'outside.pdf').exists())
        with patch('medplatform.s02_service.os.fsync',side_effect=OSError('TEST_FAILURE_PRIVATE')):
            failed=self.upload()
        self.assertEqual(failed.status_code,503);self.assertNotIn('TEST_FAILURE_PRIVATE',failed.text)

    def test_draft_content_resource_revision_and_exact_plan_reference(self):
        draft=self.draft();did=draft['draft_id'];entry=copy.deepcopy(draft['entries'][0]);entry['medical_notes']='更正的虚构文字'
        saved=self.call(self.a,'PUT',f'/drafts/{did}',{'expected_revision':1,'source_file_ids':[],'entries':[entry]})
        pending=self.pending(saved)
        self.assertEqual(pending['content_revision'],2);self.assertEqual(pending['meta']['revision'],3)
        self.assertIsNone(pending['formal_plan'])
        plan=self.confirm(pending)
        confirmed=self.call(self.a,'GET',f'/drafts/{did}')
        self.assertEqual(confirmed['formal_plan'],{'plan_id':plan['plan_id'],'plan_version':1})
        self.assertEqual(plan['source_draft_revision'],2)
        self.call(self.a,'PUT',f'/drafts/{did}',{'expected_revision':4,'source_file_ids':[],'entries':[entry]},expected=409)
        self.assertEqual(len(self.call(self.a,'GET',f'/patients/{PA}/drafts?status=confirmed')['items']),1)

    def test_incomplete_plan_returned_and_editable_no_half_plan(self):
        draft=self.draft();draft['entries'][0]['dose_value']=None
        draft=self.call(self.a,'PUT',f"/drafts/{draft['draft_id']}",{'expected_revision':1,'source_file_ids':[],'entries':draft['entries']})
        pending=self.pending(draft)
        body=dict(draft_id=pending['draft_id'],draft_revision=2,existing_plan_id=None,expected_plan_version=None,effective_from=stamp(self.clock()+timedelta(hours=1)),confirmed=True)
        self.call(self.a,'POST',f'/patients/{PA}/plan-confirmations',body,expected=409)
        returned=self.call(self.a,'GET',f"/drafts/{draft['draft_id']}")
        self.assertEqual(returned['status'],'returned');self.assertTrue(returned['return_reason'])
        self.assertEqual(self.call(self.a,'GET',f'/patients/{PA}/plans')['items'],[])

    def test_multi_medication_atomic_slots_stable_and_readonly(self):
        plan=self.confirm(self.pending(self.draft(count=2)))
        url=f'/patients/{PA}/dose-slots?window_start=2026-11-17T00:00:00%2B08:00&window_end=2026-11-18T00:00:00%2B08:00'
        before=self.db.path.read_bytes();slots=self.call(self.a,'GET',url);again=self.call(self.a,'GET',url)
        self.assertEqual(slots,again);self.assertEqual(len(slots['items']),4);self.assertEqual(self.db.path.read_bytes(),before)
        self.assertEqual(len({s['dose_slot_id'] for s in slots['items']}),4)
        self.call(self.a,'GET',f'/patients/{PA}/dose-slots?window_start=2027-01-01T00:00:00Z&window_end=2027-01-02T00:00:00Z',expected=409)
        with self.db.connection(readonly=True) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM change_notices').fetchone()[0],1)

    def test_weekly_calendar_and_declared_interval_across_midnight(self):
        draft=self.draft(schedule={'kind':'weekly','times':['00:10','23:50'],'weekdays':[1,2]})
        entry=draft['entries'][0];entry['min_interval_minutes']=60
        draft=self.call(self.a,'PUT',f"/drafts/{draft['draft_id']}",{'expected_revision':1,'source_file_ids':[],'entries':[entry]})
        pending=self.pending(draft)
        body=dict(draft_id=pending['draft_id'],draft_revision=2,existing_plan_id=None,expected_plan_version=None,effective_from=stamp(self.clock()+timedelta(hours=1)),confirmed=True)
        self.call(self.a,'POST',f'/patients/{PA}/plan-confirmations',body,expected=422)
        valid=self.confirm(self.pending(self.draft(schedule={'kind':'weekly','times':['09:00'],'weekdays':[2,4]})))
        from zoneinfo import ZoneInfo
        with self.db.connection(readonly=True) as c:
            slots=c.execute('SELECT scheduled_at FROM dose_slots WHERE plan_id=?',(valid['plan_id'],)).fetchall()
        self.assertTrue(slots)
        self.assertTrue(all(datetime.fromisoformat(r[0]).astimezone(ZoneInfo('Asia/Shanghai')).isoweekday() in (2,4) for r in slots))

    def test_file_db_failure_keeps_valid_file_and_no_visible_partial_result(self):
        good=self.upload();self.assertEqual(good.status_code,201)
        identifier=good.json()['data']['file_id'];original=(self.app.state.s02.file_root/(identifier+'.blob')).read_bytes()
        with patch('medplatform.s02_service.save',side_effect=sqlite3.OperationalError('PRIVATE_DB_FAILURE')):
            failed=self.upload()
        self.assertEqual(failed.status_code,503)
        self.assertEqual((self.app.state.s02.file_root/(identifier+'.blob')).read_bytes(),original)
        self.assertEqual(len(self.call(self.a,'GET',f'/patients/{PA}/files')['items']),1)

    def test_future_plan_replacement_keeps_old_entries_and_history(self):
        old=self.confirm();new=self.confirm(existing_plan_id=old['plan_id'],expected_plan_version=1,effective_from=stamp(self.clock()+timedelta(days=2)))
        self.assertEqual(new['plan_version'],2)
        history=self.call(self.a,'GET',f"/plans/{old['plan_id']}/versions/1")
        self.assertEqual(history['entries'],old['entries']);self.assertEqual(history['effective_until'],new['effective_from'])
        with self.db.connection(readonly=True) as c:
            self.assertGreater(c.execute("SELECT count(*) FROM dose_slots WHERE plan_version=1 AND status='superseded'").fetchone()[0],0)
            self.assertGreater(c.execute("SELECT count(*) FROM dose_slots WHERE plan_version=1 AND status='active'").fetchone()[0],0)
        self.call(self.a,'GET',f'/patients/{PA}/plans?plan_id='+old['plan_id'])

    def test_plan_publish_failure_rolls_back_all_references_and_slots(self):
        pending=self.pending()
        with patch.object(self.app.state.s02,'materialize',side_effect=sqlite3.OperationalError('PRIVATE_SQL')):
            body=dict(draft_id=pending['draft_id'],draft_revision=1,existing_plan_id=None,expected_plan_version=None,effective_from=stamp(self.clock()+timedelta(hours=1)),confirmed=True)
            self.call(self.a,'POST',f'/patients/{PA}/plan-confirmations',body,expected=503)
        draft=self.call(self.a,'GET',f"/drafts/{pending['draft_id']}")
        self.assertEqual(draft['status'],'pending_confirmation');self.assertIsNone(draft['formal_plan'])
        with self.db.connection(readonly=True) as c:
            self.assertEqual(len(all_docs(c,'PlanVersion')),0)
            self.assertEqual(c.execute('SELECT count(*) FROM dose_slots').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT count(*) FROM change_notices').fetchone()[0],0)

    def test_reminder_config_only_defaults_limits_privacy_and_permissions(self):
        self.call(self.a,'GET',f'/patients/{PA}/reminder-preferences',expected=404)
        settings=defaults();settings.update(enabled=True,routine_mode='night_shift',privacy_enabled=True,custom_text='今日事项待确认。',
                                            anchors=[{'event':'wake','label':None,'local_time':'09:00','offset_minutes':0}])
        saved=self.call(self.a,'PUT',f'/patients/{PA}/reminder-preferences',{'expected_revision':0,'settings':settings})
        self.assertEqual(self.call(self.a,'GET',f'/patients/{PA}/reminder-preferences'),saved)
        settings['repeat_interval_minutes']=1;settings['max_repeats']=1
        self.call(self.a,'PUT',f'/patients/{PA}/reminder-preferences',{'expected_revision':1,'settings':settings},expected=422)
        settings=defaults();settings['channels']=['system_notification']
        self.call(self.a,'PUT',f'/patients/{PA}/reminder-preferences',{'expected_revision':1,'settings':settings},expected=422)
        settings=defaults();settings['notify_family']=True
        self.call(self.a,'PUT',f'/patients/{PA}/reminder-preferences',{'expected_revision':1,'settings':settings},expected=403)

    def test_idempotency_fingerprint_conflict_expiry_and_revalidation(self):
        binding,grant=self.bind(['medication:edit'])
        op=key();body={'name':'虚构药品','notes':None}
        a=self.call(self.f,'POST',f'/patients/{PA}/medications',body,operation=op,expected=201)
        same=self.call(self.f,'POST',f'/patients/{PA}/medications',{'name':'虚构药品'},operation=op,expected=201)
        self.assertEqual(a,same)
        self.call(self.f,'POST',f'/patients/{PA}/medications',{'name':'另一内容'},operation=op,expected=409)
        self.call(self.a,'POST',f"/grants/{grant['grant_id']}/revoke",{'expected_revision':1,'reason':'撤销'})
        self.call(self.f,'POST',f'/patients/{PA}/medications',body,operation=op,expected=403)
        with self.db.transaction() as c:
            c.execute("UPDATE idempotency_receipts SET full_receipt_until='2000-01-01T00:00:00.000000+00:00' WHERE resource_id=?",(a['medication_id'],))
        # Regrant cannot make an expired key create a second medication.
        self.call(self.a,'PUT',f"/family-bindings/{binding['binding_id']}/grant",{'expected_revision':2,'scopes':['medication:edit'],'valid_until':None,'confirmed':True})
        error=self.call(self.f,'POST',f'/patients/{PA}/medications',body,operation=op,expected=409)
        self.assertEqual(error['code'],'IDEMPOTENCY_EXPIRED')

    def test_json_duplicates_unknowns_nan_and_forgeries_rejected(self):
        headers={'Origin':BASE,'X-CSRF-Token':self.a.csrf,'Idempotency-Key':key(),'Content-Type':'application/json'}
        for text in ('{"name":"one","name":"two"}','{"name":"one","source":"real"}','{"name":NaN}'):
            r=self.a.post(f'/api/v1/patients/{PA}/medications',content=text,headers=headers);self.assertEqual(r.status_code,422,r.text)
        self.call(self.a,'POST',f'/patients/{PA}/profiles',{'response_id':'unknown','patient_id':PB},expected=422)
        self.call(self.a,'GET',f'/patients/{PA}/medications?patient_id={PB}',expected=422)
        self.call(self.a,'POST',f'/patients/{PA}/questionnaire-responses',{'questionnaire_version':'initial-v0.1','respondent_mode':'self'},expected=422)

    def test_pagination_cursor_bound_to_identity_patient_and_filter(self):
        for i in range(3):self.medication()
        page=self.call(self.a,'GET',f'/patients/{PA}/medications?limit=1')
        cursor=page['next_cursor'];self.assertTrue(cursor)
        next_page=self.call(self.a,'GET',f'/patients/{PA}/medications?limit=1&cursor='+cursor)
        self.assertNotEqual(page['items'][0]['medication_id'],next_page['items'][0]['medication_id'])
        self.call(self.b,'GET',f'/patients/{PB}/medications?cursor='+cursor,expected=422)
        self.call(self.a,'GET',f'/patients/{PA}/files?cursor='+cursor,expected=422)

    def test_inflight_duplicate_does_not_repeat_effect(self):
        started=threading.Event();release=threading.Event();original=self.app.state.s02.write
        def slow(*args):
            if args[1]=='medication_create':
                started.set();release.wait(5)
            return original(*args)
        op=key();responses=[]
        def first():
            responses.append(self.a.post(f'/api/v1/patients/{PA}/medications',json={'name':'虚构并发'},headers={'Origin':BASE,'X-CSRF-Token':self.a.csrf,'Idempotency-Key':op}))
        with patch.object(self.app.state.s02,'write',side_effect=slow):
            worker=threading.Thread(target=first);worker.start();self.assertTrue(started.wait(5))
            try:
                retry=self.a.post(f'/api/v1/patients/{PA}/medications',json={'name':'虚构并发'},headers={'Origin':BASE,'X-CSRF-Token':self.a.csrf,'Idempotency-Key':op})
                self.assertEqual(retry.status_code,409,retry.text);self.assertEqual(retry.headers.get('Retry-After'),'1')
            finally:
                release.set();worker.join(8)
        self.assertFalse(worker.is_alive());self.assertEqual(responses[0].status_code,201)
        self.assertEqual(len(self.call(self.a,'GET',f'/patients/{PA}/medications')['items']),1)

    def test_migration_preserves_s01_data_and_seed_repeat_preserves_edits(self):
        self.call(self.a,'PATCH',f'/patients/{PA}',{'expected_revision':1,'display_name':'保留用户修改'})
        seed_demo(self.db,self.clock)
        self.assertEqual(self.call(self.a,'GET',f'/patients/{PA}')['display_name'],'保留用户修改')
        with self.db.connection(readonly=True) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM o_accounts').fetchone()[0],4)
        # The first two immutable SQL files must still match the S01 commit.
        for name in ('0001_foundation.sql','0002_event_history.sql'):
            baseline=json.loads((ROOT/'docs'/'S01'/'验证结果.json').read_text(encoding='utf8'))
            self.assertEqual(hashlib.sha256((ROOT/'migrations'/name).read_bytes()).hexdigest(),baseline['source_sha256']['migrations/'+name])

    def test_explicit_receipt_maintenance_keeps_tombstones_and_business(self):
        from medplatform.idempotency import expire_receipts
        med=self.medication()
        with self.db.transaction() as c:
            c.execute("UPDATE idempotency_receipts SET full_receipt_until='2000-01-01T00:00:00.000000+00:00' WHERE resource_id=?",(med['medication_id'],))
        result=expire_receipts(self.db,self.clock)
        self.assertEqual(result['expired_tombstones'],1)
        with self.db.connection(readonly=True) as c:
            receipt=c.execute('SELECT * FROM idempotency_receipts WHERE resource_id=?',(med['medication_id'],)).fetchone()
            self.assertEqual(receipt['state'],'expired');self.assertIsNone(receipt['response_ref'])
            self.assertEqual(get(c,'Medication',med['medication_id'])['name'],med['name'])

    def test_dpapi_corruption_fails_and_does_not_create_another_login(self):
        operation=key();client=self.login('demo-admin',operation=operation)
        with self.db.transaction() as c:
            c.execute("UPDATE idempotency_receipts SET protected_response=? WHERE key_hash=?",(b'corrupted',hashlib.sha256(operation.encode()).hexdigest()))
        before=self.db.path.read_bytes()
        r=client.post('/api/v1/auth/demo-session',json={'demo_account_id':'demo-admin'},headers={'Origin':BASE,'Idempotency-Key':operation})
        self.assertEqual(r.status_code,503);self.assertEqual(self.db.path.read_bytes(),before)

    def test_no_later_phase_routes_or_background_tasks(self):
        self.assertEqual(len(ROUTES),40)
        # B02 registers /cases for demo:manage; C formal services remain absent.
        denied=self.call(self.a,'GET','/cases',expected=403)
        self.assertEqual(denied['code'],'ADMIN_REQUIRED')
        cases=self.call(self.login('demo-admin'),'GET','/cases')['items']
        self.assertEqual({case['case_id'] for case in cases},{'case-low-mood','case-anxiety','case-fatigue'})
        for path in ('/api/v1/patients/'+PA+'/statistics','/api/v1/patients/'+PA+'/services'):
            self.assertEqual(self.a.get(path).status_code,404)
        self.assertEqual(self.a.get('/api/v1/tasks').status_code,405)
        self.assertNotIn('Task',{r[0] for r in self.db_connection_table_names()})

    def db_connection_table_names(self):
        with self.db.connection(readonly=True) as c:
            return c.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()
